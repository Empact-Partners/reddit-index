#!/usr/bin/env python3
"""Run one backfill job (decision 0018) inside a receipt, metered on the node counter.

Writes a `public.pipeline_runs` row (stage 'backfill') before the job, passes its id to the job as RI_RUN_ID (the
mentions it writes carry it, so `scripts/schedule_check.py` matches them), keeps the Mac awake for this job only
(`caffeinate -i`, ended with the job), and closes the receipt with the exit status and the egress the node counter
measured. Refuses inside the night window (00:00-05:30 UTC): the sweep owns the Reddit app and the lock then.

  python3 ops/backfill_run.py <label> -- python3 worker/backfill_posts.py
  python3 ops/backfill_run.py sweep-90d-aba-therapy -- python3 worker/sweep.py --days 90 --tree-cap 150 --only a,b,c
"""
from __future__ import annotations

import datetime as dt
import json
import os
import signal
import subprocess
import sys
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def main() -> int:
    if "--" not in sys.argv or sys.argv.index("--") < 2:
        print(__doc__)
        return 2
    label = sys.argv[1]
    cmd = sys.argv[sys.argv.index("--") + 1:]
    h = dt.datetime.now(dt.timezone.utc).time()
    if h < dt.time(5, 30):
        print("inside the night window (00:00-05:30 UTC): not running")
        return 1
    import db
    import investigation_2026_10 as inv
    run_id, t0 = str(uuid.uuid4()), time.time()
    start = inv._metrics()["transmit_bytes"]

    def record(status: str, notes: dict) -> None:
        with db.connect() as c:
            c.autocommit = True
            c.execute("insert into public.pipeline_runs (run_id, stage, code_version, started_at, finished_at, status, notes) "
                      "values (%s, 'backfill', %s, to_timestamp(%s), case when %s = 'running' then null else now() end, %s, %s) "
                      "on conflict (run_id) do update set finished_at = excluded.finished_at, status = excluded.status, "
                      "notes = excluded.notes", (run_id, label, t0, status, status, json.dumps(notes)))

    record("running", {"label": label, "command": " ".join(cmd)})
    print(f"backfill {label}: receipt {run_id}", flush=True)
    p = subprocess.Popen(["/usr/bin/caffeinate", "-i", *cmd], cwd=ROOT, env={**os.environ, "RI_RUN_ID": run_id},
                         start_new_session=True)   # its own process group: a stop reaches the job, not only caffeinate
    stopped = {"by": None}

    def on_term(signum, frame):   # a stop ends the job and still writes the receipt (the job resumes from disk)
        stopped["by"] = "stopped by the caller (SIGTERM)"
        os.killpg(p.pid, signal.SIGTERM)
    signal.signal(signal.SIGTERM, on_term)
    p.wait()
    end = inv._metrics()["transmit_bytes"]
    notes = {"label": label, "command": " ".join(cmd), "exit": p.returncode, "stopped": stopped["by"],
             "minutes": round((time.time() - t0) / 60, 1),
             "egress_gb": round((end - start) / 1e9, 4) if end >= start else None,
             "egress_source": "node counter (the write-ahead-log tail after the job is not on it)"}
    record("ok" if p.returncode == 0 else ("capped" if stopped["by"] else "failed"), notes)
    print(json.dumps(notes), flush=True)
    return p.returncode


if __name__ == "__main__":
    sys.exit(main())
