"""Postgres access for the daily worker — Supavisor SESSION pooler, env-first.

The direct host (db.<ref>.supabase.co:5432) is IPv6-only and unreachable from
a Railway container; the session pooler (aws-0-<region>.pooler.supabase.com)
resolves to IPv4 A-records (verified 2026-08-09). Credentials come from env
vars in the container and fall back to ~/.claude/.reddit-index.json on the
Mac, so the same module serves both sides.

The org-wide Supabase PAT never enters the container — the db password is
scoped to this one database.
"""
import json
import os

import psycopg

_LOCAL = os.path.expanduser("~/.claude/.reddit-index.json")


def _cfg():
    try:
        return json.load(open(_LOCAL))
    except Exception:
        return {}


def dsn():
    c = _cfg()
    ref = os.environ.get("SUPABASE_PROJECT_REF") or c.get("project_ref")
    region = os.environ.get("SUPABASE_REGION") or c.get("region", "us-east-1")
    host = os.environ.get("SUPABASE_DB_HOST") or f"aws-0-{region}.pooler.supabase.com"
    port = os.environ.get("SUPABASE_DB_PORT", "5432")
    user = os.environ.get("SUPABASE_DB_USER") or (f"postgres.{ref}" if ref else None)
    password = os.environ.get("SUPABASE_DB_PASSWORD") or c.get("db_password")
    name = os.environ.get("SUPABASE_DB_NAME", "postgres")
    if not (user and password):
        raise RuntimeError("database credentials missing: set SUPABASE_DB_USER/"
                           "SUPABASE_DB_PASSWORD (or SUPABASE_PROJECT_REF + local file)")
    return f"host={host} port={port} dbname={name} user={user} password={password} sslmode=require"


def connect():
    return psycopg.connect(dsn(), autocommit=False)
