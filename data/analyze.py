#!/usr/bin/env python3
"""Reddit Index — turn raw probe JSON into the shipped CSVs.

Reads one JSON per measured subreddit (written by probe.py) and produces:

  subreddit-measurements.csv   one row per unique subreddit
  category-tests-20.csv        category rollup, with 95% upper bounds
  categories.csv               gains threshold_tier / precision_target_pp / n_min

Two rules govern scoring eligibility, both from the docs:

  * GENERALIST ONLY. A subreddit named for a vendor or product never scores a
    brand, for cross-brand comparability (14-category-tests.md section 3).
  * HOSTILE SUBS DO NOT SCORE. A sub whose rules ban vendor talk cannot carry an
    unbiased sample of it.

A zero brand-bearing share is never read as absence: one 100-comment page
measures an instant, not a base rate, so every zero carries a rule-of-three
95% upper bound (3/n) instead.
"""
import csv, json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE_DIR = os.environ.get(
    "PROBE_DIR",
    "/private/tmp/claude-501/-Users-vladshvets--claude/f6928dd3-ec32-4042-ab81-563839239aff/scratchpad/probe20")
CAT_JSON = os.environ.get(
    "CAT_JSON",
    "/private/tmp/claude-501/-Users-vladshvets--claude/f6928dd3-ec32-4042-ab81-563839239aff/scratchpad/cat20.json")

HOURS_3Y = 3 * 365 * 24

def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

# A subreddit is vendor-named if its name matches a product or company. Derived
# from the brand gazetteer plus the per-category seed brands rather than a
# hand-maintained regex -- a hand-written list silently missed r/ObsidianMD,
# r/logseq and r/Anytype on the first pass, and a missed vendor sub pollutes the
# rankings without any visible symptom.
EXTRA_VENDORS = [
    # products that appear as subreddit names but are not in the seed gazetteer
    "Obsidian", "ObsidianMD", "Logseq", "Anytype", "OneNote", "Evernote", "Roam Research",
    "Craft Docs", "Monero", "unRAID", "TrueNAS", "QNAP", "MicrosoftFabric", "GoHighLevel",
    "Odoo", "Acumatica", "Epicor", "Penpot", "InVision", "Filmora", "Gorgias", "Kustomer",
    "Mattermost", "Zulip", "Rocket.Chat", "Teamtailor", "JazzHR", "iCIMS", "Brevo",
    "Sendinblue", "Marketo", "Pardot", "Braze", "Duplicati", "Restic", "Hetzner",
]

# Subreddit names that LOOK like a brand but are the generic category term. These
# are never vendor subs even when a brand shares the string.
GENERIC_SUBS = {norm(x) for x in [
    "CRM", "ERP", "Payroll", "Accounting", "NAS", "PasswordManagers", "MarketingAutomation",
    "AutomatedMarketing", "Emailmarketing", "BusinessIntelligence", "ecommerce", "analytics",
    "VideoEditing", "helpdesk", "recruiting", "talentacquisition", "Zettelkasten", "design",
]}

def _vendor_terms():
    terms = set()
    gz = os.path.join(HERE, "brand-gazetteer-seed.csv")
    if os.path.exists(gz):
        with open(gz) as f:
            for row in csv.DictReader(f):
                if row.get("brand"):
                    terms.add(norm(row["brand"]))
                for a in (row.get("aliases") or "").split(";"):
                    if a.strip():
                        terms.add(norm(a))
    try:
        for c in json.load(open(CAT_JSON)):
            for b in c.get("brands", []):
                terms.add(norm(b))
    except Exception:
        pass
    terms |= {norm(x) for x in EXTRA_VENDORS}
    # drop terms too short or too generic to match a subreddit name safely
    return {t for t in terms if len(t) >= 3} - GENERIC_SUBS

VENDOR_TERMS = _vendor_terms()

def _tokens(name):
    """Split a subreddit name into words: camelCase, digits, and separators.
    FigmaDesign -> [figma, design]; Dynamics365 -> [dynamics, 365];
    salesforce_admins -> [salesforce, admins]; Frontend -> [frontend]."""
    parts = re.split(r"[^A-Za-z0-9]+", name or "")
    toks = []
    for p in parts:
        for t in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+|[0-9]+", p):
            toks.append(t.lower())
    return toks

def is_vendor_sub(name):
    """A subreddit is a vendor sub if its name IS a product/company, or contains
    one as a word. Token matching rather than a bare prefix test: a prefix test
    called r/Frontend a vendor sub because the brand 'Front' is a prefix of it."""
    n = norm(name)
    if n in GENERIC_SUBS:
        return False
    if n in VENDOR_TERMS:
        return True
    toks = _tokens(name)
    for t in toks:
        if len(t) >= 4 and t in VENDOR_TERMS and t not in GENERIC_SUBS:
            return True
    # multi-word product names collapse to one token run, e.g. r/ProtonPass
    for i in range(len(toks) - 1):
        if "".join(toks[i:i + 2]) in VENDOR_TERMS:
            return True
    return False

HOSTILE = {"hostile"}

def load():
    recs = {}
    for fn in os.listdir(PROBE_DIR):
        if not fn.endswith(".json"):
            continue
        try:
            r = json.load(open(os.path.join(PROBE_DIR, fn)))
        except Exception:
            continue
        if r.get("subreddit"):
            recs[r["subreddit"].lower()] = r
    return recs

def enrich(r):
    """Per-subreddit derived fields."""
    n = r.get("comment_page_n", 0) or 0
    share = r.get("brand_bearing_share", 0.0) or 0.0
    cph = r.get("comments_per_hour", 0.0) or 0.0
    # rule of three: with 0 hits in n trials the 95% upper bound on the rate is 3/n
    ub95 = round(3.0 / n, 4) if n and share == 0 else round(share, 4)
    r["density_ub95"] = ub95
    r["bb_per_hour"] = round(share * cph, 4)
    r["bb_per_hour_ub95"] = round(ub95 * cph, 4)
    r["is_vendor_sub"] = is_vendor_sub(r["subreddit"])
    r["scorable"] = bool(
        r.get("status") == "ok"
        and not r["is_vendor_sub"]
        and r.get("rule_posture") not in HOSTILE
    )
    return r

# Provisional tier cut points on estimated 3-year brand-bearing volume across a
# category's scorable generalist subs. Round numbers, stated, not fitted -- and
# PROVISIONAL: this study measures category-level comment flow, not per-brand n,
# so Phase 0 must confirm each tier from real per-brand n_eff before publishing.
TIERS = [("deep", 4, 600, 20000), ("standard", 5, 400, 5000), ("thin", 7, 200, 0)]

def tier_for(seed_bb_3y):
    for name, pp, n_min, floor in TIERS:
        if seed_bb_3y >= floor:
            return name, pp, n_min
    return "thin", 7, 200

def main():
    recs = {k: enrich(v) for k, v in load().items()}
    cats = json.load(open(CAT_JSON))

    # ---- subreddit-measurements.csv ----
    cols = ["subreddit", "status", "subscribers", "rule_posture", "is_vendor_sub",
            "comment_page_n", "comments_per_hour", "comment_span_hours",
            "brand_bearing_share", "density_ub95", "bb_per_hour", "scorable",
            "distinct_threads_in_page", "measured_at"]
    rows = sorted(recs.values(), key=lambda r: r["subreddit"].lower())
    with open(os.path.join(HERE, "subreddit-measurements.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})

    # ---- category-tests-20.csv ----
    out = []
    for c in cats:
        subs = [recs.get(s.lower()) for s in c["subreddits"]]
        subs = [s for s in subs if s]
        ok = [s for s in subs if s.get("status") == "ok"]
        vendor = [s for s in ok if s["is_vendor_sub"]]
        hostile = [s for s in ok if not s["is_vendor_sub"] and s.get("rule_posture") in HOSTILE]
        scorable = [s for s in ok if s["scorable"]]
        live = sum(s["bb_per_hour"] for s in scorable)
        live_ub = sum(s["bb_per_hour_ub95"] for s in scorable)
        seed = int(round(live * HOURS_3Y))
        seed_ub = int(round(live_ub * HOURS_3Y))
        tier, pp, n_min = tier_for(seed)
        out.append({
            "category": c["category"], "candidates": len(c["subreddits"]),
            "ok": len(ok), "hostile": len(hostile), "vendor_subs": len(vendor),
            "scorable": len(scorable),
            "live_bb_per_hour": round(live, 2), "live_bb_per_hour_ub95": round(live_ub, 2),
            "seed_bb_3y": seed, "seed_bb_3y_ub95": seed_ub,
            "meets_5_sub_floor": len(scorable) >= 5,
            "threshold_tier": tier, "precision_target_pp": pp, "n_min": n_min,
        })
    with open(os.path.join(HERE, "category-tests-20.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader(); w.writerows(out)

    # ---- merge tiers into categories.csv ----
    cpath = os.path.join(HERE, "categories.csv")
    crows = list(csv.DictReader(open(cpath)))
    by_cat = {o["category"]: o for o in out}
    for r in crows:
        o = by_cat.get(r["category"])
        if o:
            r["threshold_tier"] = o["threshold_tier"]
            r["precision_target_pp"] = o["precision_target_pp"]
            r["n_min"] = o["n_min"]
            r["scorable_subreddits"] = o["scorable"]
            r["meets_5_sub_floor"] = o["meets_5_sub_floor"]
    with open(cpath, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(crows[0]))
        w.writeheader(); w.writerows(crows)

    # ---- report ----
    tot_ok = sum(1 for r in rows if r.get("status") == "ok")
    print(f"unique subreddits measured : {len(rows)}  (ok {tot_ok})")
    print(f"vendor subs                : {sum(1 for r in rows if r['is_vendor_sub'])}")
    print(f"hostile (non-vendor)       : {sum(1 for r in rows if not r['is_vendor_sub'] and r.get('rule_posture') in HOSTILE)}")
    print(f"scorable                   : {sum(1 for r in rows if r['scorable'])}")
    print(f"clear the 5-sub floor      : {sum(1 for o in out if o['meets_5_sub_floor'])} / 20\n")
    w = max(len(o["category"]) for o in out)
    for o in sorted(out, key=lambda x: -x["seed_bb_3y"]):
        flag = "OK " if o["meets_5_sub_floor"] else "-- "
        print(f"{flag}{o['category']:{w}} scorable={o['scorable']:3} "
              f"bb/h={o['live_bb_per_hour']:7} 3y={o['seed_bb_3y']:8} "
              f"tier={o['threshold_tier']:8} n_min={o['n_min']}")

if __name__ == "__main__":
    main()
