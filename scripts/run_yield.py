#!/usr/bin/env python3
"""What one sweep run's collection yielded, read back from the database: the numbers decision 0029 is judged on.

  python3 scripts/run_yield.py <run id or its first 8 characters> [...]

Per run: the collect stage's receipt (mode, subreddits, Reddit calls, mentions, the bytes the node sent while it
collected) and, from the tables, what became of the mentions it wrote: labelled, rejected as not the product, still
waiting, by posts and comments, and the share of the brand "reddit". Read-only, through the Management API (not
between 00:00 and 05:30 UTC).
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(os.path.dirname(HERE), d) for d in ("ops", "scripts", "worker")]
import watch_link as w  # noqa: E402


def one(prefix: str) -> dict:
    if not re.fullmatch(r"[0-9a-f-]{8,36}", prefix):
        raise SystemExit(f"not a run id: {prefix!r}")
    rows = w.query(f"select run_id::text rid, status, started_at::text s, notes from public.pipeline_runs "
                   f"where run_id::text like '{prefix}%' order by started_at desc limit 1")
    if not rows:
        raise SystemExit(f"no run {prefix}")
    r = rows[0]
    notes = r["notes"] if isinstance(r["notes"], dict) else json.loads(r["notes"] or "{}")
    c = (notes.get("stages") or {}).get("collect") or {}
    rid = r["rid"]
    t = w.query(f"""
        with m as (select brand_id, doc_id, doc_type from public.mentions where run_id = '{rid}')
        select count(*) mentions,
               count(*) filter (where doc_type = 1) comments,
               count(*) filter (where doc_type = 2) posts,
               count(*) filter (where exists (select 1 from public.mention_sentiment s
                                where s.doc_id = m.doc_id and s.brand_id = m.brand_id)) labelled,
               count(*) filter (where exists (select 1 from public.mention_rejections x
                                where x.doc_id = m.doc_id and x.brand_id = m.brand_id)) rejected,
               count(*) filter (where m.brand_id = (select id from public.brands where slug = 'reddit')) reddit
        from m""")[0]
    calls = c.get("reddit_calls") or 0
    judged = (t["labelled"] or 0) + (t["rejected"] or 0)
    sent = c.get("sent_mb")
    return {
        "run": rid[:8], "started": (r["s"] or "")[:16], "status": r["status"], "mode": c.get("mode", "trees"),
        "subreddits": c.get("subs_visited"), "reddit_calls": calls, "mentions_new": c.get("mentions_new"),
        "mentions_a_call": round((c.get("mentions_new") or 0) / calls, 2) if calls else None,
        "threads_new": c.get("threads_new"), "threads_a_mention":
            round((c.get("threads_new") or 0) / c["mentions_new"], 2) if c.get("mentions_new") else None,
        "collect_sent_mb": sent, "kb_sent_a_mention":
            round(sent * 1000 / c["mentions_new"], 1) if (sent and c.get("mentions_new")) else None,
        "stream_gaps": c.get("stream_gaps"), "mentions_without_thread": c.get("mentions_without_thread"),
        "in_tables": t, "rejected_share": round(t["rejected"] / judged, 3) if judged else None,
        "reddit_share": round(t["reddit"] / t["mentions"], 3) if t["mentions"] else None,
        "allowance_used": c.get("allowance_used"), "stopped": c.get("stopped"),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for a in sys.argv[1:]:
        print(json.dumps(one(a), default=str))
