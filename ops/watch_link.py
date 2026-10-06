#!/usr/bin/env python3
"""The organic mentions board's link into the index (decision 0019): mirror its mentions, say which the index holds.

Empact Ops' organic pull (Empact-Partners/empact-ops scripts/sync/organic_pull.py, Vlad's Mac, every 10 minutes) hands
this script the board's mentions as JSON on stdin; it upserts them into `watch.organic_mentions` (migration 0024), tied
to the index's brand by the partner's `index_slug`, and answers, per board record, whether the index's own uniform
collection holds the same document for the same brand. Never the site's tables, never a score, never a persona name.

Through Supabase's Management API (works from a network that blocks the database port). Refuses inside the sweep's
night window (00:00-05:30 UTC). A few kilobytes a run.

  ... | python3 ops/watch_link.py            {"rows": [...], "watched": [...]} in, {board_id: {"present", "brand"}} out
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
        ("mention_type", "text"), ("engagement", "text"), ("replied", "boolean"), ("board_url", "text"),
        # decision 0020: what a public card needs, and whether it may be shown (on the board, not "not about them")
        ("author", "text"), ("body", "text"), ("thread_title", "text"), ("score", "integer"), ("matched_form", "text"),
        ("public", "boolean"))
BATCH = 300


def query(sql: str):
    if dt.datetime.now(dt.timezone.utc).time() < dt.time(5, 30):   # checked before every request, batches included
        raise SystemExit("inside the night window (00:00-05:30 UTC): not querying")
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
    upd = ", ".join(f"{k} = excluded.{k}" for k, _ in COLS if k not in ("board_id", "index_slug", "body", "public")) + \
        ", brand_id = excluded.brand_id, mirrored_at = now()" + \
        ", body = case when watch.organic_mentions.purged_at is null then excluded.body end" + \
        ", public = excluded.public and watch.organic_mentions.purged_at is null"   # a takedown is final
    return f"""
with x as (select * from jsonb_to_recordset({TAG}{payload}{TAG}::jsonb) as x({spec})),
up as (
  insert into watch.organic_mentions (board_id, partner, brand_id, reddit_id, doc_type, subreddit, url, written_at, found_at,
                                      sentiment, mention_type, engagement, replied, board_url, author, body, thread_title,
                                      score, matched_form, public)
  select x.board_id, x.partner, b.id, x.reddit_id, x.doc_type, x.subreddit, x.url, x.written_at, x.found_at, x.sentiment,
         x.mention_type, x.engagement, coalesce(x.replied, false), x.board_url, x.author, x.body, x.thread_title, x.score,
         x.matched_form,
         -- a document the takedown ledger holds is never mirrored as showable again
         coalesce(x.public, false) and not exists (select 1 from public.removals r where r.doc_id = x.reddit_id)
  from x left join public.brands b on b.slug = x.index_slug
  on conflict (board_id) do update set {upd}
  returning board_id, brand_id, reddit_id, written_at)
select up.board_id, b.slug as brand,
       exists (select 1 from public.mentions m where m.brand_id = up.brand_id and m.doc_id = up.reddit_id
               and (up.written_at is null
                    or m.created_utc between up.written_at - interval '1 hour' and up.written_at + interval '1 hour')) as in_index
from up left join public.brands b on b.id = up.brand_id"""


def link(rows: list[dict], watched: list[dict] | None = None) -> dict:
    """Mirror the board's rows; then (decision 0020) keep the watched list for /methodology and rebuild every watched
    company's public cards (site.refresh_watch: a few dozen rows each). A changed card list changes the page's
    fingerprint, and the nightly sweep's publisher re-renders and re-proves that page."""
    rows = list({r["board_id"]: r for r in rows if r.get("board_id") and r.get("reddit_id")}.values())   # one row per record, the last wins
    out = {}
    for i in range(0, len(rows), BATCH):
        for r in query(upsert_sql(rows[i:i + BATCH])):
            out[r["board_id"]] = {"present": bool(r["in_index"]), "brand": r["brand"]}
    slugs = sorted({w["index_slug"] for w in watched or [] if w.get("index_slug")} |
                   {r["index_slug"] for r in rows if r.get("index_slug")})
    if slugs:
        lit = ",".join("'" + s.replace("'", "''") + "'" for s in slugs)
        query(f"""insert into site.watched_brand (brand_id, slug, name)
                  select id, slug, name from public.brands where slug in ({lit}) and status = 'published'
                  on conflict (brand_id) do update set slug = excluded.slug, name = excluded.name""")
        query(f"delete from site.watched_brand where slug not in ({lit})")
        cards = query(f"select b.slug, site.refresh_watch(b.id) as cards from public.brands b where b.slug in ({lit}) order by b.slug")
        out["_cards"] = {c["slug"]: c["cards"] for c in cards}
    return out


def coverage() -> list[dict]:
    return query("select partner, count(*) as on_board, count(*) filter (where in_index) as in_index, "
                 "count(*) filter (where brand_id is null) as not_a_brand, max(written_at)::date as newest "
                 "from watch.organic_coverage group by partner order by on_board desc")


def main() -> int:
    if "--coverage" in sys.argv:
        print(json.dumps(coverage(), indent=1, default=str))
        return 0
    data = json.load(sys.stdin)   # a list of rows, or {"rows": [...], "watched": [{"index_slug": ...}]}
    rows, watched = (data, None) if isinstance(data, list) else (data.get("rows") or [], data.get("watched"))
    print(json.dumps(link(rows, watched)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
