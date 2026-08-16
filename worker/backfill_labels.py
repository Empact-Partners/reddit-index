#!/usr/bin/env python3
"""Commit labels that exist in the on-disk model cache but not in Postgres.

Needed because of an asymmetry that would otherwise lose work permanently:
the classifier writes its model judgment to the item cache BEFORE the row
reaches the DB, and on startup it treats everything in that cache as `known`
and skips it. So any label harvested but never committed — e.g. the ~76k
blocked behind a NUL byte for ten hours — becomes invisible to the daemon
forever. Restarting the classifier does not recover them; this does, without
re-spending a single fleet call.

Idempotent: ON CONFLICT DO NOTHING, so it is always safe to re-run.

    python3 worker/backfill_labels.py --dry-run
    python3 worker/backfill_labels.py
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import db  # noqa: E402
from classify import MODEL_VERSION, STAGE_LLM, LABEL_CODE  # noqa: E402
from classify_codex import CACHE  # noqa: E402
from classify_daemon import pg_text  # noqa: E402

CHUNK = 500

INSERT = """
    INSERT INTO mention_sentiment (doc_id, brand_id, model_version, label,
        intensity, conf, stage, is_comparative, is_recommendation,
        is_category_gripe, evidence_span)
    SELECT %s, b.id, %s, %s, %s, %s, %s, %s, %s, %s, %s
    FROM brands b WHERE b.slug = %s
    ON CONFLICT (doc_id, brand_id, model_version) DO NOTHING
"""


def rows_from_cache():
    """Every cached judgment, shaped exactly as the daemon shapes it."""
    rows, files, entity_rejected = [], 0, 0
    for fp in glob.glob(os.path.join(CACHE, "codex_*.json")):
        files += 1
        try:
            obj = json.load(open(fp))
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        for item_id, r in obj.items():
            if not isinstance(r, dict):
                continue
            # entity-rejected items intentionally never get a row
            if r.get("entity_ok") is False:
                entity_rejected += 1
                continue
            if ":" not in item_id:
                continue
            doc_id, bslug = item_id.rsplit(":", 1)
            rows.append((doc_id, MODEL_VERSION,
                         LABEL_CODE.get(str(r.get("label", "abstain")).lower(), 3),
                         float(r.get("intensity") or 0),
                         float(r.get("confidence") or 0),
                         STAGE_LLM, bool(r.get("comparative")),
                         bool(r.get("recommendation")),
                         bool(r.get("category_gripe")),
                         pg_text(r.get("evidence"), 300), bslug))
    return rows, files, entity_rejected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows, files, rejected = rows_from_cache()
    print(f"cache: {files:,} files → {len(rows):,} committable judgments "
          f"({rejected:,} entity-rejected, correctly skipped)")

    state = {"conn": db.connect()}

    def _count(c):
        with c.cursor() as cur:
            cur.execute("SELECT count(*)::int FROM mention_sentiment")
            return cur.fetchone()[0]

    before = db.run(state, _count, label="count")
    print(f"mention_sentiment before: {before:,}")
    if args.dry_run:
        print("dry-run — nothing written")
        return 0

    done = dropped = 0
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i:i + CHUNK]

        def _ins(c, ch=chunk):
            with c.cursor() as cur:
                cur.executemany(INSERT, ch)
                c.commit()
        try:
            db.run(state, _ins, label="backfill")
        except Exception as e:
            print(f"  chunk {i // CHUNK} failed ({str(e)[:70]}) — isolating")
            for row in chunk:
                def _one(c, r=row):
                    with c.cursor() as cur:
                        cur.execute(INSERT, r)
                        c.commit()
                try:
                    db.run(state, _one, label="backfill one")
                except Exception:
                    dropped += 1
        done += len(chunk)
        if (i // CHUNK) % 20 == 0:
            print(f"  {done:,}/{len(rows):,} processed", flush=True)

    after = db.run(state, _count, label="count")
    print(f"\nmention_sentiment after: {after:,}  (+{after - before:,} new)")
    if dropped:
        print(f"  {dropped:,} rows unwritable and dropped")
    try:
        state["conn"].close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
