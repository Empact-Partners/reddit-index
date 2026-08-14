#!/usr/bin/env python3
"""The daily fetch. Runs in a Railway cron container; writes ONLY to Supabase.

Per scoring subreddit, per day:
  1. /r/{sub}/new (limit 100, up to 3 pages while everything is newer than the
     watermark) — content-qualify each post: a brand alias or an owning
     category's noun in title or selftext, not removed, not locked. The
     backfill's `num_comments >= 3` floor is deliberately DROPPED here: a
     fresh thread legitimately has zero comments; the revisit loop catches
     its discussion as it accumulates.
  2. Upsert qualifying threads (num_comments/score refreshed on conflict).
  3. REVISIT: fetch full comment trees for this sub's threads first seen in
     the last 72h (up to 12/day, busiest first). ON CONFLICT DO NOTHING on
     the mentions PK makes a re-fetch free of duplicates while catching the
     comments that arrived since yesterday.
  4. Resolve (rules-only Aho-Corasick, same resolver as the backfill), insert
     mentions verbatim, COMMIT, then advance the watermark — per-sub commits,
     so a mid-run death costs nothing already committed.

Classification, scoring and publishing happen on the Mac (classify_daily.py,
score_db.py) — the LLM engines live there, not here.

Env (Railway): REDDIT_CLIENT_ID/SECRET/USER_AGENT, SUPABASE_DB_PASSWORD,
SUPABASE_PROJECT_REF (or SUPABASE_DB_USER), RI_CACHE=/tmp/ri-cache.
"""
import argparse, csv, datetime, json, os, sys, time, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import reddit_client as rc  # noqa: E402
import db  # noqa: E402
from resolve import Resolver  # noqa: E402
from harvest import CATEGORY_NOUNS, build_alias_re, load_brands, tree_docs  # noqa: E402

CODE_VERSION = "daily-v1"
REVISIT_HOURS = 72
TREES_PER_SUB = 12
RUN_ID = str(uuid.uuid4())


def load_scoring_map():
    """sub -> [category_slug…], scoring rows only."""
    out = {}
    with open(os.path.join(REPO, "data", "category-subreddits.csv")) as f:
        for r in csv.DictReader(f):
            if r.get("is_scoring") == "True":
                out.setdefault(r["subreddit"], []).append(r["category_slug"])
    return out


def ensure_partitions(cur):
    """Monthly partitions for this month and the next. Must run before any
    row for a new month could land in mentions_default — Postgres refuses a
    partition whose range overlaps rows already in the default partition."""
    today = datetime.date.today().replace(day=1)
    for base in (today, (today + datetime.timedelta(days=32)).replace(day=1)):
        nxt = (base + datetime.timedelta(days=32)).replace(day=1)
        name = f"mentions_{base.strftime('%Y_%m')}"
        try:
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF mentions "
                f"FOR VALUES FROM (%s) TO (%s)", (base, nxt))
        except Exception as e:
            print(f"  partition {name}: {e}", flush=True)


def get_watermark(cur, sub):
    cur.execute("SELECT watermark FROM ingest_state WHERE scope=%s AND ym='daily' "
                "AND stage='new_listing' AND code_version=%s", (sub, CODE_VERSION))
    row = cur.fetchone()
    return row[0] if row else None


def set_watermark(cur, sub, wm, n_threads):
    cur.execute(
        "INSERT INTO ingest_state (scope, ym, stage, code_version, watermark, rows, status, finished_at) "
        "VALUES (%s,'daily','new_listing',%s,%s,%s,'ok',now()) "
        "ON CONFLICT (scope, ym, stage, code_version) DO UPDATE SET "
        "watermark=EXCLUDED.watermark, rows=EXCLUDED.rows, status='ok', finished_at=now()",
        (sub, CODE_VERSION, wm, n_threads))


def fetch_new(sub, watermark_ts):
    """Newest posts, watermark-bounded. 100/page, at most 3 pages.

    Returns (posts, ok). ok=False when any page failed: an error response used
    to collapse into an empty page, indistinguishable from a clean end of
    listing, and the caller then advanced the watermark past posts it had
    never seen — a permanent, unrecorded gap (reproduced: a drop on page 2 of
    250 new posts skipped 150 forever, and the next healthy run returned
    nothing because the watermark had moved). The sweep learned this same
    lesson; the daily lane must not repeat it.
    """
    posts, after, ok = [], None, True
    for _ in range(3):
        r = rc.get(f"/r/{sub}/new", {"limit": 100, "raw_json": 1,
                                     **({"after": after} if after else {})},
                   bucket="stream", use_cache=False)
        if "_err" in r:
            ok = False
            break
        kids = r.get("data", {}).get("children", [])
        if not kids:
            break
        page = [k["data"] for k in kids if k.get("kind") == "t3"]
        posts.extend(page)
        oldest = min((p.get("created_utc") or 0) for p in page)
        after = r.get("data", {}).get("after")
        if watermark_ts is None or oldest <= watermark_ts or not after:
            break
    if watermark_ts is not None:
        posts = [p for p in posts if (p.get("created_utc") or 0) > watermark_ts]
    return posts, ok


def content_qualify(p, cat_slugs, alias_re):
    if p.get("removed_by_category") or p.get("locked"):
        return False
    text = f"{p.get('title') or ''}\n{p.get('selftext') or ''}".lower()
    if alias_re and alias_re.search(text):
        return True
    for cs in cat_slugs:
        for noun in CATEGORY_NOUNS.get(cs, []):
            if noun in text:
                return True
    return False


def tree_fresh(post_id):
    return rc.get(f"/comments/{post_id}",
                  {"depth": 6, "limit": 200, "raw_json": 1, "sort": "top"},
                  bucket="stream", use_cache=False)


def insert_mentions(cur, rows):
    """Batch-50 with ON CONFLICT DO NOTHING; bisect to row-by-row if the
    vendor-sub trigger (or anything else) rejects a batch."""
    q = ("INSERT INTO mentions (brand_id, doc_id, doc_type, thread_id, subreddit_id, "
         "author, created_utc, permalink, score, body, match_conf, matched_form, "
         "rule_fired, run_id) "
         "SELECT b.id, %s, %s, %s, %s, %s, to_timestamp(%s), %s, %s, %s, %s, %s, %s, %s "
         "FROM brands b WHERE b.slug = %s "
         "ON CONFLICT (brand_id, doc_id, created_utc) DO NOTHING")
    inserted = rejected = 0
    for i in range(0, len(rows), 50):
        batch = rows[i:i + 50]
        try:
            cur.executemany(q, batch)
            inserted += len(batch)
        except Exception:
            cur.connection.rollback()
            for r in batch:
                try:
                    cur.execute(q, r)
                    cur.connection.commit()
                    inserted += 1
                except Exception as e:
                    cur.connection.rollback()
                    rejected += 1
                    print(f"  reject {r[0]}: {str(e).splitlines()[0][:120]}", flush=True)
    return inserted, rejected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch + qualify + resolve, print counts, write NOTHING")
    ap.add_argument("--only", action="append", help="subreddit; repeatable (testing)")
    args = ap.parse_args()

    mapping = load_scoring_map()
    subs = args.only or sorted(mapping)
    brands = load_brands()
    all_brands = [b for bs in brands.values() for b in bs]
    alias_re = build_alias_re(all_brands)
    resolver = Resolver()

    conn = None if args.dry_run else db.connect()
    sub_ids = {}
    if conn:
        with conn.cursor() as cur:
            ensure_partitions(cur)
            conn.commit()
            cur.execute("SELECT name, id FROM subreddits")
            sub_ids = dict(cur.fetchall())

    t0 = time.time()
    tot_threads = tot_mentions = tot_rejects = 0
    for si, sub in enumerate(subs, 1):
        cat_slugs = mapping.get(sub, [])
        try:
            cur = conn.cursor() if conn else None
            wm = None
            if cur:
                wmv = get_watermark(cur, sub)
                wm = wmv.timestamp() if hasattr(wmv, "timestamp") else (float(wmv) if wmv else None)

            posts, listing_ok = fetch_new(sub, wm)
            qual = [p for p in posts if content_qualify(p, cat_slugs, alias_re)]
            newest = max([p.get("created_utc") or 0 for p in posts], default=wm or 0)

            sid = sub_ids.get(sub)
            if cur and sid and qual:
                cur.executemany(
                    "INSERT INTO threads (id, subreddit_id, link_title, permalink, created_utc, "
                    "num_comments, archived, score, first_seen_at) "
                    "VALUES (%s,%s,%s,%s,to_timestamp(%s),%s,%s,%s,now()) "
                    "ON CONFLICT (id) DO UPDATE SET num_comments=EXCLUDED.num_comments, "
                    "score=EXCLUDED.score",
                    [(f"t3_{p['id']}", sid, (p.get("title") or "")[:500],
                      "https://www.reddit.com" + (p.get("permalink") or ""),
                      p.get("created_utc") or 0, p.get("num_comments") or 0,
                      bool(p.get("archived")), p.get("score") or 0) for p in qual])

            # revisit window
            revisit = []
            if cur and sid:
                cur.execute(
                    "SELECT id, link_title FROM threads WHERE subreddit_id=%s "
                    "AND first_seen_at > now() - make_interval(hours => %s) "
                    "ORDER BY num_comments DESC LIMIT %s", (sid, REVISIT_HOURS, TREES_PER_SUB))
                revisit = cur.fetchall()
            elif args.dry_run:
                revisit = [(f"t3_{p['id']}", p.get("title") or "") for p in qual[:TREES_PER_SUB]]

            mrows = []
            for tid, title in revisit:
                tree = tree_fresh(tid.replace("t3_", ""))
                docs, _t = tree_docs(tree)
                for doc in docs:
                    body = doc.get("body") or ""
                    for h in resolver.resolve(body, sub, title):
                        mrows.append((doc["id"], doc.get("doc_type", 1), tid, sid,
                                      doc.get("author") or "", doc.get("created_utc") or 0,
                                      doc.get("permalink") or "", doc.get("score") or 0,
                                      body, h["conf"], h["alias"], h["rule_fired"],
                                      RUN_ID, h["brand_slug"]))

            ins = rej = 0
            if cur and mrows:
                ins, rej = insert_mentions(cur, mrows)
            if cur:
                # Only advance the watermark when the listing was COMPLETE.
                # Advancing after a partial fetch buries every post the
                # failed pages would have carried: the next run starts above
                # them and they are unreachable forever.
                if newest and listing_ok:
                    set_watermark(cur, sub, datetime.datetime.fromtimestamp(
                        newest, datetime.timezone.utc), len(qual))
                elif not listing_ok:
                    print(f"  {sub}: listing incomplete — watermark held", flush=True)
                conn.commit()
                cur.close()
            tot_threads += len(qual)
            tot_mentions += ins if cur else len(mrows)
            tot_rejects += rej
            if args.dry_run or len(qual) or mrows:
                print(f"[{si}/{len(subs)}] r/{sub}: {len(posts)} new, {len(qual)} qualify, "
                      f"{len(revisit)} trees, {len(mrows)} mentions", flush=True)
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"!! r/{sub}: {type(e).__name__}: {e}", flush=True)

    if conn:
        with conn.cursor() as cur:
            set_watermark(cur, "_run", datetime.datetime.now(datetime.timezone.utc), tot_threads)
            conn.commit()
        conn.close()
    s = rc.stats()
    print(f"\nDONE — {tot_threads} threads, {tot_mentions} mentions "
          f"({tot_rejects} rejected), {s['calls']} calls in "
          f"{(time.time() - t0) / 60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
