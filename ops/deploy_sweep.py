#!/usr/bin/env python3
"""Deploy the daily sweep to its own Railway service, reddit-index-sweep, from a folder built for it.

Why a separate folder: the repository root's railway.json belongs to the old collector service, parked on
2026-10-02 because Railway kept re-running it (decision 0016). Deploying the sweep from the root would hand that
service's settings to this one, or the other way round. This script copies exactly what the image needs into a
temporary folder with its own railway.json, and deploys that folder to the sweep service only.

What it sets on the service (read from the local credential files, never printed):
  SUPABASE_*            the ri_sweep login (ops/sweep_role.py), session pooler, port 5432
  REDDIT_*              the Reddit app (today the shared one; 01-legal.md wants a dedicated one: owner step)
  TYPESAFE_API_KEY      Jev
  ZAI_API_KEY           GLM, through the Codex CLI
  SLACK_BOT_TOKEN       the Empact bot, for the one DM a failed or capped run sends
  REVALIDATE_SECRET     the site's page-expiry endpoint
  VERCEL_BYPASS         the preview's protection bypass (trial runs only)

The schedule (cron, region, restart policy) is declared once, in ops/schedule.json, and set on the service before
every deploy. Railway copies it into each DEPLOYMENT's manifest and runs the newest manifest's cron, so
scripts/schedule_check.py compares the newest deployment's manifest with ops/schedule.json after every deploy.
A deploy also starts the container once; outside the run window the sweep refuses and exits.

  ops/deploy_sweep.py --dry-run     # build the folder, print what would be set (names only), deploy nothing
  ops/deploy_sweep.py               # create the service if missing, set variables, deploy
  ops/deploy_sweep.py --vars-only   # set variables, no new deployment
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
HELPERS = os.path.expanduser("~/.claude/api_helpers")

PROJECT = "90cd4c29-797c-4552-90d9-81c3b9914ffa"
ENV = "f3a7784c-7cd9-4cb8-a9ea-05efe657a7ff"
OLD_COLLECTOR = "ff501aef-926d-4e24-8ef8-476855cd41b9"     # parked; this script must never deploy to it
NAME = "reddit-index-sweep"
DAY_NAME = "reddit-index-day"                               # the daytime passes' requester (ops/day_tick.py)
DAY_START = "python3 -u /app/ops/day_tick.py"
REGION = "us-east4-eqdc4a"                                  # Virginia, next to the database (aws us-east-1)
DATA = ["categories.csv", "category-subreddits.csv", "brands.csv", "brand-aliases.csv", "alias-blocklist.csv",
        "alias-hostile.csv", "english-words.txt"]
OPS = ["schedule.json", "classify_thresholds.json", "retention.py",   # retention.py: the nightly retention stage
       "day_tick.py"]                                                  # the day service's start command

TOKENS_SHIM = '''"""The one function the vendored Jev client needs, reading the container's environment."""
import os


def typesafe_key() -> str:
    return os.environ["TYPESAFE_API_KEY"]
'''


def gql(query: str, variables: dict) -> dict:
    subprocess.run(["railway", "whoami"], capture_output=True, timeout=60)   # refreshes the access token
    tok = json.load(open(os.path.expanduser("~/.railway/config.json")))["user"]["accessToken"]
    req = urllib.request.Request("https://backboard.railway.com/graphql/v2",
                                 data=json.dumps({"query": query, "variables": variables}).encode(),
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json",
                                          "User-Agent": "Mozilla/5.0"})
    try:
        out = json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"railway: HTTP {e.code} {e.read().decode()[:400]}")
    if out.get("errors"):
        raise SystemExit("railway: " + json.dumps(out["errors"])[:300])
    return out["data"]


def service_id(create: bool, name: str = NAME) -> str | None:
    d = gql("query($p:String!){ project(id:$p){ services { edges { node { id name } } } } }", {"p": PROJECT})
    for e in d["project"]["services"]["edges"]:
        if e["node"]["name"] == name:
            return e["node"]["id"]
    if not create:
        return None
    return gql("mutation($i:ServiceCreateInput!){ serviceCreate(input:$i){ id } }",
               {"i": {"projectId": PROJECT, "name": name}})["serviceCreate"]["id"]


def variables() -> dict:
    c = json.load(open(os.path.expanduser("~/.claude/.reddit-index.json")))
    import reddit_client as rc
    sys.path.insert(0, HELPERS)
    import tokens
    zai = json.load(open(os.path.expanduser("~/.claude/.zai.json")))["api_key"]
    v = {
        "SUPABASE_PROJECT_REF": c["project_ref"], "SUPABASE_REGION": c.get("region", "us-east-1"),
        "SUPABASE_DB_USER": f"ri_sweep.{c['project_ref']}", "SUPABASE_DB_PASSWORD": c["sweep_password"],
        "SUPABASE_DB_PORT": "5432",
        "REDDIT_CLIENT_ID": rc.CLIENT_ID, "REDDIT_CLIENT_SECRET": rc.CLIENT_SECRET,
        "REDDIT_USER_AGENT": rc.USER_AGENT,
        "TYPESAFE_API_KEY": tokens.typesafe_key(), "ZAI_API_KEY": zai,
        "SLACK_BOT_TOKEN": tokens.slack_bot_token("empact"),
        "REVALIDATE_SECRET": c["revalidate_secret"],
        # the node's metrics endpoint: the sweep reads its own egress on the counter the watchdog follows (decision
        # 0025). The endpoint takes only the service key on this project (a dedicated secret key answered 401).
        "SUPABASE_METRICS_KEY": c["metrics_key"],
        "VERCEL_BYPASS": c["vercel_bypass"],      # only used against *.vercel.app (the trial runs' preview)
        # 1.2 s between Reddit calls = 50 a minute, the declared pace (the shared app drew 429s above ~54)
        "RI_SLEEP": str(json.load(open(os.path.join(ROOT, "ops", "schedule.json")))["reddit_pace_seconds"]),
    }
    missing = [k for k, x in v.items() if not x]
    if missing:
        raise SystemExit(f"missing values: {missing}")
    return v


def assemble(dest: str, cron: str | None = None, start: str | None = None) -> None:
    """The build folder. `cron` and `start`: the service's own schedule and start command (default: the sweep's
    cron and the image's CMD, worker/run_daily.py)."""
    sched = json.load(open(os.path.join(ROOT, "ops", "schedule.json")))
    shutil.copy(os.path.join(ROOT, "deploy", "sweep", "Dockerfile"), dest)
    shutil.copytree(os.path.join(ROOT, "worker"), os.path.join(dest, "worker"),
                    ignore=shutil.ignore_patterns(".cache", "__pycache__", "artifacts", "*.log", "launchd", "*.jsonl"))
    os.makedirs(os.path.join(dest, "data"))
    for f in DATA:
        shutil.copy(os.path.join(ROOT, "data", f), os.path.join(dest, "data", f))
    os.makedirs(os.path.join(dest, "ops"))
    for f in OPS:
        shutil.copy(os.path.join(ROOT, "ops", f), os.path.join(dest, "ops", f))
    os.makedirs(os.path.join(dest, "api_helpers"))
    shutil.copy(os.path.join(HELPERS, "typesafe.py"), os.path.join(dest, "api_helpers", "typesafe.py"))
    open(os.path.join(dest, "api_helpers", "tokens.py"), "w").write(TOKENS_SHIM)
    os.makedirs(os.path.join(dest, "codex-zai"))
    cfg = ['model_provider = "ZAI"', 'model = "glm-5.3"', 'model_reasoning_effort = "low"',
           'model_catalog_json = "/app/codex-zai/models.json"', "",
           "[model_providers.ZAI]", 'name = "ZAI"', 'base_url = "https://api.z.ai/api/v1"',
           'wire_api = "responses"', 'env_key = "ZAI_API_KEY"']
    open(os.path.join(dest, "codex-zai", "config.toml"), "w").write("\n".join(cfg) + "\n")
    shutil.copy(os.path.expanduser("~/.codex-zai/models.json"), os.path.join(dest, "codex-zai", "models.json"))
    rj = {"$schema": "https://railway.com/railway.schema.json",
          "build": {"builder": "DOCKERFILE", "dockerfilePath": "Dockerfile"},
          "deploy": {"cronSchedule": cron or sched["railway"]["cron"], "restartPolicyType": "NEVER",
                     "multiRegionConfig": {REGION: {"numReplicas": 1}}}}
    if start:
        rj["deploy"]["startCommand"] = start
    json.dump(rj, open(os.path.join(dest, "railway.json"), "w"), indent=1)


DEPLOY_MINUTES = 6   # a build and its switch-over take about four minutes; the margin is the rest


def safe_to_deploy(key: str, now: dt.datetime) -> tuple[bool, str]:
    """A new deployment of a cron service stops the execution the old one is running ("Stopping Container"). On
    12 Oct at 18:12 UTC a deploy of the day service stopped the pass its 18:00 tick had started. So a service is
    deployed only where none of its starts can fall inside the next DEPLOY_MINUTES: the day service's ticks are at
    :00 and :30 from 06:00 to 21:30 UTC, the night service starts at 00:00 UTC."""
    mins = now.hour * 60 + now.minute
    if key == "day":
        if 5 * 60 + 54 <= mins <= 21 * 60 + 31 and (now.minute % 30) > 30 - DEPLOY_MINUTES:
            return False, f"the day service ticks at :{(now.minute // 30 + 1) * 30 % 60:02d} UTC"
        if 5 * 60 + 54 <= mins <= 21 * 60 + 31 and (now.minute % 30) < 1:
            return False, "the day service is ticking now"
        return True, ""
    if mins >= 24 * 60 - DEPLOY_MINUTES or mins < 1:
        return False, "the night's run starts at 00:00 UTC"
    return True, ""


def open_runs() -> int | None:
    """Sweep runs or retention steps still running (receipts younger than 6 hours with no end). None: unknown."""
    try:
        import watch_link as w
        return int(w.query("select count(*) n from public.pipeline_runs where finished_at is null and stage in "
                           "('sweep', 'retention') and started_at > now() - interval '6 hours'")[0]["n"])
    except Exception:  # noqa: BLE001
        return None


def wait_for_a_gap(key: str, force: bool, max_wait_s: int = 1800) -> None:
    """Refuse while a run is open; wait (at most half an hour) out of a window where a start could be cut off."""
    if force:
        return
    n = open_runs()
    if n is None:
        raise SystemExit("refusing: could not read whether a run is open (watch_link). --force deploys anyway.")
    if n:
        raise SystemExit(f"refusing: {n} run(s) open. A deploy stops a running pass or night run. Wait for it to "
                         f"end, or --force.")
    end = time.time() + max_wait_s
    while True:
        ok, why = safe_to_deploy(key, dt.datetime.now(dt.timezone.utc))
        if ok:
            break
        if time.time() > end:
            raise SystemExit(f"refusing: still no gap after {max_wait_s // 60} minutes ({why})")
        print(f"waiting: {why}; a deploy now could stop the run it starts", flush=True)
        time.sleep(30)
    if open_runs():   # a tick may have started one while this waited
        raise SystemExit("refusing: a run opened while waiting for a gap")


def deploy_one(name: str, cron: str, start: str | None, v: dict, dry_run: bool, vars_only: bool) -> int:
    with tempfile.TemporaryDirectory(prefix="ri-sweep-") as dest:
        assemble(dest, cron, start)
        size = sum(os.path.getsize(os.path.join(p, f)) for p, _, fs in os.walk(dest) for f in fs)
        print(f"{name}: build folder {size / 1e6:.1f} MB; variables: {sorted(v)}")
        if dry_run:
            print(open(os.path.join(dest, "railway.json")).read())
            return 0
        svc = service_id(create=True, name=name)
        if svc == OLD_COLLECTOR:
            raise SystemExit("refusing: that is the parked collector service")
        gql("mutation($i:VariableCollectionUpsertInput!){ variableCollectionUpsert(input:$i) }",
            {"i": {"projectId": PROJECT, "environmentId": ENV, "serviceId": svc, "variables": v,
                   "skipDeploys": True}})
        print(f"service {name} ({svc[:8]}): {len(v)} variables set")
        # Railway read this folder's railway.json (2026-10-02) and still deployed with no cron in Europe: the
        # cron, region and restart policy are service settings, copied into each deployment's manifest. Set
        # them on the service first (one field per call: a combined update was refused), so the deployment
        # below carries them.
        fields = [{"cronSchedule": cron}, {"restartPolicyType": "NEVER"},
                  {"multiRegionConfig": {REGION: {"numReplicas": 1}}}]
        if start:
            fields.append({"startCommand": start})
        for field in fields:
            gql("mutation($s:String!,$e:String!,$i:ServiceInstanceUpdateInput!){ "
                "serviceInstanceUpdate(serviceId:$s, environmentId:$e, input:$i) }", {"s": svc, "e": ENV, "i": field})
        print(f"service settings: cron {cron} UTC, region {REGION}, never restarted"
              + (f", start command {start}" if start else ""))
        if vars_only:
            return 0
        p = subprocess.run(["railway", "up", "-p", PROJECT, "-e", ENV, "-s", svc, "--ci"],
                           cwd=dest, capture_output=True, text=True, timeout=1800)
        tail = (p.stdout + p.stderr).strip().splitlines()[-15:]
        print("\n".join(tail))
        return p.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--vars-only", action="store_true")
    ap.add_argument("--only", choices=["sweep", "day"], help="deploy one of the two services (default: both)")
    ap.add_argument("--force", action="store_true",
                    help="deploy even with a run open or a start due within minutes (it stops that run)")
    a = ap.parse_args()
    v = variables()
    sched = json.load(open(os.path.join(ROOT, "ops", "schedule.json")))
    # the same image, two services: the night's run on its cron, and the daytime passes' tick (decision 0026)
    services = [("sweep", NAME, sched["railway"]["cron"], None), ("day", DAY_NAME, sched["day"]["cron"], DAY_START)]
    rc = 0
    for key, name, cron, start in services:
        if a.only and a.only != key:
            continue
        if not (a.dry_run or a.vars_only):
            wait_for_a_gap(key, a.force)
        rc = deploy_one(name, cron, start, v, a.dry_run, a.vars_only) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
