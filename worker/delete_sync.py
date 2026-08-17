#!/usr/bin/env python3
"""Purge content its author deleted on Reddit, then invalidate the cached page.

This is not deferrable. Reddit's Developer Terms require deletions to propagate
"as soon as possible", and `decisions/0002` makes it a CONDITION of the decision
to display full comment text at all — not a feature that lands later. The clock
starts the moment the first real comment is public, which is the moment the site
is.

The chain, per 08-architecture.md §8:

    stored doc_ids -> /api/info -> purge mentions and children
                   -> write removals -> revalidateTag -> stamp revalidated_at

⚠️ Purging Postgres is HALF the job. A cached page keeps serving a removed
comment until its tag is invalidated, which is why `delete_sync` owns the
revalidate call rather than leaving it to the daily publish, and why
`removals.revalidated_at` is the receipt. **A row with `purged_at` set and
`revalidated_at` null is an open defect**, and `gate_checks.sql` asserts it.

The UI contract this serves: a card whose source was deleted simply is not in
the list on the next pass. No tombstone, no cached copy, no "[deleted]"
placeholder holding the slot.
"""
import argparse, json, os, sys, urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import reddit_client as rc  # noqa: E402

REF = json.load(open(os.path.expanduser("~/.claude/.reddit-index.json")))["project_ref"]
TOKEN = open(os.path.expanduser("~/.claude/.supabase-empact.token")).read().strip()
BATCH = 100  # /api/info's limit


def sql(query):
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as f:
        return json.loads(f.read())


def lit(v):
    return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"


def revalidate(tags, secret, site):
    """POST /api/revalidate. The publisher DIFFS rather than blanket-sends, and
    logs the slug set every time — a day sending thousands of tags is a defect
    in the diff, not a busy news day (08 §4)."""
    if not tags or not secret:
        return False
    body = json.dumps({"tags": sorted(tags)}).encode()
    req = urllib.request.Request(
        site.rstrip("/") + "/api/revalidate", data=body,
        headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as f:
            print(f"  revalidated {len(tags)} tag(s): {sorted(tags)[:12]}"
                  f"{' …' if len(tags) > 12 else ''}")
            return f.status < 300
    except Exception as e:
        print(f"  revalidate failed: {e}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5000,
                    help="documents to probe this pass; the oldest-checked first")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--publish-follows", action="store_true",
                    help="a full rebuild runs after this in the same chain "
                         "(daily_mac.sh), which invalidates more thoroughly "
                         "than a tag ever could — stamp revalidated_at on it")
    args = ap.parse_args()

    # LEAST-RECENTLY-CHECKED first, not oldest-loaded first.
    #
    # This ordered by `m.loaded_at asc` and stamped nothing, so every pass
    # probed the same oldest 5,000 documents and no mention collected after
    # them was ever checked for deletion at all. Reddit's Developer Terms
    # require deletions to propagate as soon as possible; a probe that can
    # only ever see the front of the table does not do that. Same shape of bug
    # as the revisit queue: a queue with no memory serves the same head
    # forever. `mentions.delete_checked_at` is that memory, and NULLS FIRST
    # means nothing is re-probed until everything has been probed once.
    rows = sql(f"""
      select m.doc_id, m.brand_id, b.slug as brand_slug, c.slug as category_slug
      from mentions m
      join brands b on b.id = m.brand_id
      left join brand_category_scores s on s.brand_id = m.brand_id
      left join categories c on c.id = s.category_id
      order by m.delete_checked_at asc nulls first, m.loaded_at asc
      limit {args.limit}""")
    if not rows:
        print("no mentions stored yet")
        return 0


    by_doc = defaultdict(list)
    for r in rows:
        by_doc[r["doc_id"]].append(r)
    doc_ids = list(by_doc)
    print(f"probing {len(doc_ids)} documents through /api/info…")

    alive = set()
    for i in range(0, len(doc_ids), BATCH):
        chunk = doc_ids[i:i + BATCH]
        resp = rc.info(chunk)
        if "_err" in resp:
            print(f"  batch {i // BATCH + 1}: error {resp['_err']}, skipping")
            continue
        for child in resp.get("data", {}).get("children", []):
            d = child.get("data", {})
            fullname = d.get("name")
            body = d.get("body") or d.get("selftext") or ""
            author = d.get("author") or ""
            # Present in the listing but blanked out is still a deletion.
            if body in ("[deleted]", "[removed]") or author == "[deleted]":
                continue
            if fullname:
                alive.add(fullname)

    gone = [d for d in doc_ids if d not in alive]
    print(f"  {len(alive)} still live · {len(gone)} deleted or removed at the source")

    # Stamp EVERY document probed, survivors included — that stamp is what
    # moves the cursor to the next slice of the table on the following pass.
    # Without it the probe re-reads the same head forever (it did).
    if not args.dry_run and doc_ids:
        ids = ", ".join(lit(d) for d in doc_ids)
        sql(f"update mentions set delete_checked_at = now() where doc_id in ({ids});")
        print(f"  stamped {len(doc_ids)} documents as checked")

    if not gone:
        print("nothing to purge")
        return 0
    if args.dry_run:
        for g in gone[:20]:
            print("   would purge", g)
        return 0

    tags = set()
    for g in gone:
        for r in by_doc[g]:
            tags.add(f"company:{r['brand_slug']}")
            if r.get("category_slug"):
                tags.add(f"category:{r['category_slug']}")
    tags.add("pooled-homepage")

    # Ledger first, then purge, then revalidate, then stamp the receipt. In that
    # order, a crash anywhere leaves a row that gate_checks.sql will flag rather
    # than a page still serving a deleted comment with nothing recording it.
    ids = ",".join(lit(g) for g in gone)
    sql(f"""
      insert into removals (doc_id, doc_type, brand_ids, reason, detected_at)
      select m.doc_id, m.doc_type, array_agg(m.brand_id), 'source_deleted', now()
      from mentions m where m.doc_id in ({ids})
      group by m.doc_id, m.doc_type
      on conflict (doc_id) do nothing;""")
    sql(f"delete from mention_sentiment where doc_id in ({ids});")
    sql(f"delete from mentions where doc_id in ({ids});")
    sql(f"update removals set purged_at = now() where doc_id in ({ids}) and purged_at is null;")
    print(f"  purged {len(gone)} documents and their sentiment rows")

    # The secret lives in the credential file on this machine and in the env
    # in a container. Reading only the env meant every Mac run silently failed
    # to revalidate and left rows that gate_checks.sql calls open defects.
    secret = os.environ.get("REVALIDATE_SECRET")
    if not secret:
        try:
            secret = json.load(open(os.path.expanduser(
                "~/.claude/.reddit-index.json"))).get("revalidate_secret")
        except Exception:
            secret = None
    site = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://redditindex.com")
    if revalidate(tags, secret, site) or args.publish_follows:
        sql(f"update removals set revalidated_at = now() where doc_id in ({ids});")
        print("  stamped revalidated_at"
              + (" (the publish in this chain rebuilds every page)"
                 if args.publish_follows else ""))
    else:
        print("  ⚠️ NOT revalidated. Every purged row is now an open defect until it is —"
              " gate_checks.sql assertion 4 will show them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
