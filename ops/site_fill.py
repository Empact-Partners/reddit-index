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


def drain(conn, chunk: int = 25, log=print) -> int:
    done, t0 = 0, time.time()
    # The pooler's session default is 2 minutes, and a SET on the function does not rescue a statement whose
    # timer is already running: the first fill died on a chunk of very large brands exactly that way.
    conn.execute("set statement_timeout = '30min'")
    while True:
        n = conn.execute("select site.refresh_dirty(%s)", (chunk,)).fetchone()[0]
        done += n
        left = conn.execute("select count(*) from site.dirty_brand").fetchone()[0]
        log(f"  refreshed {done} brands, {left} left, {time.time() - t0:.0f}s", flush=True)
        if n == 0 or left == 0:
            return done


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
