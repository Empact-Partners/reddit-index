#!/usr/bin/env python3
"""Lane D harvest: scoped search, thread qualification, comment trees.

Lane D is the workhorse here, and that is a measurement rather than a
preference. Lane B — the live comment stream — yields about 0.58 brand-bearing
comments per API call, because it returns everything a subreddit says and
almost none of it names a product. Lane D returns roughly 5.9 per call, because
a qualified thread is 30% brand-bearing against 0.7% for the raw stream. Ten
times the yield for the same budget.

Lane B still runs, because it is the only lane that reaches TODAY, and Lane D
only reaches what Reddit's search has indexed. Neither is a census: Lane A, the
archive dumps, is the only lane that would be, and it is not running. Every
count this produces is a floor and the methodology says so.

Two corrections to 13-algorithm.md §4, both measured:

  1. `num_comments` is an actively HARMFUL ranking key. A 1,232-comment r/sales
     thread returned 2 brand-bearing comments; a 34-comment r/CRM thread
     returned 12. Big threads are general chatter. It stays a floor, never a
     rank.

  2. "Not archived" as a qualification rule would discard every thread older
     than about six months — which is the entire backfill. Reddit's archiving
     blocks WRITES, not reads. `archived` is recorded, never filtered on.

Usage:
  python3 worker/harvest.py --category crm --depth deep
  python3 worker/harvest.py --all --depth thin
"""
import argparse, csv, json, os, re, sys, time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import reddit_client as rc  # noqa: E402

OUT = os.path.join(HERE, ".cache", "corpus")
os.makedirs(OUT, exist_ok=True)

# ── query grid ──────────────────────────────────────────────────────────────
# Category nouns first, brands second. Reddit's search indexes titles and post
# bodies, not comment text, so the thread that carries "we moved off HubSpot"
# in a reply is reachable only through a question with the CATEGORY noun in its
# title. Brand queries find the head; category queries find the long tail.
INTENT_QUERIES = [
    "{cat}",
    "best {cat}",
    "{cat} recommendation",
    "what {cat} do you use",
    "switched from",
    "alternative to",
]

# Category vocabulary, used for qualification and as a resolution feature.
def _load_nouns():
    """Category vocabulary now lives in data/categories.csv (`nouns`, ;-joined)
    so 100 categories don't mean a 100-entry dict in code. The first noun is
    primary — queries_for() puts it into the intent templates."""
    out = {}
    with open(os.path.join(REPO, "data", "categories.csv")) as f:
        for r in csv.DictReader(f):
            nouns = [n.strip() for n in (r.get("nouns") or "").split(";") if n.strip()]
            out[r["slug"]] = nouns or [r["category"].lower()]
    return out


CATEGORY_NOUNS = _load_nouns()

DEPTHS = {
    # queries per sub, sorts, max threads to fetch trees for
    "deep": {"queries": 15, "trees": 900},
    "thin": {"queries": 8, "trees": 90},
}

SORTS = [("relevance", "year"), ("top", "year"), ("relevance", "all"), ("top", "all")]


def load_mapping():
    p = os.path.join(REPO, "data", "category-subreddits.csv")
    rows = list(csv.DictReader(open(p)))
    by_cat = defaultdict(list)
    for r in rows:
        if r["is_scoring"] == "True":
            by_cat[r["category_slug"]].append(r)
    return by_cat


def load_brands():
    p = os.path.join(REPO, "data", "brands.csv")
    by_cat = defaultdict(list)
    for r in csv.DictReader(open(p)):
        for slug in [r["primary_category_slug"]] + [
                s for s in (r["also_in_category_slugs"] or "").split(";") if s]:
            by_cat[slug].append(r)
    return by_cat


def queries_for(cat_slug, cat_name, brands, cap):
    nouns = CATEGORY_NOUNS.get(cat_slug, [cat_name.lower()])
    qs = [t.format(cat=nouns[0]) for t in INTENT_QUERIES]
    qs += [f'"{n}"' for n in nouns[1:3]]
    # Brand queries at the brand's most precise surface form: a quoted multi-word
    # name or a bare unambiguous one. A high-ambiguity bare token would return
    # the weekday, the herb, or the fluid.
    for b in sorted(brands, key=lambda x: (x["ambiguity_class"] != "low", x["brand"])):
        name = b["brand"]
        qs.append(f'"{name}"' if " " in name else name)
    out, seen = [], set()
    for q in qs:
        k = q.lower()
        if k not in seen:
            seen.add(k)
            out.append(q)
    return out[:cap]


# ── qualification: zero API calls, every field is already in the search result ─
def qualify(t3, cat_slug, alias_re):
    """Returns (ok, score). `num_comments` is a FLOOR, and a weak ranking term."""
    d = t3
    if (d.get("num_comments") or 0) < 3:
        return False, 0.0
    if d.get("removed_by_category"):
        return False, 0.0
    if d.get("locked"):
        return False, 0.0

    title = (d.get("title") or "")
    body = (d.get("selftext") or "")
    nouns = CATEGORY_NOUNS.get(cat_slug, [])
    tl, bl = title.lower(), body.lower()

    alias_title = bool(alias_re and alias_re.search(title))
    noun_title = any(n in tl for n in nouns)
    alias_body = bool(alias_re and alias_re.search(body))
    noun_body = any(n in bl for n in nouns)

    # Brand-bearing OR category-bearing. A thread titled "Looking for a new free
    # password manager" names no brand and is exactly where the opinions are.
    if not (alias_title or noun_title or alias_body or noun_body):
        return False, 0.0

    import math
    score = (3.0 * alias_title + 2.0 * noun_title
             + 1.0 * (alias_body or noun_body)
             + 0.5 * math.log1p(d.get("num_comments") or 0))
    return True, round(score, 3)


def build_alias_re(brands):
    forms = []
    for b in brands:
        if b["ambiguity_class"] == "low":
            forms.append(b["brand"])
        for d in (b["domains"] or "").split(";"):
            if d:
                forms.append(d)
    if not forms:
        return None
    pat = "|".join(re.escape(f) for f in sorted(set(forms), key=len, reverse=True))
    return re.compile(rf"(?<![a-z0-9]){pat}(?![a-z0-9])", re.I)


def flatten_tree(listing, out):
    """Depth-first over the comment listing. `replies` is "" when absent."""
    for child in listing.get("data", {}).get("children", []):
        kind = child.get("kind")
        d = child.get("data", {})
        if kind == "more":
            out["more"] += int(d.get("count") or 0)
            continue
        if kind != "t1":
            continue
        body = d.get("body") or ""
        author = d.get("author") or ""
        if body in ("[deleted]", "[removed]") or author in ("[deleted]",):
            continue
        out["comments"].append({
            "id": "t1_" + d["id"],
            "link_id": d.get("link_id"),
            "subreddit": d.get("subreddit"),
            "author": author,
            "score": d.get("score"),
            "created_utc": d.get("created_utc"),
            "depth": d.get("depth"),
            # Copied from the response, never constructed from a title slug.
            "permalink": d.get("permalink"),
            "body": body,
        })
        replies = d.get("replies")
        if isinstance(replies, dict):
            flatten_tree(replies, out)


REDDIT = "https://www.reddit.com"

# 06-sentiment.md stage 1: automated content is removed BEFORE any polarity is
# assigned. It never was, and measured 4.1% of the corpus (6,645 mentions) —
# AutoModerator rule posts, "I am a bot" footers, submission acknowledgements.
# They are not opinions, they are counted in n, and they inflate the distinct
# author floor that is supposed to prove independent voices.
BOT_AUTHORS = {"automoderator", "[deleted]", "reddit", "sub_doesnt_exist_bot"}
BOT_MARKERS = ("i am a bot", "performed automatically", "beep boop",
               "thank you for your submission", "this action was performed",
               "^(i am a bot")


def is_bot_doc(author, body):
    a = (author or "").strip().lower()
    if a in BOT_AUTHORS or a.endswith("bot") or a.endswith("-bot") or a.endswith("_bot"):
        return True
    b = (body or "").lower()
    return any(m in b for m in BOT_MARKERS)


def _abs(permalink):
    p = permalink or ""
    return p if p.startswith("http") else REDDIT + p


def post_doc(d):
    """The POST itself as a scorable document (doc_type 2), or None.

    THE BODY IS TITLE + SELFTEXT. It used to be selftext alone, and that single
    omission is why the index reads as comments-only:

      * a brand named in the TITLE — the most common place a brand appears on
        Reddit ("Anyone moved off HubSpot?") — resolved to nothing, because the
        title was passed only as context to the resolver and never scanned;
      * a link/image post has an EMPTY selftext, so it produced no document at
        all and its title was never read by anything.

    Callers must not build this shape themselves: tree_docs, sweep.py and
    daily.py all mint post rows and they must agree byte for byte, because the
    mentions primary key is (brand_id, doc_id, created_utc) and the stored body
    is what the site renders.
    """
    author = d.get("author") or ""
    if author in ("", "[deleted]", "[removed]") or author is None:
        return None
    title = (d.get("title") or "").strip()
    selftext = (d.get("selftext") or "").strip()
    if selftext in ("[removed]", "[deleted]"):
        selftext = ""
    body = f"{title}\n\n{selftext}".strip() if selftext else title
    if not body or is_bot_doc(author, body):
        return None
    pid = str(d.get("id") or "")
    if not pid:
        return None
    return {
        "id": pid if pid.startswith("t3_") else f"t3_{pid}",
        "doc_type": 2,
        "author": author,
        "body": body,
        "created_utc": d.get("created_utc"),
        "permalink": _abs(d.get("permalink")),
        "score": d.get("score"),
    }


def tree_docs(tree):
    """Every scorable document in a /comments/{id} response, as (docs, title).

    Comments (doc_type 1) then the post body (doc_type 2), absolute
    permalinks, in exactly the shape the mentions rows are built from.

    This exists because daily.py and sweep.py each open-coded the flattening
    and both got flatten_tree's contract wrong the same way — it takes a DICT
    accumulator and the listing ITSELF, and both passed a list plus
    listing["data"]. The loop body therefore never ran: on a real 435-comment
    thread they extracted ZERO comments and collected post bodies only, which
    is why the sweep's yield looked like ~2 mentions per thread. One helper,
    one contract, both callers.
    """
    docs, title = [], ""
    if not (isinstance(tree, list) and len(tree) == 2):
        return docs, title
    out = {"comments": [], "more": 0}
    flatten_tree(tree[1], out)
    for c in out["comments"]:
        if is_bot_doc(c.get("author"), c.get("body")):
            continue
        docs.append({
            "id": c["id"], "doc_type": 1,
            "author": c.get("author") or "",
            "body": c.get("body") or "",
            "created_utc": c.get("created_utc"),
            "permalink": _abs(c.get("permalink")),
            "score": c.get("score"),
        })
    for k in tree[0].get("data", {}).get("children", []):
        d = k.get("data", {})
        title = d.get("title") or title
        pd = post_doc(d)
        if pd:
            docs.append(pd)
    return docs, title


def harvest_category(cat_slug, cat_name, subs, brands, depth, trees_override=0):
    cfg = dict(DEPTHS[depth])
    if trees_override:
        # More trees on the SAME cached queries: search replays free from disk,
        # only the extra tree fetches spend calls. The lever for topping up a
        # starved category without re-searching anything.
        cfg["trees"] = trees_override
    alias_re = build_alias_re(brands)
    qs = queries_for(cat_slug, cat_name, brands, cfg["queries"])

    threads, seen = {}, set()
    q_log = []
    for sub in subs:
        name = sub["subreddit"]
        for q in qs:
            for sort, window in SORTS:
                r = rc.search_subreddit(name, q, sort=sort, t=window)
                kids = r.get("data", {}).get("children", []) if "_err" not in r else []
                new = 0
                qual = 0
                for k in kids:
                    d = k.get("data", {})
                    tid = d.get("id")
                    if not tid or tid in seen:
                        continue
                    seen.add(tid)
                    new += 1
                    ok, score = qualify(d, cat_slug, alias_re)
                    if ok:
                        qual += 1
                        threads[tid] = {
                            "id": "t3_" + tid,
                            "post_id": tid,
                            "subreddit": d.get("subreddit"),
                            "title": d.get("title"),
                            "selftext": d.get("selftext") or "",
                            "permalink": d.get("permalink"),
                            "created_utc": d.get("created_utc"),
                            "num_comments": d.get("num_comments"),
                            "archived": d.get("archived", False),
                            "score": d.get("score"),
                            "author": d.get("author"),
                            "qual_score": score,
                        }
                q_log.append({"subreddit": name, "q": q, "sort": sort, "window": window,
                              "results_n": len(kids), "unique_new_n": new, "qualifying_n": qual})
        print(f"    r/{name:<24} {len(threads):>5} qualifying threads "
              f"({rc.stats()['calls']} calls)", flush=True)

    # Rank by brand-density prior, stratified so no single subreddit takes more
    # than 35% of the budget — which protects the distinct-subreddits floor from
    # being decided by whichever community happens to be busiest.
    ranked = sorted(threads.values(), key=lambda t: -t["qual_score"])
    cap = cfg["trees"]
    per_sub_cap = max(3, int(cap * 0.35))
    picked, per_sub = [], defaultdict(int)
    for t in ranked:
        if len(picked) >= cap:
            break
        if per_sub[t["subreddit"]] >= per_sub_cap:
            continue
        per_sub[t["subreddit"]] += 1
        picked.append(t)

    print(f"    fetching {len(picked)} comment trees…", flush=True)
    comments, more_total = [], 0
    for i, t in enumerate(picked, 1):
        r = rc.comment_tree(t["post_id"])
        if isinstance(r, dict) and "_err" in r:
            continue
        if not isinstance(r, list) or len(r) < 2:
            continue
        out = {"comments": [], "more": 0}
        flatten_tree(r[1], out)
        for c in out["comments"]:
            c["thread_id"] = t["id"]
            c["link_title"] = t["title"]
        comments.extend(out["comments"])
        more_total += out["more"]
        if i % 100 == 0:
            print(f"      {i}/{len(picked)} trees · {len(comments)} comments "
                  f"· {rc.stats()['calls']} calls", flush=True)

    # Post bodies count as mentions too — same weight, different doc_type.
    posts = [{
        "id": t["id"], "thread_id": t["id"], "subreddit": t["subreddit"],
        "author": t.get("author") or "", "score": t.get("score"),
        "created_utc": t["created_utc"], "permalink": t["permalink"],
        "body": (t["title"] + "\n\n" + t["selftext"]).strip(),
        "link_title": t["title"], "doc_type": 2,
    } for t in picked if (t.get("author") or "") not in ("", "[deleted]")]
    for c in comments:
        c["doc_type"] = 1

    payload = {
        "category_slug": cat_slug,
        "harvested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "depth": depth,
        "queries": qs,
        "threads": picked,
        "documents": posts + comments,
        "coverage_gap_more_branches": more_total,
        "query_log": q_log,
    }
    fp = os.path.join(OUT, f"{cat_slug}.json")
    with open(fp + ".tmp", "w") as f:
        json.dump(payload, f)
    os.replace(fp + ".tmp", fp)
    print(f"    -> {len(picked)} threads, {len(payload['documents'])} documents, "
          f"{more_total} comments left behind in `more` branches\n", flush=True)
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", action="append", help="category slug; repeatable")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--depth", default="thin", choices=list(DEPTHS))
    ap.add_argument("--force", action="store_true", help="re-harvest categories already on disk")
    ap.add_argument("--deep-category", default=None,
                    help="one category to harvest at depth=deep while the rest run thin")
    ap.add_argument("--trees", type=int, default=0,
                    help="override the depth's tree-fetch cap (search stays cached)")
    args = ap.parse_args()

    mapping = load_mapping()
    brands = load_brands()
    cats = {r["slug"]: r["category"] for r in
            csv.DictReader(open(os.path.join(REPO, "data", "categories.csv")))}

    targets = list(cats) if args.all else (args.category or [])
    if not targets:
        ap.error("pass --category SLUG or --all")

    for slug in targets:
        subs = mapping.get(slug, [])
        if not subs:
            print(f"!! {slug}: no scoring subreddits, skipping\n")
            continue
        depth = "deep" if slug == args.deep_category else args.depth
        out_fp = os.path.join(OUT, f"{slug}.json")
        if os.path.exists(out_fp) and not args.force:
            print(f"=== {cats[slug]} ({slug}) — already harvested, skipping")
            continue
        print(f"=== {cats[slug]} ({slug}) — {len(subs)} scoring subreddits, depth={depth}")
        try:
            harvest_category(slug, cats[slug], subs, brands.get(slug, []), depth, args.trees)
        except Exception as e:
            # Disk is the source of truth and every response is already cached,
            # so a category that dies costs its parse, not its calls. Losing the
            # remaining nineteen to one blip is the expensive failure.
            print(f"!! {slug} failed: {type(e).__name__}: {e}\n", flush=True)

    s = rc.stats()
    print(f"\nDONE — {s['calls']} API calls, {s['cached']} cache hits, "
          f"{s['errors']} errors, {s['calls_per_min']} calls/min over {s['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
