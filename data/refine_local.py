#!/usr/bin/env python3
"""Fix subreddit scoring with word-boundary yield + keyword topicality.

The LLM topicality pass failed (claude -p needs a foreground terminal). This
uses keyword matching against the subreddit description instead — same signal,
deterministic, and the subreddit descriptions are already cached from the
discovery pass.
"""
import csv, json, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".discover-cache")

# ── Category vocabulary for topicality scoring ──────────────────────────────
CATEGORY_TERMS = {
    "crm": ["crm", "customer relationship", "sales pipeline", "lead management", "deal", "prospect"],
    "project-management": ["project management", "task management", "kanban", "sprint", "agile", "scrum", "workflow"],
    "accounting": ["accounting", "bookkeeping", "invoice", "ledger", "tax", "expense", "financial"],
    "hr": ["human resource", "hris", "hr software", "employee", "onboarding", "people ops", "talent"],
    "email-marketing": ["email marketing", "newsletter", "email campaign", "subscriber", "drip", "autoresponder"],
    "marketing-automation": ["marketing automation", "lead nurtur", "marketing platform", "campaign", "lifecycle"],
    "password-managers": ["password manager", "password", "vault", "credential", "2fa", "authentication", "security"],
    "note-taking": ["note taking", "notes app", "knowledge base", "second brain", "wiki", "personal knowledge"],
    "design": ["design tool", "prototyp", "wireframe", "ui design", "graphic design", "illustration", "creative"],
    "video-editing": ["video edit", "video production", "filmmaker", "footage", "post-production", "premiere"],
    "help-desk": ["help desk", "customer support", "ticketing", "support ticket", "service desk", "shared inbox"],
    "erp": ["erp", "enterprise resource", "inventory", "manufacturing", "supply chain", "business process"],
    "business-intelligence": ["business intelligence", "analytics", "data viz", "dashboard", "reporting", "data analysis"],
    "ecommerce": ["ecommerce", "e-commerce", "online store", "shopify", "woocommerce", "online retail", "dropship"],
    "recruiting": ["recruiting", "applicant tracking", "ats", "hiring", "talent acquisition", "candidate"],
    "payroll": ["payroll", "salary", "compensation", "contractor payment", "wages", "pay stub"],
    "cloud-hosting": ["hosting", "cloud", "server", "deploy", "devops", "infrastructure", "vps", "serverless"],
    "team-chat": ["team chat", "collaboration", "messaging", "video call", "slack", "teams", "communication tool"],
    "backup-storage": ["backup", "cloud storage", "file sync", "data protection", "nas", "disaster recovery"],
    "payment-processing": ["payment process", "merchant", "payment gateway", "stripe", "checkout", "transaction", "fintech"],
}

# Subreddits that are NEVER topically relevant regardless of word matches
HARD_EXCLUDE = {
    "bjj", "hardwareswap", "studentloans", "knitting", "lawncare", "boston",
    "valueinvesting", "bisexual", "nfl", "rugbyunion", "worldbuilding",
    "superstonk", "ukrainianconflict", "nmscoordinateexchange",
    "vexillologycirclejerk", "peoplefuckingdying", "citiesskylines",
    "infrastructureporn", "mexico", "soccer", "mma", "fitness",
}


def load_sub_info():
    """Load subreddit descriptions from the discovery cache."""
    out = {}
    for fn in os.listdir(CACHE):
        if fn.startswith("_") or not fn.endswith(".json"):
            continue
        fp = os.path.join(CACHE, fn)
        try:
            d = json.load(open(fp))
            name = d.get("subreddit", fn.replace(".json", ""))
            desc = (d.get("public_description") or "") + " " + (d.get("title") or "")
            out[name.lower()] = desc.lower()
        except Exception:
            pass
    return out


def topicality(sub_name, cat_slug, sub_desc):
    """0.0 / 0.5 / 1.0 — same scale as 13-algorithm.md's T."""
    if sub_name.lower() in HARD_EXCLUDE:
        return 0.0
    terms = CATEGORY_TERMS.get(cat_slug, [])
    if not terms:
        return 0.5
    text = sub_desc + " " + sub_name.lower()
    hits = sum(1 for t in terms if t in text)
    if hits >= 2:
        return 1.0
    if hits == 1:
        return 0.5
    return 0.0


def probe_terms():
    """Per category slug, the SAFE surface forms for word-boundary matching."""
    by_brand = {r["slug"]: r for r in csv.DictReader(open(os.path.join(HERE, "brands.csv")))}
    out = {}
    for a in csv.DictReader(open(os.path.join(HERE, "brand-aliases.csv"))):
        if a["surface_class"] != "SAFE" or a["bare_disabled"] == "True":
            continue
        b = by_brand.get(a["brand_slug"])
        if not b:
            continue
        for slug in [b["primary_category_slug"]] + [
                s for s in (b["also_in_category_slugs"] or "").split(";") if s]:
            out.setdefault(slug, set()).add(a["alias"].lower())
    return {k: sorted(v) for k, v in out.items()}


TERMS = probe_terms()
_re_cache = {}


def matcher(slug):
    if slug in _re_cache:
        return _re_cache[slug]
    terms = TERMS.get(slug, [])
    if not terms:
        _re_cache[slug] = None
        return None
    pat = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
    _re_cache[slug] = re.compile(rf"(?<![a-z0-9])(?:{pat})(?![a-z0-9])", re.I)
    return _re_cache[slug]


def brand_bearing_share(slug, bodies):
    m = matcher(slug)
    if not m or not bodies:
        return 0.0
    return round(sum(1 for b in bodies if m.search(b)) / len(bodies), 4)


def main():
    src = os.path.join(HERE, "category-subreddits.csv")
    rows = list(csv.DictReader(open(src)))
    sub_info = load_sub_info()

    # Load cached comment bodies for word-boundary remeasurement
    bodies_cache = {}
    bodies_dir = os.path.join(CACHE, "bodies")
    if os.path.exists(bodies_dir):
        for fn in os.listdir(bodies_dir):
            if fn.endswith(".json"):
                try:
                    d = json.load(open(os.path.join(bodies_dir, fn)))
                    bodies_cache[fn.replace(".json", "")] = d.get("bodies", [])
                except Exception:
                    pass

    for r in rows:
        sub_low = r["subreddit"].lower()
        # Re-measure with word-boundary matching
        bodies = bodies_cache.get(sub_low, [])
        if bodies:
            share = brand_bearing_share(r["category_slug"], bodies)
            r["brand_bearing_share_substring"] = r["brand_bearing_share"]
            r["brand_bearing_share"] = str(share)
            r["bb_per_hour"] = str(round(float(r["comments_per_hour"] or 0) * share, 4))

        # Topicality from keywords
        desc = sub_info.get(sub_low, "")
        t = topicality(r["subreddit"], r["category_slug"], desc)
        r["topicality"] = str(t)
        r["worth"] = str(round(t * float(r["bb_per_hour"] or 0), 5))

    # is_scoring: top 8 by worth, among scorable AND at least adjacent (T >= 0.5)
    for r in rows:
        r["is_scoring"] = "False"
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)

    for cat, rs in by_cat.items():
        pool = [r for r in rs if r["scorable"] == "True" and float(r["topicality"]) >= 0.5]
        for r in sorted(pool, key=lambda x: -float(x["worth"]))[:8]:
            r["is_scoring"] = "True"

    cols = list(rows[0].keys())
    for c in ("topicality", "worth", "brand_bearing_share_substring"):
        if c not in cols:
            cols.append(c)

    with open(src + ".tmp", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    os.replace(src + ".tmp", src)

    scoring = [r for r in rows if r["is_scoring"] == "True"]
    scoring_cats = sum(1 for rs in by_cat.values()
                       if sum(1 for r in rs if r["is_scoring"] == "True") >= 5)
    print(f"WROTE {src}")
    print(f"  scoring slots: {len(scoring)}")
    print(f"  categories with >=5 scoring subs: {scoring_cats}/20")

    for cat, rs in sorted(by_cat.items()):
        picked = sorted([r for r in rs if r["is_scoring"] == "True"],
                        key=lambda x: -float(x["worth"]))
        if picked:
            print(f"\n  {cat} ({len(picked)} scoring)")
            for r in picked:
                print(f"    r/{r['subreddit']:<26} T={r['topicality']:<4} "
                      f"bb/h={r['bb_per_hour']:<8} worth={r['worth']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
