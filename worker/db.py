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
import time

import psycopg

_LOCAL = os.path.expanduser("~/.claude/.reddit-index.json")

# A multi-day run rides through network drops rather than dying in one. Every
# connection is retried with capped backoff, and callers use is_transient() to
# tell "the link went away" (wait, reconnect, retry — costs nothing) from "the
# query is wrong" (a real error that must surface).
CONNECT_TRIES = int(os.environ.get("RI_DB_CONNECT_TRIES", "12"))


def is_transient(exc):
    """True when an exception is a dropped/refused connection rather than a
    bad query. psycopg raises OperationalError for network loss and
    InterfaceError for use of an already-closed connection."""
    if isinstance(exc, (psycopg.OperationalError, psycopg.InterfaceError)):
        return True
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    msg = str(exc).lower()
    return any(s in msg for s in (
        "connection", "server closed", "terminating", "timeout", "eof detected",
        "could not translate host", "temporary failure in name resolution"))


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
    # TCP keepalives are not optional here. The daily lane holds one connection
    # while it spends 20-60 SECONDS per subreddit talking to Reddit, and
    # Supavisor drops a connection that quiet: a 40-subreddit sample took 17
    # drops in 19 minutes without them. The kernel now pokes the socket every
    # 30s, which is well inside any pooler's idle window.
    return (f"host={host} port={port} dbname={name} user={user} password={password} "
            "sslmode=require keepalives=1 keepalives_idle=30 keepalives_interval=10 "
            "keepalives_count=5")


def connect(tries=CONNECT_TRIES):
    """Connect, riding out a network outage instead of dying in it.

    Backoff caps at 2 minutes, so the full ladder waits ~15 minutes before
    giving up — long enough for a router reboot or an ISP blip, and the
    caller's on-disk state means even a failure past that resumes for free.
    """
    last = None
    for attempt in range(tries):
        try:
            return psycopg.connect(dsn(), autocommit=False, connect_timeout=20)
        except Exception as e:
            last = e
            if not is_transient(e) and attempt >= 2:
                raise
            wait = min(120, 5 * 2 ** attempt)
            print(f"  db connect failed ({str(e).splitlines()[0][:90]}) — "
                  f"retry {attempt + 1}/{tries} in {wait}s", flush=True)
            time.sleep(wait)
    raise last


def run(state, fn, tries=8, label=""):
    """Execute fn(conn) with reconnect-on-drop.

    state is any dict holding the live connection under "conn" (the sweep's
    ctx, for instance); it is REPLACED in place when a reconnect happens, so
    every later caller uses the new connection. A transient failure rolls
    back, reconnects and retries; a genuine query error surfaces immediately.
    """
    last = None
    for attempt in range(tries):
        try:
            return fn(state["conn"])
        except Exception as e:
            last = e
            if not is_transient(e):
                raise
            wait = min(120, 5 * 2 ** attempt)
            print(f"  db {label or 'op'} transient failure "
                  f"({str(e).splitlines()[0][:80]}) — reconnect in {wait}s", flush=True)
            try:
                state["conn"].close()
            except Exception:
                pass
            time.sleep(wait)
            try:
                state["conn"] = connect()
            except Exception as ce:
                last = ce
    raise last
