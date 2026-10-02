#!/usr/bin/env python3
"""Run tests/site-parity.test.tsx: the old build's read path against the new tables. ONE corpus read (~0.2 GB).

Takes the site's read-only connection string from Vercel (never printed) and hands it to vitest in the
environment. RAIL_ALLOW_STALE=1 because the old rail is deliberately not refreshed: the comparison marks the
brands whose cards are expected to differ.
"""
import json, os, subprocess, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRJ = "prj_OhSRGKEKFeN2A9JU1BTeebdR6E29"


def main() -> int:
    tok = json.load(open(os.path.expanduser("~/.claude/.vercel-empact.json")))["token"]
    def get(path):
        req = urllib.request.Request("https://api.vercel.com" + path,
                                     headers={"Authorization": "Bearer " + tok, "User-Agent": "Mozilla/5.0"})
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    env_id = next(e["id"] for e in get(f"/v9/projects/{PRJ}/env")["envs"] if e["key"] == "DATABASE_URL_READONLY")
    url = get(f"/v1/projects/{PRJ}/env/{env_id}")["value"]
    dump = os.path.join(ROOT, "worker", ".cache", "parity", "site.json")
    if not os.path.exists(dump):
        print("run ops/parity_dump.py first"); return 2
    env = {**os.environ, "DATABASE_URL_READONLY": url, "RAIL_ALLOW_STALE": "1", "RI_PARITY_DUMP": dump}
    return subprocess.call(["pnpm", "exec", "vitest", "run", "tests/site-parity.test.tsx"], cwd=ROOT, env=env)


if __name__ == "__main__":
    sys.exit(main())
