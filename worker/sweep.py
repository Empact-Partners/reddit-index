#!/usr/bin/env python3
"""The sweep — every qualifying thread per scoring subreddit.

Two modes:

LEGACY (no --days): the original all-time pass — /new + /top t=all|year|month,
num_comments >= 3, low-ambiguity alias regex qualification. Unchanged.

90-DAY (--days N, docs/depth-execution-plan.md Stage 3): /new paginated until
posts age past the cutoff — that alone fully covers any sub under ~11
posts/day. Subs whose /new listing cap is younger than the cutoff are marked
coverage="approximate" and get supplements: /top t=month + t=year
(client-filtered) plus per-noun scoped search. Qualification uses the FULL
alias automaton (Resolver.has_alias) — a false qualify costs one tree fetch,
a false reject drops a thread forever; extraction still runs the gated
resolve() so junk threads yield nothing. num_comments >= 2.

  1. LISTINGS — per mode, deduped by post id.
  2. QUALIFY — brand surface form or owning-category noun in title/selftext,
     not removed, not locked, comment floor per mode.
  3. TREES — one comment-tree fetch (limit 500) per qualifying thread,
     resolve with the full gazetteer, insert mentions, upsert the thread row.
  4. STATE — .cache/sweep/<sub>.json v2: mode (days/cutoff/matcher) recorded
     so a resume never mixes modes; listing errors and failed trees recorded
     so a rate-limited fetch is retried, never silently marked complete.

Disk is the source of truth: kill at any point and re-running fills exactly
the gaps. A tree re-fetch is harmless (mentions PK is ON CONFLICT DO NOTHING).
Classification is deliberately NOT here — classify_daily (nightly, capped)
plus supervised burns drain the backlog.

Usage:
    python3 worker/sweep.py --days 90 --only r1,r2   # pilot
    python3 worker/sweep.py --days 90                # Stage 3 (via depth_run)
    python3 worker/sweep.py                          # legacy all-time
    python3 worker/sweep.py --status [--days 90]
"""
import argparse, csv, datetime, json, os, sys, time, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import reddit_client as rc  # noqa: E402
import db  # noqa: E402
from resolve import Resolver  # noqa: E402
from harvest import build_alias_re, load_brands, flatten_tree, CATEGORY_NOUNS  # noqa: E402
from daily import (  # noqa: E402
    load_scoring_map, ensure_partitions, content_qualify, insert_mentions,
)

CODE_VERSION = "sweep-v2"
RUN_ID = str(uuid.uuid4())
PAGES = 10               # per listing lane (Reddit stops around 1000 anyway)
MIN_COMMENTS_LEGACY = 3  # the backfill floor for all-time threads
MIN_COMMENTS_DAYS = 2    # depth plan: a thread nobody answered has no opinions
TREE_LIMIT = 500         # one request either way; deeper comment coverage
STATE_DIR = os.path.join(HERE, ".cache", "sweep")
os.makedirs(STATE_DIR, exist_ok=True)


def state_path(sub):
    return os.path.join(STATE_DIR, sub.lower() + ".json")


def mode_key(mode):
    """The STABLE identity of a collection mode.

    Deliberately excludes cutoff_ts: it is recomputed from time.time() on
    every invocation, so comparing whole mode dicts would invalidate every
    state file on every restart and re-run all listings — the opposite of
    resumable. The stored cutoff_ts stays in state as the record of what a
    sub was actually collected against.
    """
    return [mode["days"], mode["min_comments"], mode["matcher"]]


def load_state(sub, mode):
    """State schema v2. A file whose mode differs from the invocation keeps
    its swept set (mentions are ON CONFLICT-safe) but re-runs listings under
    the new mode — this migrates the all-time pilot files in place."""
    try:
        st = json.load(open(state_path(sub)))
    except Exception:
        st = {}
    if st.get("schema") != 2 or mode_key(st.get("mode") or {"days": None,
                                                            "min_comments": None,
                                                            "matcher": None}) != mode_key(mode):
        st = {"schema": 2, "mode": mode, "listings_done": False,
              "coverage": "complete", "new_oldest_ts": None,
              "post_ids": st.get("post_ids", []), "swept": st.get("swept", []),
              "failed_trees": {}, "listing_errors": 0}
    st.setdefault("failed_trees", {})
    st.setdefault("listing_errors", 0)
    st.setdefault("coverage", "complete")
    return st


def save_state(sub, st):
    fp = state_path(sub)
    json.dump(st, open(fp + ".tmp", "w"))
    os.replace(fp + ".tmp", fp)


def fetch_listing(sub, lane, cutoff_ts=None, pages=PAGES, use_cache=False):
    """lane: ('new', None) or ('top', 'all'|'year'|'month').

    Returns (posts, ok, exhausted). ok=False when any page came back _err —
    the caller must NOT mark listings done (the 429-truncation guard).
    exhausted=True when pagination ended by running out (no `after`), not by
    the cutoff — the busy-sub signal for /new.
    """
    kind, t = lane
    posts, after, ok, exhausted = [], None, True, True
    for _ in range(pages):
        params = {"limit": 100, "raw_json": 1, **({"t": t} if t else {}),
                  **({"after": after} if after else {})}
        r = rc.get(f"/r/{sub}/{kind}", params, bucket="sweep", use_cache=use_cache)
        if "_err" in r:
            ok = False
            break
        kids = r.get("data", {}).get("children", [])
        page = [k["data"] for k in kids if k.get("kind") == "t3"]
        if not page:
            break
        posts.extend(page)
        after = r.get("data", {}).get("after")
        if cutoff_ts is not None and kind == "new":
            oldest = min((p.get("created_utc") or 0) for p in page)
            if oldest <= cutoff_ts:
                exhausted = False  # cutoff reached inside the listing = full coverage
                break
        if not after:
            break
    if cutoff_ts is not None:
        posts = [p for p in posts if (p.get("created_utc") or 0) >= cutoff_ts]
    return posts, ok, exhausted


def fetch_search(sub, q, cutoff_ts):
    """Busy-sub supplement: scoped search, newest first, client-filtered.
    Cache bypassed — the `search` bucket holds the one-shot harvest's stale
    pages under identical (path, params) keys."""
    posts, after, ok = [], None, True
    for _ in range(3):
        params = {"q": q, "restrict_sr": 1, "t": "year", "sort": "new",
                  "limit": 100, "raw_json": 1, "include_over_18": "on",
                  **({"after": after} if after else {})}
        r = rc.get(f"/r/{sub}/search", params, bucket="sweep", use_cache=False)
        if "_err" in r:
            ok = False
            break
        page = [k["data"] for k in r.get("data", {}).get("children", [])
                if k.get("kind") == "t3"]
        if not page:
            break
        posts.extend(page)
        after = r.get("data", {}).get("after")
        oldest = min((p.get("created_utc") or 0) for p in page)
        if oldest <= cutoff_ts or not after:
            break
    return [p for p in posts if (p.get("created_utc") or 0) >= cutoff_ts], ok


def sweep_qualify(p, cat_slugs, ctx):
    """Mode-dependent thread qualification."""
    if p.get("removed_by_category") or p.get("locked"):
        return False
    if (p.get("num_comments") or 0) < ctx["min_comments"]:
        return False
    if ctx["days"] is None:
        return content_qualify(p, cat_slugs, ctx["alias_re"])
    if (p.get("created_utc") or 0) < ctx["cutoff_ts"]:
        return False
    text = f"{p.get('title') or ''}\n{p.get('selftext') or ''}".lower()
    if ctx["resolver"].has_alias(text):
        return True
    for cs in cat_slugs:
        for noun in CATEGORY_NOUNS.get(cs, []):
            if noun in text:
                return True
    return False


def collect_listings(sub, cat_slugs, st, ctx):
    """All lanes for the mode. Returns (qualified_posts, ok)."""
    seen, qual, all_ok = set(st["post_ids"]), [], True

    def take(posts):
        for p in posts:
            if p["id"] in seen:
                continue
            seen.add(p["id"])
            if sweep_qualify(p, cat_slugs, ctx):
                qual.append(p)

    if ctx["days"] is None:
        for lane in (("new", None), ("top", "all"), ("top", "year"), ("top", "month")):
            posts, ok, _ = fetch_listing(sub, lane)
            all_ok = all_ok and ok
            take(posts)
        return qual, all_ok

    posts, ok, exhausted = fetch_listing(sub, ("new", None), ctx["cutoff_ts"])
    all_ok = all_ok and ok
    take(posts)
    if posts:
        st["new_oldest_ts"] = min((p.get("created_utc") or 0) for p in posts)
    if ok and exhausted:
        # /new's ~1000-cap is younger than the cutoff: busy sub. Supplement
        # with /top windows + per-noun scoped search; coverage is approximate.
        st["coverage"] = "approximate"
        for lane in (("top", "month"), ("top", "year")):
            posts, ok, _ = fetch_listing(sub, lane, ctx["cutoff_ts"])
            all_ok = all_ok and ok
            take(posts)
        nouns = []
        for cs in cat_slugs:
            nouns.extend(CATEGORY_NOUNS.get(cs, [])[:2])
        for q in dict.fromkeys(nouns):
            posts, ok = fetch_search(sub, q, ctx["cutoff_ts"])
            all_ok = all_ok and ok
            take(posts)
    else:
        st["coverage"] = "complete"
    return qual, all_ok


def sweep_sub(sub, cat_slugs, ctx, tree_cap=10 ** 9):
    conn, sub_ids = ctx["conn"], ctx["sub_ids"]
    st = load_state(sub, ctx["mode"])
    sid = sub_ids.get(sub)
    if sid is None:
        print(f"  {sub}: not in subreddits table, skipped", flush=True)
        return 0, 0

    # ── listings (once per sub; retried while any lane errored) ─────────────
    if not st["listings_done"]:
        qual, ok = collect_listings(sub, cat_slugs, st, ctx)
        with conn.cursor() as cur:
            if qual:
                # first_seen_at backdated for old threads so the sweep does
                # not hijack the daily loop's 72h revisit budget
                cur.executemany(
                    "INSERT INTO threads (id, subreddit_id, link_title, permalink, "
                    "created_utc, num_comments, archived, score, first_seen_at) "
                    "VALUES (%s,%s,%s,%s,to_timestamp(%s),%s,%s,%s, "
                    "CASE WHEN to_timestamp(%s) < now() - interval '72 hours' "
                    "THEN to_timestamp(%s) ELSE now() END) "
                    "ON CONFLICT (id) DO UPDATE SET num_comments=EXCLUDED.num_comments, "
                    "score=EXCLUDED.score",
                    [(f"t3_{p['id']}", sid, (p.get("title") or "")[:500],
                      "https://www.reddit.com" + (p.get("permalink") or ""),
                      p.get("created_utc") or 0, p.get("num_comments") or 0,
                      bool(p.get("archived")), p.get("score") or 0,
                      p.get("created_utc") or 0, p.get("created_utc") or 0)
                     for p in qual])
            conn.commit()
        st["post_ids"] = sorted({p["id"] for p in qual} | set(st["post_ids"]))
        if ok:
            st["listings_done"] = True
        else:
            st["listing_errors"] += 1
            print(f"  {sub}: listing errors — will retry (attempt {st['listing_errors']})",
                  flush=True)
        save_state(sub, st)
        if ok:
            print(f"  {sub}: listings done ({st['coverage']}), "
                  f"{len(st['post_ids'])} qualifying threads", flush=True)

    # ── trees, resumable ─────────────────────────────────────────────────────
    swept = set(st["swept"])
    failed = st["failed_trees"]
    todo = [pid for pid in st["post_ids"]
            if pid not in swept and failed.get(pid, 0) < 3][:tree_cap]
    n_mentions = 0
    # Mentions accumulate across threads and flush at the state checkpoint.
    # A commit per thread costs a Supabase round trip (~200ms from here) on
    # top of the 0.75s API floor — measured 34 trees/min against the ~80/min
    # the rate limit allows, i.e. the pipeline was round-trip bound, not
    # API bound. Flushing on the same boundary as the state save keeps crash
    # recovery consistent: whatever is lost is also not marked swept, and a
    # re-fetch re-inserts it (mentions PK is ON CONFLICT DO NOTHING).
    pending_rows = []

    def flush(force=False):
        nonlocal pending_rows
        if not pending_rows and not force:
            return
        with conn.cursor() as cur:
            insert_mentions(cur, pending_rows)
            conn.commit()
        pending_rows = []

    for i, pid in enumerate(todo, 1):
        tid = f"t3_{pid}"
        tree = rc.get(f"/comments/{pid}",
                      {"depth": 6, "limit": TREE_LIMIT, "raw_json": 1, "sort": "top"},
                      bucket="sweep", use_cache=False)
        if isinstance(tree, dict) and "_err" in tree:
            # a rate-limited tree is NOT swept — recorded and retried (<=3)
            failed[pid] = failed.get(pid, 0) + 1
            continue
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
            for h in ctx["resolver"].resolve(body, sub, title):
                mrows.append((doc["id"], doc.get("doc_type", 1), tid, sid,
                              doc.get("author") or "", doc.get("created_utc") or 0,
                              doc.get("permalink") or "", doc.get("score") or 0,
                              body, h["conf"], h["alias"], h["rule_fired"],
                              RUN_ID, h["brand_slug"]))
        pending_rows.extend(mrows)
        n_mentions += len(mrows)
        swept.add(pid)
        failed.pop(pid, None)
        if i % 20 == 0 or i == len(todo):
            flush()
            st["swept"] = sorted(swept)
            st["failed_trees"] = failed
            save_state(sub, st)
            print(f"  {sub}: {len(swept)}/{len(st['post_ids'])} trees, "
                  f"+{n_mentions} mentions", flush=True)
    flush()
    st["swept"] = sorted(swept)
    st["failed_trees"] = failed
    save_state(sub, st)
    return len(todo), n_mentions


def sub_complete(sub, mode):
    """True when listings finished under THIS mode and every tree is swept
    or given up (3 failures)."""
    try:
        st = json.load(open(state_path(sub)))
    except Exception:
        return False
    if (st.get("schema") != 2 or not st.get("listings_done")
            or mode_key(st.get("mode") or {"days": None, "min_comments": None,
                                           "matcher": None}) != mode_key(mode)):
        return False
    swept = set(st.get("swept", []))
    failed = st.get("failed_trees", {})
    return all(pid in swept or failed.get(pid, 0) >= 3 for pid in st.get("post_ids", []))


def make_mode(days):
    if days is None:
        return {"days": None, "min_comments": MIN_COMMENTS_LEGACY,
                "matcher": "alias-re-v1", "lanes": ["new", "top-all", "top-year", "top-month"]}
    return {"days": days, "cutoff_ts": int(time.time() - days * 86400),
            "min_comments": MIN_COMMENTS_DAYS, "matcher": "automaton-v1",
            "lanes": ["new", "busy-supplements"]}


def prepare(days):
    """Build the shared context once (gazetteer, resolver, DB). The
    orchestrator (depth_run.py) drives run over per-category sub lists."""
    mode = make_mode(days)
    ctx = {"mode": mode, "days": mode["days"],
           "cutoff_ts": mode.get("cutoff_ts"),
           "min_comments": mode["min_comments"], "resolver": Resolver()}
    brands = load_brands()  # {category_slug: [brand rows]}
    ctx["alias_re"] = build_alias_re([b for bs in brands.values() for b in bs])
    ctx["conn"] = db.connect()
    with ctx["conn"].cursor() as cur:
        ensure_partitions(cur)
        ctx["conn"].commit()
        cur.execute("SELECT name, id FROM subreddits")
        ctx["sub_ids"] = dict(cur.fetchall())
    ctx["mapping"] = load_scoring_map()
    return ctx


def run_subs(subs, ctx, tree_cap=10 ** 9):
    """The per-sub loop, reusable in-process. Returns (trees, mentions)."""
    tot_trees = tot_m = 0
    t0 = time.time()
    for i, sub in enumerate(subs, 1):
        try:
            trees, m = sweep_sub(sub, ctx["mapping"].get(sub, []), ctx, tree_cap)
            tot_trees += trees
            tot_m += m
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"  {sub}: ERROR {str(e).splitlines()[0][:160]}", flush=True)
            try:
                ctx["conn"].rollback()
            except Exception:
                ctx["conn"] = db.connect()
        if i % 10 == 0:
            mins = (time.time() - t0) / 60
            print(f"[{i}/{len(subs)}] {tot_trees} trees, {tot_m} mentions, "
                  f"{mins:.0f} min", flush=True)
    return tot_trees, tot_m


def status(subs, mode):
    total_q = total_s = pending_subs = approx = 0
    for sub in subs:
        try:
            st = json.load(open(state_path(sub)))
        except Exception:
            st = {}
        q, s = len(st.get("post_ids", [])), len(st.get("swept", []))
        total_q += q
        total_s += s
        if not sub_complete(sub, mode):
            pending_subs += 1
        if st.get("coverage") == "approximate":
            approx += 1
    print(f"{len(subs)} subs | {total_s}/{total_q} threads swept | "
          f"{pending_subs} subs unfinished | {approx} approximate-coverage")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, help="window in days (Stage 3 = 90); absent = legacy all-time")
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
        return status(subs, make_mode(args.days))

    ctx = prepare(args.days)
    tot_trees, tot_m = run_subs(subs, ctx, args.tree_cap)
    print(f"\nSWEEP PASS DONE: {tot_trees} trees, {tot_m} mentions", flush=True)
    ctx["conn"].close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
