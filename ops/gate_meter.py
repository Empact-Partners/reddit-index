#!/usr/bin/env python3
"""Measure a scheduled night's egress for the go-live gate: "a full run plus the day's page regeneration under 1 GB".

Reads the database node's transmit counter (the number the egress watchdog and the bill follow) at 23:58 UTC the
evening before, waits for that night's sweep receipt (public.pipeline_runs, stage 'sweep'), waits 20 minutes more
for the write-ahead log to finish shipping (measured 2026-10-03: the tail belongs to the work), reads it again,
and writes docs/go-live/egress-<night>.json. Nothing else of ours may run in that window (the backlog classifier
and retention share the sweep's lock and are scheduled outside it).

  caffeinate -i python3 ops/gate_meter.py --night 2026-10-04 --night 2026-10-05
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def sleep_until(t: dt.datetime) -> None:
    while True:
        left = (t - dt.datetime.now(dt.timezone.utc)).total_seconds()
        if left <= 0:
            return
        time.sleep(min(left, 300))


def counter() -> tuple[float, str]:
    import investigation_2026_10 as inv
    for attempt in range(5):
        try:
            return inv._metrics()["transmit_bytes"], dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        except Exception:  # noqa: BLE001 - a missed reading is retried, never invented
            time.sleep(30 * (attempt + 1))
    raise RuntimeError("the node counter could not be read")


def measure(night: str) -> dict:
    import db
    day = dt.datetime.fromisoformat(night).replace(tzinfo=dt.timezone.utc)
    sleep_until(day - dt.timedelta(minutes=2))
    before, at0 = counter()
    receipt = None
    while receipt is None:
        with db.connect() as conn:
            r = conn.execute("select run_id, started_at, finished_at, status, notes from public.pipeline_runs "
                             "where stage = 'sweep' and started_at >= %s and finished_at is not null "
                             "and status <> 'running' order by started_at limit 1", (day,)).fetchone()
        if r:
            receipt = r
            break
        if dt.datetime.now(dt.timezone.utc) > day + dt.timedelta(hours=8):
            break
        time.sleep(120)
    if receipt is None:
        out = {"night": night, "found_run": False, "counter_at_start": at0}
    else:
        sleep_until(receipt[2] + dt.timedelta(minutes=20))
        after, at1 = counter()
        n = receipt[4] if isinstance(receipt[4], dict) else json.loads(receipt[4] or "{}")
        out = {"night": night, "found_run": True, "run_id": str(receipt[0]), "status": receipt[3],
               "run_started": receipt[1].isoformat(), "run_finished": receipt[2].isoformat(),
               "counter_read_at": [at0, at1], "egress_bytes": round(after - before),
               "egress_gb": round((after - before) / 1e9, 3), "gate_under_1_gb": (after - before) < 1e9,
               "run_minutes": n.get("minutes"), "caps_hit": n.get("caps_hit"), "problems": n.get("problems"),
               "stages": {k: {x: v.get(x) for x in ("reddit_calls", "mentions_new", "docs_checked", "docs_gone",
                                                    "labelled", "rejected", "glm_credits", "jev_usd",
                                                    "pages_expired", "pages_verified", "takedown_pages", "failed")
                              if isinstance(v, dict) and x in v}
                          for k, v in (n.get("stages") or {}).items()}}
    os.makedirs(os.path.join(ROOT, "docs", "go-live"), exist_ok=True)
    with open(os.path.join(ROOT, "docs", "go-live", f"egress-{night}.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(out, default=str), flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--night", action="append", required=True, help="YYYY-MM-DD, the UTC date the run starts")
    a = ap.parse_args()
    for night in a.night:
        measure(night)
    return 0


if __name__ == "__main__":
    sys.exit(main())
