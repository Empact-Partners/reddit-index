#!/usr/bin/env python3
"""Daytime passes on Railway, one after another, inside the day's room under the 2 GB line (2026-10-06).

Each pass is the sweep's own run (worker/run_daily.py) started on Railway with a request row (migration 0023) that names
its stages and carries the day's remaining room as its egress cap (migration 0028). Before each pass this script reads
the database's node counter (the egress watchdog's measure) and starts nothing when the room is gone. The laptop only
polls over HTTPS (the Management API and Railway), so a sleeping or flaky laptop never breaks a pass; it only delays
the next one.

  ops/day_passes.py --stages backfill,classify,refresh,score --until 21:00
  ops/day_passes.py --stages classify,refresh,score --until 21:00 --max-calls 0

The day's usage is the node counter now minus its reading at the start of the UTC day (the go-live gate meter's file
for that day, docs/go-live/egress-<day>.json; or --day-start-gb). It stops when the room is under 0.06 GB, at --until,
or when a pass fails.
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
LINE_GB = 1.90   # Vlad's 2 GB a day, less 0.1 GB for what moves after the last pass (6 Oct: the tail and normal reads took the day to 2.036 GB from 1.95)


def log(*a):
    print(f"[{dt.datetime.now(dt.timezone.utc):%H:%M:%S}]", *a, flush=True)


def used_today(start_bytes: float | None) -> float:
    import investigation_2026_10 as inv
    now = inv._metrics()["transmit_bytes"]
    day = dt.datetime.now(dt.timezone.utc).date()
    if start_bytes is None:
        g = json.load(open(os.path.join(ROOT, "docs", "go-live", f"egress-{day}.json")))
        start_bytes = float(g["counter_before"]["bytes"])
    return (now - start_bytes) / 1e9


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
    import watch_link as w
    import deploy_sweep as d
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


def wait_for(t0: dt.datetime, start_bytes: float | None) -> dict | None:
    """Wait for the pass's receipt. Every minute, the node counter: a pass caps itself on its OWN estimate, and on
    7 Oct a backfill pass capped at 0.69 GB moved the counter by about 1.5 GB, taking the day to 2.42 GB. When the
    day reaches the line, the switch goes off (the pass stops at its next check) and comes back on when it ends."""
    import watch_link as w
    tripped = False
    try:
        for _ in range(330):   # a pass is at most 5.5 hours
            time.sleep(60)
            if not tripped:
                try:
                    used = used_today(start_bytes)
                except Exception:  # noqa: BLE001 - a missed reading is retried next minute
                    used = None
                if used is not None and used >= LINE_GB:
                    switch(False, f"day pass guard: the day's egress reached {used:.2f} GB (node counter)")
                    tripped = True
                    log(f"the day reached {used:.2f} GB on the node counter: stop switch off until this pass ends")
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


def main() -> int:
    ap = argparse.ArgumentParser()
    # collect and label only: a page changes only when the night publishes it, and the night refreshes and scores
    # every brand the day dirtied, so a daytime refresh rewrites the same rows twice (9 Oct: 33 minutes, 1,887
    # brands, write-ahead log the egress line pays for) for nothing the site shows. Backfill finished on 9 Oct.
    ap.add_argument("--stages", default="collect,classify")
    ap.add_argument("--until", default="21:00", help="start no pass after this UTC time; each pass ends by 21:30")
    ap.add_argument("--max-calls", type=int, default=15000)
    ap.add_argument("--end-by", default="23:15", help="UTC: a pass ends by then (45 minutes before the night's run)")
    ap.add_argument("--day-start-gb", type=float, default=None, help="the node counter at the day's start, in bytes/1e9")
    a = ap.parse_args()
    until = dt.datetime.strptime(a.until, "%H:%M").time()
    start_bytes = a.day_start_gb * 1e9 if a.day_start_gb is not None else None
    while dt.datetime.now(dt.timezone.utc).time() < until:
        try:
            room = LINE_GB - used_today(start_bytes)
        except Exception as e:  # noqa: BLE001
            log(f"could not read the node counter ({e}); waiting"); time.sleep(300); continue
        if room < 0.06:
            log(f"the day's room under the 2 GB line is used ({room:.2f} GB left); stopping")
            break
        # the run's cap is its own ESTIMATE, which reads low: on 6 Oct a pass capped at 0.128 GB moved the node counter
        # by about 0.2 GB (day_egress.py uses the same x1.6 for the night). So the cap is the room divided by 1.6.
        cap = min(0.7, (room - 0.03) / (2.4 if "backfill" in a.stages else 1.6))   # 7 Oct: a backfill pass ~2.2x
        t0 = dt.datetime.now(dt.timezone.utc)
        width = tree_workers()
        try:
            request(a.stages, a.max_calls, a.end_by, cap, width)
        except Exception as e:  # noqa: BLE001
            log(f"could not start a pass: {e}"); time.sleep(120); continue
        log(f"pass requested: stages {a.stages}, egress cap {cap:.2f} GB (room {room:.2f})"
            + (f", comment trees {width} at a time" if width else ""))
        run = wait_for(t0, start_bytes)
        if not run:
            log("no finished receipt in 5.5 hours; stopping"); break
        n = run["notes"] if isinstance(run["notes"], dict) else json.loads(run["notes"] or "{}")
        st = n.get("stages") or {}
        bf, cl, co = st.get("backfill") or {}, st.get("classify") or {}, st.get("collect") or {}
        if co:
            per_min = (f", {co['reddit_calls'] / co['minutes']:.0f} calls a minute"
                       if co.get("minutes") and co.get("reddit_calls") else "")
            log(f"  collect: {co.get('subs_visited')} subreddits visited, {co.get('mentions_new')} new mentions, "
                f"{co.get('reddit_calls')} calls{per_min}, {co.get('allowance_used') or co.get('stopped')}")
            if co.get("seconds"):
                log(f"  collect time: trees {co.get('tree_workers', 1)} at a time; seconds {json.dumps(co['seconds'])}")
        log(f"pass {run['status']}: backfill done {len(bf.get('done') or [])} subs, left {bf.get('left')}, "
            f"{bf.get('mentions')} mentions, {bf.get('reddit_calls')} calls, stopped: {bf.get('stopped')}; "
            f"classify labelled {cl.get('labelled')}, rejected {cl.get('rejected')}, left {cl.get('left_in_queue')}; "
            f"egress estimate {n.get('egress_estimate_gb')} GB; caps hit {n.get('caps_hit')}")
        if run["status"] not in ("ok", "capped") and "day pass guard" not in json.dumps(n):
            log("the pass failed; stopping"); break
        if "backfill" in a.stages and bf.get("note") == "every declared subreddit is done" and cl.get("left_in_queue") == 0:
            log("backfill and labels done"); break
        rf = st.get("refresh") or {}
        work = sum(int(x or 0) for x in (co.get("reddit_calls"), co.get("mentions_new"),
                                         bf.get("reddit_calls"), bf.get("trees"), len(bf.get("done") or []),
                                         cl.get("labelled"), cl.get("rejected"), rf.get("brands_refreshed")))
        if work == 0:   # 9 Oct: 150 passes in a row did nothing, one a minute; an empty pass means wait, not retry
            log("the pass did nothing; next request in 30 minutes")
            time.sleep(1800)
    log("passes ended")
    return 0


if __name__ == "__main__":
    sys.exit(main())
