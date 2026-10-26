#!/usr/bin/env python3
"""Keys for the read API (decision 0040): mint, list, revoke.

A key is read-only: it can call GET /api/v1/threads and GET /api/v1/brands, nothing else. The database keeps the
sha256 of the key, never the key; `mint` prints the key ONCE and it cannot be shown again (a lost key is revoked
and a new one minted). A revoked key is refused from the next call; the row stays as the record.

  ops/api_keys.py mint --name heather     # prints the key id and the key, once
  ops/api_keys.py list                     # id, name, created, last used, calls today, revoked
  ops/api_keys.py revoke kid_1a2b3c4d      # refused from the next call

From Python (to hand a key on without printing it): `from api_keys import mint; key_id, key = mint("heather")`.
Connects as `postgres` through the session pooler (worker/db.py), like every ops script.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import secrets
import string
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))

PREFIX = "rik_"   # a recognisable prefix, so a key pasted somewhere it should not be is easy to find
ALPHABET = string.ascii_letters + string.digits


def key_hash(key: str) -> str:
    """The same hash the site computes (lib/api/v1.ts hashKey): sha256 of the UTF-8 key, lowercase hex."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def mint(name: str) -> tuple[str, str]:
    """Create a key for `name`. Returns (key_id, key); only the hash is stored."""
    import db
    name = name.strip()
    if not name:
        raise SystemExit("a key needs a --name: who holds it")
    key = PREFIX + "".join(secrets.choice(ALPHABET) for _ in range(40))   # ~238 bits
    key_id = "kid_" + secrets.token_hex(4)
    with db.connect() as conn:
        conn.execute("insert into api.api_keys (id, name, key_hash) values (%s, %s, %s)", (key_id, name, key_hash(key)))
        conn.commit()
    return key_id, key


def rows() -> list[tuple]:
    import db
    with db.connect() as conn:
        return conn.execute(
            "select id, name, created_at, last_used_at, case when day = (now() at time zone 'utc')::date "
            "then day_calls else 0 end, revoked_at from api.api_keys order by created_at").fetchall()


def revoke(key_id: str) -> bool:
    import db
    with db.connect() as conn:
        n = conn.execute("update api.api_keys set revoked_at = now() where id = %s and revoked_at is null",
                         (key_id,)).rowcount
        conn.commit()
    return n == 1


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mint")
    m.add_argument("--name", required=True)
    sub.add_parser("list")
    r = sub.add_parser("revoke")
    r.add_argument("key_id")
    a = ap.parse_args()

    if a.cmd == "mint":
        key_id, key = mint(a.name)
        print(f"key id: {key_id}  (for {a.name})")
        print(f"key:    {key}")
        print("This is the only time the key is shown. Keep it in 1Password; never in a repo.")
        return 0
    if a.cmd == "list":
        fmt = lambda t: t.strftime("%Y-%m-%d %H:%M") if t else "-"  # noqa: E731
        print(f"{'id':<14} {'name':<16} {'created':<17} {'last used':<17} {'today':>5}  revoked")
        for kid, name, created, used, today, revoked in rows():
            print(f"{kid:<14} {name[:16]:<16} {fmt(created):<17} {fmt(used):<17} {today:>5}  {fmt(revoked)}")
        return 0
    if a.cmd == "revoke":
        if revoke(a.key_id):
            print(f"{a.key_id} revoked: refused from the next call")
            return 0
        print(f"{a.key_id}: no such key, or already revoked")
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
