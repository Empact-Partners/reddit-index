#!/usr/bin/env python3
"""Give the site's database role (`ri_site`) a login, and hand the connection string to the site.

`ri_site` is created by migration 0007 with SELECT on schema `site` only and a 5 s statement timeout. This
sets (or rotates) its password, keeps the connection string in ~/.claude/.reddit-index.json (0600) as
`site_url` for local builds, and, with --vercel, writes it to the Vercel project as DATABASE_URL_SITE for
production and preview. The password is generated here and never printed.

  ops/site_role.py              # create or rotate the login; store locally
  ops/site_role.py --vercel     # also set DATABASE_URL_SITE on Vercel (production + preview)
  ops/site_role.py --check      # connect as ri_site and prove what it can and cannot read
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import string
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
CREDS = os.path.expanduser("~/.claude/.reddit-index.json")
VERCEL_PROJECT = "prj_OhSRGKEKFeN2A9JU1BTeebdR6E29"


def _creds() -> dict:
    return json.load(open(CREDS))


def _save(d: dict) -> None:
    tmp = CREDS + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(d, f, indent=1)
    os.replace(tmp, CREDS)


def rotate() -> str:
    import db
    c = _creds()
    pw = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(40))
    with db.connect() as conn:
        conn.autocommit = True
        # the password is alphanumeric, so quoting it is safe; ALTER ROLE cannot take a bind parameter
        conn.execute(f"alter role ri_site with login password '{pw}'")
    url = (f"postgresql://ri_site.{c['project_ref']}:{pw}@aws-0-{c.get('region', 'us-east-1')}"
           f".pooler.supabase.com:6543/postgres")
    c["site_url"] = url
    _save(c)
    print("ri_site can log in; connection string stored locally as site_url")
    return url


def to_vercel(url: str) -> None:
    tok = json.load(open(os.path.expanduser("~/.claude/.vercel-empact.json")))["token"]

    def call(method: str, path: str, body: dict | None = None) -> dict:
        req = urllib.request.Request("https://api.vercel.com" + path, method=method,
                                     data=json.dumps(body).encode() if body else None,
                                     headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json",
                                              "User-Agent": "Mozilla/5.0"})
        try:
            return json.loads(urllib.request.urlopen(req, timeout=60).read() or b"{}")
        except urllib.error.HTTPError as e:
            raise SystemExit(f"vercel {method} {path}: HTTP {e.code} {e.read().decode()[:200].replace(url, '<redacted>')}")

    call("POST", f"/v10/projects/{VERCEL_PROJECT}/env?upsert=true",
         {"key": "DATABASE_URL_SITE", "value": url, "type": "encrypted", "target": ["production", "preview"]})
    names = sorted({e["key"] for e in call("GET", f"/v9/projects/{VERCEL_PROJECT}/env").get("envs", [])})
    print("vercel env now has:", names)


def check() -> int:
    import psycopg
    url = _creds().get("site_url")
    if not url:
        print("no site_url stored: run ops/site_role.py first"); return 2
    bad = 0
    with psycopg.connect(url, prepare_threshold=None, autocommit=True, connect_timeout=20) as conn:
        who = conn.execute("select current_user, current_setting('statement_timeout')").fetchone()
        print(f"connected as {who[0]}, statement timeout {who[1]}")
        for label, sql in [("site.brand_stats", "select count(*) from site.brand_stats"),
                           ("site.rail_card (one brand)", "select count(*) from site.rail_card where brand_slug = 'hubspot'"),
                           ("site.meta", "select count(*) from site.meta"),
                           ("site.methodology_params", "select count(*) from site.methodology_params")]:
            try:
                print(f"  can read   {label}: {conn.execute(sql).fetchone()[0]} rows")
            except Exception as e:  # noqa: BLE001
                bad += 1
                print(f"  CANNOT read {label}: {str(e).splitlines()[0][:100]}")
        for label, sql in [("public.mentions", "select count(*) from public.mentions"),
                           ("published.mentions", "select count(*) from published.mentions"),
                           ("public.mention_rail_mv", "select count(*) from public.mention_rail_mv"),
                           ("site.rail_key (the table behind the view)", "select count(*) from site.rail_key"),
                           ("site.refresh_brand()", "select site.refresh_brand(1)"),
                           ("a write", "update site.meta set updated_at = now()")]:
            try:
                conn.execute(sql).fetchone() if sql.startswith("select") else conn.execute(sql)
                bad += 1
                print(f"  CAN reach  {label}  <-- it must not")
            except Exception as e:  # noqa: BLE001
                print(f"  refused    {label}: {str(e).splitlines()[0][:70]}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vercel", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check()
    url = rotate()
    if a.vercel:
        to_vercel(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
