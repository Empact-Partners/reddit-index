#!/usr/bin/env python3
"""Read or clear Vercel's Attack Challenge Mode on the reddit-index project.

WHY THIS EXISTS
    On 2026-08-17 at 21:05 UTC every request to redditindex.com started coming
    back `403` with `x-vercel-mitigated: challenge` — Vercel's interstitial,
    which makes a static site feel broken and slow to a human. Nobody turned it
    on: the firewall events record it as `system-action`, Vercel's own
    automatic mitigation, and the project's firewall config was empty the whole
    time. It cleared in seconds once the flag was written back to false.

    The dashboard is the normal way to do that. This exists because the flag is
    not visible in the project settings API, the toggle has no GET, and at 3am
    the useful thing is one command:

        python3 scripts/attack-mode.py            # what is the site serving?
        python3 scripts/attack-mode.py --off      # clear the challenge

    Credentials: ~/.claude/.vercel-empact.json (team-scoped token, 0600).
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

TEAM = "team_YDjSLKf93n88onmsyKisSKgC"          # Empact Partners
PROJECT = "prj_OhSRGKEKFeN2A9JU1BTeebdR6E29"    # reddit-index
CRED = os.path.expanduser("~/.claude/.vercel-empact.json")
SITE = "https://redditindex.com/"


def token():
    return json.load(open(CRED))["token"]


def api(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        "https://api.vercel.com" + path, data=data, method=method,
        headers={"Authorization": f"Bearer {token()}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:300]}


def probe():
    """What a visitor actually gets. The flag is not observable through the
    API, so the site's own response IS the reading."""
    out = subprocess.run(
        ["curl", "-sS", "-o", "/dev/null", "-D", "-", "-w",
         "%{http_code} %{time_starttransfer}", SITE],
        capture_output=True, text=True, timeout=60)
    headers = out.stdout.lower()
    code, ttfb = out.stdout.strip().splitlines()[-1].split()
    return {"status": int(code), "ttfb_s": float(ttfb),
            "challenged": "x-vercel-mitigated" in headers}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--off", action="store_true", help="clear attack challenge mode")
    args = ap.parse_args()

    before = probe()
    print(f"site: HTTP {before['status']} · ttfb {before['ttfb_s']:.2f}s · "
          f"{'CHALLENGED' if before['challenged'] else 'clean'}")

    if not args.off:
        if before["challenged"]:
            print("run again with --off to clear it")
        return 0 if not before["challenged"] else 1

    st, body = api(f"/v1/security/attack-mode?teamId={TEAM}", "POST",
                   {"projectId": PROJECT, "attackModeEnabled": False})
    print(f"attack-mode POST -> {st} {json.dumps(body)[:120]}")
    after = probe()
    print(f"site: HTTP {after['status']} · ttfb {after['ttfb_s']:.2f}s · "
          f"{'STILL CHALLENGED' if after['challenged'] else 'clean'}")
    return 1 if after["challenged"] else 0


if __name__ == "__main__":
    sys.exit(main())
