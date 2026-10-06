#!/usr/bin/env python3
"""Phase B collection (decision 0018), one job after another, resumable, inside the day.

1. a 90-day sweep (`worker/sweep.py --days 90 --tree-cap 150`) of each new category's core subreddits, one category
   at a time (partner-priority subreddits are most of them);
2. the post backfill (`worker/backfill_posts.py`), which resumes from its own watermark.

Each job runs through `ops/backfill_run.py` (a 'backfill' receipt, RI_RUN_ID on its rows, the Mac awake for the job
only). The chain stops starting jobs at STOP_UTC, kills the running one at KILL_UTC (both well before the night
run at 00:00), and kills it as soon as the database's node counter has moved by the day's remaining room under the
2 GB line (`ops/day_egress.py`). Every job resumes from disk or its watermark, so a stop loses nothing. A category
whose sweep finished is recorded in docs/phase-b/chain-state.json and skipped next time.

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


def main() -> int:
    import db
    import day_egress
    import investigation_2026_10 as inv
    with db.connect() as c:
        room = day_egress.used_today(c)["room_gb"] - 0.05
    start = inv._metrics()["transmit_bytes"]
    log(f"room under the 2 GB line today: {room:.2f} GB")
    state = json.load(open(STATE)) if os.path.exists(STATE) else {"done": []}
    core = {}
    for r in csv.DictReader(open(os.path.join(ROOT, "data", "category-subreddits.csv"))):
        if r["category_slug"] in NEW and r.get("is_core") == "True":
            core.setdefault(r["category_slug"], []).append(r["subreddit"])
    jobs = [(f"sweep-90d-{slug}", ["python3", "worker/sweep.py", "--days", "90", "--tree-cap", "150", "--only",
                                   ",".join(core[slug])]) for slug in NEW if slug in core and slug not in state["done"]]
    jobs.append(("posts-backfill", ["python3", "worker/backfill_posts.py"]))
    for label, cmd in jobs:
        t = now().time()
        if t >= STOP_UTC or t < dt.time(5, 30):
            log(f"stop: {t:%H:%M} UTC is past the chain's start limit ({STOP_UTC:%H:%M}) or in the night window")
            break
        log(f"start {label}")
        p = subprocess.Popen(["python3", "ops/backfill_run.py", label, "--", *cmd], cwd=ROOT)
        stopped = None
        while p.poll() is None:
            time.sleep(60)
            try:
                used = (inv._metrics()["transmit_bytes"] - start) / 1e9
            except Exception:  # noqa: BLE001 - a missed reading keeps the job running one more minute
                continue
            if used >= room:
                stopped = f"the day's room under the 2 GB line ({room:.2f} GB) used"
            elif now().time() >= KILL_UTC:
                stopped = f"{KILL_UTC:%H:%M} UTC: the night run's window approaches"
            if stopped:
                log(f"stopping {label}: {stopped}")
                p.send_signal(signal.SIGTERM)
                p.wait(timeout=300)
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
