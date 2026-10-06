#!/usr/bin/env python3
"""Measure a scheduled night's egress for the go-live gate: "a full run plus the day's page regeneration under 1 GB".

Two meters, both on the database node's transmit counter (the number the egress watchdog and the bill follow):

  laptop     the counter's last reading before the run starts (every tick from 08:00 UTC), and again 20 minutes after its receipt is
             written (the write-ahead log keeps shipping after heavy writes; measured 2026-10-03, the tail belongs
             to the work). Exact for the run, when the laptop was awake at both moments.
  watchdog   the command-center supabase watchdog's own reading at 07:01 UTC the morning of the run: reddit-index's
             GB over the 24 hours since the previous 07:01. Off the laptop, always there, an upper bound (it also
             holds whatever else touched the database that day).

It is a tick, not a long process (the first version was one, and it died with the session that started it,
2026-10-04): launchd runs it every 10 minutes while the Mac is awake, each tick does whatever is due and records
it in docs/go-live/egress-<night>.json, and a reading that was missed is left missing, never invented. Nothing
holds the Mac awake (feedback_mac_sleeps_normally_no_caffeinate).

  python3 ops/gate_meter.py tick --night 2026-10-05 --night 2026-10-06    # what launchd runs
  python3 ops/gate_meter.py show --night 2026-10-05
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "ops"))

WATCHDOG = {"project": "a5b85d75-81f3-42bc-a698-9a5745e29151", "service": "e22ba8ea-a2b6-4c81-af3d-ac780bc58c83"}
TAIL = dt.timedelta(minutes=20)


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def path(night: str) -> str:
    return os.path.join(ROOT, "docs", "go-live", f"egress-{night}.json")


def load(night: str) -> dict:
    try:
        with open(path(night)) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"night": night}


def save(rec: dict) -> None:
    os.makedirs(os.path.dirname(path(rec["night"])), exist_ok=True)
    tmp = path(rec["night"]) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(rec, f, indent=1, default=str)
    os.replace(tmp, path(rec["night"]))


def counter() -> tuple[float, str] | None:
    import investigation_2026_10 as inv
    try:
        return inv._metrics()["transmit_bytes"], now().isoformat(timespec="seconds")
    except Exception:  # noqa: BLE001 - a missed reading is left missing, never invented
        return None


class _ApiConn:
    """The few reads the meter needs, through Supabase's Management API (HTTPS) when the database port is not
    reachable from this network (6 Oct: outbound 5432 and 6543 blocked on the laptop's network). Parameters are
    inlined as quoted literals: they are timestamps and ids from our own receipts."""

    def __init__(self):
        import investigation_2026_10 as inv
        self.inv = inv
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql: str, params=()):
        import urllib.request
        for p in params:
            v = p.isoformat() if hasattr(p, "isoformat") else str(p)
            sql = sql.replace("%s", "'" + v.replace("'", "''") + "'", 1)
        req = urllib.request.Request(
            f"https://api.supabase.com/v1/projects/{self.inv.REF}/database/query", method="POST",
            data=json.dumps({"query": sql}).encode(),
            headers={"Authorization": "Bearer " + self.inv._mgmt_token(), "Content-Type": "application/json",
                     "User-Agent": "Mozilla/5.0"})
        rows = json.loads(urllib.request.urlopen(req, timeout=600).read())
        return _Rows([tuple(r.values()) for r in rows])


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


def _conn():
    if os.environ.get("RI_DB_VIA_API"):
        return _ApiConn()
    import socket
    import db
    try:   # a quick look at the port first: db.connect() retries for minutes on a network that blocks it
        socket.create_connection((os.environ.get("SUPABASE_DB_HOST") or "aws-0-us-east-1.pooler.supabase.com",
                                  int(os.environ.get("SUPABASE_DB_PORT", "5432"))), timeout=8).close()
    except OSError:
        return _ApiConn()
    return db.connect()


def receipt(day: dt.datetime):
    with _conn() as conn:
        r = conn.execute("select run_id, started_at, finished_at, status, notes from public.pipeline_runs "
                         "where stage = 'sweep' and started_at >= %s and started_at < %s "
                         "and finished_at is not null and status not in ('running', 'skipped') "
                         "and coalesce(notes->>'manual', 'false') = 'false' order by started_at limit 1",
                         (day, day + dt.timedelta(hours=8))).fetchone()
    if r and isinstance(r[1], str):   # through the API: text, not datetimes
        r = (r[0], dt.datetime.fromisoformat(r[1]), dt.datetime.fromisoformat(r[2]), r[3], r[4])
    return r


def reconcile(rec: dict) -> dict:
    """The gate's second half: the receipt's counts against the rows in the database for the same run."""
    st = rec.get("stages") or {}
    a, b = rec["run_started"], rec["run_finished"]
    with _conn() as conn:
        if not isinstance(conn, _ApiConn):
            conn.execute("set statement_timeout = '10min'")
        one = lambda q, *p: conn.execute(q, p).fetchone()[0]  # noqa: E731
        pairs = {
            "new mentions": ((st.get("collect") or {}).get("mentions_new"),
                             one("select count(*) from public.mentions where run_id = %s", rec["run_id"])),
            "labels": ((st.get("classify") or {}).get("labelled"),
                       one("select count(*) from public.mention_sentiment where scored_at between %s and %s", a, b)),
            "not this product": ((st.get("classify") or {}).get("rejected"),
                                 one("select count(*) from public.mention_rejections where rejected_at between %s and %s", a, b)),
            "takedowns found": (None if "takedowns" not in st else
                                int(st["takedowns"].get("docs_gone") or 0) + int(st["takedowns"].get("docs_edited") or 0),
                                one("select count(*) from public.removals where detected_at between %s and %s", a, b)),
        }
        if "posts_qualified" in (st.get("collect") or {}):   # receipts from 2026-10-04 on read threads back
            pairs["new threads"] = (st["collect"].get("threads_new"),
                                    one("select count(*) from public.threads where first_seen_at between %s and %s", a, b))
    out = {k: {"receipt": r, "database": d_, "match": (r == d_) if r is not None else d_ == 0} for k, (r, d_) in pairs.items()}
    # a receipt that never reached a stage proves nothing about it: the core counts must be there (review 4 Oct)
    missing = [k for k in ("new mentions", "labels", "not this product", "takedowns found") if out[k]["receipt"] is None]
    out["_complete"] = {"receipt": None if missing else True, "database": None, "match": not missing,
                        "missing": missing}
    with _conn() as conn:
        out["_dangling_text"] = {"receipt": 0, "database": conn.execute(
            "select count(*) from public.mentions m where m.body is null and not exists (select 1 from "
            "public.mentions h where h.doc_id = m.doc_id and h.created_utc = m.created_utc "
            "and h.brand_id = m.body_from and h.body is not null)").fetchone()[0]}
        out["_dangling_text"]["match"] = out["_dangling_text"]["database"] == 0
    return out


def watchdog_reading(day: dt.datetime) -> dict | None:
    """reddit-index's 'GB/day now' line from the watchdog pass at 07:01 UTC on the run's day."""
    import deploy_sweep as d
    p, s = WATCHDOG["project"], WATCHDOG["service"]
    env = d.gql("query($p:String!){ project(id:$p){ environments { edges { node { id } } } } }",
                {"p": p})["project"]["environments"]["edges"][0]["node"]["id"]
    deps = d.gql("query($p:String!,$s:String!,$e:String!){ deployments(first:3, input:{projectId:$p, serviceId:$s, "
                 "environmentId:$e}){ edges { node { id createdAt } } } }", {"p": p, "s": s, "e": env})
    for e in deps["deployments"]["edges"]:
        logs = d.gql("query($d:String!){ deploymentLogs(deploymentId:$d, limit:5000){ message timestamp } }",
                     {"d": e["node"]["id"]})["deploymentLogs"]
        lo, hi = (day + dt.timedelta(hours=6, minutes=50)).isoformat(), (day + dt.timedelta(hours=9)).isoformat()
        for line in logs:
            ts = line["timestamp"]
            m = re.match(r"\s*reddit-index\s+([\d.]+)\s+([\d.]+)\s*$", line["message"])
            if m and lo[:16] <= ts[:16] <= hi[:16]:
                return {"gb_last_24h": float(m.group(1)), "gb_per_day_7d": float(m.group(2)), "logged_at": ts,
                        "window": f"the 24 hours to {ts}"}
    return None


def tick(night: str) -> dict:
    rec = load(night)
    day = dt.datetime.fromisoformat(night).replace(tzinfo=dt.timezone.utc)
    t = now()
    # the baseline is the LAST reading before 00:00: every tick from 08:00 UTC overwrites it, so daytime jobs that
    # finished before the Mac's last evening tick fall outside the night's window
    if day - dt.timedelta(hours=16) <= t < day:   # from 08:00 UTC: a Mac asleep all evening still has one
        c = counter()
        if c:
            rec["counter_before"] = {"bytes": c[0], "at": c[1]}
    if "run_id" not in rec or rec.get("status") in (None, "running"):
        r = receipt(day) if t >= day else None
        if r:
            n = r[4] if isinstance(r[4], dict) else json.loads(r[4] or "{}")
            rec.update({"run_id": str(r[0]), "status": r[3], "run_started": r[1].isoformat(),
                        "run_finished": r[2].isoformat(), "run_minutes": n.get("minutes"),
                        "caps_hit": n.get("caps_hit"), "problems": n.get("problems"),
                        "allowances_used": n.get("allowances_used"), "egress_estimate_gb": n.get("egress_estimate_gb"),
                        "stages": {k: {x: v.get(x) for x in (
                            "reddit_calls", "mentions_new", "subs_visited", "docs_checked", "docs_gone", "labelled",
                            "rejected", "not_checked", "glm_credits", "jev_usd", "error", "pages_expired",
                            "pages_verified", "takedown_pages", "failed", "render_estimate_gb", "docs_edited",
                            "threads_new", "posts_qualified") if x in v}
                                   for k, v in (n.get("stages") or {}).items() if isinstance(v, dict)}})
    if "run_id" in rec and "reconcile" not in rec:
        rec["reconcile"] = reconcile(rec)
        rec["receipt_matches_database"] = all(v["match"] for v in rec["reconcile"].values())
    if "run_finished" in rec and "counter_after" not in rec and "counter_before" in rec:
        if t >= dt.datetime.fromisoformat(rec["run_finished"]) + TAIL:
            c = counter()
            if c and c[0] < rec["counter_before"]["bytes"]:   # the node restarted: no window, never a low number
                rec["counter_after"] = {"bytes": c[0], "at": c[1]}
                rec["laptop_note"] = "the counter went down (node restart): no laptop measurement this night"
            elif c:
                rec["counter_after"] = {"bytes": c[0], "at": c[1]}
                gb = (c[0] - rec["counter_before"]["bytes"]) / 1e9
                rec["laptop_egress_gb"] = round(gb, 3)
                late = (t - dt.datetime.fromisoformat(rec["run_finished"]) - TAIL).total_seconds() / 3600
                if late > 0.5:   # the laptop slept through the tail: the reading holds idle hours too
                    rec["laptop_note"] = f"read {late:.1f} hours after the tail ended: an upper bound"
    if "watchdog" not in rec and t >= day + dt.timedelta(hours=7, minutes=5):
        try:
            w = watchdog_reading(day)
        except SystemExit as e:   # deploy_sweep.gql exits on a Railway error: try again next tick
            w, rec["watchdog_error"] = None, str(e)[:200]
        if w:
            rec["watchdog"] = w
            rec.pop("watchdog_error", None)
            # the reading counts only if it came after the run and its tail: an earlier one does not contain it
            if "run_finished" in rec and dt.datetime.fromisoformat(w["logged_at"][:26].replace("Z", "") + "+00:00") \
                    < dt.datetime.fromisoformat(rec["run_finished"]) + TAIL:
                w["covers_the_run"] = False
    # the gate: the exact laptop window when it exists, else the watchdog's day (an upper bound)
    wd = rec.get("watchdog") or {}
    gb = rec.get("laptop_egress_gb", wd.get("gb_last_24h") if wd.get("covers_the_run", True) else None)
    if gb is not None and "run_id" in rec:
        rec["gate_egress_gb"] = gb
        rec["gate_source"] = "laptop window" if "laptop_egress_gb" in rec else "watchdog day (upper bound)"
        rec["gate_under_1_gb"] = gb < 1.0
    rec["last_tick"] = t.isoformat(timespec="seconds")
    save(rec)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["tick", "show"])
    ap.add_argument("--night", action="append", required=True, help="YYYY-MM-DD, the UTC date the run starts")
    a = ap.parse_args()
    for night in a.night:
        rec = tick(night) if a.cmd == "tick" else load(night)
        print(json.dumps(rec, default=str), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
