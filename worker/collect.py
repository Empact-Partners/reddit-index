#!/usr/bin/env python3
"""The sweep's collection stage: new posts and recent comment trees from every scoring subreddit.

This is worker/daily.py's collection, reused function by function (listing, qualification, resolution,
insertion and the watermark rules are its, and each carries the incident it was written for), inside a loop
that can be stopped and bounded:

  * caps checked before every subreddit and every comment tree: Reddit calls, new mentions, wall time. A cap can
    therefore be passed by at most one subreddit's listing (up to 8 calls) or one subreddit's new mentions; the
    caps are safety bounds set well above a normal day, not exact quotas (review, 2026-10-03);
  * a stop check every 25 subreddits (public.sweep_control, and anything else the caller passes in);
  * a comment tree Reddit failed to return is NOT marked read (daily.py marked it read and lost it);
  * a quiet subreddit (no qualifying post on its last pass) is visited every third day, not every day;
  * a thread whose comment count and score did not change is not rewritten (each rewrite is shipped to
    backup storage and counted as egress);
  * the brand list and subreddit lists are the repository's, read at start: the old collector ran a
    19 August image for six weeks and never saw 4,471 brands added after it.

Order is daily.py's: core subreddits first, then longest-waiting, so a run that stops at a cap resumes
tomorrow where it stopped and every subreddit comes round.
"""
from __future__ import annotations

import datetime as dt
import time

import daily as d          # worker/daily.py: the collection helpers
import db
import reddit_client as rc
from harvest import post_doc, tree_docs

QUIET_DAYS = 3

THREADS_UPSERT = (
    "INSERT INTO threads (id, subreddit_id, link_title, permalink, created_utc, num_comments, archived, score, "
    "first_seen_at) VALUES (%s,%s,%s,%s,to_timestamp(%s),%s,%s,%s,now()) "
    "ON CONFLICT (id) DO UPDATE SET num_comments = EXCLUDED.num_comments, score = EXCLUDED.score "
    "WHERE (threads.num_comments, threads.score) IS DISTINCT FROM (EXCLUDED.num_comments, EXCLUDED.score)")


class Stop(Exception):
    """A cap or a stop switch: end the stage cleanly, keep everything committed so far."""


def plan(conn, today: dt.datetime) -> tuple[list[str], dict, set, int]:
    mapping = d.load_scoring_map()
    core = set(d.load_scoring_map(core_only=True))
    rows = conn.execute(
        "SELECT scope, finished_at, rows FROM ingest_state WHERE ym='daily' AND stage='new_listing' "
        "AND code_version=%s AND scope NOT LIKE '\\_%%'", (d.CODE_VERSION,)).fetchall()
    seen = {r[0].lower(): (r[1], r[2]) for r in rows}
    never = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    subs, quiet = [], 0
    for s in mapping:
        fin, n = seen.get(s.lower(), (None, None))
        if fin is not None and n == 0 and fin > today - dt.timedelta(days=QUIET_DAYS):
            quiet += 1
            continue
        subs.append(s)
    subs.sort(key=lambda x: (x not in core, seen.get(x.lower(), (never, 0))[0] or never))
    return subs, mapping, core, quiet


def run(conn, caps: dict, deadline: float, should_stop=lambda: None, log=print) -> dict:
    """caps: reddit_calls, mentions. should_stop(): returns a reason string to stop, or None."""
    t0 = time.time()
    calls0 = rc.stats()["calls"]
    now = dt.datetime.now(dt.timezone.utc)
    subs, mapping, core, quiet = plan(conn, now)
    rec = {"subs_planned": len(subs) + quiet, "subs_skipped_quiet": quiet, "subs_visited": 0, "threads_new": 0,
           "mentions_new": 0, "mentions_rejected": 0, "trees_fetched": 0, "trees_failed": 0,
           "capped_listings": 0, "errors": 0, "reddit_calls": 0, "stopped": None}

    brands = d.load_brands()
    alias_re = d.build_alias_re([b for bs in brands.values() for b in bs])
    resolver = d.Resolver()
    sub_ids = {name.lower(): sid for name, sid in conn.execute("SELECT name, id FROM subreddits").fetchall()}
    run_id = d.RUN_ID

    def check(where: str) -> None:
        used = rc.stats()["calls"] - calls0
        if used >= caps["reddit_calls"]:
            raise Stop(f"Reddit call cap ({caps['reddit_calls']}) reached {where}")
        if rec["mentions_new"] >= caps["mentions"]:
            raise Stop(f"new-mention cap ({caps['mentions']}) reached {where}")
        if time.time() > deadline:
            raise Stop(f"time window ended {where}")

    log(f"  collect: {len(subs)} subreddits to visit ({quiet} quiet ones skipped today), "
        f"{len(core & set(subs))} core")
    try:
        for si, sub in enumerate(subs, 1):
            check(f"before r/{sub} ({si}/{len(subs)})")
            if si % 25 == 1:
                reason = should_stop()
                if reason:
                    raise Stop(reason)
            sid = sub_ids.get(sub.lower())
            if sid is None:
                rec["errors"] += 1
                log(f"  r/{sub}: not in the subreddits table, skipped")
                continue
            try:
                with conn.transaction():
                    cur = conn.cursor()
                    wm = d.get_watermark(cur, sub)
                    posts, listing_ok, capped = d.fetch_new(sub, wm)
                    qual = [p for p in posts if d.content_qualify(p, mapping.get(sub, []), alias_re)]
                    newest = max([p.get("created_utc") or 0 for p in posts], default=wm or 0)
                    if qual:
                        cur.executemany(THREADS_UPSERT, [
                            (f"t3_{p['id']}", sid, (p.get("title") or "")[:500],
                             "https://www.reddit.com" + (p.get("permalink") or ""), p.get("created_utc") or 0,
                             p.get("num_comments") or 0, bool(p.get("archived")), p.get("score") or 0)
                            for p in qual])
                    cur.execute(
                        "SELECT id, link_title FROM threads WHERE subreddit_id=%s "
                        "AND first_seen_at > now() - make_interval(hours => %s) "
                        "ORDER BY tree_fetched_at NULLS FIRST, num_comments DESC LIMIT %s",
                        (sid, d.REVISIT_HOURS, d.TREES_PER_SUB))
                    revisit = cur.fetchall()

                    mrows = []
                    for p in qual:
                        doc = post_doc(p)
                        if not doc:
                            continue
                        for h in resolver.resolve(doc["body"], sub, p.get("title") or ""):
                            mrows.append((doc["id"], 2, doc["id"], sid, doc["author"], doc.get("created_utc") or 0,
                                          doc.get("permalink") or "", doc.get("score") or 0, doc["body"],
                                          h["conf"], h["alias"], h["rule_fired"], run_id, h["brand_slug"]))
                    fetched = []
                    for tid, title in revisit:
                        check(f"inside r/{sub}")
                        tree = d.tree_fresh(tid.replace("t3_", ""))
                        if not isinstance(tree, list) or (isinstance(tree, dict) and "_err" in tree):
                            rec["trees_failed"] += 1      # asked again on the next pass
                            continue
                        docs, _ = tree_docs(tree)
                        fetched.append(tid)
                        for doc in docs:
                            body = doc.get("body") or ""
                            for h in resolver.resolve(body, sub, title):
                                mrows.append((doc["id"], doc.get("doc_type", 1), tid, sid, doc.get("author") or "",
                                              doc.get("created_utc") or 0, doc.get("permalink") or "",
                                              doc.get("score") or 0, body, h["conf"], h["alias"],
                                              h["rule_fired"], run_id, h["brand_slug"]))
                    ins = rej = 0
                    if mrows:
                        ins, rej = d.insert_mentions(cur, mrows)
                    if fetched:
                        cur.execute("UPDATE threads SET tree_fetched_at = now() WHERE id = ANY(%s)", (fetched,))
                    # the watermark moves only after a COMPLETE listing (daily.py's rule)
                    if newest and listing_ok and not capped:
                        d.set_watermark(cur, sub, dt.datetime.fromtimestamp(newest, dt.timezone.utc), len(qual))
                    elif capped:
                        rec["capped_listings"] += 1
                rec["subs_visited"] += 1
                rec["threads_new"] += len(qual)
                rec["mentions_new"] += ins
                rec["mentions_rejected"] += rej
                rec["trees_fetched"] += len(fetched)
            except Stop:
                raise
            except Exception as e:  # noqa: BLE001 - one subreddit's failure must not end the run
                rec["errors"] += 1
                log(f"  !! r/{sub}: {type(e).__name__}: {str(e)[:160]}")
                if db.is_transient(e):
                    raise
            if si % 100 == 0:
                log(f"    {si}/{len(subs)} subreddits, {rec['mentions_new']} new mentions, "
                    f"{rc.stats()['calls'] - calls0} calls, {(time.time() - t0) / 60:.0f} min", flush=True)
    except Stop as s:
        rec["stopped"] = str(s)
        log(f"  collect stopped: {s}")
    rec["reddit_calls"] = rc.stats()["calls"] - calls0
    rec["minutes"] = round((time.time() - t0) / 60, 1)
    return rec
