#!/usr/bin/env python3
"""Apply supabase/migrations/*.sql to the database, once each, and remember it.

Until 2026-10 migrations were pasted through the Management API by hand and nothing recorded which had run
(one column, mentions.delete_checked_at, exists in the database and in no file). This keeps a ledger,
`public.schema_migrations`, and refuses to apply a file whose content changed after it was applied: a fix
goes in a NEW migration.

  ops/migrate.py --status            # what is applied, what is pending
  ops/migrate.py --apply 0007        # apply one file (prefix match), in ONE transaction
  ops/migrate.py --adopt 0001 0002   # record files that were applied by hand before the ledger existed

Connects as `postgres` through the session pooler (worker/db.py; ~/.claude/.reddit-index.json or env).
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
MIG = os.path.join(ROOT, "supabase", "migrations")

LEDGER = """
create table if not exists public.schema_migrations (
  name       text primary key,
  sha256     text not null,
  applied_at timestamptz not null default now(),
  note       text
);
alter table public.schema_migrations enable row level security;
"""


def files() -> list[tuple[str, str, str]]:
    out = []
    for path in sorted(glob.glob(os.path.join(MIG, "*.sql"))):
        body = open(path, encoding="utf-8").read()
        out.append((os.path.basename(path), hashlib.sha256(body.encode()).hexdigest(), body))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--status", action="store_true")
    g.add_argument("--apply", metavar="PREFIX")
    g.add_argument("--adopt", nargs="+", metavar="PREFIX")
    a = ap.parse_args()

    import db  # worker/db.py
    with db.connect() as conn:
        conn.autocommit = True
        conn.execute(LEDGER)
        applied = {r[0]: r[1] for r in conn.execute("select name, sha256 from public.schema_migrations")}
        fs = files()

        if a.status:
            for name, sha, _ in fs:
                state = "pending"
                if name in applied:
                    state = "applied" if applied[name] in (sha, "pre-ledger") else "CHANGED SINCE APPLIED"
                print(f"{state:22} {name}")
            return 0

        if a.adopt:
            for pref in a.adopt:
                hit = [f for f in fs if f[0].startswith(pref)]
                if len(hit) != 1:
                    print(f"{pref}: matches {len(hit)} files"); return 2
                conn.execute("insert into public.schema_migrations (name, sha256, note) values (%s, %s, %s) "
                             "on conflict (name) do nothing",
                             (hit[0][0], "pre-ledger", "applied by hand before the ledger existed"))
                print("adopted", hit[0][0])
            return 0

        hit = [f for f in fs if f[0].startswith(a.apply)]
        if len(hit) != 1:
            print(f"{a.apply}: matches {len(hit)} files"); return 2
        name, sha, body = hit[0]
        if name in applied:
            print(f"{name} is already applied" + ("" if applied[name] == sha else
                  " AND THE FILE HAS CHANGED SINCE: write a new migration instead"))
            return 0 if applied[name] == sha else 2
        with conn.transaction():
            conn.execute("set local statement_timeout = '30min'")
            conn.execute("set local lock_timeout = '30s'")
            conn.execute(body)  # simple protocol: the whole file, one transaction
            conn.execute("insert into public.schema_migrations (name, sha256) values (%s, %s)", (name, sha))
        print("applied", name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
