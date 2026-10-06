#!/usr/bin/env python3
"""How much database egress the index's own jobs have used today (UTC), all of them together.

Each job had its own ceiling (the sweep 0.8 GB a run, the backlog 0.5 GB a day, retention 0.4 GB a day) and on
3 October 2026 their SUM reached 2.4 GB in a day and tripped the organisation's egress alarm. From then on the
laptop-run jobs (backlog classifier, retention) take their room from one day total, DAY_TOTAL_GB, after
subtracting what the night's sweep and every other job already used.

Sources, most trusted first: the gate meter's node-counter measurement of the night's sweep
(docs/go-live/egress-<day>.json); otherwise each receipt's own figure in public.pipeline_runs. A sweep receipt
carries an ESTIMATE that leaves out the pages the publisher fetched, so it is scaled by the ratio measured on
3 October (0.559 GB measured for 0.351 estimated).

  python3 ops/day_egress.py        # today's total and the room left
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))

DAY_TOTAL_GB = 2.0   # Vlad, 2026-10-05: "move on with the data collection". 1.0 was this session's own guard;
                     # 2.0 stays under the egress watchdog's alert line (2 GB a day), so it never pages him
SWEEP_ESTIMATE_TO_MEASURED = 1.6


def used_today(conn) -> dict:
    today = dt.datetime.now(dt.timezone.utc).date()
    out = {"day": str(today), "sweep_gb": 0.0, "other_gb": 0.0, "sweep_source": "none"}
    gate = os.path.join(ROOT, "docs", "go-live", f"egress-{today}.json")
    measured, measured_run = None, None
    if os.path.exists(gate):
        g = json.load(open(gate))
        if g.get("run_id") and g.get("gate_egress_gb") is not None:   # ops/gate_meter.py's tick format (4 Oct on)
            measured, measured_run = float(g["gate_egress_gb"]), g["run_id"]
    rows = conn.execute("select run_id::text, stage, notes from public.pipeline_runs where started_at::date = %s",
                        (today,)).fetchall()
    est = 0.0
    for run_id, stage, notes in rows:
        n = notes if isinstance(notes, dict) else json.loads(notes or "{}")
        v = float(n.get("egress_estimate_gb") or n.get("egress_gb") or 0)
        if stage == "sweep" and run_id == measured_run:
            continue          # measured below, on the node counter
        if stage == "sweep":   # a by-hand day run: its receipt's estimate (it counts its page renders)
            est += v
        else:
            out["other_gb"] += v
    if measured is not None:
        out["sweep_gb"] = measured + est
        out["sweep_source"] = f"night run on the node counter ({g.get('gate_source')}) + day runs' estimates"
    else:
        out["sweep_gb"], out["sweep_source"] = est * SWEEP_ESTIMATE_TO_MEASURED, "receipt estimate x 1.6"
    out["used_gb"] = round(out["sweep_gb"] + out["other_gb"], 3)
    out["room_gb"] = round(max(0.0, DAY_TOTAL_GB - out["used_gb"]), 3)
    return out


if __name__ == "__main__":
    import db
    with db.connect() as c:
        print(json.dumps(used_today(c), indent=1))
