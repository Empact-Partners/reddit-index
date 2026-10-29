#!/usr/bin/env python3
"""Daytime passes on Railway, one after another, inside the day's room under its egress line (2026-10-06).

Each pass is the sweep's own run (worker/run_daily.py) started on Railway with a request row (migration 0023) that names
its stages and carries the day's remaining room as its egress cap (migration 0028). Before each pass this script reads
the database's node counter (the egress watchdog's measure) and judges the room as the pass and the day tick do: the
watchdog's day, 07:00 to 07:00 UTC, with the day's backup and tonight's run counted as sent while they are still to
come (decision 0035, worker/meter.py ledger), under that day's line (ops/schedule.json day_line_gb, or its dated
override: decision 0041). The laptop only polls over HTTPS (the Management API and Railway), so a sleeping or flaky
laptop never breaks a pass; it only delays the next one.

  ops/day_passes.py --stages backfill,classify --until 20:30
  ops/day_passes.py --stages classify,refresh,score --until 21:00 --max-calls 0

Every reading it takes is kept in public.egress_counter as "day passes (laptop)", at least every three minutes while it
runs; the day tick on Railway (ops/day_tick.py) starts no pass of its own while such a reading is fresh, so the two
never request a pass at once (decision 0041). It waits while another run is open, and a pass that stood aside because
another job held the sweep's lock is asked again, not taken for a failure. When the day's room is used it waits for
the next watchdog's day if that starts before --until, else it stops; it also stops at --until, when a pass fails, or
when the stop switch is off.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, d) for d in ("ops", "scripts", "worker")]
LAPTOP_SOURCE = "day passes (laptop)"   # ops/day_tick.py stands aside while a reading with this source is fresh
GUARD_EVERY_S = 180                      # the guard's reading while a pass runs, as often as the pass reads its own
MIN_ROOM_GB = 0.15                       # the day tick's min_room_gb: less is not worth a pass


def log(*a):
    print(f"[{dt.datetime.now(dt.timezone.utc):%H:%M:%S}]", *a, flush=True)


def schedule() -> dict:
    return json.load(open(os.path.join(ROOT, "ops", "schedule.json")))


def counter_now() -> float:
    """The node counter now, kept as a laptop reading (which is also this script's sign of life for the day tick)."""
    import investigation_2026_10 as inv
    import watch_link as w
    now = inv._metrics()["transmit_bytes"]
    w.query(f"insert into public.egress_counter (bytes, source) values ({now:.0f}, '{LAPTOP_SOURCE}') "
            f"on conflict (at) do nothing")
    return now


def ledger_now() -> dict:
    """The watchdog's day as the pass judges it (worker/meter.py ledger_from, decision 0035) with the day's own line
    (decision 0041): `line`, `sent`, `used` (sent plus what is held for the day's backup and tonight's run; None when
    the day's start is not known), in bytes. Until 29 Oct this script judged the 24 hours to now, which the passes
    stopped using on 15 Oct: the day after a full backup it read no room while the watchdog's day had plenty."""
    import meter
    import watch_link as w
    b = counter_now()
    now = dt.datetime.now(dt.timezone.utc)
    rows = w.query("select extract(epoch from at)::text t, bytes::text b from public.egress_counter "
                   "where at > now() - interval '4 days' order by at")
    size = w.query("select pg_database_size(current_database())::text s")
    rs = [(dt.datetime.fromtimestamp(float(r["t"]), dt.timezone.utc), float(r["b"])) for r in rows]
    return meter.ledger_from(rs, b, now, schedule(), float(size[0]["s"]) if size else None)


def open_runs() -> int:
    """Sweep runs or retention steps still running (receipts younger than 6 hours with no end), as the tick counts them."""
    import watch_link as w
    return int(w.query("select count(*) n from public.pipeline_runs where finished_at is null and stage in "
                       "('sweep', 'retention') and started_at > now() - interval '6 hours'")[0]["n"])


def sleep_alive(seconds: float, beat: float = GUARD_EVERY_S) -> None:
    """Sleep, reading the counter every `beat` seconds so the day tick keeps standing aside (decision 0041)."""
    end = time.time() + seconds
    while time.time() < end:
        time.sleep(max(1.0, min(beat, end - time.time())))
        if time.time() < end:
            try:
                counter_now()
            except Exception:  # noqa: BLE001 - a missed beat is one missed beat
                pass


TREE_WORKERS_FILE = os.path.expanduser("~/Library/Logs/reddit-index/tree-workers")


def tree_workers(path: str = TREE_WORKERS_FILE) -> int | None:
    """Comment trees in flight at once for the next pass: the number in the file (1 to 4), or None to leave the
    sweep's own setting (ops/schedule.json collect.tree_workers). A file on the laptop so the width can be changed
    between two passes of one day, to compare them; a width that is kept goes into the schedule."""
    try:
        n = int(open(path).read().strip())
    except (OSError, ValueError):
        return None
    return n if 1 <= n <= 4 else None


def request(stages: str, max_calls: int, end_by: str, egress_gb: float, workers: int | None = None) -> None:
    import re
    import watch_link as w
    import deploy_sweep as d
    # the values go into the statement as text (the query endpoint takes no parameters): only these shapes pass
    if not re.fullmatch(r"[a-z]+(,[a-z]+)*", stages) or not re.fullmatch(r"\d\d:\d\d", end_by):
        raise ValueError(f"not a stage list or an HH:MM time: {stages!r}, {end_by!r}")
    cols, vals = "stages, max_calls, end_by_utc, max_egress_gb", f"'{stages}', {int(max_calls)}, '{end_by}'::time, {egress_gb:.3f}"
    if workers:   # the column exists since migration 0032; without a width the insert is what it always was
        cols, vals = cols + ", options", vals + f""", '{{"tree_workers": {int(workers)}}}'::jsonb"""
    w.query(f"insert into public.day_run_request ({cols}) values ({vals})")
    svcs = d.gql("query($p:String!){ project(id:$p){ services { edges { node { id name } } } } }",
                 {"p": d.PROJECT})["project"]["services"]["edges"]
    sid = [e["node"]["id"] for e in svcs if e["node"]["name"] == d.NAME][0]
    si = d.gql("query($s:String!,$e:String!){ serviceInstance(serviceId:$s, environmentId:$e){ id } }",
               {"s": sid, "e": d.ENV})["serviceInstance"]["id"]
    d.gql("mutation($i: DeploymentInstanceExecutionCreateInput!){ deploymentInstanceExecutionCreate(input: $i) }",
          {"i": {"serviceInstanceId": si}})


def switch(on: bool, reason: str) -> None:
    """The sweep's stop switch (public.sweep_control, read by a running pass before every stage and inside the long
    ones). Turned off only by the meter guard below, and back on as soon as that pass has ended."""
    import watch_link as w
    w.query("update public.sweep_control set enabled = " + ("true" if on else "false") + ", reason = '"
            + reason.replace("'", "''") + "', updated_at = now()")


def wait_for(t0: dt.datetime) -> dict | None:
    """Wait for the pass's receipt. Every three minutes, the node counter judged on the watchdog's day: a pass caps
    itself on its OWN estimate and stops itself at the line (decision 0025), but on 7 Oct a backfill pass capped at
    0.69 GB moved the counter by about 1.5 GB. If the day reaches its line and the pass has not stopped, the switch
    goes off (the pass stops at its next check) and comes back on when it ends."""
    import watch_link as w
    tripped = False
    last_guard = 0.0
    try:
        for _ in range(330):   # a pass is at most 5.5 hours
            time.sleep(60)
            if not tripped and time.time() - last_guard >= GUARD_EVERY_S:
                last_guard = time.time()
                try:
                    led = ledger_now()
                except Exception:  # noqa: BLE001 - a missed reading is retried at the next guard
                    led = None
                if led and led["used"] is not None and led["used"] >= led["line"]:
                    switch(False, f"day pass guard: the watchdog's day reached {led['used'] / 1e9:.2f} GB with what "
                                  f"is still to come in it (line {led['line'] / 1e9:g} GB, node counter)")
                    tripped = True
                    log(f"the day reached {led['used'] / 1e9:.2f} GB of its {led['line'] / 1e9:g} GB line: stop "
                        f"switch off until this pass ends")
            try:
                r = w.query(f"select run_id, status, finished_at, notes from public.pipeline_runs where stage = 'sweep' "
                            f"and started_at > '{t0.isoformat()}' order by started_at desc limit 1")
            except Exception:  # noqa: BLE001 - a missed poll is a missed poll
                continue
            if r and r[0]["finished_at"]:
                return r[0]
        return None
    finally:
        if tripped:   # never leave the switch off: the night's run must start
            for _ in range(5):
                try:
                    switch(True, "started by hand (day pass guard released)")
                    log("stop switch back on")
                    break
                except Exception:  # noqa: BLE001
                    time.sleep(30)


def next_day_start(now: dt.datetime) -> dt.datetime:
    import meter
    return meter.watchdog_day_start(now, schedule().get("watchdog_reads_utc", "07:00")) + dt.timedelta(days=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    # collect and label only: a page changes only when the night publishes it, and the night refreshes and scores
    # every brand the day dirtied, so a daytime refresh rewrites the same rows twice (9 Oct: 33 minutes, 1,887
    # brands, write-ahead log the egress line pays for) for nothing the site shows. Backfill finished on 9 Oct.
    ap.add_argument("--stages", default="collect,classify")
    ap.add_argument("--until", default="21:00", help="start no pass after this UTC time; each pass ends by 21:30")
    ap.add_argument("--max-calls", type=int, default=15000)
    ap.add_argument("--end-by", default="23:15", help="UTC: a pass ends by then (45 minutes before the night's run)")
    a = ap.parse_args()
    until = dt.datetime.strptime(a.until, "%H:%M").time()
    failures = 0
    while dt.datetime.now(dt.timezone.utc).time() < until:
        try:
            led = ledger_now()
        except Exception as e:  # noqa: BLE001
            log(f"could not read the node counter ({str(e)[:120]}); waiting"); sleep_alive(300); continue
        if led["used"] is None:
            log("no counter reading before the watchdog's day began: the room is not known; waiting")
            sleep_alive(300); continue
        line, room = led["line"] / 1e9, (led["line"] - led["used"]) / 1e9
        if room < MIN_ROOM_GB:
            now = dt.datetime.now(dt.timezone.utc)
            nxt = next_day_start(now)
            if nxt.date() == now.date() and nxt.time() < until:
                log(f"the watchdog's day has {room:.2f} GB of room under its {line:g} GB line with what is still to "
                    f"come in it ({led.get('backup_why')}; {led.get('night_why')}); waiting for the next day at "
                    f"{nxt:%H:%M} UTC")
                sleep_alive((nxt - now).total_seconds() + 120); continue
            log(f"the day's room under its {line:g} GB line is used ({room:.2f} GB left); stopping")
            break
        n_open = open_runs()
        if n_open:   # the night's run, a retention step, or a pass the tick started before this script began
            log(f"{n_open} run(s) open: waiting for them to end"); sleep_alive(120, beat=60); continue
        # the run's cap is its own ESTIMATE, which reads low: on 6 Oct a pass capped at 0.128 GB moved the node counter
        # by about 0.2 GB (day_egress.py uses the same x1.6 for the night). So the cap is the room divided by 1.6.
        cap = min(0.7, (room - 0.03) / (2.4 if "backfill" in a.stages else 1.6))   # 7 Oct: a backfill pass ~2.2x
        t0 = dt.datetime.now(dt.timezone.utc)
        width = tree_workers()
        try:
            request(a.stages, a.max_calls, a.end_by, cap, width)
        except Exception as e:  # noqa: BLE001
            log(f"could not start a pass: {e}"); sleep_alive(120); continue
        log(f"pass requested: stages {a.stages}, egress cap {cap:.2f} GB (room {room:.2f} under {line:g})"
            + (f", comment trees {width} at a time" if width else ""))
        run = wait_for(t0)
        if not run:
            log("no finished receipt in 5.5 hours; stopping"); break
        n = run["notes"] if isinstance(run["notes"], dict) else json.loads(run["notes"] or "{}")
        if run["status"] == "skipped":
            why = str(n.get("skipped") or "")
            if "lock" in why:   # another pass got there first: ask again once it ends (decision 0041)
                log(f"the pass stood aside: {why}; asking again"); sleep_alive(120, beat=60); continue
            log(f"the pass did not run: {why}; stopping"); break
        st = n.get("stages") or {}
        bf, cl, co = st.get("backfill") or {}, st.get("classify") or {}, st.get("collect") or {}
        la = st.get("label_alongside") or {}   # decision 0037: labels made beside collection
        if co:
            per_min = (f", {co['reddit_calls'] / co['minutes']:.0f} calls a minute"
                       if co.get("minutes") and co.get("reddit_calls") else "")
            log(f"  collect: {co.get('subs_visited')} subreddits visited, {co.get('mentions_new')} new mentions, "
                f"{co.get('reddit_calls')} calls{per_min}, {co.get('allowance_used') or co.get('stopped')}")
            if co.get("seconds"):
                log(f"  collect time: trees {co.get('tree_workers', 1)} at a time; seconds {json.dumps(co['seconds'])}")
        log(f"pass {run['status']}: backfill done {len(bf.get('done') or [])} subs, left {bf.get('left')}, "
            f"{bf.get('mentions')} mentions, {bf.get('reddit_calls')} calls, stopped: {bf.get('stopped')}; "
            f"classify labelled {cl.get('labelled')}, rejected {cl.get('rejected')}, left {cl.get('left_in_queue')} "
            f"(beside collection: {la.get('labelled', 0)} labelled, {la.get('rejected', 0)} rejected); "
            f"egress estimate {n.get('egress_estimate_gb')} GB, measured {n.get('egress_measured_gb')} GB; "
            f"caps hit {n.get('caps_hit')}")
        if run["status"] not in ("ok", "capped") and "day pass guard" not in json.dumps(n):
            failures += 1
            if failures >= 2:
                log("a second pass in a row failed; stopping"); break
            log(f"the pass failed ({'; '.join(n.get('problems') or [])[:300]}); one more try in 10 minutes")
            sleep_alive(600); continue
        failures = 0
        if "backfill" in a.stages and bf.get("note") == "every declared subreddit is done" and cl.get("left_in_queue") == 0:
            log("backfill and labels done"); break
        rf = st.get("refresh") or {}
        work = sum(int(x or 0) for x in (co.get("reddit_calls"), co.get("mentions_new"),
                                         bf.get("reddit_calls"), bf.get("trees"), len(bf.get("done") or []),
                                         cl.get("labelled"), cl.get("rejected"), rf.get("brands_refreshed"),
                                         la.get("labelled"), la.get("rejected")))
        if work == 0:   # 9 Oct: 150 passes in a row did nothing, one a minute; an empty pass means wait, not retry
            # no sign of life while it waits: the day tick may run its own passes meanwhile (decision 0041)
            log("the pass did nothing; next request in 30 minutes")
            time.sleep(1800)
    log("passes ended")
    return 0


if __name__ == "__main__":
    sys.exit(main())
