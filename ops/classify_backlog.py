#!/usr/bin/env python3
"""Label the backlog: every mention collected since 25 August that nothing has classified (one time).

The same stage the daily sweep runs (worker/classify_sweep.py: Jev in front, GLM-5.3 on the rest), inside the
budgets declared before the first job (docs/classify-backlog.md):

  GLM-5.3     60,000 credits for the whole backlog (43% of one week's plan); at most 20,000 a run; never in
              Z.ai's peak hours (06:00-10:00 UTC); at most 8 jobs in flight
  Jev         $60 for the whole backlog
  egress      1.5 GB for the whole backlog, at most 0.5 GB a UTC day: the text the judges read plus the
              write-ahead log the labels produce, both counted

Totals are read back from public.pipeline_runs (stage 'classify-backlog'), so a run started on any machine
knows what the earlier ones spent. It holds the sweep's advisory lock, so it never overlaps the daily sweep.
A failure is residue: an item no judge answered stays in the queue, is counted, and is asked again.

  ops/classify_backlog.py --until 05:30            # run until 05:30 UTC or a cap, whichever first
  ops/classify_backlog.py --max-items 2000         # the pilot: one batch, costed
  ops/classify_backlog.py --status                 # what the backlog has spent and what is left
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))

BUDGET = {"glm_credits_total": 60000, "glm_credits_run": 20000, "jev_usd_total": 60.0,
          "egress_gb_total": 1.5, "egress_gb_day": 0.5, "glm_in_flight": 8}
LOCK_KEY = 0x52494458   # worker/run_daily.py's: one writer at a time


def log(*a, **_):
    print(f"[{dt.datetime.now(dt.timezone.utc).strftime('%H:%M:%S')}]", *a, flush=True)


def spent(conn) -> dict:
    rows = conn.execute("select started_at, notes from public.pipeline_runs where stage = 'classify-backlog'").fetchall()
    today = dt.datetime.now(dt.timezone.utc).date()
    out = {"runs": len(rows), "glm_credits": 0.0, "jev_usd": 0.0, "egress_gb": 0.0, "egress_gb_today": 0.0,
           "labelled": 0, "rejected": 0}
    for started, notes in rows:
        n = notes if isinstance(notes, dict) else json.loads(notes or "{}")
        out["glm_credits"] += float(n.get("glm_credits") or 0)
        out["jev_usd"] += float(n.get("jev_usd") or 0)
        out["egress_gb"] += float(n.get("egress_estimate_gb") or 0)
        out["labelled"] += int(n.get("labelled") or 0)
        out["rejected"] += int(n.get("rejected") or 0)
        if started and started.astimezone(dt.timezone.utc).date() == today:
            out["egress_gb_today"] += float(n.get("egress_estimate_gb") or 0)
    return {k: round(v, 3) if isinstance(v, float) else v for k, v in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", default="05:30", help="UTC time to stop by (HH:MM)")
    ap.add_argument("--max-items", type=int, default=400000)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    import db
    import classify_sweep as cs
    from run_daily import wal_bytes

    conn = db.connect()
    conn.autocommit = True
    s = spent(conn)
    left = conn.execute("select count(*) from public.classify_queue").fetchone()[0]
    if a.status:
        print(json.dumps({"spent": s, "budget": BUDGET, "queue": left}, indent=1))
        return 0
    if not conn.execute("select pg_try_advisory_lock(%s)", (LOCK_KEY,)).fetchone()[0]:
        log("the daily sweep or another backlog run holds the lock: not running")
        return 0

    room = {"glm": min(BUDGET["glm_credits_run"], BUDGET["glm_credits_total"] - s["glm_credits"]),
            "jev": BUDGET["jev_usd_total"] - s["jev_usd"],
            "egress": min(BUDGET["egress_gb_day"] - s["egress_gb_today"], BUDGET["egress_gb_total"] - s["egress_gb"])}
    if min(room.values()) <= 0:
        log(f"a backlog budget is used up: {room}; spent so far {s}")
        return 0
    now = dt.datetime.now(dt.timezone.utc)
    hh, mm = (int(x) for x in a.until.split(":"))
    end = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if end <= now:
        end += dt.timedelta(days=1)
    deadline = time.time() + (end - now).total_seconds()

    run_id, t0, wal0, read0 = str(uuid.uuid4()), time.time(), wal_bytes(conn), cs.READ_BYTES

    def egress() -> int:
        w = wal_bytes(conn)
        return ((w - wal0) if (w is not None and wal0 is not None) else 0) + (cs.READ_BYTES - read0)

    def should_stop():
        if egress() > room["egress"] * 1e9:
            return f"backlog egress room for today ({room['egress']:.2f} GB) used"
        return None

    def record(status: str, rec: dict) -> None:
        notes = {**rec, "egress_estimate_gb": round(egress() / 1e9, 4), "minutes": round((time.time() - t0) / 60, 1),
                 "budget_room": room}
        conn.execute(
            "insert into public.pipeline_runs (run_id, stage, code_version, started_at, finished_at, status, notes) "
            "values (%s, 'classify-backlog', 'classify-v1', to_timestamp(%s), now(), %s, %s) "
            "on conflict (run_id) do update set finished_at = now(), status = excluded.status, notes = excluded.notes",
            (run_id, t0, status, json.dumps(notes, default=str)))

    record("running", {})
    log(f"backlog run {run_id[:8]}: {left:,} queued; room {room}; until {end:%H:%M} UTC")
    cfg = {"max_items": a.max_items, "jev_usd_max": room["jev"], "glm_credits_max": room["glm"],
           "glm_in_flight": BUDGET["glm_in_flight"], "glm_model": cs.GLM_DEFAULT}
    try:
        rec = cs.run(conn, cfg, deadline, should_stop, log)
        status = "capped" if rec.get("stopped") and "time" not in rec["stopped"] else "ok"
    except Exception as e:  # noqa: BLE001
        rec = {"error": f"{type(e).__name__}: {str(e)[:300]}"}
        status = "failed"
    record(status, rec)
    log(f"backlog run {run_id[:8]} {status}: {json.dumps(rec, default=str)}")
    return 0 if status != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
