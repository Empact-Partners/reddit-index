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
CATEGORY_NOUNS = {
    "crm": ["crm", "pipeline", "deal", "lead", "contact"],
    "project-management": ["project management", "pm tool", "kanban", "sprint", "task"],
    "accounting": ["accounting", "bookkeeping", "invoice", "ledger", "expense"],
    "hr": ["hris", "hr software", "onboarding", "payroll", "people ops"],
    "email-marketing": ["email marketing", "newsletter", "esp", "campaign", "subscriber"],
    "marketing-automation": ["marketing automation", "lead nurture", "drip", "lifecycle"],
    "password-managers": ["password manager", "vault", "passkey", "2fa", "credential"],
    "note-taking": ["note taking", "notes app", "second brain", "knowledge base", "wiki"],
    "design": ["design tool", "prototyping", "wireframe", "ui design", "mockup"],
    "video-editing": ["video editing", "editor", "timeline", "render", "footage"],
    "help-desk": ["help desk", "ticketing", "support tool", "shared inbox", "sla"],
    "erp": ["erp", "inventory", "manufacturing", "supply chain", "gl"],
    "business-intelligence": ["bi tool", "dashboard", "analytics", "data viz", "warehouse"],
    "ecommerce": ["ecommerce platform", "online store", "storefront", "checkout", "cart"],
    "recruiting": ["ats", "applicant tracking", "recruiting software", "hiring", "candidate"],
    "payroll": ["payroll", "paycheck", "contractor payments", "eor", "w2"],
    "cloud-hosting": ["hosting", "deploy", "vps", "serverless", "infrastructure"],
    "team-chat": ["team chat", "collaboration tool", "video call", "huddle", "channels"],
    "backup-storage": ["backup", "cloud storage", "nas", "sync", "restore"],
    "payment-processing": ["payment processor", "merchant account", "gateway", "chargeback", "payouts"],
}

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


def harvest_category(cat_slug, cat_name, subs, brands, depth):
    cfg = DEPTHS[depth]
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
    ap.add_argument("--deep-category", default=None,
                    help="one category to harvest at depth=deep while the rest run thin")
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
        print(f"=== {cats[slug]} ({slug}) — {len(subs)} scoring subreddits, depth={depth}")
        harvest_category(slug, cats[slug], subs, brands.get(slug, []), depth)

    s = rc.stats()
    print(f"\nDONE — {s['calls']} API calls, {s['cached']} cache hits, "
          f"{s['errors']} errors, {s['calls_per_min']} calls/min over {s['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
