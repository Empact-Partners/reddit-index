#!/usr/bin/env python3
"""Daily classification: label every mention in Supabase that has no
mention_sentiment row yet, on the Codex fleet, then upsert the labels back.

Runs on the Mac (the fleet lives here), after the Railway fetch. Reuses
classify_codex's machinery and the shared item-level label cache, so a
re-run never re-spends a model call.

The anti-join deliberately ignores model_version: ANY sentiment row means
classified. model_version on new rows stays the pipeline version constant
(the engine is recorded per-item in the cache as `_engine`) so the published
view's pinned-version join keeps working.
"""
import argparse, datetime, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import db  # noqa: E402
from classify import MODEL_VERSION, STAGE_LLM, LABEL_CODE, mark_target, load_known  # noqa: E402
from classify_codex import (  # noqa: E402
    batch_task, harvest_out, wait_for_slot, journal, fleet, MODEL, SERVER, RUN,
    burn_lock, burn_refresh, burn_release, burn_active,
)
import csv  # noqa: E402
import hashlib  # noqa: E402

REPO = os.path.dirname(HERE)
WINDOW_DAYS = 400
# The unsupervised nightly run is BOUNDED: the historical sweep (docs/
# depth-plan.md P2) can dump six figures of unlabelled mentions at once, and
# an uncapped anti-join would fire them all at the fleet at 03:30 with nobody
# watching. Newest first, so the boards stay current while the backlog drains
# across nights and supervised daytime burns (--cap 0 --loop).
DAILY_CAP = int(os.environ.get("CLASSIFY_DAILY_CAP", "30000"))
CYCLE_MAX = 50000  # --loop fetches at most this many rows per cycle


def fetch_unlabelled(conn, slugs=None, cap=None):
    """Anti-join for unlabelled mentions, newest first.

    slugs scoping is SUB-scoped, not brand-scoped: score_db builds each
    category's corpus by subreddit membership then filters brands by also_in
    in Python — sub-scoping guarantees everything score_db will read for
    these categories is labelled. Brand-scoping would miss also_in brands'
    mentions in the category's subs (silently excluded from the score).
    """
    scope = ""
    params = [WINDOW_DAYS]
    if slugs:
        scope = """
              AND m.subreddit_id IN (
                  SELECT cs.subreddit_id FROM category_subreddits cs
                  JOIN categories c ON c.id = cs.category_id
                  WHERE c.slug = ANY(%s) AND cs.is_scoring)"""
        params.append(list(slugs))
    params.append(cap if cap else DAILY_CAP)
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT m.doc_id, b.slug, s.name, coalesce(t.link_title, ''),
                   m.body, m.matched_form
            FROM mentions m
            JOIN brands b ON b.id = m.brand_id
            JOIN subreddits s ON s.id = m.subreddit_id
            LEFT JOIN threads t ON t.id = m.thread_id
            LEFT JOIN mention_sentiment ms
                   ON ms.doc_id = m.doc_id AND ms.brand_id = m.brand_id
            WHERE ms.doc_id IS NULL
              AND m.created_utc >= now() - make_interval(days => %s){scope}
            ORDER BY m.created_utc DESC
            LIMIT %s
        """, params)
        return cur.fetchall()


def classify_rows(conn, rows, brand_names):
    print(f"{len(rows)} unlabelled mentions", flush=True)

    items, by_id = [], {}
    for doc_id, bslug, sub, title, body, form in rows:
        iid = f"{doc_id}:{bslug}"
        if iid in by_id:
            continue
        # the DB stores no char_offset — recompute; mark_target's re-find
        # window is tight around the offset, so 0 would miss deep matches
        off = (body or "").lower().find((form or "").lower())
        items.append({
            "item_id": iid, "brand_slug": bslug, "subreddit": sub,
            "link_title": title,
            "marked": mark_target(body or "", form or "", max(0, off)),
        })
        by_id[iid] = (doc_id, bslug)

    known = load_known()
    for rnd in range(1, 4):
        have = load_known()
        left = [it for it in items if it["item_id"] not in have]
        if not left:
            break
        batches = {}
        for i in range(0, len(left), 40):
            chunk = left[i:i + 40]
            bid = hashlib.sha256("".join(it["item_id"] for it in chunk).encode()).hexdigest()[:16]
            batches[bid] = chunk
        pending = {b: its for b, its in batches.items()
                   if harvest_out(b, [it["item_id"] for it in its]) == "pending"}
        if not pending:
            break
        print(f"round {rnd}: {len(left)} items in {len(pending)} batches", flush=True)
        for bid, its in pending.items():
            fp = os.path.join(RUN, f"out_{bid}.json")
            if os.path.exists(fp):
                os.remove(fp)
            wait_for_slot()
            journal({"daily": True, "batch": bid, "round": rnd, "t": time.time()})
            for attempt in range(5):
                try:
                    r = fleet.submit(batch_task(its, brand_names, fp), server=SERVER,
                                     mode="workspace-write", model=MODEL, workspace=RUN,
                                     timeout=420, reasoning_effort="low")
                    journal({"daily": True, "batch": bid, "job_id": r["job_id"]})
                    break
                except Exception:
                    time.sleep(10 * (attempt + 1))
        deadline = time.time() + 540
        while time.time() < deadline:
            if not [1 for b, its in pending.items()
                    if harvest_out(b, [it["item_id"] for it in its]) == "pending"]:
                break
            time.sleep(20)

    # upsert labels
    have = load_known()
    vals, dropped = [], 0
    for it in items:
        r = have.get(it["item_id"])
        if not isinstance(r, dict):
            continue
        if r.get("entity_ok") is False:
            dropped += 1
            continue  # an entity decision: excluded, not labelled
        label = str(r.get("label", "abstain")).lower()
        doc_id, bslug = by_id[it["item_id"]]
        vals.append((doc_id, MODEL_VERSION, LABEL_CODE.get(label, 3),
                     float(r.get("intensity") or 0), float(r.get("confidence") or 0),
                     STAGE_LLM, bool(r.get("comparative")), bool(r.get("recommendation")),
                     bool(r.get("category_gripe")), str(r.get("evidence") or "")[:300],
                     bslug))
    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO mention_sentiment (doc_id, brand_id, model_version, label,
                intensity, conf, stage, is_comparative, is_recommendation,
                is_category_gripe, evidence_span)
            SELECT %s, b.id, %s, %s, %s, %s, %s, %s, %s, %s, %s
            FROM brands b WHERE b.slug = %s
            ON CONFLICT (doc_id, brand_id, model_version) DO NOTHING
        """, [(v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7], v[8], v[9], v[10])
              for v in vals])
        conn.commit()
    print(f"labelled {len(vals)} (+{dropped} entity-rejected) of {len(items)}", flush=True)
    # return INSERTED only: entity-rejected mentions never get a sentiment row,
    # so the anti-join refetches them every cycle — a loop keyed on processed
    # count would spin forever on that residue
    return len(vals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", action="append",
                    help="scope to a category slug (repeatable) — supervised burn")
    ap.add_argument("--cap", type=int, default=None,
                    help="row cap per fetch; 0 = uncapped (burn). Default: CLASSIFY_DAILY_CAP")
    ap.add_argument("--loop", action="store_true",
                    help="repeat fetch->classify cycles until the anti-join is empty")
    args = ap.parse_args()
    supervised = bool(args.category or args.loop or args.cap == 0)

    if not supervised and burn_active():
        # the launchd nightly defers to a running supervised burn — they share
        # the codex-absa dir and would clobber each other's out-files
        print("supervised burn active — nightly classify skipped", flush=True)
        return 0
    if supervised and not burn_lock():
        print("another burn already holds burn.lock — refusing to double-run", flush=True)
        return 1

    brand_names = {r["slug"]: r["brand"] for r in
                   csv.DictReader(open(os.path.join(REPO, "data", "brands.csv")))}
    cap = args.cap if args.cap else (CYCLE_MAX if args.loop else DAILY_CAP)
    conn = db.connect()
    try:
        total = 0
        while True:
            rows = fetch_unlabelled(conn, slugs=args.category, cap=cap)
            if not rows:
                print(f"backlog empty — {total} labelled this run", flush=True)
                break
            done = classify_rows(conn, rows, brand_names)
            total += done
            if supervised:
                burn_refresh()
            if not args.loop:
                break
            if done == 0:
                # a full cycle produced nothing (fleet down?) — do not spin
                print("cycle labelled 0 — stopping loop", flush=True)
                break
    finally:
        if supervised:
            burn_release()
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
