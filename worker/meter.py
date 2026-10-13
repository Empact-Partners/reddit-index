#!/usr/bin/env python3
"""The database node's transmit counter, read from inside the sweep.

The counter is what the egress watchdog and the bill follow. A run's own estimate (its write-ahead log plus the text
it reads) misses whatever else leaves the node: on 11 Oct the daily physical backup at 11:15 UTC shipped every page a
bulk step had rewritten that morning, a daytime pass capped at 0.36 GB estimated ran through it, and the day reached
2.42 GB. The guard that should have stopped the pass read the counter on a laptop that was asleep.

read()        the counter in bytes, or None when it cannot be read (no key in the environment, or the endpoint
              did not answer). One read is 18 KB of egress itself (compressed), so nothing here reads in a loop.
record(conn)  read and keep the reading in public.egress_counter (migration 0033).
used_24h(...) bytes sent in the 24 hours before a reading, from the newest reading at least 24 hours older; a gap in
              the readings makes the window longer, never shorter, so the figure can only read high.
"""
from __future__ import annotations

import base64
import gzip
import math
import os
import urllib.request

UA = "reddit-index-sweep/1.0 (+https://redditindex.com/methodology/)"


def parse(text: str) -> float | None:
    """The sum of node_network_transmit_bytes_total over every interface but loopback, or None if absent."""
    total, seen = 0.0, False
    for line in text.splitlines():
        if line.startswith("node_network_transmit_bytes_total") and 'device="lo"' not in line and " " in line:
            try:
                v = float(line.rsplit(" ", 1)[1])
            except ValueError:
                continue
            if not math.isfinite(v):   # "NaN" and "+Inf" are valid in the format and are not a reading
                return None
            total += v
            seen = True
    return total if (seen and total > 0) else None


def read(timeout: float = 30.0) -> float | None:
    key, ref = os.environ.get("SUPABASE_METRICS_KEY"), os.environ.get("SUPABASE_PROJECT_REF")
    if not key or not ref:
        return None
    auth = base64.b64encode(("service_role:" + key).encode()).decode()
    req = urllib.request.Request(f"https://{ref}.supabase.co/customer/v1/privileged/metrics",
                                 headers={"Authorization": "Basic " + auth, "User-Agent": UA,
                                          "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            text = (gzip.decompress(raw) if r.headers.get("Content-Encoding") == "gzip" else raw).decode()
    except Exception:  # noqa: BLE001 - an unread meter is "not known", never zero
        return None
    return parse(text)


def record(conn, source: str = "sweep") -> float | None:
    """Read the counter and keep the reading. Returns the bytes, or None when it could not be read or kept."""
    b = read()
    if b is None:
        return None
    try:
        conn.execute("insert into public.egress_counter (bytes, source) values (%s, %s) on conflict (at) do nothing",
                     (b, source))
    except Exception:  # noqa: BLE001 - the table is missing (migration 0033 not applied): the reading is still good
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
    return b


def used_24h(conn, now_bytes: float) -> tuple[float | None, str | None]:
    """(bytes sent in the last 24 hours or longer, when the older reading was taken). (None, None) when no reading is
    old enough or the counter went backwards (the node restarted)."""
    try:
        row = conn.execute("select bytes, at from public.egress_counter where at <= now() - interval '24 hours' "
                           "order by at desc limit 1").fetchone()
    except Exception:  # noqa: BLE001
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None, None
    if not row:
        return None, None
    used = now_bytes - float(row[0])
    if used < 0:
        return None, None
    return used, row[1].isoformat(timespec="minutes") if hasattr(row[1], "isoformat") else str(row[1])


def backup_reserve(conn, now_bytes: float, now: "dt.datetime", cfg: dict) -> tuple[float, str]:
    """Bytes to hold back for the day's backup, and why (decision 0033).

    Supabase's daily backup (about 11:15 UTC; 10-13 Oct between 11:15 and 11:21) ships the pages changed since the
    one before, and the node counter counts it: 249 MB on 12 Oct, 390 MB on 13 Oct, a quarter of what the node sent
    in the day before it (1.556 GB). A pass that fills the line before it leaves the backup over the line (13 Oct:
    2.20 GB in the 24 hours to 11:30). Until `cfg["after_utc"]` the expected backup is held back: `fraction` of what
    the node has sent since the same time yesterday, or `default_gb` when that is not known. After it, nothing: the
    backup is in the counter. A node restart is not handled here: the callers first need `used_24h`, which is
    unknown across a restart, and then no pass starts (decision 0025); `default_gb` covers a missing reading.
    That the backup really runs before `after_utc` is checked from its own record by scripts/schedule_check.py."""
    import datetime as _dt
    hh, mm = (int(x) for x in cfg.get("after_utc", "11:45").split(":"))
    today = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if now >= today:
        return 0.0, "the day's backup is in the counter"
    since = today - _dt.timedelta(days=1)
    default = float(cfg.get("default_gb", 0.4)) * 1e9
    try:
        row = conn.execute("select bytes from public.egress_counter where at <= %s order by at desc limit 1",
                           (since,)).fetchone()
    except Exception:  # noqa: BLE001
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        row = None
    if not row or now_bytes < float(row[0]):
        return default, f"{default / 1e9:.2f} GB held for the backup at about 11:15 UTC (what it follows is not known)"
    sent = now_bytes - float(row[0])
    held = max(float(cfg.get("min_gb", 0.15)) * 1e9, float(cfg.get("fraction", 0.3)) * sent)
    return held, (f"{held / 1e9:.2f} GB held for the backup at about 11:15 UTC ({cfg.get('fraction', 0.3)} of the "
                  f"{sent / 1e9:.2f} GB sent since {hh:02d}:{mm:02d} UTC yesterday)")
