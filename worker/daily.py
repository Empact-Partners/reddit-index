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
import argparse, csv, datetime, json, os, re, sys, time, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import reddit_client as rc  # noqa: E402
import db  # noqa: E402
from resolve import Resolver  # noqa: E402
from harvest import CATEGORY_NOUNS, build_alias_re, load_brands, post_doc, tree_docs  # noqa: E402

CODE_VERSION = "daily-v1"
REVISIT_HOURS = 72
# Trees per subreddit per pass. Raised from 12 the day the revisit queue got a
# memory (threads.tree_fetched_at): with fair ordering, a bigger budget spends
# on threads nobody has read rather than on re-reading the same busiest twelve.
TREES_PER_SUB = int(os.environ.get("RI_TREES_PER_SUB", "24"))
# /new pages per subreddit per pass, 100 posts each. At two passes a day this
# covers a sub publishing up to ~800 posts/day; anything busier reports capped
# and holds its watermark rather than skipping the overflow (see fetch_new).
MAX_PAGES = int(os.environ.get("RI_MAX_PAGES", "4"))
RUN_ID = str(uuid.uuid4())


def load_scoring_map(core_only=False):
    """sub -> [category_slug…], scoring rows only.

    core_only restricts to the CORE set (data/select_core_subs.py): the
    subreddits that actually carry each category's product conversation,
    ranked by topicality, observed brand evidence and measured density. It is
    a FETCH-ORDER filter, not a membership one — `is_scoring` still governs
    what counts, so the tail can be swept later without a methodology change.
    """
    out = {}
    with open(os.path.join(REPO, "data", "category-subreddits.csv")) as f:
        for r in csv.DictReader(f):
            if r.get("is_scoring") != "True":
                continue
            if core_only and r.get("is_core") != "True":
                continue
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


def as_epoch(v):
    """Whatever `ingest_state.watermark` hands back -> epoch seconds, or None.

    `watermark` is a TEXT column. psycopg writes a datetime into it as
    '2026-08-15 10:02:29+00' and reads it back as that STRING, so the old
    `float(wmv) if wmv else None` raised ValueError on EVERY subreddit and the
    whole run collected nothing. It survived its own smoke test because the
    FIRST run reads None (no row yet) and works perfectly; only the second run
    onwards is dead. Cost: 2026-08-16 and 2026-08-17 produced 0 rows.

    Parsing lives here, in one place, so no caller can reintroduce the
    assumption that the column is a number.
    """
    if v is None or v == "":
        return None
    if hasattr(v, "timestamp"):                    # datetime
        return v.timestamp()
    s = str(v).strip()
    try:                                           # a bare epoch, old rows
        return float(s)
    except ValueError:
        pass
    # Postgres renders '2026-08-15 10:02:29+00'; fromisoformat wants
    # '+00:00' before 3.11 and accepts a space separator throughout.
    iso = s.replace(" ", "T", 1)
    if re.search(r"[+-]\d{2}$", iso):
        iso += ":00"
    try:
        return datetime.datetime.fromisoformat(iso).timestamp()
    except ValueError:
        print(f"  unparseable watermark {s!r} — treated as absent", flush=True)
        return None


def get_watermark(cur, sub):
    """Epoch seconds of the newest post this sub has already been read to."""
    cur.execute("SELECT watermark FROM ingest_state WHERE scope=%s AND ym='daily' "
                "AND stage='new_listing' AND code_version=%s", (sub, CODE_VERSION))
    row = cur.fetchone()
    return as_epoch(row[0]) if row else None


def set_watermark(cur, sub, wm, n_threads, status="ok"):
    # The column is TEXT: write ISO-8601 explicitly rather than leaning on
    # psycopg's datetime adaptation, so what goes in is what as_epoch() reads.
    if hasattr(wm, "isoformat"):
        wm = wm.isoformat()
    cur.execute(
        "INSERT INTO ingest_state (scope, ym, stage, code_version, watermark, rows, status, finished_at) "
        "VALUES (%s,'daily','new_listing',%s,%s,%s,%s,now()) "
        "ON CONFLICT (scope, ym, stage, code_version) DO UPDATE SET "
        "watermark=EXCLUDED.watermark, rows=EXCLUDED.rows, status=EXCLUDED.status, "
        "finished_at=now()",
        (sub, CODE_VERSION, wm, n_threads, status))


def fetch_new(sub, watermark_ts):
    """Newest posts, watermark-bounded. 100/page, at most MAX_PAGES pages.

    Returns (posts, ok, capped).

    ok=False when any page failed: an error response used to collapse into an
    empty page, indistinguishable from a clean end of listing, and the caller
    then advanced the watermark past posts it had never seen — a permanent,
    unrecorded gap (reproduced: a drop on page 2 of 250 new posts skipped 150
    forever, and the next healthy run returned nothing because the watermark
    had moved). The sweep learned this same lesson; the daily lane must not
    repeat it.

    capped=True when the page budget ran out BEFORE reaching the watermark —
    the same wound through a different door, and the one this lane actually
    walks into. r/pcmasterrace publishes ~512 posts a day, so a 3-page (300
    post) budget covers 14 hours of a 24-hour gap; the run reported ok, the
    watermark jumped to the newest post, and the ~210 posts below the 300th
    became unreachable for good. Every day. The caller HOLDS the watermark on
    a capped read, so the next pass starts from the same floor and the pages
    are re-walked rather than skipped.
    """
    posts, after, ok, capped = [], None, True, False
    for page_no in range(MAX_PAGES):
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
        if page_no == MAX_PAGES - 1:
            # Budget exhausted with the listing still ahead of the watermark.
            capped = True
    if watermark_ts is not None:
        posts = [p for p in posts if (p.get("created_utc") or 0) > watermark_ts]
    return posts, ok, capped


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
    """Batch-50 with ON CONFLICT DO NOTHING; fall back to row-by-row if the
    vendor-sub trigger (or anything else) rejects a batch.

    EVERY failure is contained in a SAVEPOINT. The first version called
    `cur.connection.rollback()` — a CONNECTION-level rollback — which threw
    away the caller's open transaction: the subreddit's whole `INSERT INTO
    threads` upsert and every batch that had already succeeded. main() then
    advanced the watermark and committed, so a single rejected row silently
    cost a subreddit's entire pass and made the loss permanent. A helper must
    never commit or roll back a transaction it does not own.

    The returned count is REAL insertions (rowcount, which ON CONFLICT DO
    NOTHING reports as 0 for a duplicate), not len(batch). The dead-run
    detector in main() reads this number to decide whether a pass found any
    new evidence at all, and len(batch) made a duplicates-only run look
    productive.
    """
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
            cur.execute("SAVEPOINT ins")
            cur.executemany(q, batch)
            inserted += max(cur.rowcount, 0)
            cur.execute("RELEASE SAVEPOINT ins")
        except Exception:
            cur.execute("ROLLBACK TO SAVEPOINT ins")
            for r in batch:
                try:
                    cur.execute("SAVEPOINT one")
                    cur.execute(q, r)
                    inserted += max(cur.rowcount, 0)
                    cur.execute("RELEASE SAVEPOINT one")
                except Exception as e:
                    cur.execute("ROLLBACK TO SAVEPOINT one")
                    rejected += 1
                    if rejected <= 5:
                        print(f"  reject {r[0]}: {str(e).splitlines()[0][:120]}", flush=True)
    return inserted, rejected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch + qualify + resolve, print counts, write NOTHING")
    ap.add_argument("--only", action="append", help="subreddit; repeatable (testing)")
    ap.add_argument("--core-only", action="store_true",
                    help="the 527 core subreddits only (fast pass)")
    ap.add_argument("--max-minutes", type=float,
                    default=float(os.environ.get("RI_MAX_MINUTES", "0")),
                    help="stop cleanly after N minutes; 0 = no budget")
    args = ap.parse_args()

    mapping = load_scoring_map()
    # CORE FIRST. A pass that runs out of time, dies, or is throttled must have
    # spent what it had on the 527 subreddits that carry the categories, not on
    # the alphabetical head of the 2,029-strong tail. `core` is a fetch-order
    # filter only — is_scoring still governs what counts (load_scoring_map).
    core = set(load_scoring_map(core_only=True))
    subs = args.only or sorted(mapping, key=lambda s: (s not in core, s))
    if args.core_only:
        subs = [s for s in subs if s in core]
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
            # Reddit names are case-preserving but case-INSENSITIVE, and 10,148
            # of the 16,980 stored rows carry capitals (r/CRM, r/SaaS). An exact
            # dict lookup on a name typed in the other case returns None, and
            # every mention for that subreddit is then rejected one by one on a
            # not-null constraint — a whole subreddit lost, loudly enough to
            # scroll past. Fold the key.
            cur.execute("SELECT name, id FROM subreddits")
            sub_ids = {name.lower(): sid for name, sid in cur.fetchall()}

    t0 = time.time()
    tot_threads = tot_mentions = tot_rejects = errors = capped_subs = 0
    stopped_early = None
    for si, sub in enumerate(subs, 1):
        if args.max_minutes and (time.time() - t0) / 60 >= args.max_minutes:
            stopped_early = f"time budget {args.max_minutes:.0f} min reached at sub {si}/{len(subs)}"
            print(f"\n{stopped_early} — stopping cleanly", flush=True)
            break
        cat_slugs = mapping.get(sub, [])
        try:
            cur = conn.cursor() if conn else None
            wm = get_watermark(cur, sub) if cur else None

            posts, listing_ok, capped = fetch_new(sub, wm)
            qual = [p for p in posts if content_qualify(p, cat_slugs, alias_re)]
            newest = max([p.get("created_utc") or 0 for p in posts], default=wm or 0)

            sid = sub_ids.get(sub.lower())
            if cur and sid is None:
                # No row, no foreign key, no mentions. Skipping is right, but
                # it must be VISIBLE: this is a whole subreddit going dark.
                print(f"  r/{sub}: not in the subreddits table — skipped", flush=True)
                errors += 1
                cur.close()
                continue
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

            # REVISIT WINDOW — unread threads first, always.
            #
            # This used to be `ORDER BY num_comments DESC LIMIT 12` with no
            # memory of what had already been fetched. num_comments is
            # refreshed on every pass, so the ordering was stable and the same
            # twelve threads were re-read for three days while the thirteenth
            # aged out of the 72h window having never been read at all. Over
            # 2026-08-10..15 that was 48,171 of 75,511 threads (64%) whose
            # comments were never collected — and comments are 80% of the
            # corpus. NULLS FIRST on tree_fetched_at is the whole fix: nothing
            # is read twice until everything in the window has been read once.
            revisit = []
            if cur and sid:
                cur.execute(
                    "SELECT id, link_title FROM threads WHERE subreddit_id=%s "
                    "AND first_seen_at > now() - make_interval(hours => %s) "
                    "ORDER BY tree_fetched_at NULLS FIRST, num_comments DESC "
                    "LIMIT %s", (sid, REVISIT_HOURS, TREES_PER_SUB))
                revisit = cur.fetchall()
            elif args.dry_run:
                revisit = [(f"t3_{p['id']}", p.get("title") or "") for p in qual[:TREES_PER_SUB]]

            mrows = []

            # 1. The POSTS themselves, resolved straight off the listing we
            #    already hold — zero extra Reddit calls. Without this a post
            #    only ever became a mention if it also won one of the 12 daily
            #    revisit slots, so on any busy subreddit most post mentions
            #    were dropped on the floor while their comments were kept.
            for p in qual:
                doc = post_doc(p)
                if not doc:
                    continue
                body = doc["body"]
                for h in resolver.resolve(body, sub, p.get("title") or ""):
                    mrows.append((doc["id"], 2, doc["id"], sid,
                                  doc["author"], doc.get("created_utc") or 0,
                                  doc.get("permalink") or "", doc.get("score") or 0,
                                  body, h["conf"], h["alias"], h["rule_fired"],
                                  RUN_ID, h["brand_slug"]))

            # 2. The comment trees of recently-seen threads (the post row comes
            #    back too, identical, and lands on ON CONFLICT DO NOTHING).
            fetched = []
            for tid, title in revisit:
                tree = tree_fresh(tid.replace("t3_", ""))
                docs, _t = tree_docs(tree)
                # Mark it read even when the tree came back empty: an empty
                # thread must not hold a slot the rest of the window needs.
                fetched.append(tid)
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
            if cur and fetched:
                cur.execute("UPDATE threads SET tree_fetched_at = now() "
                            "WHERE id = ANY(%s)", (fetched,))
            if cur:
                # Only advance the watermark when the listing was COMPLETE.
                # Advancing after a partial fetch buries every post the
                # failed pages would have carried: the next run starts above
                # them and they are unreachable forever.
                # A capped read is an incomplete read: the pages below the
                # budget were never fetched, so moving the watermark to the
                # newest post would bury them for good.
                if newest and listing_ok and not capped:
                    set_watermark(cur, sub, datetime.datetime.fromtimestamp(
                        newest, datetime.timezone.utc), len(qual))
                elif capped:
                    capped_subs += 1
                    print(f"  r/{sub}: {MAX_PAGES * 100} posts still short of the "
                          f"watermark — held (run more often)", flush=True)
                else:
                    print(f"  r/{sub}: listing incomplete — watermark held", flush=True)
                conn.commit()
                cur.close()
            tot_threads += len(qual)
            tot_mentions += ins if cur else len(mrows)
            tot_rejects += rej
            if args.dry_run or len(qual) or mrows:
                print(f"[{si}/{len(subs)}] r/{sub}: {len(posts)} new, {len(qual)} qualify, "
                      f"{len(revisit)} trees, {len(mrows)} mentions", flush=True)
        except Exception as e:
            errors += 1
            if conn:
                conn.rollback()
            print(f"!! r/{sub}: {type(e).__name__}: {e}", flush=True)

    # A run that raises on every subreddit still printed "DONE" and exited 0,
    # so Railway showed a green cron for two days while the index froze. A pass
    # that mostly threw, or that fetched nothing at all, is a FAILED pass and
    # says so in its exit code and in ingest_state.
    attempted = min(len(subs), si if subs else 0)
    bad = errors > max(20, 0.05 * max(attempted, 1))
    dead = attempted > 50 and tot_threads == 0 and tot_mentions == 0
    status = "error" if (bad or dead) else "ok"

    if conn:
        # `--only` is a TEST invocation. It used to overwrite the global _run
        # marker, so a three-subreddit smoke test made the health check believe
        # a full pass had just finished with 283 threads.
        if not args.only:
            with conn.cursor() as cur:
                set_watermark(cur, "_run", datetime.datetime.now(datetime.timezone.utc),
                              tot_mentions, status=status)
                cur.execute(
                    "INSERT INTO ingest_state (scope, ym, stage, code_version, watermark, "
                    "rows, status, finished_at) VALUES ('_run_coverage','daily','new_listing',"
                    "%s,%s,%s,%s,now()) ON CONFLICT (scope, ym, stage, code_version) "
                    "DO UPDATE SET watermark=EXCLUDED.watermark, rows=EXCLUDED.rows, "
                    "status=EXCLUDED.status, finished_at=now()",
                    (CODE_VERSION,
                     f"{attempted}/{len(subs)} subs · {tot_threads} threads · "
                     f"{errors} errors · {capped_subs} capped",
                     attempted, status))
            conn.commit()
        conn.close()
    s = rc.stats()
    print(f"\nDONE — {tot_threads} threads, {tot_mentions} NEW mentions "
          f"({tot_rejects} rejected), {errors} subreddit errors, {capped_subs} capped "
          f"listings, {s['calls']} calls in {(time.time() - t0) / 60:.1f} min", flush=True)
    if stopped_early:
        print(f"NOTE — {stopped_early}", flush=True)
    if status == "error":
        print(f"FAILED — {errors} of {attempted} subreddits raised"
              if bad else
              f"FAILED — {attempted} subreddits fetched and produced nothing",
              flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
