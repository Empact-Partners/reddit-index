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
follow) and stops at the budget declared in docs/retention.md: 0.9 GB a day, 2.5 GB in all, and never past
the day's 1.9 GB line on that counter. It holds the sweep's
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
BUDGET = {"one_copy_gb_day": 0.9, "one_copy_gb_total": 2.5}   # measured 9 Oct: 4.4 KB of egress a cleared row
LINE_GB = 1.90   # the day's line on the node counter, every index job together (ops/day_passes.py)
CHUNKS = 32   # a partition is cleared in 32 slices by comment id, so no statement holds a long transaction

READABLE = ("coalesce(m.body, (select k.body from {holders} k where k.doc_id = m.doc_id "
            "and k.created_utc = m.created_utc and k.brand_id = m.body_from))")
HOLDERS = "public.mentions"   # where a pointer's text is looked up (the test points it at its scratch table)


def log(*a):
    print(f"[{dt.datetime.now(dt.timezone.utc).strftime('%H:%M:%S')}]", *a, flush=True)


def record(conn, run_id: str, t0: float, status: str, notes: dict) -> None:
    conn.execute(
        "insert into public.pipeline_runs (run_id, stage, code_version, started_at, finished_at, status, notes) "
        "values (%s, 'retention', 'retention-v1', to_timestamp(%s), case when %s = 'running' then null else now() end, %s, %s) "
        "on conflict (run_id) do update set finished_at = excluded.finished_at, status = excluded.status, notes = excluded.notes",
        (run_id, t0, status, status, json.dumps(notes, default=str)))


def threads(conn) -> dict:
    n = conn.execute("""
        with moved as (
          delete from public.threads t
           where t.first_seen_at < now() - interval '7 days'
             and not exists (select 1 from public.mentions m where m.thread_id = t.id)
          returning t.*)
        insert into archive.threads select moved.*, now() from moved""").rowcount
    return {"threads_archived_and_removed": n}


def rejected(conn, limit: int | None = None) -> dict:
    """Rows judged "not this product" more than 30 days ago. A row that holds the text other rows point at first
    gives the text back to them. `limit` takes the oldest N rows (the nightly run's cap, so the first night after
    2 November does not move 225 MB at once)."""
    old = ("select m.brand_id, m.doc_id, m.created_utc from public.mentions m join public.mention_rejections x "
           "on x.doc_id = m.doc_id and x.brand_id = m.brand_id where x.rejected_at < now() - interval '30 days'"
           + (f" order by x.rejected_at, m.doc_id, m.brand_id limit {int(limit)}" if limit else ""))
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
        # bookkeeping that pointed at the removed rows (review, 2026-10-03): a probe row for a document with no
        # mention left would wedge the takedown slow lap; a queue row would be re-selected forever
        conn.execute("delete from public.classify_queue q where not exists (select 1 from public.mentions m "
                     "where m.brand_id = q.brand_id and m.doc_id = q.doc_id and m.created_utc = q.created_utc) "
                     "and q.doc_id in (select doc_id from archive.mentions where archived_at > now() - interval '1 hour')")
        probes = conn.execute("delete from public.doc_probe p where not exists (select 1 from public.mentions m "
                              "where m.doc_id = p.doc_id) and p.doc_id in (select doc_id from archive.mentions "
                              "where archived_at > now() - interval '1 hour')").rowcount
    return {"rejected_rows_archived_and_removed": n, "their_labels_archived": sent, "text_given_back": rehomed,
            "probe_rows_removed": probes}


def qual(part: str) -> str:
    return part if "." in part else f"public.{part}"


def checksum(conn, part: str) -> tuple[int, str]:
    """Every row's key with its readable text: a swap between rows, or a NULL where text was, changes it
    (review 4 Oct: a sum over the texts alone was blind to both)."""
    r = conn.execute(f"select count(*), coalesce(sum(hashtextextended(m.doc_id || '|' || m.brand_id::text || '|' || "
                     f"m.created_utc::text || '|' || coalesce({READABLE.format(holders=HOLDERS)}, chr(1)), 0)::numeric), 0) "
                     f"from {qual(part)} m").fetchone()
    return int(r[0]), str(r[1])


def dangling(conn, part: str) -> int:
    """Rows whose text lives on another row that is gone or holds no text: the one failure that loses text."""
    return conn.execute(f"select count(*) from {qual(part)} m where m.body is null and not exists ("
                        f"select 1 from {HOLDERS} h where h.doc_id = m.doc_id and h.created_utc = m.created_utc "
                        f"and h.brand_id = m.body_from and h.body is not null)").fetchone()[0]


def one_copy(conn, part: str, meter, room_bytes: float) -> dict:
    """Clear a row's text where it is word for word the text of the comment's holder (its lowest brand_id with
    text, the same row migration 0019's trigger points new rows at). Per chunk, in one transaction: rows that point
    at a row about to be cleared are re-pointed at the holder first, so no chain is ever made (review 4 Oct), and
    every cleared row is remembered in a temporary table, so a restore puts back exactly what this run took."""
    out = {"partition": part, "cleared": 0, "repointed": 0}
    T = qual(part)
    conn.execute("create temporary table if not exists one_copy_cleared (doc_id text, created_utc timestamptz, "
                 "brand_id bigint, holder bigint)")
    conn.execute("truncate one_copy_cleared")
    before = checksum(conn, part)
    holder = (f"select distinct on (doc_id, created_utc) doc_id, created_utc, brand_id, body from {T} "
              f"where body is not null and abs(hashtext(doc_id)::bigint) % {CHUNKS} = {{k}} "
              f"order by doc_id, created_utc, brand_id")
    for k in range(CHUNKS):
        if meter() >= room_bytes:
            out["stopped"] = "egress budget for today reached"
            break
        with conn.transaction():
            out["repointed"] += conn.execute(f"""
                update {T} d set body_from = h.brand_id
                  from ({holder.format(k=k)}) h, {T} x
                 where x.doc_id = h.doc_id and x.created_utc = h.created_utc and x.brand_id <> h.brand_id
                   and x.body is not null and x.body = h.body
                   and d.doc_id = x.doc_id and d.created_utc = x.created_utc and d.body_from = x.brand_id
                   and abs(hashtext(d.doc_id)::bigint) % {CHUNKS} = {k}""").rowcount
            out["cleared"] += conn.execute(f"""
                with c as (
                  update {T} m set body = null, body_from = h.brand_id
                    from ({holder.format(k=k)}) h
                   where m.doc_id = h.doc_id and m.created_utc = h.created_utc and m.brand_id <> h.brand_id
                     and m.body is not null and m.body = h.body
                     and abs(hashtext(m.doc_id)::bigint) % {CHUNKS} = {k}
                  returning m.doc_id, m.created_utc, m.brand_id, h.brand_id as holder)
                insert into one_copy_cleared select * from c""").rowcount
    after = checksum(conn, part)
    out["dangling"] = dangling(conn, part)
    out["checksum_equal"] = before == after and out["dangling"] == 0
    out["rows"] = before[0]
    if not out["checksum_equal"]:
        out["restored"] = conn.execute(f"""
            update {T} m set body = h.body, body_from = null
              from one_copy_cleared c, {HOLDERS} h
             where m.doc_id = c.doc_id and m.created_utc = c.created_utc and m.brand_id = c.brand_id
               and h.doc_id = c.doc_id and h.created_utc = c.created_utc and h.brand_id = c.holder""").rowcount
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
    import investigation_2026_10 as inv   # the node counter: every step's egress goes on its receipt (review 4 Oct)
    start = inv._metrics()["transmit_bytes"]
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
            last = {"v": start, "at": time.time()}

            def meter() -> float:
                if time.time() - last["at"] > 60:   # 300 s let 9 Oct's first run spend 0.763 GB against a 0.4 cap
                    last["v"], last["at"] = inv._metrics()["transmit_bytes"], time.time()
                return last["v"] - start
            spent = conn.execute("select coalesce(sum((notes->>'egress_gb')::numeric), 0), coalesce(sum((notes->>'egress_gb')::numeric) "
                                 "filter (where started_at::date = now()::date), 0) from public.pipeline_runs "
                                 "where stage = 'retention' and notes->>'step' = 'one-copy'").fetchone()
            sys.path.insert(0, os.path.join(ROOT, "ops"))
            import day_passes   # the node counter since the UTC day began (day_egress's figure is an estimate)
            room = min(BUDGET["one_copy_gb_day"] - float(spent[1]), BUDGET["one_copy_gb_total"] - float(spent[0]),
                       LINE_GB - 0.1 - day_passes.used_today(None)) * 1e9
            if room <= 0:
                notes["stopped"] = "no room today under the line on the node counter"
            parts = [r[0] for r in conn.execute(
                "select c.relname from pg_inherits i join pg_class c on c.oid = i.inhrelid "
                "where i.inhparent = 'public.mentions'::regclass order by pg_total_relation_size(c.oid) desc")]
            want = parts if sys.argv[2:] == ["all"] else sys.argv[2:]
            notes["partitions"] = []
            for part in want:
                if part not in parts:
                    raise SystemExit(f"no partition {part}")
                if meter() >= room:
                    notes["stopped"] = "egress budget reached"
                    break
                r = one_copy(conn, part, meter, room)
                log(json.dumps(r))
                notes["partitions"].append(r)
                if not r["checksum_equal"]:
                    notes["stopped"] = (f"{part}: text changed under clearing or a pointer dangled; restored "
                                        f"({'verified' if r.get('restored_checksum_equal') else 'NOT verified'})")
                    if not r.get("restored_checksum_equal"):
                        raise RuntimeError(notes["stopped"])
                    break
                if r.get("stopped"):
                    notes["stopped"] = r["stopped"]
                    break
        else:
            print(__doc__)
            return 2
        notes["after"] = sizes(conn)
        status = "ok" if not notes.get("stopped") else "capped"
    except Exception as e:  # noqa: BLE001
        notes["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        status = "failed"
    try:   # the step's egress, failed or not (the write-ahead-log tail after this reading is not on it)
        end = inv._metrics()["transmit_bytes"]
        notes["egress_gb"] = round((end - start) / 1e9, 4) if end >= start else None
        notes["egress_source"] = "node counter" if end >= start else "node counter reset during the step"
    except Exception as e:  # noqa: BLE001
        notes["egress_source"] = f"node counter unreadable at the end: {str(e)[:80]}"
    record(conn, run_id, t0, status, notes)
    log(json.dumps(notes, default=str))
    return 0 if status != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
