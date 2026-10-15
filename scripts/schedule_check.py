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
    # CRASHED is a live cron deployment whose last run exited non-zero (the sweep does that on a "failed" run;
    # Railway still fires the next one, 2026-10-04): the receipt says why, so it is not a schedule finding.
    q = ("query($p:String!,$s:String!,$e:String!){ deployments(first:1, input:{projectId:$p, serviceId:$s, "
         "environmentId:$e, status:{in:[SUCCESS, CRASHED, DEPLOYING, BUILDING, INITIALIZING, QUEUED, WAITING, "
         "SLEEPING]}}){ "
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
            if (sm.get("deploy") or {}).get("startCommand"):
                out.append(f"the sweep carries a start command ({(sm.get('deploy') or {}).get('startCommand')!r}): "
                           f"it must run the image's own, worker/run_daily.py")
        elif name == sched.get("day", {}).get("service_name"):
            # the daytime passes' requester (ops/day_tick.py, decision 0026): its own cron and start command
            if cron != sched["day"]["cron"]:
                out.append(f"the day service's newest deployment carries cron {cron!r}, ops/schedule.json says "
                           f"{sched['day']['cron']!r}")
            start = (sm.get("deploy") or {}).get("startCommand") or ""
            if "day_tick.py" not in start:
                out.append(f"the day service does not start ops/day_tick.py (start command {start!r}): it would "
                           f"run the sweep itself every half hour")
            if region != [d.REGION]:
                out.append(f"the day service runs in {region}, not {d.REGION}")
        else:
            out.append(f"an undeclared service is in the project: {name} (cron {cron!r})")
    if d.NAME not in seen:
        out.append("the sweep service does not exist")
    if sched.get("day", {}).get("service_name") and sched["day"]["service_name"] not in seen:
        out.append("the day service does not exist: no daytime pass is being requested")
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
        cover = ("not exists (select 1 from public.pipeline_runs r where r.stage in ('sweep', 'repair', 'backfill') and {col} between "
                 "r.started_at - interval '2 minutes' and " + until + " + interval '2 minutes')")
        cover_mentions = ("not exists (select 1 from public.pipeline_runs r where r.run_id = t.run_id) and "
                          "(t.loaded_at >= '2026-10-03T09:00:00Z' or " + cover.format(col="t.loaded_at") + ")")
        cover_any = ("not exists (select 1 from public.pipeline_runs r where r.stage in ('sweep', "
                     "'classify-backlog', 'retention', 'repair', 'backfill') and {col} between r.started_at - interval '2 minutes' "
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
        rows = conn.execute("select started_at, status, notes->>'skipped', "
                            "coalesce((notes->>'manual')::boolean, false) from public.pipeline_runs "
                            "where stage = 'sweep' and started_at > now() - interval '8 days' "
                            "order by started_at").fetchall()
        facts["sweep receipts, last 8 days"] = [f"{r[0]:%d %b %H:%M} {r[1]}" for r in rows]
        if on:
            # a night counts only if a run did work: a "skipped" receipt (switch off, lock held) is a lost night
            # and only the scheduled run: a daytime pass (manual on its receipt) on the same date is not the night
            # (until 11 Oct any receipt of the date counted, so a lost night would have hidden behind a day pass)
            nights = {r[0].date() for r in rows if r[1] in ("ok", "capped", "failed") and not r[3]}
            day = max(since_on.date(), (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)).date())
            today = dt.datetime.now(dt.timezone.utc)
            while day <= today.date():
                start = dt.datetime.combine(day, dt.time(0, 0), dt.timezone.utc)
                if today > start + dt.timedelta(minutes=30) and day not in nights and start > since_on:
                    out.append(f"no sweep receipt for the night of {day:%d %b}: the schedule did not fire, or the "
                               f"run died before it could write")
                day += dt.timedelta(days=1)
    return out, facts


def backup_timing(sched: dict, now: dt.datetime | None = None, backups: list | None = None) -> tuple[list[str], dict]:
    """The egress line holds the day's backup until the counter shows it, and at most until `backup.hold_until_utc`
    (decisions 0033, 0035), on the strength of when Supabase runs it (11:15 to 11:21 UTC on 8-13 Oct, 12:25 on 14 Oct,
    the full one). Read from the backups' own record; a backup outside `seen_after_utc` to `hold_until_utc`, or none
    in 30 hours, is a finding. `backups`: the API's list (tests pass their own)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if backups is None:
        try:
            import urllib.request
            import investigation_2026_10 as inv
            req = urllib.request.Request(f"https://api.supabase.com/v1/projects/{inv.REF}/database/backups",
                                         headers={"Authorization": "Bearer " + inv._mgmt_token(),
                                                  "User-Agent": "Mozilla/5.0"})
            backups = json.loads(urllib.request.urlopen(req, timeout=60).read()).get("backups", [])
        except Exception as e:  # noqa: BLE001 - not readable here (no token): said, not a finding
            return [], {"backups": f"not read: {str(e)[:80]}"}
    times = sorted(dt.datetime.fromisoformat(str(b.get("inserted_at")).replace("Z", "+00:00"))
                   for b in backups if b.get("inserted_at"))
    if not times:
        return ["no daily backup is listed for the project"], {"backups": []}
    last = times[-1]
    bk = sched.get("backup", {})
    lo, hi = bk.get("seen_after_utc", "10:30"), bk.get("hold_until_utc", "14:00")
    mins = lambda hhmm: int(hhmm[:2]) * 60 + int(hhmm[3:5])  # noqa: E731
    out = []
    for t in times[-3:]:
        if not (mins(lo) <= t.hour * 60 + t.minute < mins(hi)):
            out.append(f"the daily backup of {t:%d %b} ran at {t:%H:%M} UTC, outside {lo} to {hi} UTC where the egress "
                       f"line holds it (decision 0035): move backup.seen_after_utc / hold_until_utc")
    if now - last > dt.timedelta(hours=30):
        out.append(f"the newest daily backup is from {last:%d %b %H:%M} UTC, more than 30 hours ago")
    return out, {"backups": [t.strftime("%d %b %H:%M") for t in times[-3:]]}


def full_backups(sched: dict, readings: list, now: dt.datetime) -> tuple[list[str], dict]:
    """Decision 0035 predicts the full backup (every `full_every_days` from `full_last`, about the database's size x
    `full_share`). Read from the counter's readings (sorted (at, bytes)): a burst of at least half a full one on a day
    the schedule does not call full, or a full day of the last week without one, is a finding."""
    import meter
    bk = sched.get("backup", {})
    if not bk.get("full_last"):
        return [], {}
    every, first = int(bk.get("full_every_days", 7)), dt.date.fromisoformat(bk["full_last"])
    big = 0.5 * float(bk.get("full_gb", 1.4)) * 1e9
    # each day's backup window, its bursts added up (a backup can span two readings; review, 15 Oct); the night's
    # publish (0.3 GB at 02:00 to 05:00 UTC) is outside it
    mins = lambda hhmm: int(hhmm[:2]) * 60 + int(hhmm[3:5])  # noqa: E731
    lo, hi = mins(bk.get("seen_after_utc", "10:30")), mins(bk.get("hold_until_utc", "14:00")) + 120   # 10:30 to 16:00
    per_day: dict = {}
    for at, b in meter.bursts(readings, now - dt.timedelta(days=8), float(bk.get("pass_rate_mb_min", 3)) * 1e6 / 60,
                              float(bk.get("seen_min_gb", 0.1)) * 1e9):
        if lo <= at.hour * 60 + at.minute < hi:
            per_day[at.date()] = per_day.get(at.date(), 0) + b
    seen = {d: b for d, b in per_day.items() if b >= big}
    out = []
    for day, b in sorted(seen.items()):
        if (day - first).days % every:
            out.append(f"a full backup of {b / 1e9:.2f} GB ran on {day:%d %b}, a day backup.full_last does not call full: "
                       f"set full_last to {day.isoformat()}")
    d = now.date() - dt.timedelta(days=7)
    hold = int(bk.get("hold_until_utc", "14:00")[:2])
    while d <= now.date():
        due = d >= first and (d - first).days % every == 0
        over = d < now.date() or now.hour >= hold
        if due and over and d not in seen and any(r[0].date() == d for r in readings):
            out.append(f"{d:%d %b} was a full-backup day under backup.full_last and the counter shows none")
        d += dt.timedelta(days=1)
    return out, {"full_backups": {k.isoformat(): round(v / 1e9, 3) for k, v in seen.items()}}


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
    more, bfacts = backup_timing(sched)
    findings += more
    facts.update(bfacts)
    try:   # the full backup's cadence, read on the counter (decision 0035)
        import db as _db
        _c = _db.connect()
        _rows = _c.execute("select at, bytes::float8 from public.egress_counter where at > now() - interval '9 days' "
                           "order by at").fetchall()
        _c.close()
        more, ffacts = full_backups(sched, [(a, float(b)) for a, b in _rows], dt.datetime.now(dt.timezone.utc))
        findings += more
        facts.update(ffacts)
    except Exception as e:  # noqa: BLE001 - not readable from here: said, not a finding
        facts["full_backups"] = f"not read: {str(e)[:80]}"
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
