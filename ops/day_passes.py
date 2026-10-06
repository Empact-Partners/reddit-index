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
LINE_GB = 1.95   # Vlad's 2 GB a day, with a margin for the write-ahead-log tail after a pass


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


def request(stages: str, max_calls: int, end_by: str, egress_gb: float) -> None:
    import watch_link as w
    import deploy_sweep as d
    w.query(f"insert into public.day_run_request (stages, max_calls, end_by_utc, max_egress_gb) values "
            f"('{stages}', {int(max_calls)}, '{end_by}'::time, {egress_gb:.3f})")
    svcs = d.gql("query($p:String!){ project(id:$p){ services { edges { node { id name } } } } }",
                 {"p": d.PROJECT})["project"]["services"]["edges"]
    sid = [e["node"]["id"] for e in svcs if e["node"]["name"] == d.NAME][0]
    si = d.gql("query($s:String!,$e:String!){ serviceInstance(serviceId:$s, environmentId:$e){ id } }",
               {"s": sid, "e": d.ENV})["serviceInstance"]["id"]
    d.gql("mutation($i: DeploymentInstanceExecutionCreateInput!){ deploymentInstanceExecutionCreate(input: $i) }",
          {"i": {"serviceInstanceId": si}})


def wait_for(t0: dt.datetime) -> dict | None:
    import watch_link as w
    for _ in range(330):   # a pass is at most 5.5 hours
        time.sleep(60)
        try:
            r = w.query(f"select run_id, status, finished_at, notes from public.pipeline_runs where stage = 'sweep' "
                        f"and started_at > '{t0.isoformat()}' order by started_at desc limit 1")
        except Exception:  # noqa: BLE001 - a missed poll is a missed poll
            continue
        if r and r[0]["finished_at"]:
            return r[0]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="backfill,classify,refresh,score")
    ap.add_argument("--until", default="21:00", help="start no pass after this UTC time; each pass ends by 21:30")
    ap.add_argument("--max-calls", type=int, default=15000)
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
        cap = min(0.7, (room - 0.03) / 1.6)
        t0 = dt.datetime.now(dt.timezone.utc)
        try:
            request(a.stages, a.max_calls, "21:30", cap)
        except Exception as e:  # noqa: BLE001
            log(f"could not start a pass: {e}"); time.sleep(120); continue
        log(f"pass requested: stages {a.stages}, egress cap {cap:.2f} GB (room {room:.2f})")
        run = wait_for(t0)
        if not run:
            log("no finished receipt in 5.5 hours; stopping"); break
        n = run["notes"] if isinstance(run["notes"], dict) else json.loads(run["notes"] or "{}")
        st = n.get("stages") or {}
        bf, cl = st.get("backfill") or {}, st.get("classify") or {}
        log(f"pass {run['status']}: backfill done {len(bf.get('done') or [])} subs, left {bf.get('left')}, "
            f"{bf.get('mentions')} mentions, {bf.get('reddit_calls')} calls, stopped: {bf.get('stopped')}; "
            f"classify labelled {cl.get('labelled')}, rejected {cl.get('rejected')}, left {cl.get('left_in_queue')}; "
            f"egress estimate {n.get('egress_estimate_gb')} GB; caps hit {n.get('caps_hit')}")
        if run["status"] not in ("ok", "capped"):
            log("the pass failed; stopping"); break
        if bf.get("note") == "every declared subreddit is done" and cl.get("left_in_queue") == 0:
            log("backfill and labels done"); break
    log("passes ended")
    return 0


if __name__ == "__main__":
    sys.exit(main())
