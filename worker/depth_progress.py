#!/usr/bin/env python3
"""Read-only progress + projection for the 90-day depth run.

`depth_run.py --status` answers "where is it". This answers "how long", and
it does so from observed data rather than an average, because thread yield
per subreddit spans two orders of magnitude (42 for r/AIMLDiscussion, 2,643
for r/AI_Agents) and a mean over the first few subs is worthless.

Method: every scoring subreddit carries a measured `comments_per_hour` from
discovery. Bucket the subs by that rate, take the MEDIAN observed thread
count within each bucket from the subs already listed, and apply it to the
subs not yet reached. Buckets with no observation fall back to the global
median. The result is reported as a range, and the sample size behind it is
printed so a thin projection is visibly thin.

    python3 worker/depth_progress.py
"""
import csv
import glob
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATE = os.path.join(HERE, ".cache", "sweep")
RUN_FP = os.path.join(HERE, ".cache", "depth", "run.json")
RATE_FP = os.path.join(HERE, ".cache", "depth", "rate.json")

# comments/hour buckets — a proxy for how much a sub posts, which is what
# actually drives thread count in a 90-day window
BUCKETS = [(0, 0.5), (0.5, 2), (2, 8), (8, 30), (30, 1e9)]


def bucket_of(cph):
    for i, (lo, hi) in enumerate(BUCKETS):
        if lo <= cph < hi:
            return i
    return len(BUCKETS) - 1


def load_subs():
    """scoring sub -> comments_per_hour (max across its category rows)."""
    out = {}
    with open(os.path.join(REPO, "data", "category-subreddits.csv")) as f:
        for r in csv.DictReader(f):
            if r.get("is_scoring") != "True":
                continue
            try:
                cph = float(r.get("comments_per_hour") or 0)
            except ValueError:
                cph = 0.0
            out[r["subreddit"]] = max(out.get(r["subreddit"], 0.0), cph)
    return out


def observed():
    """sub_lower -> (threads, swept, listings_done, coverage)."""
    seen = {}
    for fp in glob.glob(os.path.join(STATE, "*.json")):
        try:
            st = json.load(open(fp))
        except Exception:
            continue
        seen[os.path.basename(fp)[:-5]] = (
            len(st.get("post_ids", [])), len(st.get("swept", [])),
            bool(st.get("listings_done")), st.get("coverage", "complete"))
    return seen


def main():
    subs = load_subs()
    seen = observed()
    done_listing = {s: v for s, v in seen.items() if v[2]}
    total_threads = sum(v[0] for v in seen.values())
    total_swept = sum(v[1] for v in seen.values())
    approx = sum(1 for v in seen.values() if v[3] == "approximate")

    # per-bucket median thread yield from the subs already listed
    by_bucket = {}
    for name, cph in subs.items():
        v = done_listing.get(name.lower())
        if v:
            by_bucket.setdefault(bucket_of(cph), []).append(v[0])
    all_obs = [t for v in by_bucket.values() for t in v]
    if not all_obs:
        print("no listed subreddits yet — nothing to project from")
        return 0
    global_med = statistics.median(all_obs)
    med = {b: statistics.median(v) for b, v in by_bucket.items()}

    remaining = 0
    for name, cph in subs.items():
        if name.lower() in done_listing:
            continue
        remaining += med.get(bucket_of(cph), global_med)
    projected_total = total_threads + remaining

    # observed throughput, persisted so a later call measures a real window
    now = time.time()
    prev = None
    if os.path.exists(RATE_FP):
        try:
            prev = json.load(open(RATE_FP))
        except Exception:
            prev = None
    json.dump({"t": now, "swept": total_swept}, open(RATE_FP, "w"))

    print(f"subs listed        {len(done_listing)}/{len(subs)}"
          f"   ({approx} approximate coverage)")
    print(f"threads found      {total_threads:,}")
    print(f"trees swept        {total_swept:,}"
          f"  ({100 * total_swept // max(total_threads, 1)}% of found)")
    print(f"\nprojected total threads   ~{int(projected_total):,}"
          f"   (from {len(all_obs)} listed subs)")
    print("  per-bucket median threads/sub:")
    for b, (lo, hi) in enumerate(BUCKETS):
        n = len(by_bucket.get(b, []))
        label = f"{lo}-{hi if hi < 1e9 else '∞'} c/h"
        if n:
            print(f"    {label:14} median {statistics.median(by_bucket[b]):>7.0f}"
                  f"   (n={n})")
        else:
            print(f"    {label:14} no observation yet -> global {global_med:.0f}")

    if prev and now - prev["t"] > 120:
        rate = (total_swept - prev["swept"]) / (now - prev["t"]) * 60
        if rate > 0:
            left = projected_total - total_swept
            print(f"\nmeasured rate      {rate:.0f} trees/min "
                  f"(over {(now - prev['t']) / 60:.0f} min)")
            print(f"remaining          ~{int(left):,} trees "
                  f"-> ~{left / rate / 60:.0f} h  (~{left / rate / 1440:.1f} days)")
    else:
        print("\n(run again in a few minutes for a measured rate)")

    if os.path.exists(RUN_FP):
        try:
            rs = json.load(open(RUN_FP))
            print(f"\ncategories done    {len(rs.get('done', []))}/100"
                  f"   classified {len(rs.get('classified', []))}"
                  f"   publish_blocked={rs.get('publish_blocked')}")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
