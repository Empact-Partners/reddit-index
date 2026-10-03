#!/usr/bin/env python3
"""Dump what the NEW read path would serve, for tests/site-parity.test.tsx to compare with the old build.

Writes worker/.cache/parity/site.json (ignored: it carries Reddit document ids and nothing else from Reddit).
Row per company page: the numbers, the subreddit table, score, rank, and the ids of the cards it shows.
`changed_since_rail` marks brands that gained or lost a mention after the old card rail was last refreshed;
for those the old build's cards are expected to differ.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))

SQL = """
with cards as (
  select brand_id, array_agg(doc_id order by doc_id) ids from site.rail_card group by brand_id),
fresh as (
  select m.brand_id, count(*) n from public.mentions m
   where m.loaded_at > (select refreshed_at from public.mention_rail_meta) group by 1)
select s.slug, s.name, s.primary_category_slug, s.pos, s.neg, s.neu, s.unlabelled, s.posts, s.comments,
       s.total_mentions,
       to_char(s.oldest_mention at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"') as oldest_mention,
       s.subreddit_stats, s.page_score, s.page_n_op, s.board_rank, s.board_size, s.rail_size,
       coalesce(c.ids, '{}') as card_ids, coalesce(f.n, 0) > 0 as changed_since_rail
from site.brand_stats s left join cards c using (brand_id) left join fresh f using (brand_id)
"""


def main() -> int:
    import db
    out = os.path.join(ROOT, "worker", ".cache", "parity")
    os.makedirs(out, exist_ok=True)
    with db.connect() as conn:
        conn.autocommit = True
        dirty = conn.execute("select count(*) from site.dirty_brand").fetchone()[0]
        if dirty:
            print(f"{dirty} brands are still dirty: run ops/site_fill.py first"); return 2
        conn.execute("set statement_timeout = '15min'")
        cur = conn.execute(SQL)
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    path = os.path.join(out, "site.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f)
    print(f"{len(rows)} pages -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
