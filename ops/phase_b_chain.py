#!/usr/bin/env python3
"""Phase B collection (decision 0018), one job after another, resumable, inside the day.

1. a 90-day sweep (`worker/sweep.py --days 90 --tree-cap 150`) of each new category's core subreddits, one category
   at a time (partner-priority subreddits are most of them);
2. the post backfill (`worker/backfill_posts.py`), which resumes from its own watermark.

Each job runs through `ops/backfill_run.py` (a 'backfill' receipt, RI_RUN_ID on its rows, the Mac awake for the job
only, its own process group, stopped by 23:40 UTC by itself). The chain:
  - starts no job after STOP_AT, or when the day's room under the 2 GB line (`ops/day_egress.py`) is already used;
  - stops the running job at KILL_AT (absolute, dated, checked every minute whether or not the counter could be read),
    or as soon as the database's node counter has moved by the day's room;
  - a stop is SIGTERM to the wrapper (which stops the job's group and closes the receipt); a wrapper still alive after
    five minutes is killed, and so is the job's group (its id comes from RI_JOB_PIDFILE).
Every job resumes from disk or its watermark, so a stop loses nothing. A category whose sweep finished is recorded in
docs/phase-b/chain-state.json and skipped next time.

  python3 ops/phase_b_chain.py
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import signal
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "ops"))
NEW = ["recreation-entertainment-insurance", "commercial-insurance-brokerage", "artist-booking", "eor-global-payroll",
       "log-management-siem", "sales-planning", "aba-therapy", "itsm"]
STOP_UTC, KILL_UTC = dt.time(22, 30), dt.time(23, 15)
STATE = os.path.join(ROOT, "docs", "phase-b", "chain-state.json")


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def log(*a):
    print(f"[{now():%H:%M:%S}]", *a, flush=True)


def counter():
    try:
        import investigation_2026_10 as inv
        return inv._metrics()["transmit_bytes"]
    except Exception:  # noqa: BLE001 - a missed reading never disables the clock
        return None


def kill_group_from(pidfile: str) -> None:
    try:
        pg = int(open(pidfile).read().strip())
        os.killpg(pg, signal.SIGKILL)
    except (OSError, ValueError):
        pass


def main() -> int:
    import db
    import day_egress
    t = now()
    if t.time() < dt.time(5, 30):
        log("inside the night window: not starting")
        return 1
    stop_at = dt.datetime.combine(t.date(), STOP_UTC, tzinfo=dt.timezone.utc)
    kill_at = dt.datetime.combine(t.date(), KILL_UTC, tzinfo=dt.timezone.utc)
    with db.connect() as c:
        room = day_egress.used_today(c)["room_gb"] - 0.05
    start = counter()
    log(f"room under the 2 GB line today: {room:.2f} GB; starts nothing after {stop_at:%H:%M}, stops by {kill_at:%H:%M} UTC")
    state = json.load(open(STATE)) if os.path.exists(STATE) else {"done": []}
    core = {}
    for r in csv.DictReader(open(os.path.join(ROOT, "data", "category-subreddits.csv"))):
        if r["category_slug"] in NEW and r.get("is_core") == "True":
            core.setdefault(r["category_slug"], []).append(r["subreddit"])
    jobs = [(f"sweep-90d-{slug}", ["python3", "worker/sweep.py", "--days", "90", "--tree-cap", "150", "--only",
                                   ",".join(core[slug])]) for slug in NEW if slug in core and slug not in state["done"]]
    jobs.append(("posts-backfill", ["python3", "worker/backfill_posts.py"]))

    def used() -> float | None:
        c = counter()
        return None if c is None or start is None or c < start else (c - start) / 1e9

    for label, cmd in jobs:
        u = used()
        if now() >= stop_at:
            log(f"stop: past the chain's start limit ({stop_at:%H:%M} UTC)")
            break
        if room <= 0 or (u is not None and u >= room):
            log(f"stop: the day's room under the 2 GB line is used ({room:.2f} GB)")
            break
        log(f"start {label}")
        pidfile = os.path.join(tempfile.gettempdir(), f"ri-phase-b-{os.getpid()}.pgid")
        p = subprocess.Popen(["python3", "ops/backfill_run.py", label, "--", *cmd], cwd=ROOT,
                             env={**os.environ, "RI_JOB_PIDFILE": pidfile})
        stopped = None
        while p.poll() is None:
            time.sleep(60)
            if now() >= kill_at:
                stopped = f"{KILL_UTC:%H:%M} UTC: the night run's window approaches"
            else:
                u = used()
                if u is not None and u >= room:
                    stopped = f"the day's room under the 2 GB line ({room:.2f} GB) used"
            if stopped:
                log(f"stopping {label}: {stopped}")
                p.send_signal(signal.SIGTERM)
                try:
                    p.wait(timeout=300)
                except subprocess.TimeoutExpired:
                    log(f"{label}: the wrapper did not stop in five minutes; killing it and the job's group")
                    kill_group_from(pidfile)
                    p.kill()
                    p.wait(timeout=60)
                break
        if stopped:
            break
        if p.returncode == 0 and label.startswith("sweep-90d-"):
            state["done"].append(label[len("sweep-90d-"):])
            json.dump(state, open(STATE, "w"), indent=1)
        log(f"{label} ended: exit {p.returncode}")
    log("chain ended")
    return 0


if __name__ == "__main__":
    sys.exit(main())
