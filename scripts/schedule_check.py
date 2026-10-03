#!/usr/bin/env python3
"""Is the Reddit Index running on the schedule it declares, and only on that schedule? Proven from the data.

Railway's own fields were wrong for seven weeks (decision 0016): the service's cron read empty while a cron in
each deployment's manifest ran the collector every night. So this reads three things and believes none of them
alone:

  1. Railway   every service in the project. The sweep's newest deployment must carry ops/schedule.json's
               cron and region and have succeeded; the old collector's newest deployment must be the parked
               image with no cron; any other service is a finding.
  2. receipts  one row in public.pipeline_runs (stage 'sweep') for every night since the sweep was switched on,
               started inside the declared window.
  3. writes    every mention and thread written since --since must fall inside a sweep's own receipt window,
               and every label or rejection inside a sweep's, the backlog classifier's or retention's.
               A write outside every receipt is something running that nobody declared.

  scripts/schedule_check.py              # print the verdict; exit 1 on any finding
  scripts/schedule_check.py --dm         # also DM Vlad, only when there is a finding
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
sys.path.insert(0, os.path.join(ROOT, "ops"))

PARKED_AT = "2026-10-02T20:47:00Z"   # the old collector was parked; nothing before this is the sweep's business


def railway(sched: dict) -> list[str]:
    import deploy_sweep as d
    out = []
    svcs = d.gql("query($p:String!){ project(id:$p){ services { edges { node { id name } } } } }",
                 {"p": d.PROJECT})["project"]["services"]["edges"]
    q = ("query($p:String!,$s:String!,$e:String!){ deployments(first:1, input:{projectId:$p, serviceId:$s, "
         "environmentId:$e, status:{in:[SUCCESS, DEPLOYING, BUILDING, INITIALIZING, QUEUED, WAITING, SLEEPING]}}){ "
         "edges { node { id status createdAt meta } } } }")
    seen = set()
    for e in svcs:
        sid, name = e["node"]["id"], e["node"]["name"]
        seen.add(name)
        deps = d.gql(q, {"p": d.PROJECT, "s": sid, "e": d.ENV})["deployments"]["edges"]
        if not deps:
            out.append(f"service {name} has no live deployment")
            continue
        n = deps[0]["node"]
        sm = (n.get("meta") or {}).get("serviceManifest") or {}
        cron = (sm.get("deploy") or {}).get("cronSchedule")
        df = (sm.get("build") or {}).get("dockerfilePath") or ""
        region = list(((sm.get("deploy") or {}).get("multiRegionConfig") or {}).keys())
        if sid == d.OLD_COLLECTOR:
            if cron or not df.endswith("Dockerfile.parked"):
                out.append(f"the old collector is not parked: newest deployment {n['id'][:8]} runs {df or '?'} "
                           f"with cron {cron!r}")
        elif name == d.NAME:
            if cron != sched["railway"]["cron"]:
                out.append(f"the sweep's newest deployment carries cron {cron!r}, ops/schedule.json says "
                           f"{sched['railway']['cron']!r}")
            if region != [d.REGION]:
                out.append(f"the sweep runs in {region}, not {d.REGION}")
        else:
            out.append(f"an undeclared service is in the project: {name} (cron {cron!r})")
    if d.NAME not in seen:
        out.append("the sweep service does not exist")
    return out


def database(sched: dict, since: str) -> tuple[list[str], dict]:
    import db
    out, facts = [], {}
    with db.connect() as conn:
        conn.autocommit = True
        conn.execute("set statement_timeout = '10min'")
        # A receipt still 'running' covers its job's writes for at most 8 hours (a crashed run must not hide later
        # writes forever). Mentions are matched to their run by run_id from 3 Oct 09:00 UTC on (the sweep stamps its
        # receipt id on every mention it writes): a write inside a sweep's time window by anything else is caught.
        until = ("coalesce(case when r.status = 'running' then least(now(), r.started_at + interval '8 hours') "
                 "else r.finished_at end, now())")
        cover = ("not exists (select 1 from public.pipeline_runs r where r.stage in ('sweep', 'repair') and {col} between "
                 "r.started_at - interval '2 minutes' and " + until + " + interval '2 minutes')")
        cover_mentions = ("not exists (select 1 from public.pipeline_runs r where r.run_id = t.run_id) and "
                          "(t.loaded_at >= '2026-10-03T09:00:00Z' or " + cover.format(col="t.loaded_at") + ")")
        cover_any = ("not exists (select 1 from public.pipeline_runs r where r.stage in ('sweep', "
                     "'classify-backlog', 'retention', 'repair') and {col} between r.started_at - interval '2 minutes' "
                     "and " + until + " + interval '2 minutes')")
        for table, col, rule in (("public.mentions", "loaded_at", cover_mentions), ("public.threads", "first_seen_at", cover),
                                 ("public.mention_sentiment", "scored_at", cover_any),
                                 ("public.mention_rejections", "rejected_at", cover_any)):
            n = conn.execute(f"select count(*), min({col}), max({col}) from {table} t "
                             f"where {col} > %s and " + (rule if "{col}" not in rule else rule.format(col=f"t.{col}")),
                             (since,)).fetchone()
            facts[f"{table} written outside any sweep"] = n[0]
            if n[0]:
                out.append(f"{n[0]:,} rows of {table} were written between {n[1]:%d %b %H:%M} and {n[2]:%d %b %H:%M} "
                           f"UTC outside every sweep's receipt")
        on, since_on = conn.execute("select enabled, updated_at from public.sweep_control").fetchone()
        facts["sweep switched on"] = bool(on)
        rows = conn.execute("select started_at, status, notes->>'skipped' from public.pipeline_runs "
                            "where stage = 'sweep' and started_at > now() - interval '8 days' "
                            "order by started_at").fetchall()
        facts["sweep receipts, last 8 days"] = [f"{r[0]:%d %b %H:%M} {r[1]}" for r in rows]
        if on:
            # a night counts only if a run did work: a "skipped" receipt (switch off, lock held) is a lost night
            nights = {r[0].date() for r in rows if r[1] in ("ok", "capped", "failed")}
            day = max(since_on.date(), (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)).date())
            today = dt.datetime.now(dt.timezone.utc)
            while day <= today.date():
                start = dt.datetime.combine(day, dt.time(0, 0), dt.timezone.utc)
                if today > start + dt.timedelta(minutes=30) and day not in nights and start > since_on:
                    out.append(f"no sweep receipt for the night of {day:%d %b}: the schedule did not fire, or the "
                               f"run died before it could write")
                day += dt.timedelta(days=1)
    return out, facts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None, help="ISO time; default: 72 hours ago, never before the parking")
    ap.add_argument("--dm", action="store_true")
    a = ap.parse_args()
    sched = json.load(open(os.path.join(ROOT, "ops", "schedule.json")))
    since = a.since or max(PARKED_AT, (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=72))
                           .strftime("%Y-%m-%dT%H:%M:%SZ"))
    findings = railway(sched)
    more, facts = database(sched, since)
    findings += more
    print(json.dumps({"since": since, "facts": facts, "findings": findings}, indent=1, default=str))
    if findings and a.dm:
        sys.path.insert(0, os.path.join(ROOT, "worker", "lib"))
        import slack_dm
        text = ("*Reddit Index: something is running off its declared schedule*\n\n"
                + " ".join(f[:200] for f in findings[:4]) +
                "\n\n*What this means for you*\nNothing yet: the check found it before it cost anything noticeable."
                "\n\n*To do*\nNothing for anyone to do; the session that owns the index is on it.\n\n"
                "*Details for the curious (and for your Claude)*\n"
                "<https://github.com/Empact-Partners/reddit-index/blob/main/SOP.md|how the daily update works>")
        slack_dm.send("U016BPWFC7Q", text)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
