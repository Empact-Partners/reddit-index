#!/usr/bin/env python3
"""Pick the CORE scoring subreddits per category — the ones that actually
carry the category's product conversation — and mark them `is_core`.

Why this exists: qualification (discover_v2) answers "could this subreddit
legitimately carry brand talk for this category". That is the right question
for MEMBERSHIP and it produced 9,053 qualifying slots. It is the wrong
question for FETCH ORDER, because a qualifying-but-diluted community
(r/smallbusiness is a legitimate adjacent sub for forty categories) returns
far less per call than the community that IS the category. Sweeping all
2,029 subs at 90-day depth measured out at ~800k threads / ~10 days; the
tail of that is where the thin data lives.

`is_scoring` is NOT touched. Methodology 2.0.1 (all_qualifying) still governs
which subreddits COUNT; this only governs which get fetched first, so the
remaining tail can be swept later without any methodology change.

Ranking, per (category, subreddit), from signals already measured:
  topicality   1.0 = the community IS the category or the work that uses it
                     daily; 0.5 = adjacent. The dominant discriminator.
  evidence     threads actually observed carrying this category's brands or
               nouns in the sitewide search (Angle B) — direct evidence, not
               opinion.
  density      bb_per_hour = measured brand-bearing comments per hour, the
               "yield per call" 13-algorithm.md asks for.
  type_tag     dedicated/profession outrank industry/adjacent — the depth
               plan's whole thesis is that practitioners talk shop in their
               PROFESSION sub.
Evidence and density are converted to WITHIN-CATEGORY percentile ranks before
combining, because their raw scales differ by orders of magnitude across
categories.

    python3 data/select_core_subs.py --budget 80000 [--min 8] [--max 22] [--apply]
"""
import argparse
import collections
import csv
import glob
import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CSV_PATH = os.path.join(HERE, "category-subreddits.csv")
STATE = os.path.join(REPO, "worker", ".cache", "sweep")

# threads-per-sub estimate by measured comments/hour, from the live run
BUCKETS = [(0, 0.5, 43), (0.5, 2, 131), (2, 8, 300), (8, 30, 235), (30, 1e9, 900)]
TYPE_BONUS = {"dedicated": 0.25, "profession": 0.20, "selfhosted": 0.10,
              "industry": 0.05, "v1": 0.05, "adjacent": 0.0, "": 0.0}


def num(r, k, d=0.0):
    try:
        return float(r.get(k) or d)
    except (TypeError, ValueError):
        return d


def est_threads(cph, cap):
    for lo, hi, est in BUCKETS:
        if lo <= cph < hi:
            return min(est, cap)
    return min(BUCKETS[-1][2], cap)


def observed_threads():
    out = {}
    for fp in glob.glob(os.path.join(STATE, "*.json")):
        try:
            st = json.load(open(fp))
        except Exception:
            continue
        if st.get("listings_done"):
            out[os.path.basename(fp)[:-5]] = len(st.get("post_ids", []))
    return out


def ranks(values):
    """percentile rank in [0,1]; ties share the average rank"""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        r = (i + j) / 2.0 / max(len(values) - 1, 1)
        for k in range(i, j + 1):
            out[order[k]] = r
        i = j + 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=80000,
                    help="target total threads to fetch")
    ap.add_argument("--min", type=int, default=8, dest="min_subs")
    ap.add_argument("--max", type=int, default=22, dest="max_subs")
    ap.add_argument("--tree-cap", type=int, default=500,
                    help="threads counted per sub (the sweep takes the richest first)")
    ap.add_argument("--apply", action="store_true", help="write is_core to the CSV")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(CSV_PATH)))
    obs = observed_threads()
    by_cat = collections.defaultdict(list)
    for r in rows:
        if r.get("is_scoring") == "True":
            by_cat[r["category_slug"]].append(r)

    scored = {}
    for slug, rs in by_cat.items():
        ev = [math.log1p(num(r, "evidence_count")) for r in rs]
        bb = [math.log1p(num(r, "bb_per_hour")) for r in rs]
        r_ev, r_bb = ranks(ev), ranks(bb)
        out = []
        for i, r in enumerate(rs):
            t = num(r, "topicality_v2") or num(r, "topicality")
            base = 0.45 * r_ev[i] + 0.35 * r_bb[i] + TYPE_BONUS.get(r.get("type_tag", ""), 0.0)
            # topicality is the discriminator, not a tiebreak: an adjacent
            # community is worth materially less per call than the category's
            # own, however busy it is
            score = base * (1.0 if t >= 1.0 else 0.55)
            out.append((score, r))
        out.sort(key=lambda x: -x[0])
        scored[slug] = out

    # A subreddit shared by several categories is SWEPT ONCE and credited to
    # all of them, so cost is per unique subreddit, never per category slot.
    swept_subs = set()

    def cost_of(r):
        sub = r["subreddit"].lower()
        if sub in swept_subs:
            return 0
        return obs.get(sub, est_threads(num(r, "comments_per_hour"), args.tree_cap))

    def take(slug, r):
        chosen.add((slug, r["subreddit"].lower()))
        swept_subs.add(r["subreddit"].lower())

    # pass 1: every category gets its floor, so no category is starved
    chosen, total = set(), 0
    for slug, out in scored.items():
        for score, r in out[:args.min_subs]:
            if (slug, r["subreddit"].lower()) in chosen:
                continue
            total += cost_of(r)
            take(slug, r)

    # pass 2: spend the remaining budget on the best remaining slots globally
    pool = []
    for slug, out in scored.items():
        for rank, (score, r) in enumerate(out[args.min_subs:args.max_subs]):
            pool.append((score, slug, r))
    pool.sort(key=lambda x: -x[0])
    for score, slug, r in pool:
        if (slug, r["subreddit"].lower()) in chosen:
            continue
        cost = cost_of(r)          # 0 when the sub is already being swept
        if total + cost > args.budget:
            continue
        total += cost
        take(slug, r)

    per_cat = collections.Counter(s for s, _ in chosen)
    uniq = len({sub for _, sub in chosen})
    print(f"core slots {len(chosen)} across {len(per_cat)} categories "
          f"({uniq} unique subreddits, was 2029)")
    print(f"estimated threads {total:,} (budget {args.budget:,}) "
          f"-> ~{total / 56 / 60:.1f} h at 56 trees/min")
    c = sorted(per_cat.values())
    print(f"core subs/category  min {c[0]}  median {statistics.median(c):.0f}  max {c[-1]}")

    thin = [s for s, n in per_cat.items() if n < 5]
    print(f"categories under 5 core subs: {len(thin)} {thin[:6]}")

    for slug in ("crm", "pos", "event-management", "rmm", "accounting"):
        if slug in scored:
            picks = [r["subreddit"] for _, r in scored[slug]
                     if (slug, r["subreddit"].lower()) in chosen][:10]
            print(f"  {slug:18} {', '.join(picks)}")

    if args.apply:
        for r in rows:
            r["is_core"] = str((r["category_slug"], r["subreddit"].lower()) in chosen)
        cols = list(rows[0].keys())
        with open(CSV_PATH + ".tmp", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        os.replace(CSV_PATH + ".tmp", CSV_PATH)
        print(f"\nwrote is_core to {CSV_PATH}")
    else:
        print("\n(dry run — pass --apply to write is_core)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
