#!/usr/bin/env python3
"""Give the read API's database role (`ri_api`) a login, and hand the connection string to the site.

`ri_api` is created by migration 0039 with EXECUTE on api.threads and api.brands and nothing else, and a 15 s
statement timeout (decision 0040). This sets (or rotates) its password, keeps the connection string in
~/.claude/.reddit-index.json (0600) as `api_url`, and, with --vercel, writes it to the Vercel project as
DATABASE_URL_API for production and preview. The password is generated here and never printed.

  ops/api_role.py              # create the login if none is stored; store locally
  ops/api_role.py --rotate     # new password (then wait a minute: the pooler caches the old one)
  ops/api_role.py --vercel     # set DATABASE_URL_API on Vercel (production + preview); takes effect on the next deploy
  ops/api_role.py --check      # connect as ri_api and prove what it can and cannot reach

The role's password alone reads nothing: both functions check an API key's hash first (ops/api_keys.py).
"""
from __future__ import annotations

import argparse
import secrets
import string
import sys

from site_role import ROOT, _creds, _save, to_vercel  # noqa: F401  (ROOT puts worker/ on sys.path)


def rotate() -> str:
    import db
    c = _creds()
    pw = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(40))
    with db.connect() as conn:
        conn.autocommit = True
        # the password is alphanumeric, so quoting it is safe; ALTER ROLE cannot take a bind parameter
        conn.execute(f"alter role ri_api with login password '{pw}'")
    # The SESSION pooler (5432), for the reason ops/site_role.py gives.
    url = (f"postgresql://ri_api.{c['project_ref']}:{pw}@aws-0-{c.get('region', 'us-east-1')}"
           f".pooler.supabase.com:5432/postgres")
    c["api_url"] = url
    _save(c)
    print("ri_api can log in; connection string stored locally as api_url")
    return url


def check() -> int:
    import psycopg
    url = _creds().get("api_url")
    if not url:
        print("no api_url stored: run ops/api_role.py first"); return 2
    bad = 0
    with psycopg.connect(url, prepare_threshold=None, autocommit=True, connect_timeout=20) as conn:
        who = conn.execute("select current_user, current_setting('statement_timeout')").fetchone()
        print(f"connected as {who[0]}, statement timeout {who[1]}")
        nokey = "0" * 64
        for label, sql in [("api.brands() with an unknown key", f"select api.brands('{nokey}')"),
                           ("api.threads() with an unknown key", f"select api.threads('{nokey}', 'contabo')")]:
            try:
                r = conn.execute(sql).fetchone()[0]
                ok = r == {"error": "unauthorized"}
                bad += not ok
                print(f"  {'answers  ' if ok else 'WRONG    '} {label}: {r}")
            except Exception as e:  # noqa: BLE001
                bad += 1
                print(f"  CANNOT call {label}: {str(e).splitlines()[0][:100]}")
        for label, sql in [("api.api_keys", "select count(*) from api.api_keys"),
                           ("api._use_key()", f"select api._use_key('{nokey}')"),
                           ("public.mentions", "select count(*) from public.mentions"),
                           ("public.brands", "select count(*) from public.brands"),
                           ("site.brand_stats", "select count(*) from site.brand_stats"),
                           ("a write", "update api.api_keys set name = name")]:
            try:
                conn.execute(sql)
                bad += 1
                print(f"  CAN reach  {label}  <-- it must not")
            except Exception as e:  # noqa: BLE001
                print(f"  refused    {label}: {str(e).splitlines()[0][:70]}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vercel", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--rotate", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check()
    url = _creds().get("api_url")
    if a.rotate or not url:
        url = rotate()
    if a.vercel:
        to_vercel(url, key="DATABASE_URL_API")
    return 0


if __name__ == "__main__":
    sys.exit(main())
