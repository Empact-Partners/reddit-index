#!/usr/bin/env python3
"""Regenerate data/alias-blocklist.csv from the judges' verdicts (2026-10-08).

The blocklist holds (alias, brand) pairs the judges reject almost every time: "uni" is not Uniswap, "workspace" is
not LSEG Workspace, "details" is not Details Flowers Software. Each such pair costs storage, egress and a judgement
for every comment it matches, and the judge throws the result away. worker/resolve.py reads the file and stops
matching the pair.

A pair is added when, over every judged mention of that brand under that exact form:
  rejected >= MIN_REJECTED  and  rejected / (rejected + labelled) >= SHARE
Never added: the brand's own name (a partner must never vanish because its name is also a word); those are printed
for a person instead. Existing rows are kept as they are.

  ops/alias_blocklist.py            # print what would be added
  ops/alias_blocklist.py --write    # add it to data/alias-blocklist.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, d) for d in ("ops", "scripts", "worker")]
FILE = os.path.join(ROOT, "data", "alias-blocklist.csv")
MIN_REJECTED, SHARE = 30, 0.90

SQL = """
with rej as (select m.brand_id, lower(m.matched_form) f, count(*) n from public.mention_rejections r
               join public.mentions m on m.doc_id = r.doc_id and m.brand_id = r.brand_id group by 1, 2),
     lab as (select m.brand_id, lower(m.matched_form) f, count(*) n from public.mention_sentiment s
               join public.mentions m on m.doc_id = s.doc_id and m.brand_id = s.brand_id group by 1, 2)
select b.slug, lower(b.name) as name, r.f as form, r.n as rejected, coalesce(l.n, 0) as labelled
  from rej r left join lab l on l.brand_id = r.brand_id and l.f = r.f
  join public.brands b on b.id = r.brand_id
 where r.n >= %d and r.n >= %f * (r.n + coalesce(l.n, 0))
 order by r.n desc
""" % (MIN_REJECTED, SHARE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    import watch_link as w
    rows = w.query(SQL)
    have = set()
    with open(FILE, newline="") as f:
        existing = list(csv.DictReader(f))
    for r in existing:
        have.add(((r.get("alias") or "").strip().lower(), (r.get("brand_slug") or "").strip()))
    add, held = [], []
    for r in rows:
        pair = (r["form"], r["slug"])
        if pair in have:
            continue
        own = r["form"] in (r["name"], r["slug"].replace("-", " "), r["slug"])
        pct = round(100 * r["rejected"] / (r["rejected"] + r["labelled"]))
        (held if own else add).append({"alias": r["form"], "brand_slug": r["slug"],
                                       "reason": f"judges_reject>={int(SHARE * 100)}pct_n{r['rejected']}",
                                       "rejected_pct": pct})
    for x in add:
        print(f"add   {x['alias']!r:32} -> {x['brand_slug']:40} {x['rejected_pct']}% rejected ({x['reason']})")
    for x in held:
        print(f"HOLD  {x['alias']!r:32} -> {x['brand_slug']:40} {x['rejected_pct']}% rejected: the brand's own name, a person decides")
    print(f"{len(add)} to add, {len(held)} held for a person, {len(existing)} already listed")
    if a.write and add:
        with open(FILE, "a", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=["alias", "brand_slug", "reason", "rejected_pct"])
            for x in add:
                wr.writerow(x)
        print(f"written to {FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
