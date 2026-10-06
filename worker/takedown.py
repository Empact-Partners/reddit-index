#!/usr/bin/env python3
"""Find documents that were deleted, removed or edited on Reddit, and purge them.

Decision 0002 makes this a CONDITION of showing Reddit text at all, and Reddit's Developer Terms require
deletions to propagate "as soon as possible". This replaces worker/delete_sync.py, which ran only when a
person ran update.sh (last time: 25 August 2026) and had three faults this one does not:

  * a batch Reddit failed to answer was read as "every document in it is gone" and purged. Here a batch
    that did not answer is `not_checked`: counted, left alone, asked again next run.
  * a post Reddit removed keeps its title and author in the answer, with an empty body, so it looked alive.
    `removed_by_category` is the field that says so.
  * the receipt (removals.revalidated_at) was stamped because an endpoint answered 200. Here this script
    never stamps it: worker/run_daily.py does, after the publisher has FETCHED the page and seen it without
    the card.

What is checked, each run:
  1. every document on a page (site.rail_key, and the closer watch's cards in site.watch_card, decision 0020),
     every time: about 140,000 documents, 1,400 calls;
  2. then, with the calls that are left, the documents longest unchecked (public.doc_probe).

What counts as gone: Reddit does not return it; its body is [deleted] or [removed]; its author is
[deleted]; removed_by_category is set. What counts as edited: `edited` is later than the moment we stored
it. Both are purged; the ledger records which (`source_deleted`, `source_edited`). A ledgered document is
never stored again (migration 0011).

The brake: if more than --max-gone-share of what was checked comes back gone, nothing is purged and the run
fails. A purge is permanent, and an API hiccup that makes everything look deleted has happened before.

  worker/takedown.py --max-calls 2000            # the nightly use
  worker/takedown.py --dry-run --max-calls 20    # probe and report, purge nothing
  worker/takedown.py --ledgered-only             # only re-purge stored rows whose document is in the ledger
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

BATCH = 100  # /api/info takes 100 fullnames a call


def judge(children: list[dict], asked: list[str], stored_at: dict[str, float]) -> dict[str, str]:
    """One /api/info answer -> {doc_id: 'alive' | 'source_deleted' | 'source_edited'} for every id asked."""
    seen: dict[str, dict] = {}
    for child in children:
        d = child.get("data", {}) if isinstance(child, dict) else {}
        if d.get("name"):
            seen[d["name"]] = d
    out = {}
    for doc_id in asked:
        d = seen.get(doc_id)
        if d is None:
            out[doc_id] = "source_deleted"      # Reddit answered the batch and this id is not in it
            continue
        body = d.get("body") if "body" in d else d.get("selftext")
        if (body in ("[deleted]", "[removed]") or (d.get("author") or "[deleted]") == "[deleted]"
                or d.get("removed_by_category")):
            out[doc_id] = "source_deleted"
            continue
        edited = d.get("edited")
        if edited and isinstance(edited, (int, float)) and edited > stored_at.get(doc_id, float("inf")):
            out[doc_id] = "source_edited"
            continue
        out[doc_id] = "alive"
    return out


def purge(conn, verdicts: dict[str, str]) -> int:
    """Ledger, purge and stamp in ONE transaction: there is no moment when the ledger says purged and the
    rows are still there. The triggers mark every affected brand for refresh."""
    gone = {d: v for d, v in verdicts.items() if v != "alive"}
    if not gone:
        return 0
    ids, reasons = list(gone), [gone[d] for d in gone]
    with conn.transaction():
        conn.execute("""
            insert into public.removals (doc_id, doc_type, brand_ids, reason, detected_at)
            select m.doc_id, min(m.doc_type), array_agg(distinct m.brand_id), v.reason, now()
              from unnest(%s::text[], %s::text[]) as v(doc_id, reason)
              join public.mentions m on m.doc_id = v.doc_id
             group by m.doc_id, v.reason
            on conflict (doc_id) do nothing""", (ids, reasons))
        conn.execute("delete from public.mention_sentiment where doc_id = any (%s)", (ids,))
        conn.execute("delete from public.mention_rejections where doc_id = any (%s)", (ids,))
        n = conn.execute("delete from public.mentions where doc_id = any (%s)", (ids,)).rowcount
        # What pointed at the purged rows goes with them: a queue row for a mention that no longer exists was
        # re-selected by the classifier every batch, forever (review, 2026-10-03), and a probe row for a
        # document with no mention could never be stamped, so the slow lap would wedge on it.
        conn.execute("delete from public.classify_queue where doc_id = any (%s)", (ids,))
        conn.execute("delete from public.doc_probe where doc_id = any (%s)", (ids,))
        conn.execute("update public.removals set purged_at = now() where doc_id = any (%s) and purged_at is null", (ids,))
    return n


def repurge_ledgered(conn, dry_run: bool) -> int:
    """Stored rows whose document is already in the ledger (a backfill re-collected 25 of them in August).
    New ones cannot arrive: the mentions table refuses them."""
    n = conn.execute("select count(*) from public.mentions m where exists "
                     "(select 1 from public.removals r where r.doc_id = m.doc_id)").fetchone()[0]
    if n and not dry_run:
        with conn.transaction():
            for t in ("mention_sentiment", "mention_rejections", "mentions", "classify_queue", "doc_probe"):
                conn.execute(f"delete from public.{t} x where exists "
                             "(select 1 from public.removals r where r.doc_id = x.doc_id)")
    return n


def run(conn, max_calls: int = 2000, dry_run: bool = False, max_gone_share: float = 0.15,
        ledgered_only: bool = False, deadline: float | None = None, log=print, should_stop=lambda: None) -> dict:
    import reddit_client as rc
    receipt = {"docs_checked": 0, "docs_not_checked": 0, "docs_gone": 0, "docs_edited": 0, "mentions_purged": 0,
               "ledgered_repurged": 0, "reddit_calls": 0, "on_pages_checked": 0, "probe_rows_without_a_document": 0,
               "brake": False, "stopped": None}
    conn.execute("set statement_timeout = '15min'")

    receipt["ledgered_repurged"] = repurge_ledgered(conn, dry_run)
    if receipt["ledgered_repurged"]:
        log(f"  {'would re-purge' if dry_run else 're-purged'} {receipt['ledgered_repurged']} stored rows of ledgered documents")
    if ledgered_only:
        return receipt

    # 1. every document on a page; 2. then the longest unchecked. One list, in that order.
    on_pages = [r[0] for r in conn.execute("select doc_id from site.rail_key union select doc_id from site.watch_card order by 1")]
    # a watch card's document is not in public.mentions: its stored time is when the watch stored it (0020)
    watch_stored = {d: float(t) for d, t in conn.execute(
        "select doc_id, extract(epoch from min(stored_at)) from site.watch_card group by 1").fetchall()}
    room = max(0, max_calls * BATCH - len(on_pages))
    rest = [r[0] for r in conn.execute(
        "select p.doc_id from public.doc_probe p where not exists "
        "(select 1 from site.rail_key k where k.doc_id = p.doc_id) "
        "and not exists (select 1 from site.watch_card w where w.doc_id = p.doc_id) "
        "order by p.checked_at nulls first, p.doc_id limit %s", (room,))] if room else []
    queue = (on_pages + rest)[: max_calls * BATCH]
    on_set = set(on_pages)
    log(f"  {len(on_pages)} documents on pages, {len(rest)} more from the slow lap, {max_calls} calls allowed")

    verdicts: dict[str, str] = {}
    calls0 = rc.stats()["calls"]
    for i in range(0, len(queue), BATCH):
        if deadline and time.time() > deadline:
            log("  out of time: the rest is not checked this run")
            break
        if (i // BATCH) % 50 == 0:
            reason = should_stop()
            if reason:
                receipt["stopped"] = reason
                log(f"  stopped: {reason}")
                break
        chunk = queue[i:i + BATCH]
        resp = rc.info(chunk)
        children = (resp.get("data") or {}).get("children") if isinstance(resp, dict) else None
        if not isinstance(resp, dict) or "_err" in resp or children is None:
            # A failure is residue, never a verdict.
            receipt["docs_not_checked"] += len(chunk)
            continue
        stored = dict(conn.execute(
            "select doc_id, extract(epoch from min(loaded_at)) from public.mentions "
            "where doc_id = any (%s) group by 1", (chunk,)).fetchall())
        stored = {k: float(v) for k, v in stored.items()}
        for d in chunk:   # the earliest time either collection stored it: an edit after either one counts (review 0020)
            if d in watch_stored:
                stored[d] = min(stored.get(d, watch_stored[d]), watch_stored[d])
        got = judge(children, [c for c in chunk if c in stored], stored)
        verdicts.update(got)
        receipt["on_pages_checked"] += sum(1 for d in got if d in on_set)
        ghosts = [c for c in chunk if c not in stored and c not in watch_stored]
        if ghosts and not dry_run:   # a probe row whose document has no mention left: nothing to check, ever
            receipt["probe_rows_without_a_document"] += conn.execute(
                "delete from public.doc_probe where doc_id = any (%s) and not exists "
                "(select 1 from public.mentions m where m.doc_id = doc_probe.doc_id)", (ghosts,)).rowcount
        if i and (i // BATCH) % 200 == 0:
            log(f"    checked {len(verdicts)} documents, {sum(v != 'alive' for v in verdicts.values())} gone or edited", flush=True)
    receipt["reddit_calls"] = rc.stats()["calls"] - calls0
    receipt["docs_checked"] = len(verdicts)
    receipt["docs_gone"] = sum(v == "source_deleted" for v in verdicts.values())
    receipt["docs_edited"] = sum(v == "source_edited" for v in verdicts.values())
    receipt["docs_not_checked"] += len(queue) - len(verdicts) - receipt["docs_not_checked"]

    gone_share = (receipt["docs_gone"] + receipt["docs_edited"]) / max(1, len(verdicts))
    receipt["gone_share"] = round(gone_share, 4)
    if len(verdicts) >= 500 and gone_share > max_gone_share:
        receipt["brake"] = True
        log(f"  BRAKE: {gone_share:.1%} of {len(verdicts)} checked documents look gone or edited "
            f"(limit {max_gone_share:.0%}). Nothing purged.")
        return receipt

    log(f"  checked {len(verdicts)}: {receipt['docs_gone']} gone, {receipt['docs_edited']} edited, "
        f"{receipt['docs_not_checked']} not checked; {receipt['reddit_calls']} Reddit calls")
    if dry_run:
        return receipt

    ids = list(verdicts)
    for i in range(0, len(ids), 5000):
        part = ids[i:i + 5000]
        receipt["mentions_purged"] += purge(conn, {d: verdicts[d] for d in part})
        gone_watch = [d for d in part if d in watch_stored and verdicts[d] != "alive"]
        if gone_watch:   # decision 0020: ledgered, the card deleted and its text dropped, in one transaction
            receipt["watch_purged"] = receipt.get("watch_purged", 0) + conn.execute(
                "select site.purge_watch(%s::text[], %s::text[])", (gone_watch, [verdicts[d] for d in gone_watch])).fetchone()[0]
        # the stamp that moves the slow lap forward, for the survivors (a purge removed the others' rows)
        alive = [d for d in part if verdicts[d] == "alive"]
        conn.execute("insert into public.doc_probe (doc_id, checked_at) select d, now() from unnest(%s::text[]) d "
                     "on conflict (doc_id) do update set checked_at = excluded.checked_at", (alive,))
    log(f"  purged {receipt['mentions_purged']} mention rows")
    return receipt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-calls", type=int, default=2000)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-gone-share", type=float, default=0.15)
    ap.add_argument("--ledgered-only", action="store_true")
    a = ap.parse_args()
    import db
    with db.connect() as conn:
        conn.autocommit = True
        r = run(conn, a.max_calls, a.dry_run, a.max_gone_share, a.ledgered_only)
    print(json.dumps(r))
    return 2 if r["brake"] else 0


if __name__ == "__main__":
    sys.exit(main())
