#!/usr/bin/env python3
"""The go-live of decision 0017, as steps that refuse when their precondition is not met.

  ops/go_live.py preflight      # the gates: two scheduled nights measured under 1 GB with matching receipts,
                                #   schedule_check clean, the old collector parked; prints what is missing
  ops/go_live.py vercel         # production builds only when site code changes on main; data never builds
  ops/go_live.py point          # the sweep publishes to https://redditindex.com from now on (schedule + redeploy)
  ops/go_live.py verify         # fetch the production site: pages, boards, notice, freshness date, fingerprints

The pull requests are merged by hand between `vercel` and `point` (#5, #7, #8, in that order), so production
builds from main with the read path.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
sys.path.insert(0, os.path.join(ROOT, "ops"))
VERCEL_PROJECT = "prj_OhSRGKEKFeN2A9JU1BTeebdR6E29"
PROD = "https://redditindex.com"

# Exit 0 = skip the build, 1 = build (Vercel's Ignored Build Step). Only main builds, and only when something the
# site is built from changed. VERCEL_GIT_PREVIOUS_SHA is the last deployed commit; without it, build.
IGNORE_STEP = (
    'if [ "$VERCEL_GIT_COMMIT_REF" != "main" ]; then echo "previews are off (decision 0017)"; exit 0; fi; '
    'if [ -z "$VERCEL_GIT_PREVIOUS_SHA" ]; then exit 1; fi; '
    'if git diff --quiet "$VERCEL_GIT_PREVIOUS_SHA" HEAD -- . ":(exclude)worker" ":(exclude)ops" '
    '":(exclude)supabase" ":(exclude)docs" ":(exclude)decisions" ":(exclude)deploy" ":(exclude)*.md"; '
    'then echo "no site change: data never rebuilds the site (decision 0017)"; exit 0; else exit 1; fi')


def vercel(method: str, path: str, body: dict | None = None) -> dict:
    tok = json.load(open(os.path.expanduser("~/.claude/.vercel-empact.json")))["token"]
    req = urllib.request.Request("https://api.vercel.com" + path, method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json",
                                          "User-Agent": "Mozilla/5.0"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read() or b"{}")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"vercel {method} {path}: HTTP {e.code} {e.read().decode()[:300]}")


def preflight(nights=("2026-10-05", "2026-10-06")) -> int:
    """Two consecutive scheduled nights, each measured under 1 GB (ops/gate_meter.py), finished ok or capped,
    with the receipt's counts matching the database; and schedule_check clean. Night 1 (2026-10-04) does not
    count: its classify stage failed (Linux argument limit), fixed the same day."""
    missing = []
    for night in nights:
        p = os.path.join(ROOT, "docs", "go-live", f"egress-{night}.json")
        if not os.path.exists(p):
            missing.append(f"no measurement for the night of {night}")
            continue
        g = json.load(open(p))
        if not g.get("run_id"):
            missing.append(f"{night}: no scheduled run found")
        elif g.get("status") not in ("ok", "capped"):
            missing.append(f"{night}: run status {g.get('status')}: {g.get('problems')}")
        elif g.get("gate_under_1_gb") is not True:
            missing.append(f"{night}: egress {g.get('gate_egress_gb')} GB ({g.get('gate_source')}), not under the 1 GB gate")
        elif g.get("receipt_matches_database") is not True:
            missing.append(f"{night}: receipt does not match the database: {g.get('reconcile')}")
    sc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "schedule_check.py")], capture_output=True,
                        text=True)
    if sc.returncode != 0:
        missing.append("schedule_check has findings: " + sc.stdout[-400:])
    print(json.dumps({"ready": not missing, "missing": missing}, indent=1))
    return 0 if not missing else 1


def set_vercel() -> int:
    vercel("PATCH", f"/v9/projects/{VERCEL_PROJECT}", {"commandForIgnoringBuildStep": IGNORE_STEP})
    got = vercel("GET", f"/v9/projects/{VERCEL_PROJECT}").get("commandForIgnoringBuildStep")
    print("Ignored Build Step now:", got)
    return 0 if got == IGNORE_STEP else 1


def point() -> int:
    p = os.path.join(ROOT, "ops", "schedule.json")
    d = json.load(open(p))
    d["site_url"] = PROD
    d.pop("site_url_note", None)
    json.dump(d, open(p, "w"), indent=1)
    open(p, "a").write("\n")
    print("ops/schedule.json site_url ->", PROD, "; redeploying the sweep")
    return subprocess.run([sys.executable, os.path.join(ROOT, "ops", "deploy_sweep.py")]).returncode


def verify() -> int:
    import re
    bad = []

    def get(path: str) -> tuple[int, str]:
        req = urllib.request.Request(PROD + path, headers={"User-Agent": "Mozilla/5.0 (reddit-index go-live check)"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, ""
    import db
    with db.connect() as conn:
        sample = [r[0] for r in conn.execute("select slug from site.brand_stats order by total_mentions desc limit 5")]
        hashes = dict(conn.execute("select slug, page_hash from site.brand_stats where slug = any (%s)", (sample,)).fetchall())
        refreshed = conn.execute("select last_success_at from site.meta").fetchone()[0]
    for path in ["/", "/methodology/"] + [f"/{s}/" for s in sample]:
        st, html = get(path)
        ok = st == 200 and "Not affiliated with, endorsed by" in html
        slug = path.strip("/")
        if slug in hashes:
            m = re.search(r'name="ri-hash" content="([^"]+)"', html)
            ok = ok and m is not None
        print(f"  {path}: {st}{'' if ok else '  <-- problem'}")
        bad += [] if ok else [path]
    st, body = get("/freshness.json")
    print("  /freshness.json:", st, body[:120])
    if refreshed is None or '"refreshedAt":null' in body.replace(" ", ""):
        bad.append("no freshness date yet")
    st, _ = get("/this-brand-does-not-exist-zz/")
    print("  unknown slug:", st)
    bad += [] if st == 404 else ["unknown slug did not 404"]
    print(json.dumps({"ok": not bad, "problems": bad}))
    return 0 if not bad else 1


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    return {"preflight": preflight, "vercel": set_vercel, "point": point, "verify": verify}.get(
        cmd, lambda: (print(__doc__), 2)[1])()


if __name__ == "__main__":
    sys.exit(main())
