#!/usr/bin/env python3
"""Build the final is_scoring column from the shipped measurements + topicality.

The shipped `subreddit-measurements.csv` has 232 measured subreddits with
reliable `bb_per_hour` values from a 100-comment-page instrument. The discovery
run found 388 unique subs across 680 slots. For subs IN the shipped file, use
the shipped measurement. For new subs, treat them as bb_per_hour=0 (no data).

Topicality is keyword-based: a subreddit is relevant if its name or the
category's seed list includes it. The HARD_EXCLUDE list catches obvious
false positives the discovery cast a wide net to find.

is_scoring = top 8 per category by bb_per_hour, among scorable subs with T >= 0.5.
"""
import csv, json, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

HARD_EXCLUDE = {
    "bjj", "hardwareswap", "studentloans", "knitting", "lawncare", "boston",
    "valueinvesting", "bisexual", "nfl", "rugbyunion", "worldbuilding",
    "superstonk", "ukrainianconflict", "nmscoordinateexchange",
    "vexillologycirclejerk", "peoplefuckingdying", "citiesskylines",
    "infrastructureporn", "mexico", "soccer", "mma", "fitness",
    "fuckcars", "atheism", "whatsthisplant", "homestead", "somethingimade",
}

# Subreddits that are clearly topical per category from the seed candidates
SEED_SUBS = {}  # populated from category-candidates-20.json below


def load_seeds():
    cands = json.load(open(os.path.join(HERE, "category-candidates-20.json")))
    cats_meta = {r["category"]: r["slug"] for r in
                 csv.DictReader(open(os.path.join(HERE, "categories.csv")))}
    for c in cands:
        slug = cats_meta.get(c["category"])
        if slug:
            SEED_SUBS[slug] = {s.lower() for s in c["subreddits"]}


def topicality(sub_name, cat_slug):
    sub_low = sub_name.lower()
    if sub_low in HARD_EXCLUDE:
        return 0.0
    seeds = SEED_SUBS.get(cat_slug, set())
    if sub_low in seeds:
        return 1.0
    return 0.5  # discovered by search, assumed adjacent


def main():
    load_seeds()

    # Load shipped measurements for bb_per_hour
    shipped = {}
    for r in csv.DictReader(open(os.path.join(HERE, "subreddit-measurements.csv"))):
        shipped[r["subreddit"].lower()] = {
            "bb_per_hour": float(r["bb_per_hour"] or 0),
            "comments_per_hour": float(r["comments_per_hour"] or 0),
            "brand_bearing_share": float(r["brand_bearing_share"] or 0),
        }

    src = os.path.join(HERE, "category-subreddits.csv")
    rows = list(csv.DictReader(open(src)))

    for r in rows:
        sub_low = r["subreddit"].lower()
        s = shipped.get(sub_low)
        if s:
            r["bb_per_hour"] = str(s["bb_per_hour"])
            r["comments_per_hour"] = str(s["comments_per_hour"])
            r["brand_bearing_share"] = str(s["brand_bearing_share"])
        t = topicality(r["subreddit"], r["category_slug"])
        r["topicality"] = str(t)
        r["worth"] = str(round(t * float(r["bb_per_hour"] or 0), 5))

    # is_scoring: top 8 by worth, among scorable AND topical
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
    for c in ("topicality", "worth"):
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

    for cat in sorted(by_cat):
        rs = by_cat[cat]
        picked = sorted([r for r in rs if r["is_scoring"] == "True"],
                        key=lambda x: -float(x["worth"]))
        scorable_n = sum(1 for r in rs if r["scorable"] == "True" and float(r.get("topicality", 0)) >= 0.5)
        if picked:
            print(f"\n  {cat} ({len(picked)} scoring of {scorable_n} eligible)")
            for r in picked[:5]:
                print(f"    r/{r['subreddit']:<26} T={r['topicality']:<4} "
                      f"bb/h={float(r['bb_per_hour']):>8.4f} worth={r['worth']}")
            if len(picked) > 5:
                print(f"    ... and {len(picked)-5} more")


if __name__ == "__main__":
    sys.exit(main())
