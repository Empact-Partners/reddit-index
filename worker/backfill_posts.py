#!/usr/bin/env python3
"""Re-read every stored thread AS A POST, so titles finally count.

WHY THIS EXISTS
    Until 2026-08-17 the post document was built from `selftext` alone
    (harvest.tree_docs). Two consequences ran through the whole corpus:

      * a brand named only in the TITLE produced no mention — and the title is
        where Reddit puts the brand ("Anyone moved off HubSpot?", "Notion vs
        Obsidian for a small team");
      * a link or image post has an empty selftext, so it produced no document
        at all and nothing ever read its title.

    The collectors are fixed (harvest.post_doc). This repairs the 187k threads
    already on disk, and it is the ONLY way to recover them: the mentions PK is
    (brand_id, doc_id, created_utc), so a post that resolved to nothing simply
    is not there.

HOW
    /api/info takes 100 fullnames per call, so the whole corpus is ~1,900 calls
    (~25 minutes at the client's 80/min ceiling) and returns the live title,
    selftext, author, permalink and score in one shot. For each thread:

      1. rebuild the post document with harvest.post_doc (title + selftext),
      2. resolve it against the same gazetteer the sweep uses,
      3. INSERT the mentions that are missing (ON CONFLICT DO NOTHING),
      4. UPDATE the body of post rows already stored, so an old selftext-only
         row gains its title and the site renders what was actually matched.

    Resumable: progress is a watermark in ingest_state
    (scope='_backfill_posts'), advanced per batch after the commit, so a kill
    costs one batch. Re-running is free — every write is idempotent.

    python3 worker/backfill_posts.py --limit 2000      # pilot
    python3 worker/backfill_posts.py                   # everything, resumable
    python3 worker/backfill_posts.py --restart         # ignore the watermark
"""
import argparse
import datetime
import os
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import db  # noqa: E402
import leases  # noqa: E402
import reddit_client as rc  # noqa: E402
from harvest import post_doc  # noqa: E402
from resolve import Resolver  # noqa: E402

CODE_VERSION = "backfill-posts-v1"
DONE_FP = os.path.join(HERE, ".cache", "backfill_posts.done")
SCOPE = "_backfill_posts"
BATCH = 100                      # /api/info's hard ceiling
RUN_ID = str(uuid.uuid4())

INSERT = (
    "INSERT INTO mentions (brand_id, doc_id, doc_type, thread_id, subreddit_id, "
    "author, created_utc, permalink, score, body, match_conf, matched_form, "
    "rule_fired, run_id) "
    "SELECT b.id, %s, 2, %s, %s, %s, to_timestamp(%s), %s, %s, %s, %s, %s, %s, %s "
    "FROM brands b WHERE b.slug = %s "
    "ON CONFLICT (brand_id, doc_id, created_utc) DO NOTHING")

# The body is per-DOCUMENT, not per-brand, so every row for this doc_id gets the
# same repair. ONE statement per batch, not one per document: a round trip per
# row across the Supavisor pooler ran at ~50/s and would have taken six hours
# for the corpus. created_utc stays in the join so the partition pruner works.
REPAIR = ("UPDATE mentions m SET body = v.body "
          "FROM (VALUES %s) AS v(doc_id, body) "
          "WHERE m.thread_id = v.doc_id AND m.doc_id = v.doc_id AND m.doc_type = 2 "
          "AND m.body IS DISTINCT FROM v.body")
# Keyed on thread_id, which is INDEXED (mentions_thread_id_idx); for a post
# document doc_id IS the thread id, so this is the same rows by a fast path.
# The first cut matched on doc_id + created_utc instead: no index covers
# doc_id, so every batch hash-joined the whole partitioned table and the pilot
# managed ~700 threads in six minutes.


def get_watermark(cur):
    cur.execute("SELECT watermark FROM ingest_state WHERE scope=%s AND ym='backfill' "
                "AND stage='posts' AND code_version=%s", (SCOPE, CODE_VERSION))
    row = cur.fetchone()
    return row[0] if row else ""


def set_watermark(cur, thread_id, rows):
    cur.execute(
        "INSERT INTO ingest_state (scope, ym, stage, code_version, watermark, rows, "
        "status, finished_at) VALUES (%s,'backfill','posts',%s,%s,%s,'ok',now()) "
        "ON CONFLICT (scope, ym, stage, code_version) DO UPDATE SET "
        "watermark=EXCLUDED.watermark, rows=ingest_state.rows + EXCLUDED.rows, "
        "status='ok', finished_at=now()",
        (SCOPE, CODE_VERSION, thread_id, rows))


def page_threads(conn, after, limit):
    """Threads in id order, keyset-paged. Ordering by id (a base-36 fullname)
    is arbitrary but STABLE, which is all a resumable cursor needs.

    Vendor subreddits are excluded HERE, not discovered at insert time. A
    mention from one raises inside reject_vendor_sub_mention() (13-algorithm.md
    §2), which aborts the whole pipelined executemany and drops the batch into
    the row-by-row fallback: 168 round trips at 176 ms across the pooler, and
    the pilot crawled at 100 threads/min. 1,045 of 187,390 threads are affected
    and they may not contribute a mention anyway.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT t.id, s.name, s.id FROM threads t "
            "JOIN subreddits s ON s.id = t.subreddit_id "
            "WHERE t.id > %s AND NOT s.is_vendor_sub ORDER BY t.id LIMIT %s",
            (after, limit))
        return cur.fetchall()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="stop after N threads")
    ap.add_argument("--restart", action="store_true", help="ignore the stored watermark")
    ap.add_argument("--dry-run", action="store_true", help="resolve and count, write nothing")
    args = ap.parse_args()

    # A one-off recovery that must survive a closed laptop: launchd keeps
    # restarting it until it finishes, and this sentinel is what makes each
    # restart free once it has.
    if os.path.exists(DONE_FP) and not args.restart:
        print(f"already complete ({open(DONE_FP).read().strip()}) — nothing to do")
        return 0

    # One backfill at a time: launchd's KeepAlive and a hand-started run must
    # not both walk the same watermark. flock, so a kill frees it immediately.
    lane = leases.Lease("backfill_posts")
    if not lane.acquire():
        print("another backfill holds the lane — exiting")
        return 0

    resolver = Resolver()
    conn = db.connect()
    with conn.cursor() as cur:
        after = "" if args.restart else (get_watermark(cur) or "")
    print(f"backfill_posts: resuming after thread id {after!r}", flush=True)

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM threads WHERE id > %s", (after,))
        remaining = cur.fetchone()[0]
    print(f"{remaining:,} threads to re-read ({remaining / BATCH * 0.75 / 60:.0f} min "
          f"of Reddit calls at the pacing floor)", flush=True)

    t0 = time.time()
    seen = inserted = repaired = gone = no_text = 0
    while True:
        rows = page_threads(conn, after, BATCH)
        if not rows:
            break
        by_id = {tid: (sub, sid) for tid, sub, sid in rows}
        resp = rc.info(list(by_id))
        if "_err" in resp:
            print(f"  /api/info error: {resp['_err']} — retrying in 30s", flush=True)
            time.sleep(30)
            continue

        mrows, repairs = [], []
        for child in resp.get("data", {}).get("children", []):
            d = child.get("data", {})
            tid = d.get("name") or ""            # 't3_abc123'
            sub, sid = by_id.get(tid, (None, None))
            if sid is None:
                continue
            doc = post_doc(d)
            if not doc:
                no_text += 1
                continue
            body = doc["body"]
            repairs.append((body, doc["id"], doc.get("created_utc") or 0, body))
            for h in resolver.resolve(body, sub, d.get("title") or ""):
                mrows.append((doc["id"], doc["id"], sid, doc["author"],
                              doc.get("created_utc") or 0, doc.get("permalink") or "",
                              doc.get("score") or 0, body, h["conf"], h["alias"],
                              h["rule_fired"], RUN_ID, h["brand_slug"]))

        gone += len(by_id) - len(resp.get("data", {}).get("children", []))
        seen += len(by_id)
        after = max(by_id)

        if not args.dry_run:
            with conn.cursor() as cur:
                if mrows:
                    try:
                        cur.executemany(INSERT, mrows)
                        inserted += max(cur.rowcount, 0)
                    except Exception as e:
                        # One poison row must not cost the batch (the NUL-byte
                        # lesson from the classifier): fall back to row by row.
                        conn.rollback()
                        print(f"  batch insert failed ({str(e).splitlines()[0][:90]})"
                              f" — retrying row by row", flush=True)
                        rejects = 0
                        for r in mrows:
                            try:
                                cur.execute("SAVEPOINT row")
                                cur.execute(INSERT, r)
                                inserted += cur.rowcount
                                cur.execute("RELEASE SAVEPOINT row")
                            except Exception as e2:
                                cur.execute("ROLLBACK TO SAVEPOINT row")
                                rejects += 1
                                if rejects <= 3:
                                    print(f"  reject {r[0]} {r[-1]}: "
                                          f"{str(e2).splitlines()[0][:110]}", flush=True)
                        if rejects > 3:
                            print(f"  … {rejects - 3} further rejects in this batch",
                                  flush=True)
                if repairs:
                    try:
                        vals = ", ".join(["(%s, %s)"] * len(repairs))
                        flat = [x for (body, did, _ts, _b2) in repairs
                                for x in (did, body)]
                        cur.execute(REPAIR % vals, flat)
                        repaired += max(cur.rowcount, 0)
                    except Exception as e:
                        conn.rollback()
                        print(f"  repair batch: {str(e).splitlines()[0][:110]}", flush=True)
                set_watermark(cur, after, len(mrows))
                conn.commit()
        else:
            inserted += len(mrows)

        if seen % 1000 == 0 or (args.limit and seen >= args.limit):
            el = max(time.time() - t0, 1)
            print(f"  {seen:,} threads · +{inserted:,} mentions · {repaired:,} bodies "
                  f"repaired · {gone:,} deleted · {seen / el * 60:.0f} threads/min",
                  flush=True)
        if args.limit and seen >= args.limit:
            break

    finished = not args.limit and not args.dry_run
    conn.close()
    lane.release()
    if finished:
        os.makedirs(os.path.dirname(DONE_FP), exist_ok=True)
        with open(DONE_FP, "w") as f:
            f.write(f"completed {time.strftime('%Y-%m-%d %H:%M:%S')} — "
                    f"{seen:,} threads re-read, +{inserted:,} post mentions")
    el = max((time.time() - t0) / 60, 0.01)
    print(f"\nDONE — {seen:,} threads re-read in {el:.1f} min: "
          f"+{inserted:,} post mentions, {repaired:,} bodies repaired, "
          f"{gone:,} deleted on Reddit, {no_text:,} with no attributable text",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
