#!/usr/bin/env python3
"""Recompute site.brand_stats and site.rail_key for every brand, or drain what is dirty.

  ops/site_fill.py --all      # mark every published brand dirty, then drain (the first fill; about 15 minutes)
  ops/site_fill.py            # drain only (what a sweep does after it has written)

Resumable by construction: the work list IS site.dirty_brand, and each chunk commits on its own.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "worker"))


from site_fill_lib import drain  # noqa: E402  (worker/site_fill_lib.py)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--chunk", type=int, default=25)
    a = ap.parse_args()
    import db
    with db.connect() as conn:
        conn.autocommit = True
        if a.all:
            n = conn.execute("insert into site.dirty_brand (brand_id) select id from public.brands "
                             "on conflict (brand_id) do nothing").rowcount
            print(f"marked {n} brands dirty", flush=True)
        drain(conn, a.chunk)
        s = conn.execute("select count(*), sum(total_mentions), sum(rail_size), "
                         "(select count(*) from site.rail_key) from site.brand_stats").fetchone()
        print(f"brand_stats: {s[0]} pages, {s[1]} mentions, {s[2]} visible cards, {s[3]} rail keys")
    return 0


if __name__ == "__main__":
    sys.exit(main())
