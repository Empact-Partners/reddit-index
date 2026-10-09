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

Vlad gets ONE Slack DM, and only when a run failed, hit a real limit (the egress cap, an abnormal flood of new
mentions), braked a purge, or found a takedown it could not prove. Never a daily report: a stage that simply used
its planned nightly allowance (collection's Reddit calls, classification's credits) ends normally and says so on
the receipt.

  worker/run_daily.py                 # what the schedule runs
  worker/run_daily.py --manual        # outside the window (a pilot, a catch-up)
  worker/run_daily.py --manual --max-calls 300 --takedown-calls 200 --classify-items 2000   # a small pilot
  worker/run_daily.py --no-dm         # never message anyone (tests)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.request
import traceback
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import db  # noqa: E402

CODE_VERSION = "sweep-v1"
LOCK_KEY = 0x52494458  # "RIDX": one sweep at a time, whatever starts it
VLAD = "U016BPWFC7Q"
STAGES = ["takedowns", "collect", "classify", "refresh", "score", "publish", "retention"]
# Only a daytime pass that names it runs this (decision 0018: the partner categories' 90-day history). Never the night.
EXTRA_STAGES = ["backfill"]


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


RENDER_BYTES_PER_PAGE = 200_000


class Run:
    def __init__(self, conn, sched: dict, args):
        self.conn, self.sched, self.args = conn, sched, args
        self.run_id = str(uuid.uuid4())
        self.started = time.time()
        caps = dict(sched["caps"])
        if args.max_calls is not None:
            caps["reddit_calls"] = args.max_calls
        if args.takedown_calls is not None:
            caps["takedown_calls"] = args.takedown_calls
        if args.max_mentions is not None:
            caps["mentions"] = args.max_mentions
        if getattr(args, "max_egress_gb", None):   # a daytime pass: the day's room under the 2 GB line, from its requester
            caps["egress_gb"] = min(caps["egress_gb"], float(args.max_egress_gb))
        self.caps = caps
        self.deadline = self.started + caps["minutes"] * 60
        if getattr(args, "day_end", None):   # a daytime pass ends by its requested time, well before the night
            end = dt.datetime.combine(dt.datetime.now(dt.timezone.utc).date(), args.day_end, dt.timezone.utc)
            self.deadline = min(self.deadline, end.timestamp())
        if not args.manual:   # a scheduled run also ends with its window, however late it started (review 4 Oct)
            end = dt.datetime.combine(dt.datetime.now(dt.timezone.utc).date(),
                                      dt.datetime.strptime(sched["window_utc"][1], "%H:%M").time(), dt.timezone.utc)
            self.deadline = min(self.deadline, end.timestamp())   # a start after the end leaves no time at all
        self.receipt: dict = {"run_id": self.run_id, "code_version": CODE_VERSION, "manual": bool(args.manual),
                              "day_run": bool(getattr(args, "day_end", None)),
                              "caps": caps, "stages": {}, "problems": [], "caps_hit": []}
        self.wal0 = wal_bytes(conn)
        self.render_bytes = 0   # what the site reads to re-render the pages the publisher fetches (set by publish)

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
        return wal + (cs.READ_BYTES if cs else 0) + self.render_bytes

    def record(self, status: str) -> None:
        if self.conn.closed:   # the laptop slept or the pooler dropped the session: the receipt still gets written
            self.conn = db.connect()
            self.conn.autocommit = True
        self.receipt["status"] = status
        self.receipt["minutes"] = round((time.time() - self.started) / 60, 1)
        self.receipt["egress_estimate_gb"] = round(self.egress_estimate() / 1e9, 3)
        self.conn.execute(
            "insert into public.pipeline_runs (run_id, stage, code_version, started_at, finished_at, status, notes) "
            "values (%s, 'sweep', %s, to_timestamp(%s), case when %s = 'running' then null else now() end, %s, %s) "
            "on conflict (run_id) do update set finished_at = excluded.finished_at, status = excluded.status, notes = excluded.notes",
            (self.run_id, CODE_VERSION, self.started, status, status, json.dumps(self.receipt, default=str)))


def in_window(sched: dict) -> bool:
    now = dt.datetime.now(dt.timezone.utc)
    start = dt.datetime.strptime(sched["window_utc"][0], "%H:%M").time()
    end = dt.datetime.strptime(sched["window_utc"][1], "%H:%M").time()
    t = now.time()
    return start <= t <= end if start <= end else (t >= start or t <= end)


def backfill_subs(categories: list[str], csv_path: str) -> list[str]:
    """The core subreddits of these categories, category by category in the given order, each once."""
    import csv
    by_cat: dict[str, list[str]] = {}
    for r in csv.DictReader(open(csv_path)):
        if r["category_slug"] in categories and r.get("is_core") == "True":
            by_cat.setdefault(r["category_slug"], []).append(r["subreddit"].lower())
    out: list[str] = []
    for c in categories:
        for s in sorted(by_cat.get(c, [])):
            if s not in out:
                out.append(s)
    return out


def backfill(run: "Run", cfg: dict, log) -> dict:
    """Decision 0018: the 90-day sweep (worker/sweep.py) of the partner categories' core subreddits, a subreddit at a
    time, inside this pass's time, Reddit-call and egress limits. A container's disk is new every pass, so what is done
    is read from the earlier receipts (stages.backfill.done), never from local files: a pass takes the next ones."""
    import reddit_client as rc
    if not cfg.get("categories"):
        return {"skipped": "no backfill declared in ops/schedule.json"}
    done = set()
    for (d,) in run.conn.execute("select notes->'stages'->'backfill'->'done' from public.pipeline_runs "
                                 "where stage = 'sweep' and notes->'stages'->'backfill'->'done' is not null").fetchall():
        done.update(d or [])
    subs = [s for s in backfill_subs(cfg["categories"], os.path.join(ROOT, "data", "category-subreddits.csv")) if s not in done]
    out = {"queue": len(subs), "done": [], "unfinished": [], "trees": 0, "mentions": 0, "stopped": None}
    if not subs:
        out["note"] = "every declared subreddit is done"
        return out
    os.environ["RI_RUN_ID"] = run.run_id   # the sweep's rows carry this receipt (schedule_check matches them)
    import sweep
    sweep.RUN_ID = run.run_id
    until = min(run.deadline - 95 * 60, time.time() + float(cfg.get("max_minutes", 150)) * 60)
    ctx = sweep.prepare(int(cfg.get("days", 90)))
    known = {k.lower(): k for k in ctx["sub_ids"]}   # the name as the subreddits table spells it (the sweep's lookup is exact)
    calls0 = rc.stats()["calls"]
    try:
        for sub in subs:
            reason = run.stop_reason()
            if reason:
                out["stopped"] = reason
                break
            if time.time() >= until:
                out["stopped"] = "the pass's backfill time is used; the next pass continues"
                break
            if rc.stats()["calls"] - calls0 >= run.caps["reddit_calls"]:
                out["stopped"] = f"the pass's Reddit calls ({run.caps['reddit_calls']}) are used"
                break
            real = known.get(sub)
            if real is None:   # not in the subreddits table yet: never marked done, so a later pass sweeps it once loaded
                out.setdefault("unknown", []).append(sub)
                continue
            trees, m = sweep.run_subs([real], ctx, int(cfg.get("tree_cap", 150)))
            out["trees"] += trees
            out["mentions"] += m
            # the sweep's own test: a thread it gave up on (three failed fetches) counts as handled. Without that,
            # three subreddits whose last threads kept failing read "not finished" forever while every pass made
            # 0 calls on them, and the day runner re-requested an empty pass every minute (9 Oct: 150 of them).
            finished = sweep.sub_complete(real, ctx["mode"], int(cfg.get("tree_cap", 150)))
            if not finished and trees == 0 and not sweep.load_state(real, ctx["mode"]).get("listings_done"):
                # the listing failed. A container's disk is new every pass, so the sweep's own retry count never
                # passes 1 and it never gives up: ask Reddit whether the subreddit exists at all (9 Oct:
                # bookingagent, salesmanagement and autismparenting answer 404, and 150 passes retried them).
                about = rc.get(f"/r/{real}/about", {"raw_json": 1}, bucket="misc", use_cache=False)
                if isinstance(about, dict) and about.get("_err") in (403, 404):
                    out.setdefault("unreachable", []).append({"sub": sub, "http": about["_err"]})
                    finished = True   # recorded in `done`: no later pass takes it again
            (out["done"] if finished else out["unfinished"]).append(sub)
            log(f"  backfill {sub}: {trees} trees, {m} mentions, {'done' if sub in out['done'] else 'not finished'}")
    finally:
        try:
            ctx["conn"].close()
        except Exception:  # noqa: BLE001
            pass
    out["reddit_calls"] = rc.stats()["calls"] - calls0
    out["left"] = len(subs) - len(out["done"])
    return out


def stage(run: Run, name: str, fn) -> None:
    if name not in run.args.stages:
        return
    reason = run.stop_reason()
    # Stopped by the switch: nothing more runs, refresh and publish included (review, 2026-10-03: a stop used to
    # be followed by a publish and an "ok" receipt). At the egress cap: the in-database refresh and scoring still
    # run (they write little and keep the tables consistent); everything that reads or calls out does not.
    if reason and (not reason.startswith("estimated database egress cap")
                   or name in ("takedowns", "collect", "classify", "publish")):
        run.receipt["stages"][name] = {"skipped": reason}
        if reason.startswith("estimated database egress cap"):
            if reason not in run.receipt["caps_hit"]:
                run.receipt["caps_hit"].append(reason)
        else:
            run.receipt["stopped"] = reason
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
    if out.get("error") and not any(x.startswith(f"{name} failed") for x in run.receipt["problems"]):
        run.receipt["problems"].append(f"{name} failed: {out['error']}")   # a stage that caught its own error
    out["minutes"] = round((time.time() - t) / 60, 1)
    run.receipt["stages"][name] = out
    if out.get("stopped"):
        run.receipt["caps_hit"].append(f"{name}: {out['stopped']}")
    if out.get("allowance_used"):   # a planned nightly allowance ran out: recorded, not an alert (Vlad gets no
        run.receipt.setdefault("allowances_used", []).append(f"{name}: {out['allowance_used']}")   # daily message)
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
    ap.add_argument("--takedown-calls", type=int, default=None, help="pilot: cap the takedown stage's Reddit calls")
    ap.add_argument("--max-mentions", type=int, default=None, help="pilot: cap new mentions")
    ap.add_argument("--classify-items", type=int, default=None, help="pilot: cap mentions classified")
    args = ap.parse_args()
    args.stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    sched = load_schedule()

    args.day_end = None
    args.max_egress_gb = None
    if not args.manual and not in_window(sched):
        # A start outside the night window is refused unless a daytime pass was requested in the last 20 minutes
        # (public.day_run_request, migration 0023; `ops/ri.py dayrun`). The request is consumed here, so one
        # request is one pass, and a stray start still finds nothing and stops.
        c0 = db.connect()
        c0.autocommit = True
        try:
            req = c0.execute("delete from public.day_run_request where requested_at > now() - interval '20 minutes' "
                             "returning stages, max_calls, end_by_utc, max_egress_gb").fetchone()
            c0.execute("delete from public.day_run_request")   # an older request is never acted on later
        finally:
            c0.close()
        if not req:
            log(f"outside the run window {sched['window_utc']}: not running (a stray start is refused)")
            return 0
        args.manual, args.no_dm = True, True
        args.stages = [x.strip() for x in req[0].split(",") if x.strip()]
        args.max_calls, args.day_end = int(req[1]), req[2]
        args.max_egress_gb = float(req[3]) if req[3] is not None else None   # the day's room, measured by the requester
        log(f"a daytime pass was requested: stages {args.stages}, {args.max_calls} Reddit calls, ends by {req[2]} UTC")

    conn = db.connect()
    conn.autocommit = True
    run = Run(conn, sched, args)
    # A run that does not work still leaves a row, so "the schedule fired and chose not to run" can be told
    # apart from "nothing started" (scripts/schedule_check.py reads both).
    if not conn.execute("select pg_try_advisory_lock(%s)", (LOCK_KEY,)).fetchone()[0]:
        log("another sweep or the backlog classifier holds the lock: not running")
        run.receipt["skipped"] = "another job held the sweep lock"
        run.record("skipped")
        try:
            on = conn.execute("select enabled from public.sweep_control").fetchone()[0]
        except Exception:  # noqa: BLE001
            on = True
        if on and not args.manual and not args.no_dm:
            # a night lost: the backlog classifier or a hand run must never overlap the window (SOP)
            try:
                dm("*Reddit Index: tonight's update did not run*\n\nAt midnight UTC another job was still holding "
                   "the index's lock, so the daily update stood aside rather than run beside it. Nothing was "
                   "collected tonight; tomorrow's run catches up.\n\n*What this means for you*\nOne day of data "
                   "arrives a day late.\n\n*To do*\nNothing for anyone to do.\n\n*Details for the curious (and "
                   "for your Claude)*\n<https://github.com/Empact-Partners/reddit-index/blob/main/SOP.md|how the "
                   "daily update works>")
            except Exception as e:  # noqa: BLE001
                log(f"could not send the DM: {e}")
        return 0
    reason = run.stop_reason()
    if reason and not reason.startswith("estimated"):
        log(reason)
        run.receipt["skipped"] = reason
        run.record("skipped")
        return 0
    if time.time() >= run.deadline:   # the window check passed, but the connection came after the window's end
        run.receipt["skipped"] = "started after its window ended"
        run.record("skipped")
        log("started after the window ended: not running")
        return 0
    run.record("running")
    log(f"run {run.run_id[:8]} caps {run.caps}")

    import site_score
    import site_publish
    import takedown

    stage(run, "takedowns", lambda: takedown.run(
        conn, max_calls=run.caps["takedown_calls"], max_gone_share=sched["takedown_brake_share"],
        deadline=run.deadline, log=log, should_stop=run.stop_reason))
    td = run.receipt["stages"].get("takedowns", {})
    if td.get("brake"):
        run.receipt["problems"].append(f"takedown brake: {td.get('gone_share')} of checked documents looked gone")

    def collect_stage():
        import collect
        import reddit_client as rc
        left = run.caps["reddit_calls"] - rc.stats()["calls"]
        # Collection ends an hour before the run's deadline: classification, refresh, score and publish need
        # that hour, and a collection that used the whole window would leave the day's mentions unlabelled.
        return collect.run(conn, {"reddit_calls": max(0, left), "mentions": run.caps["mentions"]},
                           run.deadline - sched.get("reserve_minutes_after_collect", 95) * 60, run.stop_reason, log,
                           run_id=run.run_id)
    stage(run, "collect", collect_stage)

    def backfill_stage():
        return backfill(run, sched.get("backfill") or {}, log)
    stage(run, "backfill", backfill_stage)

    def classify_stage():
        if not sched.get("classify", {}).get("enabled"):
            return {"skipped": "the classifier is not enabled yet; new mentions stay unlabelled and are counted"}
        import classify_sweep
        cfg = dict(sched["classify"])
        if args.classify_items is not None:
            cfg["max_items"] = args.classify_items
        # and classification leaves time for refresh, score and publish (measured 4 Oct: refresh 15 minutes for
        # 3,262 brands, publish about 3 minutes per 1,000 pages)
        return classify_sweep.run(conn, cfg, run.deadline - sched.get("reserve_minutes_after_classify", 35) * 60,
                                  run.stop_reason, log)
    stage(run, "classify", classify_stage)

    def refresh_stage():
        import site_fill_lib
        # refresh stops 8 minutes before the run's end so publish can still prove the takedown pages
        # (measured 4 Oct: 0.28 s a brand on the night, 1.3 s a brand in the afternoon)
        n = site_fill_lib.drain(conn, 25, log=lambda *a, **k: None, deadline=run.deadline - 8 * 60)
        left = conn.execute("select count(*) from site.dirty_brand").fetchone()[0]
        out = {"brands_refreshed": n, "still_dirty": left}
        if left:
            out["allowance_used"] = f"the time for refresh ended with {left} brands left for the next run"
        return out
    stage(run, "refresh", refresh_stage)
    stage(run, "score", lambda: site_score.run(conn, log=log))

    def publish_stage():
        on = conn.execute("select publish_enabled from public.sweep_control").fetchone()[0]
        if not on:
            return {"skipped": "publishing is off until decision 0017: the site is not told about changes"}
        rec = site_publish.run(conn, sched["site_url"], verify_n=sched["verify_pages"],
                               max_expire=sched["max_expire_pages"], log=log, deadline=run.deadline)
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
                                where rp.gone_at is null)
               -- a brand still waiting for its refresh has an old page_hash that may equal the old served_hash:
               -- the purge is not on its page yet, so nothing is proven (review, 2026-10-04)
               and not exists (select 1 from unnest(r.brand_ids) b join site.dirty_brand d on d.brand_id = b)""").rowcount
        rec["takedown_receipts_stamped"] = stamped
        # Every page the publisher fetched was re-rendered by the site from the database: about 0.2 MB a company
        # page (measured on the pilot), counted here so the receipt's estimate covers the whole night (2026-10-04:
        # the first scheduled run's estimate left them out and read 0.555 GB where the meter's day read 0.89).
        pages = int(rec.get("pages_fetched") or 0)   # every fetch the site answered rendered, proven or not
        run.render_bytes = pages * RENDER_BYTES_PER_PAGE
        rec["render_estimate_gb"] = round(run.render_bytes / 1e9, 3)
        if rec.get("failed"):
            run.receipt["problems"].append(f"{len(rec['failed'])} pages failed verification")
        rec.pop("verified_brand_ids", None)
        return rec
    stage(run, "publish", publish_stage)

    def retention_stage():
        """docs/retention.md steps 1 and 2 and the archive's 14 days, every night (until 9 Oct they ran only by
        hand, once). Each moves rows into `archive` in the statement that deletes them. Step 2 takes at most
        20,000 rows a night; nothing qualifies before 2 November."""
        if run.stop_reason():
            return {"skipped": run.stop_reason()}
        sys.path.insert(0, os.path.join(ROOT, "ops"))
        import retention as ret
        out = ret.threads(conn)
        out.update(ret.rejected(conn, limit=sched.get("retention", {}).get("rejected_per_night", 20000)))
        out["archive_expired"] = {t: conn.execute(f"delete from archive.{t} where archived_at < now() - interval "
                                                  f"'14 days'").rowcount
                                  for t in ("threads", "mentions", "mention_sentiment")}
        return out
    stage(run, "retention", retention_stage)

    # whatever ran tonight: a takedown older than 36 hours that is not proven on the site is a legal condition
    # (decision 0002) and fails the run, so Vlad hears of it (review 4 Oct: it was checked only inside publish)
    try:
        open_td = conn.execute("select count(*) from public.removals where revalidated_at is null "
                               "and detected_at < now() - interval '36 hours'").fetchone()[0]
    except Exception as e:  # noqa: BLE001
        open_td, run.receipt["takedown_check_error"] = None, str(e)[:200]
        run.receipt["problems"].append("takedown proof check failed: could not read the removals ledger")
    if open_td:
        run.receipt["problems"].append(f"takedown proof failed: {open_td} takedowns older than 36 hours are "
                                       f"not yet proven on the site")
    hard = [p for p in run.receipt["problems"] if "failed" in p or "brake" in p]
    status = ("stopped" if run.receipt.get("stopped") else
              "failed" if hard else ("capped" if run.receipt["caps_hit"] else "ok"))
    ran = all("skipped" not in run.receipt["stages"].get(s, {"skipped": 1}) for s in ("refresh", "score"))
    if status in ("ok", "capped") and ran:
        conn.execute("update site.meta set last_success_at = now(), last_run_id = %s", (run.run_id,))
        # The footer date comes from /freshness.json, which refreshes itself at most every five minutes (decision
        # 0022; an expiry never reached it). Read it back until it says this run, so a stale date is a receipt line,
        # not something Vlad notices. Only after a run that published: a pass without publish changed no page.
        pub = run.receipt["stages"].get("publish") or {}
        if pub and "skipped" not in pub and not pub.get("failed"):
            try:
                import site_publish
                want = conn.execute("select to_char(last_success_at at time zone 'utc', "
                                    "'YYYY-MM-DD\"T\"HH24:MI:SS') from site.meta").fetchone()[0]
                served, t_end = None, time.time() + 480
                while True:
                    req = urllib.request.Request(sched["site_url"].rstrip("/") + "/freshness.json",
                                                 headers=site_publish._headers(sched["site_url"]))
                    with urllib.request.urlopen(req, timeout=30) as r:
                        served = json.loads(r.read()).get("refreshedAt")
                    if (served or "")[:19] == want or time.time() > t_end:
                        break
                    time.sleep(30)
                run.receipt["freshness_served"] = served
                if (served or "")[:19] != want:
                    run.receipt["problems"].append(f"the site's freshness date reads {served} eight minutes after "
                                                   f"the run, not this run's {want}")
            except Exception as e:  # noqa: BLE001 - the footer date is cosmetic; the data is already served
                run.receipt["problems"].append(f"freshness date not read back: {str(e)[:120]}")
    run.record(status)
    log(f"run {run.run_id[:8]} {status}: {json.dumps({k: v for k, v in run.receipt.items() if k != 'stages'}, default=str)[:600]}")
    if not args.no_dm and status != "stopped":   # a stop is someone's decision; they know
        tell_vlad(run)
    return 0 if status != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
