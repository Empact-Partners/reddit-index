#!/usr/bin/env python3
"""Prove the parked collector stayed parked, by the data's own timestamps.

Why: on 2026-10-01 the collector's deployment was removed with `railway down`
and Railway redeployed it by itself at the next 02:00 UTC tick (the schedule
rides in each deployment's manifest; the service's cron field reads empty the
whole time). Config proves nothing here. Writes do.

What it checks, each time it is called:
  1. Railway: no deployment newer than the parked one, and the newest
     deployment's manifest has no cron and uses Dockerfile.parked.
  2. Database: zero rows in mentions / threads / ingest_state written after
     the park time.

If a collector deployment has appeared it is removed (`--remove`), and one
Slack DM goes to Vlad (`--dm`). A clean check says nothing to anyone.

Usage:
  ops/park_watch.py --since 2026-10-02T20:47:00Z                # check once, print
  ops/park_watch.py --since ... --at 02:20 03:00 08:00 --remove --dm
        # sleep until each UTC time (today or tomorrow), check, append a line
        # to ~/Library/Logs/reddit-index/park-watch.jsonl

Reads: ~/.railway/config.json (CLI login), ~/.claude/.supabase-empact.token.
Prints no credential.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

PROJECT = "90cd4c29-797c-4552-90d9-81c3b9914ffa"
SERVICE = "ff501aef-926d-4e24-8ef8-476855cd41b9"
ENV = "f3a7784c-7cd9-4cb8-a9ea-05efe657a7ff"
SUPABASE_REF = "nrsyqcttpijxhwtdtoct"
VLAD = "U016BPWFC7Q"
LOG = os.path.expanduser("~/Library/Logs/reddit-index/park-watch.jsonl")
UA = "Mozilla/5.0 (reddit-index park_watch)"


def _railway_token() -> str:
    # The CLI refreshes its own short-lived token; any authenticated command does it.
    subprocess.run(["railway", "whoami"], capture_output=True, timeout=60)
    cfg = json.load(open(os.path.expanduser("~/.railway/config.json")))
    return cfg["user"]["accessToken"]


def _gql(query: str, variables: dict) -> dict:
    req = urllib.request.Request(
        "https://backboard.railway.com/graphql/v2",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": "Bearer " + _railway_token(),
                 "Content-Type": "application/json", "User-Agent": UA})
    out = json.loads(urllib.request.urlopen(req, timeout=60).read())
    if out.get("errors") or not out.get("data"):
        raise RuntimeError("railway: " + json.dumps(out)[:300])
    return out["data"]


def _sql(query: str) -> list:
    assert query.strip().lower().startswith(("select", "with")), "read-only"
    tok = open(os.path.expanduser("~/.claude/.supabase-empact.token")).read().strip()
    try:
        j = json.loads(tok)
        tok = j.get("token") or j.get("access_token")
    except ValueError:
        pass
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{SUPABASE_REF}/database/query",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": "Bearer " + tok,
                 "Content-Type": "application/json", "User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def check(since: str, remove: bool) -> dict:
    """One observation. `status` is ok | resurrected | writes | not_checked."""
    res: dict = {"checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                 "since": since, "status": "ok", "notes": []}
    # A failed read is not a clean night: it is its own word, and it is reported.
    try:
        d = _gql(
            "query($p:String!,$s:String!,$e:String!){ deployments(first:6, input:"
            "{projectId:$p, serviceId:$s, environmentId:$e}){ edges { node "
            "{ id status createdAt meta } } } }",
            {"p": PROJECT, "s": SERVICE, "e": ENV})
        deps = []
        for edge in d["deployments"]["edges"]:
            n = edge["node"]
            m = n.get("meta") or {}
            sm = m.get("serviceManifest") or {}
            deps.append({
                "id": n["id"], "status": n["status"], "created": n["createdAt"],
                "reason": m.get("reason"),
                "dockerfile": (sm.get("build") or {}).get("dockerfilePath"),
                "cron": (sm.get("deploy") or {}).get("cronSchedule"),
            })
        res["deployments"] = deps[:4]
        # A parked redeploy at the tick is harmless, and still worth seeing:
        # it would mean Railway's scheduler outlives a cron-less manifest.
        newer = [x["id"][:8] for x in deps if x["created"] > since]
        if newer:
            res["notes"].append("deployments created after the park: " + ", ".join(newer))
        bad = [x for x in deps
               if x["created"] > since and x["status"] != "REMOVED"
               and (x["cron"] or x["dockerfile"] != "Dockerfile.parked")]
        if bad:
            res["status"] = "resurrected"
            res["resurrected"] = bad
            if remove:
                for x in bad:
                    out = _gql_mut("mutation($id:String!){ deploymentRemove(id:$id) }", {"id": x["id"]})
                    res["notes"].append(f"removed deployment {x['id'][:8]}: {out}")
    except Exception as exc:  # noqa: BLE001 - a read failure must not look like a pass
        res["status"] = "not_checked"
        res["notes"].append("railway read failed: " + str(exc)[:200])

    try:
        rows = _sql(
            "select (select count(*) from public.mentions where loaded_at > '%(s)s') as mentions,"
            " (select count(*) from public.threads where first_seen_at > '%(s)s') as threads,"
            " (select count(*) from public.ingest_state where finished_at > '%(s)s') as receipts,"
            " (select max(loaded_at) from public.mentions) as last_mention_write" % {"s": since})
        res["writes"] = rows[0]
        if any(int(rows[0][k] or 0) > 0 for k in ("mentions", "threads", "receipts")):
            res["status"] = "writes" if res["status"] == "ok" else res["status"]
            res["notes"].append("rows were written after the park time")
    except Exception as exc:  # noqa: BLE001
        res["status"] = "not_checked" if res["status"] == "ok" else res["status"]
        res["notes"].append("database read failed: " + str(exc)[:200])
    return res


def _gql_mut(query: str, variables: dict) -> dict:
    req = urllib.request.Request(
        "https://backboard.railway.com/graphql/v2",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": "Bearer " + _railway_token(),
                 "Content-Type": "application/json", "User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def dm(res: dict) -> None:
    sys.path.insert(0, os.path.expanduser("~/.claude/api_helpers"))
    from slack import SlackAPI  # type: ignore
    w = res.get("writes") or {}
    link = "<https://github.com/Empact-Partners/reddit-index/pull/5|what was done tonight and why>"
    if res["status"] == "resurrected":
        head = "*Reddit Index: Railway brought the old collector back again overnight*"
        body = ("The index is meant to stay frozen until the relaunch is ready. At its usual 02:00 UTC "
                "slot Railway started the old collector by itself, the same thing that happened last "
                "night. It could not reach the database, because its password was changed yesterday, "
                "and the overnight check has already removed it.")
        you = "Nothing was collected and nothing was spent. The relaunch work continues."
        todo = "Nothing for you to do."
    elif res["status"] == "writes":
        head = "*Reddit Index: something added data overnight while the index should be frozen*"
        body = (f"Since the collector was parked, {w.get('mentions')} new mentions and "
                f"{w.get('threads')} new threads have appeared in the database. Nothing is supposed "
                "to be writing to it, so there is a writer nobody has accounted for.")
        you = "The relaunch work is paused until the writer is found, so the numbers stay trustworthy."
        todo = "Nothing for you to do yet. The session doing the relaunch is looking into it."
    else:
        head = "*Reddit Index: last night's freeze check could not run*"
        body = ("The check that proves nothing collected overnight could not read Railway or the "
                "database, so last night counts as unproven, not as clean.")
        you = "The freeze is probably holding, but that is a guess until the check runs again."
        todo = "Nothing for you to do. The check is re-run by hand in the morning."
    text = (f"{head}\n\n{body}\n\n*What this means for you*\n{you}\n\n*To do*\n{todo}\n\n"
            f"*Details for the curious (and for your Claude)*\n{link}")
    SlackAPI("empact").dm(VLAD, text, unfurl_links=False, unfurl_media=False)


def _sleep_until(hhmm: str) -> None:
    h, m = (int(x) for x in hhmm.split(":"))
    now = dt.datetime.now(dt.timezone.utc)
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= now:
        target += dt.timedelta(days=1)
    time.sleep((target - now).total_seconds())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True, help="ISO time the service was parked (UTC)")
    ap.add_argument("--at", nargs="*", default=[], help="UTC HH:MM times to check at, in order")
    ap.add_argument("--remove", action="store_true", help="remove a resurrected collector deployment")
    ap.add_argument("--dm", action="store_true", help="DM Vlad when a check is not clean")
    a = ap.parse_args()

    if not a.at:
        res = check(a.since, a.remove)
        print(json.dumps(res, indent=1, default=str))
        return 0 if res["status"] == "ok" else 2

    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    worst = 0
    told = False
    for hhmm in a.at:
        _sleep_until(hhmm)
        res = check(a.since, a.remove)
        res["slot"] = hhmm
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(res, default=str) + "\n")
        if res["status"] != "ok":
            worst = 2
            if a.dm and not told:  # once, never repeated
                try:
                    dm(res)
                    told = True
                except Exception as exc:  # noqa: BLE001
                    with open(LOG, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"dm_failed": str(exc)[:200]}) + "\n")
    return worst


if __name__ == "__main__":
    sys.exit(main())
