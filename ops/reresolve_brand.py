#!/usr/bin/env python3
"""Re-run today's resolver over one brand's stored mentions and reject the ones it no longer accepts.

A resolver or alias fix only changes what the next collection matches; the mentions already stored keep counting
until they are judged again. This reads the brand's live mentions (not rejected, not taken down), resolves each
stored body with the current data/ files, and writes a row to public.mention_rejections for every document that
no longer resolves to the brand. The brand is then marked for refresh. Nothing is deleted.

  ops/reresolve_brand.py stock-analysis            # what it would reject (dry run)
  ops/reresolve_brand.py stock-analysis --apply    # write the rejections
First used for Stock Analysis, issue 106 (2026-11-20).
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
import db  # noqa: E402
from resolve import Resolver  # noqa: E402

MODEL = "resolver-reresolve"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--reason", default="not this product (re-resolved after a resolver fix)")
    a = ap.parse_args()
    r = Resolver()
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("select id from public.brands where slug = %s", (a.slug,))
    row = cur.fetchone()
    if not row:
        print(f"no brand {a.slug}"); return 2
    bid = row[0]
    # a row whose text lives on another brand's row of the same document (body_from, decision 0019) reads it there
    cur.execute("""select m.doc_id,
                          coalesce(m.body, (select x.body from public.mentions x
                                             where x.doc_id = m.doc_id and x.created_utc = m.created_utc
                                               and x.brand_id = m.body_from)),
                          sr.name, m.matched_form
                     from public.mentions m left join public.subreddits sr on sr.id = m.subreddit_id
                    where m.brand_id = %s
                      and not exists (select 1 from public.mention_rejections x
                                       where x.doc_id = m.doc_id and x.brand_id = m.brand_id)
                      and not exists (select 1 from public.removals d where d.doc_id = m.doc_id)""", (bid,))
    rows = cur.fetchall()
    drop, keep, nobody = [], 0, 0
    for doc_id, body, sub, form in rows:
        if not body:
            nobody += 1; continue
        if any(h["brand_slug"] == a.slug for h in r.resolve(body, subreddit=sub)):
            keep += 1
        else:
            drop.append((doc_id, form))
    print(f"{a.slug}: {len(rows)} live mentions, {keep} still resolve, {len(drop)} no longer do, "
          f"{nobody} without a stored body (left alone)")
    print("  by matched form:", dict(Counter((f or "").lower() for _, f in drop)))
    if a.apply and drop:
        cur.executemany("""insert into public.mention_rejections (doc_id, brand_id, model_version, conf, reason, rejected_at)
                           values (%s, %s, %s, 1.0, %s, now())""", [(d, bid, MODEL, a.reason) for d, _ in drop])
        cur.execute("insert into site.dirty_brand (brand_id) values (%s) on conflict do nothing", (bid,))
        conn.commit()
        print(f"  wrote {len(drop)} rejections; brand marked for refresh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
