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
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
HELPERS = os.path.expanduser("~/.claude/api_helpers")

PROJECT = "90cd4c29-797c-4552-90d9-81c3b9914ffa"
ENV = "f3a7784c-7cd9-4cb8-a9ea-05efe657a7ff"
OLD_COLLECTOR = "ff501aef-926d-4e24-8ef8-476855cd41b9"     # parked; this script must never deploy to it
NAME = "reddit-index-sweep"
REGION = "us-east4-eqdc4a"                                  # Virginia, next to the database (aws us-east-1)
DATA = ["categories.csv", "category-subreddits.csv", "brands.csv", "brand-aliases.csv", "alias-blocklist.csv",
        "english-words.txt"]
OPS = ["schedule.json", "classify_thresholds.json"]

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


def service_id(create: bool) -> str | None:
    d = gql("query($p:String!){ project(id:$p){ services { edges { node { id name } } } } }", {"p": PROJECT})
    for e in d["project"]["services"]["edges"]:
        if e["node"]["name"] == NAME:
            return e["node"]["id"]
    if not create:
        return None
    return gql("mutation($i:ServiceCreateInput!){ serviceCreate(input:$i){ id } }",
               {"i": {"projectId": PROJECT, "name": NAME}})["serviceCreate"]["id"]


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
    }
    missing = [k for k, x in v.items() if not x]
    if missing:
        raise SystemExit(f"missing values: {missing}")
    return v


def assemble(dest: str) -> None:
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
          "deploy": {"cronSchedule": sched["railway"]["cron"], "restartPolicyType": "NEVER",
                     "multiRegionConfig": {REGION: {"numReplicas": 1}}}}
    json.dump(rj, open(os.path.join(dest, "railway.json"), "w"), indent=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--vars-only", action="store_true")
    a = ap.parse_args()
    v = variables()
    with tempfile.TemporaryDirectory(prefix="ri-sweep-") as dest:
        assemble(dest)
        size = sum(os.path.getsize(os.path.join(p, f)) for p, _, fs in os.walk(dest) for f in fs)
        print(f"build folder: {size / 1e6:.1f} MB; variables: {sorted(v)}")
        if a.dry_run:
            print(open(os.path.join(dest, "railway.json")).read())
            return 0
        svc = service_id(create=True)
        if svc == OLD_COLLECTOR:
            raise SystemExit("refusing: that is the parked collector service")
        gql("mutation($i:VariableCollectionUpsertInput!){ variableCollectionUpsert(input:$i) }",
            {"i": {"projectId": PROJECT, "environmentId": ENV, "serviceId": svc, "variables": v,
                   "skipDeploys": True}})
        print(f"service {NAME} ({svc[:8]}): {len(v)} variables set")
        # Railway read this folder's railway.json (2026-10-02) and still deployed with no cron in Europe: the
        # cron, region and restart policy are service settings, copied into each deployment's manifest. Set
        # them on the service first (one field per call: a combined update was refused), so the deployment
        # below carries them.
        sched = json.load(open(os.path.join(ROOT, "ops", "schedule.json")))
        for field in ({"cronSchedule": sched["railway"]["cron"]}, {"restartPolicyType": "NEVER"},
                      {"multiRegionConfig": {REGION: {"numReplicas": 1}}}):
            gql("mutation($s:String!,$e:String!,$i:ServiceInstanceUpdateInput!){ "
                "serviceInstanceUpdate(serviceId:$s, environmentId:$e, input:$i) }", {"s": svc, "e": ENV, "i": field})
        print(f"service settings: cron {sched['railway']['cron']} UTC, region {REGION}, never restarted")
        if a.vars_only:
            return 0
        p = subprocess.run(["railway", "up", "-p", PROJECT, "-e", ENV, "-s", svc, "--ci"],
                           cwd=dest, capture_output=True, text=True, timeout=1800)
        tail = (p.stdout + p.stderr).strip().splitlines()[-15:]
        print("\n".join(tail))
        return p.returncode


if __name__ == "__main__":
    sys.exit(main())
