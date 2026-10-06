#!/usr/bin/env python3
"""Stop, start or inspect the Reddit Index's daily sweep in one step.

  python3 ops/ri.py status                  # the switch, the login, the last runs, the queue, the next run
  python3 ops/ri.py stop "reason"           # the sweep does nothing from its next check on
  python3 ops/ri.py start                   # switch on (publishing stays as it is)
  python3 ops/ri.py publish on|off          # whether the sweep tells the site about changed pages
  python3 ops/ri.py dayrun [calls] [HH:MM]  # one daytime pass on Railway now (default 10,000 calls, ends 21:30 UTC)

`stop` does two things, each enough on its own:
  * public.sweep_control.enabled = false. A running sweep reads it before every stage and every 25 subreddits
    and stops; a starting one records "skipped" and exits.
  * the sweep's database login is switched off (`alter role ri_sweep nologin`), so even a sweep that ignored
    the switch could not connect. Railway keeps the schedule; with no login it cannot touch the data.
`start` reverses both. Neither touches the site: it keeps serving what it has.

Runs on the laptop with the owner's database credentials (~/.claude/.reddit-index.json); the sweep's own role
cannot change the switch.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))


def status(conn) -> dict:
    sw = conn.execute("select enabled, publish_enabled, reason, updated_at from public.sweep_control").fetchone()
    login = conn.execute("select rolcanlogin from pg_roles where rolname = 'ri_sweep'").fetchone()[0]
    runs = conn.execute("select started_at, stage, status, notes->>'skipped', notes->>'egress_estimate_gb' "
                        "from public.pipeline_runs where stage in ('sweep', 'classify-backlog') "
                        "order by started_at desc limit 6").fetchall()
    meta = conn.execute("select last_success_at from site.meta").fetchone()
    out = {"switch": {"enabled": sw[0], "publish_enabled": sw[1], "reason": sw[2], "changed": str(sw[3])},
           "sweep_login": login,
           "last_success": str(meta[0]) if meta else None,
           "queue_to_classify": conn.execute("select count(*) from public.classify_queue").fetchone()[0],
           "pages_to_refresh": conn.execute("select count(*) from site.dirty_brand").fetchone()[0],
           "recent_runs": [f"{r[0]:%Y-%m-%d %H:%M} {r[1]} {r[2]}" + (f" ({r[3]})" if r[3] else "")
                           + (f" egress~{r[4]} GB" if r[4] else "") for r in runs]}
    try:
        sys.path.insert(0, os.path.join(ROOT, "ops"))
        import deploy_sweep as d
        svc = d.service_id(create=False)
        if svc:
            si = d.gql("query($s:String!,$e:String!){ serviceInstance(serviceId:$s, environmentId:$e){ "
                       "cronSchedule nextCronRunAt } }", {"s": svc, "e": d.ENV})["serviceInstance"]
            out["railway"] = si
    except Exception as e:  # noqa: BLE001
        out["railway"] = f"not read: {str(e)[:80]}"
    return out


def dayrun(calls: int, end_by: str) -> int:
    """A daytime pass on Railway (Vlad, 2026-10-05: move on with the data collection). Writes the request row
    (migration 0023) through Supabase's Management API, so it works from a network that blocks the database port,
    then starts the sweep's Railway service once. The sweep consumes the request; without one it refuses."""
    import urllib.request
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    sys.path.insert(0, os.path.join(ROOT, "ops"))
    import investigation_2026_10 as inv
    import deploy_sweep as d
    sql = (f"insert into public.day_run_request (max_calls, end_by_utc) values ({int(calls)}, '{end_by}'::time) "
           f"returning requested_at")
    req = urllib.request.Request(f"https://api.supabase.com/v1/projects/{inv.REF}/database/query", method="POST",
                                 data=json.dumps({"query": sql}).encode(),
                                 headers={"Authorization": "Bearer " + inv._mgmt_token(),
                                          "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    print("requested:", json.loads(urllib.request.urlopen(req, timeout=120).read()))
    svcs = d.gql("query($p:String!){ project(id:$p){ services { edges { node { id name } } } } }",
                 {"p": d.PROJECT})["project"]["services"]["edges"]
    sid = [e["node"]["id"] for e in svcs if e["node"]["name"] == d.NAME][0]
    si = d.gql("query($s:String!,$e:String!){ serviceInstance(serviceId:$s, environmentId:$e){ id } }",
               {"s": sid, "e": d.ENV})["serviceInstance"]["id"]
    out = d.gql("mutation($i: DeploymentInstanceExecutionCreateInput!){ deploymentInstanceExecutionCreate(input: $i) }",
                {"i": {"serviceInstanceId": si}})
    print("started on Railway:", out)
    return 0


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "dayrun":
        return dayrun(int(sys.argv[2]) if len(sys.argv) > 2 else 10000, sys.argv[3] if len(sys.argv) > 3 else "21:30")
    if len(sys.argv) < 2 or sys.argv[1] not in ("status", "stop", "start", "publish"):
        print(__doc__)
        return 2
    import db
    cmd = sys.argv[1]
    with db.connect() as conn:
        conn.autocommit = True
        if cmd == "stop":
            reason = " ".join(sys.argv[2:]) or "stopped by hand"
            with conn.transaction():
                conn.execute("update public.sweep_control set enabled = false, reason = %s, updated_at = now()",
                             (reason,))
                conn.execute("alter role ri_sweep nologin")
            print(f"stopped: {reason}")
        elif cmd == "start":
            with conn.transaction():
                conn.execute("update public.sweep_control set enabled = true, reason = 'started by hand', "
                             "updated_at = now()")
                conn.execute("alter role ri_sweep login")
            print("started: the next scheduled run works")
        elif cmd == "publish":
            on = len(sys.argv) > 2 and sys.argv[2] == "on"
            conn.execute("update public.sweep_control set publish_enabled = %s, updated_at = now()", (on,))
            print(f"publishing {'on' if on else 'off'}")
        print(json.dumps(status(conn), indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
