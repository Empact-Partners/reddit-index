#!/usr/bin/env python3
"""Apply the retention policy (docs/retention.md). Every step is safe to repeat and resumes from the data.

  ops/retention.py status                       # sizes, what each step would remove, archive contents
  ops/retention.py threads                      # step 1: threads with no mention, older than 7 days
  ops/retention.py rejected                     # step 2: rows judged "not this product" over 30 days ago
  ops/retention.py one-copy mentions_2026_09    # step 3, one monthly partition (or: one-copy all)
  ops/retention.py expire-archive               # drop archived copies older than 14 days

Steps 1 and 2 move rows into the `archive` schema in the same statement that deletes them, so nothing is removed
that was not copied. Step 3 deletes nothing: it clears a row's text only where it is word for word the text of
another row of the same comment, and records which row (`body_from`); it proves each partition with a checksum of
every row's readable text before and after, and restores the partition exactly if the two differ.

Step 3 meters itself on the database's node transmit counter (the number the egress watchdog and the bill
follow) and stops at the budget declared in docs/retention.md: 0.4 GB a day, 1.0 GB in all. It holds the sweep's
lock, so it never runs beside the sweep or the backlog classifier.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

LOCK_KEY = 0x52494458
BUDGET = {"one_copy_gb_day": 0.4, "one_copy_gb_total": 1.0}
CHUNKS = 32   # a partition is cleared in 32 slices by comment id, so no statement holds a long transaction

READABLE = ("coalesce(m.body, (select k.body from public.mentions k where k.doc_id = m.doc_id "
            "and k.created_utc = m.created_utc and k.brand_id = m.body_from))")


def log(*a):
    print(f"[{dt.datetime.now(dt.timezone.utc).strftime('%H:%M:%S')}]", *a, flush=True)


def record(conn, run_id: str, t0: float, status: str, notes: dict) -> None:
    conn.execute(
        "insert into public.pipeline_runs (run_id, stage, code_version, started_at, finished_at, status, notes) "
        "values (%s, 'retention', 'retention-v1', to_timestamp(%s), now(), %s, %s) "
        "on conflict (run_id) do update set finished_at = now(), status = excluded.status, notes = excluded.notes",
        (run_id, t0, status, json.dumps(notes, default=str)))


def threads(conn) -> dict:
    n = conn.execute("""
        with moved as (
          delete from public.threads t
           where t.first_seen_at < now() - interval '7 days'
             and not exists (select 1 from public.mentions m where m.thread_id = t.id)
          returning t.*)
        insert into archive.threads select moved.*, now() from moved""").rowcount
    return {"threads_archived_and_removed": n}


def rejected(conn) -> dict:
    """Rows judged "not this product" more than 30 days ago. A row that holds the text other rows point at first
    gives the text back to them."""
    old = ("select m.brand_id, m.doc_id, m.created_utc from public.mentions m join public.mention_rejections x "
           "on x.doc_id = m.doc_id and x.brand_id = m.brand_id where x.rejected_at < now() - interval '30 days'")
    with conn.transaction():
        rehomed = conn.execute(f"""
            update public.mentions s set body = h.body, body_from = null
              from public.mentions h, ({old}) d
             where h.brand_id = d.brand_id and h.doc_id = d.doc_id and h.created_utc = d.created_utc
               and h.body is not null
               and s.doc_id = h.doc_id and s.created_utc = h.created_utc and s.body_from = h.brand_id""").rowcount
        sent = conn.execute(f"""
            with moved as (
              delete from public.mention_sentiment s using ({old}) d
               where s.doc_id = d.doc_id and s.brand_id = d.brand_id
              returning s.*)
            insert into archive.mention_sentiment select moved.*, now() from moved""").rowcount
        n = conn.execute(f"""
            with moved as (
              delete from public.mentions m using ({old}) d
               where m.brand_id = d.brand_id and m.doc_id = d.doc_id and m.created_utc = d.created_utc
              returning m.*)
            insert into archive.mentions select moved.*, now() from moved""").rowcount
    return {"rejected_rows_archived_and_removed": n, "their_labels_archived": sent, "text_given_back": rehomed}


def checksum(conn, part: str) -> tuple[int, str]:
    r = conn.execute(f"select count(*), coalesce(sum(hashtextextended({READABLE}, 0)::numeric), 0) "
                     f"from public.{part} m").fetchone()
    return int(r[0]), str(r[1])


def one_copy(conn, part: str, meter, room_bytes: float) -> dict:
    out = {"partition": part, "cleared": 0}
    before = checksum(conn, part)
    for k in range(CHUNKS):
        if meter() > room_bytes:
            out["stopped"] = "egress budget for today reached"
            break
        out["cleared"] += conn.execute(f"""
            update public.{part} m set body = null, body_from = h.brand_id
              from (select distinct on (doc_id, created_utc) doc_id, created_utc, brand_id, body
                      from public.{part}
                     where body is not null and abs(hashtext(doc_id)) % {CHUNKS} = {k}
                     order by doc_id, created_utc, brand_id) h
             where m.doc_id = h.doc_id and m.created_utc = h.created_utc and m.brand_id <> h.brand_id
               and m.body is not null and m.body = h.body
               and abs(hashtext(m.doc_id)) % {CHUNKS} = {k}""").rowcount
    after = checksum(conn, part)
    out["checksum_equal"] = before == after
    out["rows"] = before[0]
    if before != after:
        restored = conn.execute(f"""
            update public.{part} m set body = h.body, body_from = null
              from public.{part} h
             where m.body_from is not null and h.doc_id = m.doc_id and h.created_utc = m.created_utc
               and h.brand_id = m.body_from""").rowcount
        out["restored"] = restored
        out["restored_checksum_equal"] = checksum(conn, part) == before
    return out


def sizes(conn) -> dict:
    r = conn.execute("""select pg_size_pretty(pg_database_size(current_database())),
        (select pg_size_pretty(sum(pg_total_relation_size(c.oid))) from pg_inherits i join pg_class c on c.oid = i.inhrelid
          where i.inhparent = 'public.mentions'::regclass),
        pg_size_pretty(pg_total_relation_size('public.threads')),
        (select count(*) from public.mentions where body_from is not null)""").fetchone()
    return {"database": r[0], "mentions": r[1], "threads": r[2], "rows_pointing_at_another_copy": r[3]}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    import db
    conn = db.connect()
    conn.autocommit = True
    conn.execute("set statement_timeout = '30min'")
    if cmd == "status":
        print(json.dumps(sizes(conn), indent=1))
        return 0
    if not conn.execute("select pg_try_advisory_lock(%s)", (LOCK_KEY,)).fetchone()[0]:
        log("the sweep or the backlog classifier holds the lock: not running")
        return 0
    run_id, t0 = str(uuid.uuid4()), time.time()
    notes: dict = {"step": cmd, "before": sizes(conn)}
    record(conn, run_id, t0, "running", notes)
    try:
        if cmd == "threads":
            notes.update(threads(conn))
        elif cmd == "rejected":
            notes.update(rejected(conn))
        elif cmd == "expire-archive":
            notes["expired"] = {t: conn.execute(f"delete from archive.{t} where archived_at < now() - interval '14 days'").rowcount
                                for t in ("threads", "mentions", "mention_sentiment")}
        elif cmd == "one-copy":
            import investigation_2026_10 as inv
            start = inv._metrics()["transmit_bytes"]
            last = {"v": start, "at": time.time()}

            def meter() -> float:
                if time.time() - last["at"] > 300:
                    last["v"], last["at"] = inv._metrics()["transmit_bytes"], time.time()
                return last["v"] - start
            spent = conn.execute("select coalesce(sum((notes->>'egress_gb')::numeric), 0), coalesce(sum((notes->>'egress_gb')::numeric) "
                                 "filter (where started_at::date = now()::date), 0) from public.pipeline_runs "
                                 "where stage = 'retention' and notes->>'step' = 'one-copy'").fetchone()
            room = min(BUDGET["one_copy_gb_day"] - float(spent[1]), BUDGET["one_copy_gb_total"] - float(spent[0])) * 1e9
            parts = [r[0] for r in conn.execute(
                "select c.relname from pg_inherits i join pg_class c on c.oid = i.inhrelid "
                "where i.inhparent = 'public.mentions'::regclass order by pg_total_relation_size(c.oid) desc")]
            want = parts if sys.argv[2:] == ["all"] else sys.argv[2:]
            notes["partitions"] = []
            for part in want:
                if part not in parts:
                    raise SystemExit(f"no partition {part}")
                if meter() > room:
                    notes["stopped"] = "egress budget reached"
                    break
                r = one_copy(conn, part, meter, room)
                log(json.dumps(r))
                notes["partitions"].append(r)
                if not r["checksum_equal"]:
                    notes["stopped"] = f"{part}: text changed under clearing; restored"
                    break
                if r.get("stopped"):
                    notes["stopped"] = r["stopped"]
                    break
            last["v"], last["at"] = inv._metrics()["transmit_bytes"], time.time()
            notes["egress_gb"] = round((last["v"] - start) / 1e9, 4)
        else:
            print(__doc__)
            return 2
        notes["after"] = sizes(conn)
        status = "ok" if not notes.get("stopped") else "capped"
    except Exception as e:  # noqa: BLE001
        notes["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        status = "failed"
    record(conn, run_id, t0, status, notes)
    log(json.dumps(notes, default=str))
    return 0 if status != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
