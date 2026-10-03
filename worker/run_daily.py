#!/usr/bin/env python3
"""The Reddit Index daily sweep. One run a day, off the laptop, bounded, resumable, with a receipt.

Stages, in order. Each one is safe to repeat, and each resumes from what the database already says, not
from a pointer this script keeps:

  0. preflight   the stop switch (public.sweep_control), the schedule window, one run at a time
                 (an advisory lock), the database and Reddit reachable
  1. takedowns   every document on a page is checked against Reddit; deleted, removed and edited ones are
                 purged (worker/takedown.py). First, so collection can never spend the calls it needs.
  2. collect     new posts and recent comment trees (worker/collect.py), inside the call, row and time caps
  3. classify    new mentions labelled: Jev in front, GLM-5.3 on the uncertain band
                 (worker/classify_sweep.py; skipped, and said so, while it is not enabled)
  4. refresh     every brand whose data changed recomputed in the database (site.refresh_brand)
  5. score       score and rank every page (worker/site_score.py)
  6. publish     only when publishing is switched on: expire changed pages, prove the ones that must be
                 proven, then stamp each takedown's receipt (removals.revalidated_at) once its pages were
                 SEEN without the card (worker/site_publish.py)
  7. receipt     one row in public.pipeline_runs with every count; site.meta.last_success_at on success

Caps (ops/schedule.json): Reddit calls, new mentions, wall time, estimated database egress. At a cap a stage
stops clean, the run finishes the cheap stages that follow (refresh, score, receipt), and says so.

Vlad gets ONE Slack DM, and only when a run failed, hit a cap, braked a purge, or found a takedown it could
not prove. Never a daily report.

  worker/run_daily.py                 # what the schedule runs
  worker/run_daily.py --manual        # outside the window (a pilot, a catch-up)
  worker/run_daily.py --stages takedowns,collect --max-calls 300 --manual   # a small pilot
  worker/run_daily.py --no-dm         # never message anyone (tests)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import traceback
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import db  # noqa: E402

CODE_VERSION = "sweep-v1"
LOCK_KEY = 0x52494458  # "RIDX": one sweep at a time, whatever starts it
VLAD = "U016BPWFC7Q"
STAGES = ["takedowns", "collect", "classify", "refresh", "score", "publish"]


def load_schedule() -> dict:
    with open(os.path.join(ROOT, "ops", "schedule.json"), encoding="utf-8") as f:
        return json.load(f)


def log(*a, **k):
    print(f"[{dt.datetime.now(dt.timezone.utc).strftime('%H:%M:%S')}]", *a, flush=True, **{x: y for x, y in k.items() if x != "flush"})


def wal_bytes(conn) -> int | None:
    try:
        return int(conn.execute("select wal_bytes from pg_stat_wal").fetchone()[0])
    except Exception:  # noqa: BLE001
        return None


class Run:
    def __init__(self, conn, sched: dict, args):
        self.conn, self.sched, self.args = conn, sched, args
        self.run_id = str(uuid.uuid4())
        self.started = time.time()
        caps = dict(sched["caps"])
        if args.max_calls is not None:
            caps["reddit_calls"] = args.max_calls
        self.caps = caps
        self.deadline = self.started + caps["minutes"] * 60
        self.receipt: dict = {"run_id": self.run_id, "code_version": CODE_VERSION, "manual": bool(args.manual),
                              "caps": caps, "stages": {}, "problems": [], "caps_hit": []}
        self.wal0 = wal_bytes(conn)

    # -- the switch, read before every stage and inside the long ones
    def stop_reason(self) -> str | None:
        try:
            enabled, reason = self.conn.execute("select enabled, reason from public.sweep_control").fetchone()
        except Exception as e:  # noqa: BLE001
            return f"could not read the stop switch: {str(e)[:80]}"
        if not enabled:
            return f"stopped by the switch: {reason or 'no reason given'}"
        if self.egress_estimate() > self.caps["egress_gb"] * 1e9:
            return f"estimated database egress cap ({self.caps['egress_gb']} GB) reached"
        return None

    def egress_estimate(self) -> int:
        """Write-ahead log produced since the run started. Every byte of it is shipped to backup storage,
        and the node counter the egress watchdog reads counts it. Query results the sweep reads are small
        by construction, except the text the classifier reads, which it counts itself."""
        w = wal_bytes(self.conn)
        wal = (w - self.wal0) if (w is not None and self.wal0 is not None) else 0
        cs = sys.modules.get("classify_sweep")
        return wal + (cs.READ_BYTES if cs else 0)

    def record(self, status: str) -> None:
        self.receipt["status"] = status
        self.receipt["minutes"] = round((time.time() - self.started) / 60, 1)
        self.receipt["egress_estimate_gb"] = round(self.egress_estimate() / 1e9, 3)
        self.conn.execute(
            "insert into public.pipeline_runs (run_id, stage, code_version, started_at, finished_at, status, notes) "
            "values (%s, 'sweep', %s, to_timestamp(%s), now(), %s, %s) "
            "on conflict (run_id) do update set finished_at = now(), status = excluded.status, notes = excluded.notes",
            (self.run_id, CODE_VERSION, self.started, status, json.dumps(self.receipt, default=str)))


def in_window(sched: dict) -> bool:
    now = dt.datetime.now(dt.timezone.utc)
    start = dt.datetime.strptime(sched["window_utc"][0], "%H:%M").time()
    end = dt.datetime.strptime(sched["window_utc"][1], "%H:%M").time()
    t = now.time()
    return start <= t <= end if start <= end else (t >= start or t <= end)


def stage(run: Run, name: str, fn) -> None:
    if name not in run.args.stages:
        return
    reason = run.stop_reason()
    if reason and name in ("takedowns", "collect", "classify"):
        run.receipt["stages"][name] = {"skipped": reason}
        run.receipt["caps_hit"].append(reason) if "cap" in reason else run.receipt["problems"].append(reason)
        log(f"{name}: skipped, {reason}")
        return
    t = time.time()
    log(f"{name}: start")
    try:
        out = fn() or {}
    except Exception as e:  # noqa: BLE001 - a failed stage is recorded, the cheap stages after it still run
        out = {"error": f"{type(e).__name__}: {str(e)[:300]}"}
        run.receipt["problems"].append(f"{name} failed: {out['error']}")
        log(f"{name}: FAILED {out['error']}")
        traceback.print_exc()
    out["minutes"] = round((time.time() - t) / 60, 1)
    run.receipt["stages"][name] = out
    if out.get("stopped"):
        run.receipt["caps_hit"].append(f"{name}: {out['stopped']}")
    log(f"{name}: done in {out['minutes']} min")


def dm(text: str) -> None:
    sys.path.insert(0, os.path.join(HERE, "lib"))
    import slack_dm  # worker/lib/slack_dm.py: env SLACK_BOT_TOKEN
    slack_dm.send(VLAD, text)


def tell_vlad(run: Run) -> None:
    r = run.receipt
    c = r["stages"].get("collect", {})
    t = r["stages"].get("takedowns", {})
    if r["status"] == "ok" and not r["caps_hit"]:
        return
    if r["status"] == "failed":
        head = "*Reddit Index: last night's update failed*"
    elif any("brake" in p.lower() for p in r["problems"]):
        head = "*Reddit Index: last night's update stopped before deleting anything*"
    elif any("takedown" in p.lower() for p in r["problems"]):
        head = "*Reddit Index: a deleted comment may still be showing on the site*"
    else:
        head = "*Reddit Index: last night's update stopped early at one of its limits*"
    story = []
    if r["caps_hit"]:
        story.append("It reached a limit set to keep the cost down: " + "; ".join(r["caps_hit"])[:300] + ".")
    if r["problems"]:
        story.append("What went wrong: " + "; ".join(r["problems"])[:400] + ".")
    story.append(f"It collected {c.get('mentions_new', 0):,} new mentions from {c.get('subs_visited', 0):,} subreddits "
                 f"and checked {t.get('docs_checked', 0):,} comments on the site against Reddit.")
    you = ("Nothing for you to do. The next run picks up where this one stopped."
           if r["status"] != "failed" else
           "Nothing for you to do yet: the site keeps showing the last good data until the next run succeeds.")
    link = "<https://github.com/Empact-Partners/reddit-index/blob/main/SOP.md|how the daily update works>"
    text = (f"{head}\n\n{' '.join(story)}\n\n*What this means for you*\n{you}\n\n*To do*\nNothing for anyone "
            f"to do.\n\n*Details for the curious (and for your Claude)*\nrun {r['run_id'][:8]} in the "
            f"database's run log · {link}")
    try:
        dm(text)
    except Exception as e:  # noqa: BLE001
        log(f"could not send the DM: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manual", action="store_true", help="run outside the schedule window")
    ap.add_argument("--stages", default=",".join(STAGES))
    ap.add_argument("--max-calls", type=int, default=None)
    ap.add_argument("--no-dm", action="store_true")
    args = ap.parse_args()
    args.stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    sched = load_schedule()

    if not args.manual and not in_window(sched):
        log(f"outside the run window {sched['window_utc']}: not running (a stray start is refused)")
        return 0

    conn = db.connect()
    conn.autocommit = True
    run = Run(conn, sched, args)
    # A run that does not work still leaves a row, so "the schedule fired and chose not to run" can be told
    # apart from "nothing started" (scripts/schedule_check.py reads both).
    if not conn.execute("select pg_try_advisory_lock(%s)", (LOCK_KEY,)).fetchone()[0]:
        log("another sweep or the backlog classifier holds the lock: not running")
        run.receipt["skipped"] = "another job held the sweep lock"
        run.record("skipped")
        return 0
    reason = run.stop_reason()
    if reason and not reason.startswith("estimated"):
        log(reason)
        run.receipt["skipped"] = reason
        run.record("skipped")
        return 0
    run.record("running")
    log(f"run {run.run_id[:8]} caps {run.caps}")

    import site_score
    import site_publish
    import takedown

    stage(run, "takedowns", lambda: takedown.run(
        conn, max_calls=run.caps["takedown_calls"], max_gone_share=sched["takedown_brake_share"],
        deadline=run.deadline, log=log))
    td = run.receipt["stages"].get("takedowns", {})
    if td.get("brake"):
        run.receipt["problems"].append(f"takedown brake: {td.get('gone_share')} of checked documents looked gone")

    def collect_stage():
        import collect
        import reddit_client as rc
        left = run.caps["reddit_calls"] - rc.stats()["calls"]
        return collect.run(conn, {"reddit_calls": max(0, left), "mentions": run.caps["mentions"]},
                           run.deadline, run.stop_reason, log)
    stage(run, "collect", collect_stage)

    def classify_stage():
        if not sched.get("classify", {}).get("enabled"):
            return {"skipped": "the classifier is not enabled yet; new mentions stay unlabelled and are counted"}
        import classify_sweep
        return classify_sweep.run(conn, sched["classify"], run.deadline, run.stop_reason, log)
    stage(run, "classify", classify_stage)

    def refresh_stage():
        import site_fill_lib
        n = site_fill_lib.drain(conn, 25, log=lambda *a, **k: None)
        left = conn.execute("select count(*) from site.dirty_brand").fetchone()[0]
        return {"brands_refreshed": n, "still_dirty": left}
    stage(run, "refresh", refresh_stage)
    stage(run, "score", lambda: site_score.run(conn, log=log))

    def publish_stage():
        on = conn.execute("select publish_enabled from public.sweep_control").fetchone()[0]
        if not on:
            return {"skipped": "publishing is off until decision 0017: the site is not told about changes"}
        rec = site_publish.run(conn, sched["site_url"], verify_n=sched["verify_pages"],
                               max_expire=sched["max_expire_pages"], log=log)
        # A takedown's receipt: every page that held the document has been SEEN at its new fingerprint
        # (or answered 404). Never stamped on a 200 from the endpoint.
        stamped = conn.execute("""
            update public.removals r set revalidated_at = now()
             where r.revalidated_at is null and r.purged_at is not null
               and not exists (select 1 from unnest(r.brand_ids) b
                                 join site.brand_stats s on s.brand_id = b
                                where s.served_hash is distinct from s.page_hash)
               and not exists (select 1 from unnest(r.brand_ids) b
                                 join public.brands br on br.id = b
                                 join site.retired_page rp on rp.slug = br.slug
                                where rp.gone_at is null)""").rowcount
        rec["takedown_receipts_stamped"] = stamped
        open_td = conn.execute("select count(*) from public.removals where revalidated_at is null "
                               "and detected_at < now() - interval '36 hours'").fetchone()[0]
        if open_td:
            run.receipt["problems"].append(f"{open_td} takedowns older than 36 hours are not yet proven on the site")
        if rec.get("failed"):
            run.receipt["problems"].append(f"{len(rec['failed'])} pages failed verification")
        rec.pop("verified_brand_ids", None)
        return rec
    stage(run, "publish", publish_stage)

    hard = [p for p in run.receipt["problems"] if "failed" in p or "brake" in p]
    status = "failed" if hard else ("capped" if run.receipt["caps_hit"] else "ok")
    if status != "failed" and all(s in run.receipt["stages"] for s in ("refresh", "score")):
        conn.execute("update site.meta set last_success_at = now(), last_run_id = %s", (run.run_id,))
    run.record(status)
    log(f"run {run.run_id[:8]} {status}: {json.dumps({k: v for k, v in run.receipt.items() if k != 'stages'}, default=str)[:600]}")
    if not args.no_dm:
        tell_vlad(run)
    return 0 if status != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
