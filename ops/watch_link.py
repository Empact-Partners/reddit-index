#!/usr/bin/env python3
"""The organic mentions board's link into the index (decision 0019): mirror its mentions, say which the index holds.

Empact Ops' organic pull (Empact-Partners/empact-ops scripts/sync/organic_pull.py, Vlad's Mac, every 10 minutes) hands
this script the board's mentions as JSON on stdin; it upserts them into `watch.organic_mentions` (migration 0024), tied
to the index's brand by the partner's `index_slug`, and answers, per board record, whether the index's own uniform
collection holds the same document for the same brand. Never the site's tables, never a score, never a persona name.

Through Supabase's Management API (works from a network that blocks the database port). Refuses inside the sweep's
night window (00:00-05:30 UTC). A few kilobytes a run.

  ... | python3 ops/watch_link.py            rows in (a JSON list), {board_id: {"present", "brand"}} out
  python3 ops/watch_link.py --coverage       per partner: mentions on the board, how many the index holds
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
TAG = "$ri_watch_link$"
COLS = (("board_id", "text"), ("partner", "text"), ("index_slug", "text"), ("reddit_id", "text"), ("doc_type", "text"),
        ("subreddit", "text"), ("url", "text"), ("written_at", "timestamptz"), ("found_at", "timestamptz"), ("sentiment", "text"),
        ("mention_type", "text"), ("engagement", "text"), ("replied", "boolean"), ("board_url", "text"))
BATCH = 300


def query(sql: str):
    import investigation_2026_10 as inv
    req = urllib.request.Request(f"https://api.supabase.com/v1/projects/{inv.REF}/database/query", method="POST",
                                 data=json.dumps({"query": sql}).encode(),
                                 headers={"Authorization": "Bearer " + inv._mgmt_token(), "Content-Type": "application/json",
                                          "User-Agent": "Mozilla/5.0"})
    out = json.loads(urllib.request.urlopen(req, timeout=120).read())
    if isinstance(out, dict) and out.get("message"):
        raise RuntimeError(out["message"][:300])
    return out


def upsert_sql(rows: list[dict]) -> str:
    payload = json.dumps([{k: r.get(k) for k, _ in COLS} for r in rows], ensure_ascii=False)
    if TAG in payload:
        raise ValueError("the payload carries the quoting tag")
    spec = ", ".join(f"{k} {t}" for k, t in COLS)
    upd = ", ".join(f"{k} = excluded.{k}" for k, _ in COLS if k not in ("board_id", "index_slug")) + \
        ", brand_id = excluded.brand_id, mirrored_at = now()"
    return f"""
with x as (select * from jsonb_to_recordset({TAG}{payload}{TAG}::jsonb) as x({spec})),
up as (
  insert into watch.organic_mentions (board_id, partner, brand_id, reddit_id, doc_type, subreddit, url, written_at, found_at,
                                      sentiment, mention_type, engagement, replied, board_url)
  select x.board_id, x.partner, b.id, x.reddit_id, x.doc_type, x.subreddit, x.url, x.written_at, x.found_at, x.sentiment,
         x.mention_type, x.engagement, coalesce(x.replied, false), x.board_url
  from x left join public.brands b on b.slug = x.index_slug
  on conflict (board_id) do update set {upd}
  returning board_id, brand_id, reddit_id, written_at)
select up.board_id, b.slug as brand,
       exists (select 1 from public.mentions m where m.brand_id = up.brand_id and m.doc_id = up.reddit_id
               and m.created_utc between up.written_at - interval '1 minute' and up.written_at + interval '1 minute') as in_index
from up left join public.brands b on b.id = up.brand_id"""


def link(rows: list[dict]) -> dict:
    h = dt.datetime.now(dt.timezone.utc).time()
    if h < dt.time(5, 30):
        raise SystemExit("inside the night window (00:00-05:30 UTC): not linking")
    out = {}
    for i in range(0, len(rows), BATCH):
        for r in query(upsert_sql(rows[i:i + BATCH])):
            out[r["board_id"]] = {"present": bool(r["in_index"]), "brand": r["brand"]}
    return out


def coverage() -> list[dict]:
    return query("select partner, count(*) as on_board, count(*) filter (where in_index) as in_index, "
                 "count(*) filter (where brand_id is null) as not_a_brand, max(written_at)::date as newest "
                 "from watch.organic_coverage group by partner order by on_board desc")


def main() -> int:
    if "--coverage" in sys.argv:
        print(json.dumps(coverage(), indent=1, default=str))
        return 0
    rows = json.load(sys.stdin)
    print(json.dumps(link(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
