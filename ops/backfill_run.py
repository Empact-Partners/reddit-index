#!/usr/bin/env python3
"""Run one backfill job (decision 0018) inside a receipt, metered on the node counter.

Writes a `public.pipeline_runs` row (stage 'backfill') before the job, passes its id to the job as RI_RUN_ID (the
mentions it writes carry it, so `scripts/schedule_check.py` matches them), keeps the Mac awake for this job only
(`caffeinate -i`, ended with the job), and closes the receipt with the exit status and the egress the node counter
measured. Refuses inside the night window (00:00-05:30 UTC), and stops the job before it begins (NIGHT_GUARD before
midnight): the sweep owns the Reddit app and the lock then.

The job runs in its own process group. Any stop (SIGTERM to this wrapper, the night guard) sends SIGTERM to the whole
group, then SIGKILL to whatever is left after GRACE seconds. The receipt is closed on every path, including a failed
launch or a failed counter reading. With RI_JOB_PIDFILE set, the job's group id is written there for a supervisor.

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
NIGHT_GUARD = dt.time(23, 40)   # the job is stopped at this UTC time at the latest (the sweep starts at 00:00)
GRACE = 60
STALL_MIN = 8                   # no line of output for this long is a hang: 20 trees or a printed rate-limit wait come far sooner
                                # (6 Oct: a Reddit read sat 27 min; three 20-minute stalls cost an hour)


def night_deadline(now: dt.datetime) -> dt.datetime:
    """The absolute moment a job started at `now` must be gone: today's NIGHT_GUARD (UTC)."""
    return dt.datetime.combine(now.date(), NIGHT_GUARD, tzinfo=dt.timezone.utc)


def in_night(now: dt.datetime) -> bool:
    return now.time() < dt.time(5, 30) or now.time() >= NIGHT_GUARD


def stop_group(pgid: int, grace: float = GRACE) -> None:
    """SIGTERM the job's whole group, then SIGKILL whatever is still there after `grace` seconds."""
    for sig, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, 0)):
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            return
        end = time.time() + wait
        while time.time() < end:
            try:
                os.killpg(pgid, 0)
            except (ProcessLookupError, PermissionError):
                return
            time.sleep(1)


def where_stuck(pgid: int) -> str:
    """What the stalled job's processes are waiting in (macOS `sample`), for the log: a network read, a database
    wait, a sleep. Best effort; never fails the stop."""
    try:
        pids = subprocess.run(["pgrep", "-g", str(pgid)], capture_output=True, text=True, timeout=10).stdout.split()
        out = []
        for pid in pids[:3]:
            smp = subprocess.run(["/usr/bin/sample", pid, "1"], capture_output=True, text=True, timeout=30).stdout
            frames = [ln.strip() for ln in smp.splitlines()
                      if any(k in ln for k in ("PySSL", "_ssl__", "psycopg", "time_sleep", "poll", "recv", "urlopen", "getaddrinfo"))]
            out.append(f"  pid {pid}: " + (" | ".join(dict.fromkeys(f.split("(in")[0].strip(" +!|:0123456789") for f in frames))[:400] or "no network or wait frame"))
        return "where it waited:\n" + "\n".join(out)
    except Exception as e:  # noqa: BLE001
        return f"where it waited: unknown ({type(e).__name__})"


def _counter():
    try:
        import investigation_2026_10 as inv
        return inv._metrics()["transmit_bytes"]
    except Exception:  # noqa: BLE001 - a missed reading costs the egress figure, never the receipt
        return None


def main() -> int:
    if "--" not in sys.argv or sys.argv.index("--") < 2:
        print(__doc__)
        return 2
    label = sys.argv[1]
    cmd = sys.argv[sys.argv.index("--") + 1:]
    now = dt.datetime.now(dt.timezone.utc)
    if in_night(now):
        print("inside the night window (23:40-05:30 UTC): not running")
        return 1
    deadline = night_deadline(now)
    import db
    run_id, t0 = str(uuid.uuid4()), time.time()
    start = _counter()
    state = {"proc": None, "stopped": None}

    def record(status: str, notes: dict) -> None:
        for attempt in range(3):
            try:
                with db.connect() as c:
                    c.autocommit = True
                    c.execute("insert into public.pipeline_runs (run_id, stage, code_version, started_at, finished_at, status, notes) "
                              "values (%s, 'backfill', %s, to_timestamp(%s), case when %s = 'running' then null else now() end, %s, %s) "
                              "on conflict (run_id) do update set finished_at = excluded.finished_at, status = excluded.status, "
                              "notes = excluded.notes", (run_id, label, t0, status, status, json.dumps(notes)))
                return
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    print(f"receipt {run_id} not written ({status}): {e}", flush=True)
                time.sleep(5)

    def on_term(signum, frame):   # a stop ends the whole job and still writes the receipt (the job resumes from disk)
        state["stopped"] = state["stopped"] or "stopped by the caller (SIGTERM)"
        if state["proc"] is not None:
            stop_group(state["proc"].pid)
    signal.signal(signal.SIGTERM, on_term)
    record("running", {"label": label, "command": " ".join(cmd)})
    print(f"backfill {label}: receipt {run_id}, stops by {deadline:%H:%M} UTC", flush=True)
    rc, err = None, None
    try:
        if state["stopped"]:
            raise RuntimeError("stopped before the job started")
        p = subprocess.Popen(["/usr/bin/caffeinate", "-i", *cmd], cwd=ROOT, env={**os.environ, "RI_RUN_ID": run_id, "PYTHONUNBUFFERED": "1"},
                             start_new_session=True,   # its own process group: a stop reaches the job, not only caffeinate
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        heard = {"at": time.time()}

        def relay():   # the job's output, passed through, and the time of its last line (the stall watchdog)
            for line in p.stdout:
                heard["at"] = time.time()
                sys.stdout.write(line)
                sys.stdout.flush()
        import threading
        threading.Thread(target=relay, daemon=True).start()
        state["proc"] = p
        if os.environ.get("RI_JOB_PIDFILE"):
            with open(os.environ["RI_JOB_PIDFILE"], "w") as f:
                f.write(str(p.pid))
        while p.poll() is None:
            if dt.datetime.now(dt.timezone.utc) >= deadline and not state["stopped"]:
                state["stopped"] = f"{NIGHT_GUARD:%H:%M} UTC: the night run's window"
                stop_group(p.pid)
            elif time.time() - heard["at"] > STALL_MIN * 60 and not state["stopped"]:
                state["stopped"] = f"stalled: no output for {STALL_MIN} minutes (resumes from its state next time)"
                print(f"backfill {label}: {state['stopped']}", flush=True)
                print(where_stuck(p.pid), flush=True)
                stop_group(p.pid)
            time.sleep(5)
        rc = p.returncode
    except Exception as e:  # noqa: BLE001 - a failed launch or wait still closes the receipt
        err = f"{type(e).__name__}: {e}"
    finally:
        if state["proc"] is not None and state["proc"].poll() is None:
            stop_group(state["proc"].pid)
        end = _counter()
        notes = {"label": label, "command": " ".join(cmd), "exit": rc, "stopped": state["stopped"], "error": err,
                 "minutes": round((time.time() - t0) / 60, 1),
                 "egress_gb": round((end - start) / 1e9, 4) if start is not None and end is not None and end >= start else None,
                 "egress_source": "node counter (the write-ahead-log tail after the job is not on it)"}
        status = "ok" if rc == 0 and not err else ("capped" if state["stopped"] else "failed")
        record(status, notes)
        print(json.dumps(notes), flush=True)
    return rc if rc is not None else 1


if __name__ == "__main__":
    sys.exit(main())
