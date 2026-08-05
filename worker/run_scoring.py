#!/usr/bin/env python3
"""Drive score_category over worker/.cache/scored/*.json into _all_scores.json.

The scorer takes label WORDS; the classifier stores the frozen integer encoding
(0 neu, 1 pos, 2 neg, 3 abstain) because that is what the database column holds.
This is the seam between them, and it is one line rather than two encodings.

The trailing 12-month window is applied HERE rather than at harvest, so widening
it later is a methodology change and a recompute — not a re-crawl.
"""
import datetime, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import score_category, load_categories  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SCORED = os.path.join(HERE, ".cache", "scored")
OUT = os.path.join(HERE, ".cache", "corpus", "_all_scores.json")
WORD = {0: "neu", 1: "pos", 2: "neg", 3: "abstain"}

cats = load_categories()
cutoff = datetime.date.today() - datetime.timedelta(days=365)
all_rows, summary = [], []

for fn in sorted(os.listdir(SCORED)):
    if not fn.endswith(".json"):
        continue
    slug = fn[:-5]
    payload = json.load(open(os.path.join(SCORED, fn)))
    ms = []
    for m in payload["mentions"]:
        ts = m.get("created_utc")
        if not ts:
            continue
        if datetime.datetime.utcfromtimestamp(float(ts)).date() < cutoff:
            continue
        ms.append({**m, "label": WORD.get(m.get("label"), "abstain")})
    if not ms:
        summary.append((slug, 0, 0, 0))
        continue
    rows = score_category(slug, ms, cats)
    for r in rows:
        r.setdefault("category_slug", slug)
    all_rows.extend(rows)
    elig = sum(1 for r in rows if r["eligible"])
    summary.append((slug, len(ms), len(rows), elig))

json.dump({"scores": all_rows}, open(OUT, "w"))
print(f"wrote {OUT} — {len(all_rows)} brand x category rows\n")
for slug, n, brands, elig in summary:
    print(f"  {slug:<24} {n:>6} in-window mentions · {brands:>3} brands · {elig} eligible")

top = sorted([r for r in all_rows if r["eligible"]],
             key=lambda r: -(r["reddit_love_score"] or 0))[:10]
if top:
    print("\n  ranked:")
    for r in top:
        print(f"    {r['brand_slug']:<24} score {r['reddit_love_score']:<4} "
              f"n={r['n']:<5} N_op={r['n_op']:<4} n_eff={r['n_eff']}")
else:
    print("\n  nothing eligible — every brand renders below threshold with its failing test named")
    for r in sorted(all_rows, key=lambda r: -r["n"])[:8]:
        print(f"    {r['brand_slug']:<24} n={r['n']:<5} N_op={r['n_op']:<4} "
              f"n_eff={r['n_eff']:<7} failed {r['failed_test']} "
              f"({r['failed_observed']}/{r['failed_required']})")
