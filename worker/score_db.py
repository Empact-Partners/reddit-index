#!/usr/bin/env python3
"""Daily scoring with SUPABASE as the corpus — the single source of truth.

Per category: pull the last 365 days of labelled mentions from the category's
scoring subreddits, RESTRICTED to brands whose category membership (primary
or also_in) includes this category — the fix for "Google Workspace tops the
CRM board" (docs/methodology-review.md §1). Then score_category() unchanged,
write .cache/index/<slug>.json in exactly the shape load.py --scores reads,
load, and prune every older week_start row so the table holds ONE truthful
set (the no-history rule).
"""
import datetime, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import db  # noqa: E402
from score import score_category, load_categories  # noqa: E402
from gate_calibration import check_rows  # noqa: E402

INDEX = os.path.join(HERE, ".cache", "index")
os.makedirs(INDEX, exist_ok=True)
WORD = {0: "neu", 1: "pos", 2: "neg", 3: "abstain"}


def main():
    # also_in membership lives in the CSV (the DB brands table has no column
    # for it) — load it here and filter in Python instead of contorting SQL.
    import csv as _csv
    also_in = {}
    for r in _csv.DictReader(open(os.path.join(REPO, "data", "brands.csv"))):
        cats = {r["primary_category_slug"]}
        cats.update(c for c in (r.get("also_in_category_slugs") or "").split(";") if c)
        also_in[r["slug"]] = cats

    cats = load_categories()
    state = {"conn": db.connect()}
    conn = state["conn"]
    window_end = datetime.date.today()
    window_start = window_end - datetime.timedelta(days=365)

    total = 0
    all_rows = []
    for slug in cats:
        # Scoring reads 100 categories in a row; a dropped link partway
        # through must reconnect and re-read that category, not abort the run
        # and block the publish.
        def _read(c, _slug=slug):
            with c.cursor() as cur:
                cur.execute("""
                SELECT b.slug, m.doc_id, m.doc_type, m.thread_id, m.author,
                       s.name, extract(epoch from m.created_utc), ms.label
                FROM mentions m
                JOIN mention_sentiment ms
                     ON ms.doc_id = m.doc_id AND ms.brand_id = m.brand_id
                JOIN brands b ON b.id = m.brand_id
                JOIN subreddits s ON s.id = m.subreddit_id
                JOIN category_subreddits cs
                     ON cs.subreddit_id = m.subreddit_id AND cs.is_scoring
                JOIN categories c ON c.id = cs.category_id
                WHERE c.slug = %s
                  AND m.created_utc >= now() - interval '365 days'
            """, (_slug,))
                return cur.fetchall()
        rows = db.run(state, _read, label=f"score read {slug}")
        ms = []
        for bslug, doc_id, doc_type, thread_id, author, sub, epoch, label in rows:
            if slug not in also_in.get(bslug, set()):
                continue  # the category-membership filter
            ms.append({"brand_slug": bslug, "doc_id": doc_id, "doc_type": doc_type,
                       "thread_id": thread_id, "author": author, "subreddit": sub,
                       "created_utc": float(epoch), "label": WORD.get(label, "abstain")})
        rows_out = score_category(slug, ms, cats) if ms else []
        for r in rows_out:
            r.setdefault("category_slug", slug)
        fp = os.path.join(INDEX, slug + ".json")
        json.dump({"category_slug": slug, "rows": rows_out,
                   "window_start": str(window_start), "window_end": str(window_end)},
                  open(fp + ".tmp", "w"))
        os.replace(fp + ".tmp", fp)
        total += len(rows_out)
        all_rows.extend(rows_out)
        if rows_out:
            print(f"  {slug:24} {len(ms):>6} mentions -> {len(rows_out):>3} brands", flush=True)
    conn.close()

    # The calibration gate: a run whose ordering contradicts its own raw data
    # never reaches the database.
    violations = check_rows(all_rows)
    if violations:
        print(f"\nCALIBRATION GATE FAILED — {len(violations)} violations, not loading:",
              flush=True)
        for v in violations:
            print("  " + v, flush=True)
        return 1

    print(f"\n{total} score rows across {len(cats)} categories; loading…", flush=True)
    loaded = subprocess.run([sys.executable, os.path.join(HERE, "load.py"), "--scores"])
    if loaded.returncode != 0:
        # NEVER prune after an incomplete load. week_start is stamped with
        # today's date, so a partial load moves max(week_start) forward and
        # the prune below would then delete the last COMPLETE published set —
        # leaving categories with no scores at all on the live site.
        print("  score load incomplete — skipping the prune and refusing to "
              "publish; the previous complete set stays live", flush=True)
        return 1

    # the no-history rule: one truthful week, nothing older
    prune_state = {"conn": db.connect()}

    def _prune(c):
        with c.cursor() as cur:
            cur.execute("DELETE FROM brand_category_scores WHERE week_start < "
                        "(SELECT max(week_start) FROM brand_category_scores)")
            n = cur.rowcount
            c.commit()
            return n
    print(f"pruned {db.run(prune_state, _prune, label='prune')} superseded score rows",
          flush=True)
    try:
        prune_state["conn"].close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
