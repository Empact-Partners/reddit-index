#!/usr/bin/env python3
"""Publish = rebuild. Trigger a production build of the CURRENT commit.

The site is fully static: every route is prerendered from one database read at
build time, so new data reaches redditindex.com only when Vercel builds again.
The nightly chain therefore has to ask for a build after it scores.

It used to ask by pushing an EMPTY COMMIT, because a deploy hook has to be
created by hand in the dashboard and never was. That works — Vercel builds
every push — but it writes a commit a day into the repository's history for
nothing, and a year of "daily publish 2026-08-17" is 365 commits that record
no change to the code.

This asks Vercel directly: take the newest production deployment and rebuild
it from the same commit. Same result, no history noise, and it reports the
deployment id so a failed publish is visible in the chain's log rather than
inferred from a stale site.

    python3 worker/publish.py             # rebuild, wait for READY
    python3 worker/publish.py --no-wait   # fire and return
    python3 worker/publish.py --status    # what is live right now

Credentials: ~/.claude/.vercel-empact.json (team-scoped token, 0600).
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

TEAM = "team_YDjSLKf93n88onmsyKisSKgC"          # Empact Partners
PROJECT_ID = "prj_OhSRGKEKFeN2A9JU1BTeebdR6E29"  # reddit-index
PROJECT = "reddit-index"
CRED = os.path.expanduser("~/.claude/.vercel-empact.json")


def api(path, method="GET", body=None):
    tok = json.load(open(CRED))["token"]
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        "https://api.vercel.com" + path, data=data, method=method,
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:400]}


def latest_production():
    st, d = api(f"/v6/deployments?projectId={PROJECT_ID}&teamId={TEAM}"
                f"&target=production&limit=1")
    if st != 200 or not d.get("deployments"):
        return None
    return d["deployments"][0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--timeout", type=int, default=2400,
                    help="seconds to wait for READY (a 4,000-page build is slow)")
    args = ap.parse_args()

    prev = latest_production()
    if not prev:
        print("could not read the current production deployment", flush=True)
        return 1
    sha = (prev.get("meta") or {}).get("githubCommitSha", "")[:8]
    print(f"current production: {prev['uid']} {prev.get('state')} commit {sha}", flush=True)
    if args.status:
        return 0

    st, dep = api(f"/v13/deployments?teamId={TEAM}&forceNew=1", "POST", {
        "name": PROJECT,
        "project": PROJECT_ID,
        "target": "production",
        "deploymentId": prev["uid"],      # rebuild THIS commit, with fresh data
        "meta": {"trigger": "reddit-index-daily-chain"},
    })
    if st not in (200, 201) or not dep.get("id"):
        print(f"publish FAILED ({st}): {json.dumps(dep)[:300]}", flush=True)
        return 1
    print(f"building {dep['id']} -> {dep.get('url')}", flush=True)
    if args.no_wait:
        return 0

    t0 = time.time()
    while time.time() - t0 < args.timeout:
        time.sleep(20)
        st, d = api(f"/v13/deployments/{dep['id']}?teamId={TEAM}")
        state = d.get("status") or d.get("readyState")
        if state in ("READY", "ERROR", "CANCELED"):
            mins = (time.time() - t0) / 60
            print(f"{state} in {mins:.1f} min", flush=True)
            if state == "READY":
                return 0
            # A BUILD THAT LOST A RACE IS NOT A FAILED PUBLISH. Every git push to
            # this repo triggers its own GitHub-integration build, and on
            # 2026-08-25 twelve pushes in one night meant three builds in flight
            # at once; one was superseded and came back ERROR while a sibling
            # deployment of the same commit went READY and carried the same data
            # (verified on the rendered page). ship_batch runs publish with
            # fatal=False, so a false failure here is silent — it just makes the
            # log claim a publish failed when the site is current.
            # Only forgive it when a NEWER deployment is actually READY: that is
            # the difference between "someone else shipped it" and "nothing
            # shipped". A genuine build break still returns 1.
            ok, lst = api(f"/v6/deployments?limit=8&projectId={PROJECT_ID}&teamId={TEAM}")
            newer = [d for d in (lst.get("deployments") or [])
                     if d.get("created", 0) > dep.get("createdAt", 0)
                     and d.get("state") == "READY"]
            if newer:
                print(f"  superseded: {newer[0].get('uid')} is READY and newer — "
                      f"the site has this data, not treating as a failed publish",
                      flush=True)
                return 0
            return 1
    print(f"still building after {args.timeout}s — not waiting further", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
