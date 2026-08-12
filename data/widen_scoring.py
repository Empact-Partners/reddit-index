#!/usr/bin/env python3
"""P1b of docs/depth-plan.md: widen is_scoring from top-8 to top-12 per
category — a RE-PICK over the already-measured rows of
category-subreddits.csv, using the worth column as shipped.

Deliberately does NOT re-run refine_local.py: that would recompute topicality
from keywords and overwrite the fleet-judged values. Same selection rule the
pipeline shipped with (scorable AND topicality >= 0.5, ranked by worth),
only the cap changes. Median measured scorable pool is 21/category, so the
data for 12 already exists — no Reddit calls, no fleet calls.
"""
import csv, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CAP = 12

src = os.path.join(HERE, "category-subreddits.csv")
rows = list(csv.DictReader(open(src)))

before = defaultdict(int)
for r in rows:
    if r["is_scoring"] == "True":
        before[r["category_slug"]] += 1

by_cat = defaultdict(list)
for r in rows:
    by_cat[r["category_slug"]].append(r)

# MONOTONIC: everything already scoring stays (the shipped selection came
# from the fleet-topicality pass and is not reproducible from the stored
# columns alone — a plain re-pick DROPPED subs in 38 categories, 6 to zero).
# Only ADD from the measured pool, best worth first, up to the cap.
after = {}
for cat, rs in by_cat.items():
    scoring = [r for r in rs if r["is_scoring"] == "True"]
    pool = [r for r in rs
            if r["is_scoring"] != "True"
            and r["scorable"] == "True" and float(r.get("topicality") or 0) >= 0.5]
    room = CAP - len(scoring)
    for r in sorted(pool, key=lambda x: -float(x.get("worth") or 0))[:max(0, room)]:
        r["is_scoring"] = "True"
        scoring.append(r)
    after[cat] = len(scoring)

with open(src + ".tmp", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
os.replace(src + ".tmp", src)

tot_b, tot_a = sum(before.values()), sum(after.values())
print(f"scoring slots {tot_b} -> {tot_a} (cap {CAP})")
grew = sum(1 for c in after if after[c] > before.get(c, 0))
print(f"{grew}/{len(after)} categories widened; "
      f"min {min(after.values())}, max {max(after.values())}")
for c in sorted(after):
    if after[c] < 5:
        print(f"  !! {c}: only {after[c]} scoring subs (viability floor is 5)")
