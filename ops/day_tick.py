#!/usr/bin/env python3
"""One tick of the daytime passes, on Railway (decision 0026).

The second Railway service of the index (`reddit-index-day`) starts this every 30 minutes between 06:00 and 21:30
UTC. A tick reads the database node's transmit counter, keeps the reading, and decides whether a daytime pass may
start: inside the daytime window, nothing else running, no daytime passes being requested from the laptop
(ops/day_passes.py, decision 0041), and room under the day's line in the watchdog's day (07:00 to 07:00 UTC, with the
day's backup and tonight's run still to come counted as sent: decision 0035; the line is dated: 0041). If it
may, the tick writes the request row (migration 0023) and becomes the pass: worker/run_daily.py in this same
container. Railway does not start a cron execution while the one before it is still running, so a pass in progress
is never doubled; the sweep's own lock covers the rest.

Until 11 Oct the passes were requested from a laptop (ops/day_passes.py): it slept on battery, and with it the
requests and the guard. The pass now guards the line itself (decision 0025) and nothing of the daily collection
waits on a laptop.

  python3 ops/day_tick.py            # one tick (what the service runs)
  python3 ops/day_tick.py --dry-run  # decide and print; request nothing, run nothing
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "worker"))


def log(*a) -> None:
    print(f"[{dt.datetime.now(dt.timezone.utc).strftime('%H:%M:%S')}]", *a, flush=True)


def _t(hhmm: str) -> dt.time:
    return dt.datetime.strptime(hhmm, "%H:%M").time()


def effective_used(conn, now_bytes: float | None, now: dt.datetime, sched: dict) -> tuple[float | None, str]:
    """What a pass is judged on (decision 0035): the bytes the node sent in the watchdog's day (07:00 to 07:00 UTC),
    plus the day's backup and tonight's run while they are still to come in it, and why ("" when nothing is held).
    None when the day's start is not known (no reading before it, or a node restart)."""
    import meter
    if now_bytes is None:
        return None, ""
    led = meter.ledger(conn, now_bytes, now, sched)
    if led["used"] is None:
        return None, ""
    held = [w for v, w in ((led["backup_held"], led["backup_why"]), (led["night_held"], led["night_why"])) if v]
    return led["used"], "; ".join(held)


LAPTOP_SOURCE = "day passes (laptop)"   # what ops/day_passes.py writes beside each counter reading


def laptop_minutes(conn) -> float | None:
    """Minutes since ops/day_passes.py last read the node counter from the laptop (it keeps each reading in
    public.egress_counter as LAPTOP_SOURCE, at least every few minutes while it runs), or None: never, or unreadable.
    Two requesters of passes collide on the sweep's lock and the loser's receipt reads "skipped" (decision 0041)."""
    try:
        r = conn.execute("select extract(epoch from now() - max(at)) / 60 from public.egress_counter "
                         "where source = %s and at > now() - interval '1 day'", (LAPTOP_SOURCE,)).fetchone()
    except Exception:  # noqa: BLE001 - not known: the tick decides as it always has
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None
    return float(r[0]) if r and r[0] is not None else None


def glm_peak(now: dt.datetime) -> bool:
    """Z.ai's peak hours, 06:00 to 10:00 UTC: GLM is not asked then and only Jev labels, its confident share
    (worker/classify_sweep.py; decision 0032 amended)."""
    return 6 <= now.hour < 10


def decide(now: dt.datetime, running: int, used_gb: float | None, cfg: dict, line_gb: float,
           queue: int | None = None, laptop_min: float | None = None) -> tuple[bool, str, float | None]:
    """(start a pass?, why in plain words, the pass's cap on its own egress estimate in GB). used_gb: the watchdog's
    day so far with what is still to come in it (effective_used). line_gb: that day's line (meter.day_line_gb).
    queue: mentions waiting for a label; in GLM's peak hours, when it is at least cfg peak_queue_max, no pass starts
    (decision 0032). laptop_min: minutes since ops/day_passes.py last read the counter from the laptop; while it is
    under cfg laptop_quiet_minutes the laptop is requesting its own passes and the tick stands aside (decision 0041)."""
    first, last = _t(cfg["window_utc"][0]), _t(cfg["window_utc"][1])
    if not (first <= now.time() <= last):
        return False, f"outside the daytime window {cfg['window_utc'][0]} to {cfg['window_utc'][1]} UTC", None
    if running:
        return False, "a run or a retention step is in progress", None
    quiet = float(cfg.get("laptop_quiet_minutes", 15))
    if laptop_min is not None and laptop_min < quiet:
        return False, (f"the laptop's day passes (ops/day_passes.py) read the counter {laptop_min:.0f} minutes ago: "
                       f"they request their own passes, and a pass from here would take the sweep's lock from "
                       f"theirs (decision 0041); the tick starts again {quiet:.0f} minutes after their last reading"), None
    if queue is not None and glm_peak(now) and queue >= int(cfg.get("peak_queue_max", 20000)):
        return False, (f"{queue:,} mentions wait for a label, and in GLM's peak hours (06:00 to 10:00 UTC) only Jev "
                       f"labels, its confident share: a pass now would mostly add to them"), None
    if used_gb is None:
        return False, ("the node counter could not be read, or no reading is older than the watchdog's day: no pass "
                       "is started without knowing the room"), None
    room = line_gb - used_gb
    if room < float(cfg["min_room_gb"]):
        return False, (f"the watchdog's day (since 07:00 UTC) stands at {used_gb:.2f} GB with what is still to come "
                       f"in it: {room:.2f} GB of room under the {line_gb} GB line, and a pass needs "
                       f"{cfg['min_room_gb']}"), None
    # the pass caps itself on its own estimate, which reads a little under the counter (1.17 to 1.19 times on the
    # two clean passes of 10 Oct); the counter itself is the pass's hard stop (decision 0025)
    cap = round(max(0.05, min(0.7, (room - 0.05) / float(cfg["estimate_factor"]))), 3)
    return True, (f"the watchdog's day (since 07:00 UTC) stands at {used_gb:.2f} GB with what is still to come in "
                  f"it: {room:.2f} GB of room, a pass capped at {cap} GB on its own estimate"), cap


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    sched = json.load(open(os.path.join(HERE, "schedule.json")))
    cfg = sched["day"]
    import db
    import meter
    conn = db.connect()
    conn.autocommit = True
    try:
        if not conn.execute("select enabled from public.sweep_control").fetchone()[0]:
            log("the sweep is switched off: no pass")
            return 0
        # a receipt left 'running' by a run that died stops being believed after 6 hours (a pass lasts at most 5.5)
        running = conn.execute("select count(*) from public.pipeline_runs where finished_at is null and stage in "
                               "('sweep', 'retention') and started_at > now() - interval '6 hours'").fetchone()[0]
        b = meter.record(conn, "day tick")
        now = dt.datetime.now(dt.timezone.utc)
        used, held_why = effective_used(conn, b, now, sched)
        if held_why:
            log(held_why)
        from classify_sweep import LABELLABLE_SQL   # entries tried five times wait for a person, not for GLM
        queue = conn.execute(LABELLABLE_SQL).fetchone()[0]
        laptop_min = laptop_minutes(conn)
        go, why, cap = decide(now, running, None if used is None else used / 1e9,
                              cfg, meter.day_line_gb(sched, now), queue, laptop_min)
        log(("a daytime pass starts: " if go else "no pass: ") + why)
        if not go or a.dry_run:
            return 0
        options = {"tree_workers": int(sched.get("collect", {}).get("tree_workers", 1))}
        try:
            conn.execute("delete from public.day_run_request")   # a request nobody consumed is never acted on later
            conn.execute("insert into public.day_run_request (stages, max_calls, end_by_utc, max_egress_gb, options) "
                         "values (%s, %s, %s::time, %s, %s::jsonb)",
                         (cfg["stages"], int(cfg["max_calls"]), cfg["end_by_utc"], cap, json.dumps(options)))
        except Exception as e:  # noqa: BLE001 - said plainly in the log; the next tick tries again
            log(f"the request could not be written, so no pass starts: {type(e).__name__}: {str(e)[:200]}")
            return 1
    finally:
        conn.close()
    sys.stdout.flush()
    run = os.path.join(ROOT, "worker", "run_daily.py")
    os.execv(sys.executable, [sys.executable, "-u", run])   # this container is now the pass
    return 0   # not reached


if __name__ == "__main__":
    sys.exit(main())
