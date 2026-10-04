#!/usr/bin/env python3
"""Measure a scheduled night's egress for the go-live gate: "a full run plus the day's page regeneration under 1 GB".

Two meters, both on the database node's transmit counter (the number the egress watchdog and the bill follow):

  laptop     the counter's last reading before the run starts (every tick from 16:00 UTC), and again 20 minutes after its receipt is
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


def receipt(day: dt.datetime):
    import db
    with db.connect() as conn:
        return conn.execute("select run_id, started_at, finished_at, status, notes from public.pipeline_runs "
                            "where stage = 'sweep' and started_at >= %s and started_at < %s "
                            "and finished_at is not null and status <> 'running' order by started_at limit 1",
                            (day, day + dt.timedelta(hours=8))).fetchone()


def reconcile(rec: dict) -> dict:
    """The gate's second half: the receipt's counts against the rows in the database for the same run."""
    import db
    st = rec.get("stages") or {}
    a, b = rec["run_started"], rec["run_finished"]
    with db.connect() as conn:
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
    # the baseline is the LAST reading before 00:00: every tick from 16:00 UTC overwrites it, so daytime jobs that
    # finished before the Mac's last evening tick fall outside the night's window
    if day - dt.timedelta(hours=8) <= t < day:
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
            if c:
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
    # the gate: the exact laptop window when it exists, else the watchdog's day (an upper bound)
    gb = rec.get("laptop_egress_gb", (rec.get("watchdog") or {}).get("gb_last_24h"))
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
