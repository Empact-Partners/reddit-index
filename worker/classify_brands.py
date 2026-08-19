#!/usr/bin/env python3
"""Classify the unlabelled mentions of a NAMED SET OF BRANDS, nothing else.

Why this exists, next to classify_api.py: the lane drains the whole backlog
oldest-first (115K items, ~$21). Sometimes the job is narrower and known --
"these 70 company pages carry no opinionated label at all, so they publish no
Reddit Love Score" (decisions/0011). That is 1,452 items, ~$0.26, and the rest
of the backlog is irrelevant to it.

Everything metered, prompted, parsed or committed is IMPORTED from
classify_api: same model, same prompt, same MODEL_VERSION, same anti-join, same
on-disk judged-cache. The only thing this file owns is WHICH rows are fed. A
row already carrying any sentiment row is never re-paid, here or there.

    python3 worker/classify_brands.py --slugs-file /tmp/slugs.txt --allow-metered
    python3 worker/classify_brands.py --slugs lever,bookwhen --dry-run
"""
import argparse
import os
import queue
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import db  # noqa: E402
import classify_api as CA  # noqa: E402
from classify import mark_target  # noqa: E402

PAGE = 2000


def candidates(state, slugs, rejudge=False):
    """Every unlabelled mention of these brands, oldest first. No time window
    and no subreddit filter: the page's Positive/Negative tiles count every
    mention ever collected, so the score computed from them must too.

    --rejudge widens this to mentions that ALREADY carry a neutral or abstain
    verdict, and (in main) ignores the on-disk judged cache, so entity-rejects
    are re-decided too. It is a genuine SECOND OPINION, not a leading one: the
    same model, the same prompt, the same everything except that the answer is
    written under a bumped model_version, which the site's latest-scored-wins
    lateral then prefers. Vlad, 2026-08-19: "If the mentions are neutral,
    reclassify them if that's what's necessary."
    """
    having = ("" if rejudge else "AND ms.doc_id IS NULL")
    filt = ("AND (ms.doc_id IS NULL OR ms.label IN (0, 3))" if rejudge else "")

    def _q(c):
        with c.cursor() as cur:
            cur.execute(f"""
                SELECT DISTINCT ON (m.created_utc, m.doc_id, b.slug)
                       m.created_utc, m.doc_id, b.slug, s.name,
                       coalesce(t.link_title, ''), m.body, m.matched_form
                FROM mentions m
                JOIN brands b ON b.id = m.brand_id
                JOIN subreddits s ON s.id = m.subreddit_id
                LEFT JOIN threads t ON t.id = m.thread_id
                LEFT JOIN mention_sentiment ms
                       ON ms.doc_id = m.doc_id AND ms.brand_id = m.brand_id
                WHERE b.slug = ANY(%s) {having} {filt}
                ORDER BY m.created_utc, m.doc_id, b.slug
            """, (list(slugs),))
            return cur.fetchall()
    return db.run(state, _q, label="brand backlog")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", default="", help="comma-separated brand slugs")
    ap.add_argument("--slugs-file", default="", help="file, one brand slug per line")
    ap.add_argument("--deepseek", type=int, default=16)
    ap.add_argument("--haiku", type=int, default=0)
    ap.add_argument("--allow-metered", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="count and cost only")
    ap.add_argument("--rejudge", action="store_true",
                    help="second opinion: include neutral/abstain rows and ignore "
                         "the on-disk judged cache; writes under a bumped model_version")
    args = ap.parse_args()

    slugs = [s.strip() for s in args.slugs.split(",") if s.strip()]
    if args.slugs_file:
        slugs += [l.strip() for l in open(args.slugs_file) if l.strip()]
    slugs = sorted(set(slugs))
    if not slugs:
        sys.exit("no slugs given")

    state = {"conn": db.connect()}
    if args.rejudge:
        CA.MV = {k: v + "-r2" for k, v in CA.MV.items()}
        print(f"rejudge: writing under {CA.MV['deepseek']} (latest scored_at wins on the site)",
              flush=True)
    rows = candidates(state, slugs, rejudge=args.rejudge)
    n = len(rows)
    print(f"{len(slugs)} brands · {n:,} unlabelled items · "
          f"deepseek estimate ${n * 0.18 / 1000:.2f}", flush=True)
    if args.dry_run or n == 0:
        return
    if args.deepseek and not args.allow_metered:
        sys.exit("--deepseek spends money: pass --allow-metered")

    key = CA.deepseek_key() if args.deepseek else None
    judged = set() if args.rejudge else CA.load_judged()
    print(f"skip-set: {len(judged):,} items already decided on disk", flush=True)

    dblock = threading.Lock()
    q: queue.Queue = queue.Queue(maxsize=args.haiku + args.deepseek + 8)
    import csv as _csv
    brand_names = {r["slug"]: r["brand"] for r in
                   _csv.DictReader(open(os.path.join(os.path.dirname(HERE),
                                                     "data", "brands.csv")))}
    t0 = time.time()

    threads = []
    for kind, k in (("haiku", args.haiku), ("deepseek", args.deepseek)):
        for _ in range(k):
            t = threading.Thread(target=CA.worker,
                                 args=(kind, q, state, dblock, brand_names, key, 400),
                                 daemon=True)
            t.start()
            threads.append(t)
    threading.Thread(target=CA.reporter, args=(t0, n), daemon=True).start()

    items = []
    for created, doc_id, bslug, sub, title, body, form in rows:
        if f"{doc_id}:{bslug}" in judged:
            continue
        off = (body or "").lower().find((form or "").lower())
        items.append({"item_id": f"{doc_id}:{bslug}", "brand_slug": bslug,
                      "subreddit": sub, "link_title": title, "doc_id": doc_id,
                      "marked": mark_target(body or "", form or "", max(0, off))})
    for i in range(0, len(items), CA.BATCH):
        q.put(items[i:i + CA.BATCH])
    # An empty QUEUE is not a finished run: the last N batches are still inside
    # the workers when the queue drains, and signalling _stop then abandons
    # calls we already paid for (measured: 312 of 1,452 items, 18 labels). Wait
    # on the PROCESSED counter instead, with a stall timeout as the backstop.
    fed = len(items)
    last, stalled = -1, 0
    while True:
        done = sum(v[2] for v in CA.STATS.values())
        if done >= fed:
            break
        stalled = 0 if done != last else stalled + 1
        last = done
        if stalled > 60:                       # 5 min with no progress
            print(f"stalled at {done}/{fed} — stopping", flush=True)
            break
        time.sleep(5)
    time.sleep(20)                             # let the final commits land
    CA._stop.set()
    for t in threads:
        t.join(timeout=300)

    tot = sum(v[0] for v in CA.STATS.values())
    print(f"committed {tot:,} labels in {(time.time()-t0)/60:.1f} min · "
          f"deepseek spend ~${CA.SPEND['in']/1e6*0.28 + CA.SPEND['out']/1e6*0.42:.2f}",
          flush=True)


if __name__ == "__main__":
    main()
