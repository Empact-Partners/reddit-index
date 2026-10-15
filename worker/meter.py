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
ledger(...)   the watchdog's day (decision 0035): what the node sent since the watchdog's last daily reading, the day's
              backup and the night's run still to come in it, and what that leaves a daytime pass and the night.
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


# ---- the watchdog's day (decision 0035) ------------------------------------------------------------------------------
# The Empact watchdog (command-center sync/admin/supabase_watchdog.py) reads every project's counter once a day, at
# about 07:01 UTC, and speaks when the pair of readings makes more than 2 GB a day. The line is judged on that same day:
# from 07:00 UTC to 07:00 UTC, with what is still to come in it (the backup, the night's run) counted as already sent.
# Until 15 Oct it was judged on the 24 hours to now. That window kept a weekly full backup (1.285 GB on 14 Oct, at
# 12:21 to 12:25 UTC) in the line for a whole day, stopping every pass from 12:25 to 21:30 and again the next morning
# until 12:25, and it never asked the night's run to make room: the night came on top and the watchdog's day read 2.2.

def _utc(t):
    import datetime as _dt
    if isinstance(t, str):
        t = _dt.datetime.fromisoformat(t)
    return t if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)


def watchdog_day_start(now, hhmm: str = "07:00"):
    """The start of the watchdog's day that `now` falls in: the latest `hhmm` UTC at or before it."""
    import datetime as _dt
    hh, mm = (int(x) for x in hhmm.split(":"))
    start = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return start if now >= start else start - _dt.timedelta(days=1)


def at_or_before(rs: list, t) -> tuple | None:
    """The newest reading (at, bytes) taken at or before t, from readings sorted by time."""
    best = None
    for at, b in rs:
        if at <= t:
            best = (at, b)
        else:
            break
    return best


def sent_since(rs: list, t, now_bytes: float) -> tuple[float | None, object]:
    """(bytes sent from the newest reading at or before t to now, that reading's time). An older reading makes the
    span longer and the figure higher, never lower. (None, None): no reading that old, or the counter went back."""
    r = at_or_before(rs, t)
    if r is None or now_bytes < r[1]:
        return None, None
    return now_bytes - r[1], r[0]


def bursts(rs: list, since, pass_rate_bps: float, min_bytes: float) -> list[tuple]:
    """(time, bytes) of every interval between two readings after `since` that sent at least `min_bytes` more than a
    pass sends at its fastest (`pass_rate_bps` a second): the day's backup, seen in the counter. By day nothing else
    sends at that rate (10 to 14 Oct: passes 1 to 3 MB a minute; backups 249 MB in 17 to 32 minutes and 1,285 MB in 4)."""
    out = []
    prev = None
    for at, b in rs:
        if at <= since:
            prev = (at, b)
            continue
        if prev is not None and b >= prev[1]:
            excess = (b - prev[1]) - pass_rate_bps * (at - prev[0]).total_seconds()
            if excess >= min_bytes:
                out.append((at, b - prev[1]))
        prev = (at, b)
    return out


def night_spends(rs: list, now, nights: int = 3) -> list[float]:
    """What the node sent in each of the last `nights` nights, 00:00 to 06:00 UTC: the night's run and nothing else
    of note (the passes start at 06:15). A night with a reading missing at either end is left out."""
    import datetime as _dt
    out = []
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if now < day + _dt.timedelta(hours=6):
        day -= _dt.timedelta(days=1)   # tonight's run is not over: the last full night is yesterday's
    for _ in range(nights):
        a, b = at_or_before(rs, day), at_or_before(rs, day + _dt.timedelta(hours=6))
        if a and b and b[0] > day and b[1] >= a[1] and (day - a[0]).total_seconds() < 6 * 3600:
            out.append(b[1] - a[1])
        day -= _dt.timedelta(days=1)
    return out


def ledger_from(rs: list, now_bytes: float, now, sched: dict, db_bytes: float | None = None) -> dict:
    """The watchdog's day as a pass and the night see it (pure; `rs` are the counter's readings sorted by time,
    `db_bytes` the database's size for a full backup's estimate). See ledger()."""
    import datetime as _dt
    rs = [r for r in rs if r[0] <= now]   # a reading after `now` (clock skew, a replay) never counts (review, 15 Oct)
    bk, nt = sched.get("backup", {}), sched.get("night", {})
    line = float(sched.get("day_line_gb", 1.9)) * 1e9
    start = watchdog_day_start(now, sched.get("watchdog_reads_utc", "07:00"))
    sent, since = sent_since(rs, start, now_bytes)
    out = {"day_start": start.isoformat(timespec="minutes"), "line": line, "sent": sent,
           "since": since.isoformat(timespec="minutes") if since is not None else None}

    # the day's backup: held as sent until the counter shows it, or until hold_until when it never shows
    day = start.date()
    t = lambda hhmm: _dt.datetime.combine(day, _dt.datetime.strptime(hhmm, "%H:%M").time(), _dt.timezone.utc)  # noqa: E731
    seen_after, hold_until = t(bk.get("seen_after_utc", "10:30")), t(bk.get("hold_until_utc", "14:00"))
    seen = bursts(rs, seen_after, float(bk.get("pass_rate_mb_min", 3)) * 1e6 / 60,
                  float(bk.get("seen_min_gb", 0.1)) * 1e9) if now > seen_after else []
    full_last = bk.get("full_last")
    every = int(bk.get("full_every_days", 7))
    full = bool(full_last) and (day - _dt.date.fromisoformat(full_last)).days % every == 0
    # what the day's backup is expected to send
    if full:
        expected = max(float(bk.get("full_gb", 1.4)) * 1e9, float(bk.get("full_share", 0.37)) * (db_bytes or 0))
        what = f"today's full backup (every {every} days since {full_last}; 14 Oct: 1.285 GB)"
    else:
        base_from = t(bk.get("since_utc", "11:30")) - _dt.timedelta(days=1)
        base, _ = sent_since(rs, base_from, now_bytes)
        if base is not None:   # the backup before is not part of what the next one follows (15 Oct: a full one)
            yday = lambda hhmm: t(hhmm) - _dt.timedelta(days=1)  # noqa: E731
            base -= sum(x[1] for x in bursts(rs, yday(bk.get("seen_after_utc", "10:30")),
                                              float(bk.get("pass_rate_mb_min", 3)) * 1e6 / 60,
                                              float(bk.get("seen_min_gb", 0.1)) * 1e9)
                        if base_from < x[0] <= yday(bk.get("hold_until_utc", "14:00")))
            base -= sum(x[1] for x in seen)   # nor is today's, while it is under way
            base = max(0.0, base)
        if base is None:
            expected = float(bk.get("default_gb", 0.4)) * 1e9
            what = "the day's backup (what it follows is not known)"
        else:
            expected = max(float(bk.get("min_gb", 0.15)) * 1e9, float(bk.get("fraction", 0.3)) * base)
            what = (f"the day's backup ({bk.get('fraction', 0.3)} of the {base / 1e9:.2f} GB sent since "
                    f"{bk.get('since_utc', '11:30')} UTC yesterday)")
    if seen:
        got = sum(x[1] for x in seen)   # a backup can span two readings (review, 15 Oct)
        last = seen[-1][0]
        # the burst is over once the interval after it came at a pass's pace (twice its fastest, for the counter's
        # minute steps), or 15 minutes passed after it (review round 2: a tail under the burst threshold is not the end)
        pace = float(bk.get("pass_rate_mb_min", 3)) * 1e6 / 60
        tail = [r for r in rs if r[0] >= last]   # the burst's last reading and every one after it
        calm = any(b - a <= 2 * pace * max(1.0, (tb - ta).total_seconds())
                   for (ta, a), (tb, b) in zip(tail, tail[1:]))
        closed = calm or (now - last).total_seconds() >= 900
        out["backup_seen_gb"] = round(got / 1e9, 3)
        if closed:
            held, why = 0.0, f"the day's backup is in the counter ({got / 1e9:.2f} GB, to {last:%H:%M} UTC)"
        else:
            held = max(0.0, expected - got)
            why = (f"{got / 1e9:.2f} GB of {what} seen so far (to {last:%H:%M} UTC): the rest of its "
                   f"{expected / 1e9:.2f} GB is held until the counter settles")
    elif now >= hold_until:
        held, why = 0.0, f"no backup seen in the counter by {bk.get('hold_until_utc', '14:00')} UTC: none is held after it"
    else:
        held, why = expected, f"{expected / 1e9:.2f} GB held for {what}"
    out["backup_held"], out["backup_why"] = held, why
    out["full_backup_day"] = full

    # the night's run still to come in this day (a pass from 07:00 to midnight), at what the last nights cost
    if now < start + _dt.timedelta(hours=17):   # before midnight: tonight's run is still ahead in this day
        spends = night_spends(rs, now)
        night = max([float(nt.get("reserve_min_gb", 0.6)) * 1e9] + spends)
        out["night_held"] = night
        out["night_why"] = (f"{night / 1e9:.2f} GB held for tonight's run (the last nights: "
                            f"{', '.join(f'{x / 1e9:.2f}' for x in spends) or 'not read'} GB)")
    else:
        out["night_held"], out["night_why"] = 0.0, "tonight's run is in this day already"
    out["used"] = None if sent is None else sent + held + out["night_held"]
    # what the night may still send before its publish and refresh (which always run) once the day is accounted
    out["night_room"] = (None if sent is None else
                         line - sent - held - float(nt.get("publish_reserve_gb", 0.35)) * 1e9)
    return out


def ledger(conn, now_bytes: float, now, sched: dict) -> dict:
    """The watchdog's day: `sent` (bytes since its start, None when not known), `backup_held`, `night_held`, `used`
    (sent plus what is held: what a daytime pass is judged on) and `night_room` (what the night's collection and
    labelling may send), each with its reason. Read from public.egress_counter (four days of readings, ~25 KB)."""
    import datetime as _dt
    try:
        rows = conn.execute("select at, bytes::float8 from public.egress_counter where at > %s order by at",
                            (now - _dt.timedelta(days=4),)).fetchall()
        db_bytes = conn.execute("select pg_database_size(current_database())::float8").fetchone()[0]
    except Exception:  # noqa: BLE001 - the readings are not there: nothing is known
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        rows, db_bytes = [], None
    rs = [(_utc(a), float(b)) for a, b in rows]
    return ledger_from(rs, now_bytes, now, sched, db_bytes)
