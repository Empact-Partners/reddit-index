#!/usr/bin/env python3
"""Give the sweep's database role (`ri_sweep`) a login, and prove it can do every stage's work and nothing else.

`ri_sweep` is created NOLOGIN by migration 0015 with exactly the grants the daily sweep needs. This sets (or
rotates) its password and keeps it in ~/.claude/.reddit-index.json (0600) as `sweep_password`; the Railway
service gets it through ops/deploy_sweep.py. The password is generated here and never printed.

Stopping the sweep in one step (ops/ri.py stop) turns the login off again: `alter role ri_sweep nologin`.

  ops/sweep_role.py              # create the login if none is stored
  ops/sweep_role.py --rotate     # new password (wait a minute before a run: the pooler caches the old one)
  ops/sweep_role.py --check      # connect as ri_sweep and prove what it can and cannot do
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import string
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
sys.path.insert(0, os.path.join(ROOT, "ops"))
from site_role import CREDS, _creds, _save  # noqa: E402

# What the stages do, table by table (worker/takedown.py, collect.py, classify_sweep.py, run_daily.py,
# site_score.py, site_publish.py and the triggers their writes fire).
MUST = [
    ("public.mentions", "select"), ("public.mentions", "insert"), ("public.mentions", "delete"),
    ("public.threads", "insert"), ("public.threads", "update"), ("public.ingest_state", "update"),
    ("public.mention_sentiment", "insert"), ("public.mention_sentiment", "delete"),
    ("public.mention_rejections", "insert"), ("public.mention_rejections", "delete"),
    ("public.removals", "insert"), ("public.removals", "update"),
    ("public.doc_probe", "insert"), ("public.doc_probe", "delete"),
    ("public.classify_queue", "insert"), ("public.classify_queue", "update"), ("public.classify_queue", "delete"),
    ("public.pipeline_runs", "insert"), ("public.pipeline_runs", "update"),
    ("public.sweep_control", "select"), ("public.brands", "select"), ("public.subreddits", "select"),
    ("site.brand_stats", "update"), ("site.dirty_brand", "delete"), ("site.rail_key", "insert"),
    ("site.retired_page", "update"), ("site.meta", "update"),
]
MUST_NOT = [
    ("public.brands", "update"), ("public.brands", "delete"), ("public.sweep_control", "update"),
    ("public.removals", "delete"), ("public.categories", "update"), ("public.subreddits", "delete"),
]
FUNCTIONS = ["site.refresh_brand(bigint)", "site.refresh_dirty(integer)", "site.compute_index_hashes()"]


def url() -> str:
    c = _creds()
    return (f"postgresql://ri_sweep.{c['project_ref']}:{c['sweep_password']}@aws-0-{c.get('region', 'us-east-1')}"
            f".pooler.supabase.com:5432/postgres")


def rotate() -> None:
    import db
    c = _creds()
    pw = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(40))
    with db.connect() as conn:
        conn.autocommit = True
        conn.execute(f"alter role ri_sweep with login password '{pw}'")   # alphanumeric: safe to inline
    c["sweep_password"] = pw
    _save(c)
    print("ri_sweep can log in; password stored locally as sweep_password")


def check() -> int:
    import psycopg
    if not _creds().get("sweep_password"):
        print("no sweep_password stored: run ops/sweep_role.py first")
        return 2
    bad = 0
    with psycopg.connect(url(), prepare_threshold=None, autocommit=True, connect_timeout=20) as conn:
        who = conn.execute("select current_user, current_setting('statement_timeout')").fetchone()
        print(f"connected as {who[0]}, statement timeout {who[1]}")
        for rel, priv in MUST + [(r, p) for r, p in MUST_NOT]:
            ok = conn.execute("select has_table_privilege(%s, %s)", (rel, priv)).fetchone()[0]
            want = (rel, priv) in MUST
            if ok != want:
                bad += 1
            print(f"  {'ok ' if ok == want else 'BAD'}  {priv:<6} {rel}: {'granted' if ok else 'refused'}")
        for fn in FUNCTIONS:
            ok = conn.execute("select has_function_privilege(%s, 'execute')", (fn,)).fetchone()[0]
            bad += not ok
            print(f"  {'ok ' if ok else 'BAD'}  execute {fn}")
        try:
            w = conn.execute("select wal_bytes from pg_stat_wal").fetchone()[0]
            print(f"  ok   reads pg_stat_wal (the egress estimate): {int(w) > 0}")
        except Exception as e:  # noqa: BLE001
            bad += 1
            print(f"  BAD  cannot read pg_stat_wal: {str(e).splitlines()[0][:80]}")
        got = conn.execute("select pg_try_advisory_lock(%s)", (0x52494458,)).fetchone()[0]
        print(f"  {'ok ' if got else 'note'} the sweep lock {'taken and released' if got else 'is held by a running job'}")
        if got:
            conn.execute("select pg_advisory_unlock(%s)", (0x52494458,))
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rotate", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check()
    if a.rotate or not _creds().get("sweep_password"):
        rotate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
