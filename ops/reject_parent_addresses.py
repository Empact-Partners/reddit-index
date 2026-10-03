#!/usr/bin/env python3
"""Record every stored mention that is only a link to a parent company's web address as "not this product".

The resolver stopped creating these on 2026-10-02 (worker/resolve.py: address_names_product). This applies the
same rule to the mentions already stored: a mention whose matched form is a web address that does not name the
brand (github.com filed under GitHub Actions, google.com under Google Sheets, apple.com under Keynote) gets a
row in public.mention_rejections, unless the text also names the brand, in which case it stays for the
classifier to judge. The rows leave the counts and cards through the same triggers any rejection uses, and
leave the classification queue.

Nothing is deleted from public.mentions. The whole step is undone with one statement:

    delete from public.mention_rejections where model_version = 'rule-parent-address-1';

  ops/reject_parent_addresses.py --dry-run     # count per pair, write nothing
  ops/reject_parent_addresses.py               # apply, one transaction per address/brand pair
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))

MODEL = "rule-parent-address-1"
REASON = "a link to a parent company's web address, not this product"

PAIRS_SQL = """
select lower(m.matched_form) as form, b.id, b.slug, b.name, count(*)
  from public.mentions m join public.brands b on b.id = m.brand_id
 where m.matched_form ~ '^[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'
 group by 1, 2, 3, 4"""

# the comment's text through migration 0019's pointer: a row whose text is held by another row has body NULL
MATCH = """
  from public.mentions m
 where m.brand_id = %(brand)s and lower(m.matched_form) = %(form)s
   and position(lower(%(name)s) in lower(coalesce(m.body, (select k.body from public.mentions k
        where k.doc_id = m.doc_id and k.created_utc = m.created_utc and k.brand_id = m.body_from)))) = 0"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    import db
    import resolve
    t0 = time.time()
    receipt = {"pairs": 0, "rejected": 0, "kept_for_classifier": 0, "dequeued": 0}
    with db.connect() as conn:
        conn.autocommit = True
        conn.execute("set statement_timeout = '30min'")
        pairs = [r for r in conn.execute(PAIRS_SQL).fetchall() if not resolve.address_names_product(r[0], r[2])]
        receipt["pairs"] = len(pairs)
        for i, (form, brand, slug, name, n) in enumerate(sorted(pairs, key=lambda r: -r[4]), 1):
            p = {"brand": brand, "form": form, "name": name, "model": MODEL, "reason": REASON}
            if a.dry_run:
                k = conn.execute("select count(*)" + MATCH, p).fetchone()[0]
                receipt["rejected"] += k
                receipt["kept_for_classifier"] += n - k
                continue
            with conn.transaction():
                k = conn.execute(
                    "insert into public.mention_rejections (doc_id, brand_id, model_version, conf, reason) "
                    "select m.doc_id, m.brand_id, %(model)s, 1.0, %(reason)s" + MATCH +
                    " on conflict (doc_id, brand_id) do nothing", p).rowcount
                d = conn.execute(
                    "delete from public.classify_queue q using public.mention_rejections x "
                    "where x.brand_id = %(brand)s and x.model_version = %(model)s "
                    "and q.brand_id = x.brand_id and q.doc_id = x.doc_id", p).rowcount
            receipt["rejected"] += k
            receipt["kept_for_classifier"] += n - k
            receipt["dequeued"] += d
            if i % 50 == 0 or n > 5000:
                print(f"  {i}/{len(pairs)}  {form} as {slug}: {k} rejected, {d} left the queue", flush=True)
    receipt["seconds"] = round(time.time() - t0)
    receipt["dry_run"] = a.dry_run
    if not a.dry_run:   # a write with a receipt, so scripts/schedule_check.py can tell it from an unknown writer
        with db.connect() as conn:
            conn.autocommit = True
            conn.execute("insert into public.pipeline_runs (run_id, stage, code_version, started_at, finished_at, "
                         "status, notes) values (gen_random_uuid(), 'repair', 'reject-parent-addresses-v1', "
                         "to_timestamp(%s), now(), 'ok', %s)", (t0, json.dumps(receipt)))
    print(json.dumps(receipt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
