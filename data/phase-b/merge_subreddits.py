#!/usr/bin/env python3
"""Phase B (decision 0018): merge the partner categories' subreddits into data/category-subreddits.csv.

Every package row becomes a scoring row of its category; a row that exists is switched to scoring and marked; a new
row carries the package's evidence. Two columns are added: `partner_priority` (1 where a partner is AI-cited, where
Empact posts, where a partner was named, or the partner's own subreddit) and `partner_evidence`. `is_core` is NOT
set here: core flags come only from `data/select_core_subs.py --add-categories <slugs>` (never the global mode).
Idempotent: a second run changes nothing.

  python3 data/phase-b/merge_subreddits.py [--dry-run]
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.dirname(HERE)
MAP = os.path.join(DATA, "category-subreddits.csv")


def main() -> int:
    dry = "--dry-run" in sys.argv
    names = {r["slug"]: r["category"] for r in csv.DictReader(open(os.path.join(DATA, "categories.csv")))}
    with open(MAP, newline="") as f:
        rd = csv.DictReader(f)
        cols = list(rd.fieldnames)
        rows = list(rd)
    for c in ("partner_priority", "partner_evidence"):
        if c not in cols:
            cols.append(c)
    at = {(r["category_slug"], r["subreddit"].lower()): r for r in rows}
    pkg = list(csv.DictReader(open(os.path.join(HERE, "category-subreddits-rows.csv"))))
    missing_cat = sorted({p["category_slug"] for p in pkg if p["category_slug"] not in names})
    if missing_cat:
        raise SystemExit(f"categories not in data/categories.csv (run the taxonomy step first): {missing_cat}")
    added = switched = marked = 0
    for p in pkg:
        key = (p["category_slug"], p["subreddit"].lower())
        pp = "1" if str(p.get("partner_priority")) == "1" else "0"
        r = at.get(key)
        if r is None:
            r = {c: "" for c in cols}
            r.update({"category": names[p["category_slug"]], "category_slug": p["category_slug"],
                      "subreddit": p["subreddit"], "status": "ok", "scorable": "True", "is_scoring": "True",
                      "comments_per_hour": p.get("comments_per_hour_est") or "", "source": "empact-partners-2026-10",
                      "partner_priority": pp, "partner_evidence": p.get("evidence") or ""})
            rows.append(r)
            at[key] = r
            added += 1
            continue
        if r.get("is_scoring") != "True":
            r["is_scoring"] = "True"
            switched += 1
        if r.get("partner_priority") != pp or r.get("partner_evidence") != (p.get("evidence") or ""):
            r["partner_priority"], r["partner_evidence"] = pp, p.get("evidence") or ""
            marked += 1
    for r in rows:
        for c in ("partner_priority", "partner_evidence"):
            r.setdefault(c, "")
    print(f"{len(pkg)} package rows: {added} added, {switched} switched to scoring, {marked} marked; "
          f"{sum(1 for p in pkg if str(p.get('partner_priority')) == '1')} with partner priority")
    if not dry:
        tmp = MAP + ".tmp"
        with open(tmp, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, MAP)
    return 0


if __name__ == "__main__":
    sys.exit(main())
