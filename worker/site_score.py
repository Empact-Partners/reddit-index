#!/usr/bin/env python3
"""Score and rank every company page from site.brand_stats, and write back only what changed.

This is the arithmetic the site's build used to do in lib/data/snapshot.ts and lib/data/boards.ts, moved to
where it can run once a day instead of once per build worker. The rules are the build's, unchanged
(decisions/0011):

  * the score uses EVERY opinionated mention collected for the brand (positive and negative, all time);
  * the prior is the brand's primary category's pooled positive rate, leaving the brand itself out;
  * a brand with at least one mention gets a score (with no opinions it is the category baseline);
  * a brand is ranked on its primary category's board when that category is published:
    score descending, then total mentions descending, then slug (plain character order).

Reads about 6,000 short rows, writes the rows whose score, rank or board size moved. Nothing here reads a
mention.

  worker/site_score.py            # score, write changes, recompute the index hashes
  worker/site_score.py --dry-run  # score and print the summary, write nothing
  worker/site_score.py --dump F   # also write inputs and outputs as JSON (for the parity test)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from numerics import fit_prior_pooled, page_score  # noqa: E402


def score_rows(rows: list[dict]) -> dict[int, dict]:
    """rows: brand_id, slug, primary_category_id, primary_category_slug, pos, neg, neu, total_mentions.
    Returns brand_id -> {page_score, page_n_op, board_rank, board_size}."""
    by_cat: dict[object, list[dict]] = defaultdict(list)
    for r in rows:
        # the build keyed the prior on the raw category id, published or not
        by_cat[r["primary_category_id"]].append(r)

    out: dict[int, dict] = {}
    for cat, rs in by_cat.items():
        tot_pos = sum(r["pos"] for r in rs) if cat is not None else 0
        tot_op = sum(r["pos"] + r["neg"] for r in rs) if cat is not None else 0
        for r in rs:
            pos, neg = r["pos"], r["neg"]
            if pos + neg <= 0 and r["neu"] <= 0:
                score = None
            else:
                # leave-one-out by mention mass; a brand with no category is scored against an empty pool
                others = [(tot_pos - pos, tot_op - pos - neg)] if cat is not None else []
                a0, b0, _ = fit_prior_pooled(others)
                score = page_score(pos, neg, a0, b0)
            out[r["brand_id"]] = {"page_score": score, "page_n_op": pos + neg, "board_rank": None, "board_size": 0}

    boards: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["primary_category_slug"] and out[r["brand_id"]]["page_score"] is not None:
            boards[r["primary_category_slug"]].append(r)
    for slug, rs in boards.items():
        rs.sort(key=lambda r: (-out[r["brand_id"]]["page_score"], -r["total_mentions"], r["slug"]))
        for i, r in enumerate(rs, 1):
            out[r["brand_id"]]["board_rank"] = i
            out[r["brand_id"]]["board_size"] = len(rs)
    return out


READ = """select brand_id, slug, primary_category_id, primary_category_slug, pos, neg, neu, total_mentions,
                 page_score, page_n_op, board_rank, board_size
          from site.brand_stats"""

WRITE = """
update site.brand_stats s
   set page_score = v.score, page_n_op = v.n_op, board_rank = v.rank, board_size = v.size, scored_at = now()
  from unnest(%s::bigint[], %s::int[], %s::int[], %s::int[], %s::int[]) as v(id, score, n_op, rank, size)
 where s.brand_id = v.id
   and (s.page_score, s.page_n_op, s.board_rank, s.board_size) is distinct from (v.score, v.n_op, v.rank, v.size)
"""


def run(conn, dry_run: bool = False, dump: str | None = None, log=print) -> dict:
    cur = conn.execute(READ)
    cols = [d.name for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    scored = score_rows(rows)
    changed = [r["brand_id"] for r in rows
               if (r["page_score"], r["page_n_op"], r["board_rank"], r["board_size"])
               != tuple(scored[r["brand_id"]][k] for k in ("page_score", "page_n_op", "board_rank", "board_size"))]
    summary = {"brands": len(rows), "scored": sum(v["page_score"] is not None for v in scored.values()),
               "ranked": sum(v["board_rank"] is not None for v in scored.values()), "changed": len(changed)}
    if dump:
        with open(dump, "w", encoding="utf-8") as f:
            json.dump([{**{k: r[k] for k in ("brand_id", "slug", "primary_category_id", "primary_category_slug",
                                             "pos", "neg", "neu", "total_mentions")}, **scored[r["brand_id"]]}
                       for r in rows], f)
    if not dry_run and changed:
        ids = changed
        conn.execute(WRITE, (ids, [scored[i]["page_score"] for i in ids], [scored[i]["page_n_op"] for i in ids],
                             [scored[i]["board_rank"] for i in ids], [scored[i]["board_size"] for i in ids]))
    if not dry_run:
        conn.execute("select site.compute_index_hashes()")
    log(f"  scored {summary['scored']} of {summary['brands']} brands, {summary['ranked']} ranked, "
        f"{summary['changed']} changed" + (" (dry run)" if dry_run else ""))
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--dump")
    a = ap.parse_args()
    import db
    with db.connect() as conn:
        conn.autocommit = True
        run(conn, a.dry_run, a.dump)
    return 0


if __name__ == "__main__":
    sys.exit(main())
