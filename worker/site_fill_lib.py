"""Drain site.dirty_brand: recompute every brand whose data changed (site.refresh_brand), in chunks.

Resumable by construction: the work list IS site.dirty_brand, and each chunk commits on its own.
"""
from __future__ import annotations

import time


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
