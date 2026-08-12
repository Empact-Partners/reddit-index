#!/usr/bin/env python3
"""The historical sweep — docs/depth-plan.md P2, lane 2.

One long, killable, resumable pass over every scoring subreddit that takes
what the one-shot harvest and the /new-only daily loop never took:

  1. LISTINGS — /r/{sub}/new paginated to the listing cap, plus /r/{sub}/top
     at t=all, t=year, t=month (PAGES pages of 100 each), deduped by post id.
  2. QUALIFY — the daily loop's content test (brand alias or owning-category
     noun in title/selftext, not removed, not locked) PLUS num_comments >= 3:
     a years-old thread nobody answered has no opinions in it.
  3. TREES — one comment-tree fetch per qualifying thread, resolve with the
     full gazetteer, insert mentions verbatim, upsert the thread row.
  4. STATE — .cache/sweep/<sub>.json records every thread id already swept
     and whether listings completed. Disk is the source of truth: kill the
     process at any point and re-running fills exactly the gaps. A tree
     re-fetch is also harmless (mentions PK is ON CONFLICT DO NOTHING).

Runs on the Mac (nohup + caffeinate), commits per thread-batch, and leans on
reddit_client's rate discipline. Classification is deliberately NOT here —
the nightly capped classify_daily plus supervised burns drain the backlog.

Usage:
    python3 worker/sweep.py --only r1,r2     # pilot
    python3 worker/sweep.py                  # everything, resumable
    python3 worker/sweep.py --status         # progress from disk state
"""
import argparse, csv, datetime, json, os, sys, time, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import reddit_client as rc  # noqa: E402
import db  # noqa: E402
from resolve import Resolver  # noqa: E402
from harvest import build_alias_re, load_brands, flatten_tree  # noqa: E402
from daily import (  # noqa: E402
    load_scoring_map, ensure_partitions, content_qualify, insert_mentions,
)

CODE_VERSION = "sweep-v1"
RUN_ID = str(uuid.uuid4())
PAGES = 10               # per listing lane (Reddit stops around 1000 anyway)
MIN_COMMENTS = 3         # the backfill floor, restored for historical threads
STATE_DIR = os.path.join(HERE, ".cache", "sweep")
os.makedirs(STATE_DIR, exist_ok=True)


def state_path(sub):
    return os.path.join(STATE_DIR, sub.lower() + ".json")


def load_state(sub):
    try:
        return json.load(open(state_path(sub)))
    except Exception:
        return {"listings_done": False, "post_ids": [], "swept": []}


def save_state(sub, st):
    fp = state_path(sub)
    json.dump(st, open(fp + ".tmp", "w"))
    os.replace(fp + ".tmp", fp)


def fetch_listing(sub, lane):
    """lane: ('new', None) or ('top', 'all'|'year'|'month'). Returns post dicts."""
    kind, t = lane
    posts, after = [], None
    for _ in range(PAGES):
        params = {"limit": 100, "raw_json": 1, **({"t": t} if t else {}),
                  **({"after": after} if after else {})}
        r = rc.get(f"/r/{sub}/{kind}", params, bucket="sweep", use_cache=False)
        kids = r.get("data", {}).get("children", []) if "_err" not in r else []
        if not kids:
            break
        posts.extend(k["data"] for k in kids if k.get("kind") == "t3")
        after = r.get("data", {}).get("after")
        if not after:
            break
    return posts


def sweep_sub(sub, cat_slugs, alias_re, resolver, conn, sub_ids, tree_cap):
    st = load_state(sub)
    sid = sub_ids.get(sub)
    if sid is None:
        print(f"  {sub}: not in subreddits table, skipped", flush=True)
        return 0, 0

    # ── listings (once per sub; the daily loop keeps /new current after) ────
    if not st["listings_done"]:
        seen, qual = set(st["post_ids"]), []
        for lane in (("new", None), ("top", "all"), ("top", "year"), ("top", "month")):
            for p in fetch_listing(sub, lane):
                if p["id"] in seen:
                    continue
                seen.add(p["id"])
                if (p.get("num_comments") or 0) >= MIN_COMMENTS \
                        and content_qualify(p, cat_slugs, alias_re):
                    qual.append(p)
        with conn.cursor() as cur:
            if qual:
                cur.executemany(
                    "INSERT INTO threads (id, subreddit_id, link_title, permalink, "
                    "created_utc, num_comments, archived, score, first_seen_at) "
                    "VALUES (%s,%s,%s,%s,to_timestamp(%s),%s,%s,%s,now()) "
                    "ON CONFLICT (id) DO UPDATE SET num_comments=EXCLUDED.num_comments, "
                    "score=EXCLUDED.score",
                    [(f"t3_{p['id']}", sid, (p.get("title") or "")[:500],
                      "https://www.reddit.com" + (p.get("permalink") or ""),
                      p.get("created_utc") or 0, p.get("num_comments") or 0,
                      bool(p.get("archived")), p.get("score") or 0) for p in qual])
            conn.commit()
        st["post_ids"] = sorted({p["id"] for p in qual} | set(st["post_ids"]))
        st["listings_done"] = True
        save_state(sub, st)
        print(f"  {sub}: listings done, {len(st['post_ids'])} qualifying threads",
              flush=True)

    # ── trees, resumable ─────────────────────────────────────────────────────
    swept = set(st["swept"])
    todo = [pid for pid in st["post_ids"] if pid not in swept][:tree_cap]
    n_mentions = 0
    for i, pid in enumerate(todo, 1):
        tid = f"t3_{pid}"
        tree = rc.get(f"/comments/{pid}",
                      {"depth": 6, "limit": 200, "raw_json": 1, "sort": "top"},
                      bucket="sweep", use_cache=False)
        docs, title = [], ""
        if isinstance(tree, list) and len(tree) == 2:
            flatten_tree(tree[1].get("data", {}), docs)
            for k in tree[0].get("data", {}).get("children", []):
                d = k.get("data", {})
                title = d.get("title") or title
                if d.get("selftext") and d.get("author") not in ("[deleted]", None):
                    docs.append({"id": f"t3_{d['id']}", "doc_type": 2,
                                 "author": d["author"], "body": d["selftext"],
                                 "created_utc": d.get("created_utc"),
                                 "permalink": "https://www.reddit.com" + (d.get("permalink") or ""),
                                 "score": d.get("score")})
        mrows = []
        for doc in docs:
            body = doc.get("body") or ""
            for h in resolver.resolve(body, sub, title):
                mrows.append((doc["id"], doc.get("doc_type", 1), tid, sid,
                              doc.get("author") or "", doc.get("created_utc") or 0,
                              doc.get("permalink") or "", doc.get("score") or 0,
                              body, h["conf"], h["alias"], h["rule_fired"],
                              RUN_ID, h["brand_slug"]))
        with conn.cursor() as cur:
            ins, _rej = insert_mentions(cur, mrows)
            conn.commit()
        n_mentions += len(mrows)
        swept.add(pid)
        if i % 20 == 0 or i == len(todo):
            st["swept"] = sorted(swept)
            save_state(sub, st)
            print(f"  {sub}: {len(swept)}/{len(st['post_ids'])} trees, "
                  f"+{n_mentions} mentions", flush=True)
    st["swept"] = sorted(swept)
    save_state(sub, st)
    return len(todo), n_mentions


def status(subs):
    total_q = total_s = pending_subs = 0
    for sub in subs:
        st = load_state(sub)
        q, s = len(st["post_ids"]), len(st["swept"])
        total_q += q
        total_s += s
        if not st["listings_done"] or s < q:
            pending_subs += 1
    print(f"{len(subs)} subs | {total_s}/{total_q} threads swept | "
          f"{pending_subs} subs unfinished")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated subreddits (pilot)")
    ap.add_argument("--tree-cap", type=int, default=100000,
                    help="max trees per sub this invocation")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    mapping = load_scoring_map()
    subs = sorted(mapping)
    if args.only:
        keep = {s.strip().lower() for s in args.only.split(",")}
        subs = [s for s in subs if s.lower() in keep]

    if args.status:
        return status(subs)

    brands = load_brands()
    alias_re = build_alias_re([b for bs in brands.values() for b in bs])
    resolver = Resolver()

    conn = db.connect()
    with conn.cursor() as cur:
        ensure_partitions(cur)
        conn.commit()
        cur.execute("SELECT name, id FROM subreddits")
        sub_ids = dict(cur.fetchall())

    t0 = time.time()
    tot_trees = tot_m = 0
    for i, sub in enumerate(subs, 1):
        try:
            trees, m = sweep_sub(sub, mapping.get(sub, []), alias_re, resolver,
                                 conn, sub_ids, args.tree_cap)
            tot_trees += trees
            tot_m += m
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"  {sub}: ERROR {str(e).splitlines()[0][:160]}", flush=True)
            try:
                conn.rollback()
            except Exception:
                conn = db.connect()
        if i % 10 == 0:
            mins = (time.time() - t0) / 60
            print(f"[{i}/{len(subs)}] {tot_trees} trees, {tot_m} mentions, "
                  f"{mins:.0f} min", flush=True)
    print(f"\nSWEEP PASS DONE: {tot_trees} trees, {tot_m} mentions, "
          f"{(time.time()-t0)/3600:.1f} h", flush=True)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
