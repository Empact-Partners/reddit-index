#!/usr/bin/env python3
"""Restore brand rows the collector dropped while public.mentions.body was still NOT NULL (2026-10-03).

Migration 0019 stores a comment's text once; the second brand row of a comment arrives with body NULL. Until
migration 0021 dropped the NOT NULL, that insert failed and the collector logged "reject <doc id>: null value in
column body" and moved on. Some of those were plain re-inserts of rows that already existed (harmless); the others
are brand rows that were never stored.

The log is not the list: the collector prints only the first five rejects of each subreddit. So the repair takes
every comment in every thread the run touched (first seen, or its comment tree re-read, inside the run's receipt
window), reads its stored text, resolves it again with the collector's own resolver, and inserts the brand rows
that are missing through the collector's own insert (which skips any row that exists). Prints what it restored.

  ops/repair_dropped_rows.py --run <run id prefix> [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import uuid
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))



def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    import db
    with db.connect() as conn:
        conn.autocommit = True
        conn.execute("set statement_timeout = '15min'")
        w = conn.execute("select started_at, coalesce(finished_at, now()) from public.pipeline_runs "
                         "where stage = 'sweep' and run_id::text like %s", (a.run + "%",)).fetchone()
        if not w:
            print("no such run")
            return 2
        ids = [r[0] for r in conn.execute("""
            select distinct m.doc_id from public.mentions m join public.threads t on t.id = m.thread_id
             where t.first_seen_at between %s and %s or t.tree_fetched_at between %s and %s""",
            (w[0], w[1], w[0], w[1])).fetchall()]
    print(f"{len(ids)} stored comments and posts in threads the run touched")
    if not ids:
        return 0
    import daily as d
    import db
    resolver = d.Resolver()
    with db.connect() as conn:
        conn.autocommit = True
        docs = conn.execute("""
            select distinct on (m.doc_id) m.doc_id, m.doc_type, m.thread_id, m.subreddit_id, m.author,
                   extract(epoch from m.created_utc), m.permalink, m.score,
                   coalesce(m.body, (select k.body from public.mentions k where k.doc_id = m.doc_id
                                       and k.created_utc = m.created_utc and k.brand_id = m.body_from)),
                   s.name, coalesce(t.link_title, '')
              from public.mentions m join public.subreddits s on s.id = m.subreddit_id
              left join public.threads t on t.id = m.thread_id
             where m.doc_id = any (%s) order by m.doc_id, (m.body is null)""", (ids,)).fetchall()
        have = {(r[0], r[1]) for r in conn.execute(
            "select m.doc_id, b.slug from public.mentions m join public.brands b on b.id = m.brand_id "
            "where m.doc_id = any (%s)", (ids,)).fetchall()}
        rows, report = [], []
        run_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "reddit-index/repair-dropped-rows/" + a.run))   # mentions.run_id is a uuid
        for doc_id, doc_type, thread_id, sid, author, created, permalink, score, body, sub, title in docs:
            for h in resolver.resolve(body or "", sub, title):
                if (doc_id, h["brand_slug"]) in have:
                    continue
                rows.append((doc_id, doc_type, thread_id, sid, author or "", float(created or 0), permalink or "",
                             score or 0, body, h["conf"], h["alias"], h["rule_fired"], run_id,
                             h["brand_slug"]))
                report.append((doc_id, h["brand_slug"]))
        missing = sorted(set(ids) - {r[0] for r in docs})
        print(json.dumps({"documents_found": len(docs), "documents_with_no_row_at_all": missing,
                          "brand_rows_missing": report}, indent=1))
        if rows and not a.dry_run:
            with conn.transaction():
                ins, rej = d.insert_mentions(conn.cursor(), rows)
            print(f"restored {ins} rows ({rej} refused), run_id {run_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
