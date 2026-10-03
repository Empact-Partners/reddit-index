#!/usr/bin/env python3
"""Tell the site which pages changed, then PROVE each one is served.

The site keeps every rendered page until it is told the page changed (app/api/revalidate/route.ts). This is
the teller, and the only one:

  1. which pages changed          site.brand_stats.page_hash is distinct from served_hash
                                  site.meta.boards_hash / slugs_hash against their served_ twins
                                  site.retired_page (a page that must now be a 404)
  2. expire those paths           POST /api/revalidate/ {"paths": [...]}; expired_hash records it
  3. fetch and read the           <meta name="ri-hash"> in the served HTML must equal the hash the database
     fingerprint back             holds. Only then is served_hash written.

Step 3 is the receipt, and it is not done for every page. Re-rendering one company page makes the site read
about 0.2 MB from the database, so fetching all of a night's changed pages would cost more egress than the
collection itself. What is ALWAYS fetched: every page that lost a card to a takedown, every page that must
now be a 404, and every index page. Beyond those, a sample (--verify, default 100). An expired page that
was not fetched re-renders from current data the first time someone opens it.

A page counts as "served" only when the live site returned it with the right fingerprint, never because
the endpoint answered 200: until October 2026 the endpoint answered 200 and changed nothing, and takedown
receipts were stamped on that answer.

  worker/site_publish.py                      # production (NEXT_PUBLIC_SITE_URL / redditindex.com)
  worker/site_publish.py --base https://...   # a preview deployment
  worker/site_publish.py --dry-run            # list what would be published
  worker/site_publish.py --verify 300         # fetch and prove up to this many company pages (takedowns always)
  worker/site_publish.py --max-expire 3000    # expire at most this many company pages this run
  worker/site_publish.py --no-stamp           # verify only: never record a preview's pages as served

Env or ~/.claude/.reddit-index.json: REVALIDATE_SECRET / revalidate_secret.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

UA = "reddit-index-publisher/1.0 (+https://redditindex.com/methodology/)"
HASH_RE = re.compile(r'<meta\s+name="ri-hash"\s+content="([0-9a-f]{0,64})"', re.I)
BATCH = 400          # the endpoint takes at most 500 paths a call
FETCHERS = 4         # concurrent page fetches; each one makes the site read one company's rows

# The flat namespace (decisions/0007). A company slug that equals one of these would be shadowed.
FRAMEWORK_PATHS = {"_next", "api", "sitemap", "sitemap.xml", "robots.txt", "favicon.ico", "llms.txt", "icon",
                   "apple-icon", "opengraph-image", "twitter-image", "manifest.webmanifest",
                   "methodology", "search", "freshness.json"}


def _secret() -> str:
    s = os.environ.get("REVALIDATE_SECRET")
    if s:
        return s
    try:
        return json.load(open(os.path.expanduser("~/.claude/.reddit-index.json")))["revalidate_secret"]
    except Exception:  # noqa: BLE001
        raise SystemExit("REVALIDATE_SECRET is not set and ~/.claude/.reddit-index.json has no revalidate_secret")


def _headers(base: str) -> dict:
    """A preview on *.vercel.app sits behind Vercel's login; the project's bypass secret lets a script in.
    Production is on its own domain and needs nothing."""
    h = {"User-Agent": UA}
    if ".vercel.app" in base:
        tok = os.environ.get("VERCEL_BYPASS")
        if not tok:
            try:
                tok = json.load(open(os.path.expanduser("~/.claude/.reddit-index.json"))).get("vercel_bypass")
            except Exception:  # noqa: BLE001
                tok = None
        if tok:
            h["x-vercel-protection-bypass"] = tok
    return h


def category_slugs() -> set[str]:
    with open(os.path.join(ROOT, "data", "categories.csv"), encoding="utf-8") as f:
        return {r["slug"] for r in csv.DictReader(f)}


def collisions(conn) -> list[str]:
    """Company slugs that would be shadowed by a category or a framework path. Must be empty."""
    taken = category_slugs() | FRAMEWORK_PATHS
    return sorted(r[0] for r in conn.execute("select slug from site.brand_stats") if r[0] in taken)


def expire(base: str, paths: list[str]) -> None:
    for i in range(0, len(paths), BATCH):
        chunk = paths[i:i + BATCH]
        req = urllib.request.Request(
            base + "/api/revalidate/", method="POST", data=json.dumps({"paths": chunk}).encode(),
            headers={**_headers(base), "Authorization": "Bearer " + _secret(), "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            got = json.loads(r.read())
        if got.get("revalidated") != len(chunk):
            raise RuntimeError(f"revalidate answered {got} for {len(chunk)} paths")


def fetch(base: str, path: str, want_hash: str | None, want_status: int = 200, tries: int = 3) -> dict:
    """GET a page. ok means: the status we expect AND (when a hash is expected) the page carries it."""
    out = {"path": path, "ok": False, "status": None, "hash": None, "bytes": 0}
    for attempt in range(tries):
        try:
            # gzip: an index page is 1.4 MB of HTML and 152 of them are fetched whenever the boards change
            req = urllib.request.Request(base + path, headers={**_headers(base), "Cache-Control": "no-cache",
                                                               "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                out["status"] = r.status
                gz = r.headers.get("Content-Encoding") == "gzip"
        except urllib.error.HTTPError as e:
            raw = e.read()
            out["status"] = e.code
            gz = e.headers.get("Content-Encoding") == "gzip"
        except Exception as e:  # noqa: BLE001 - a failed fetch is "not verified", never "fine"
            out["error"] = str(e)[:120]
            time.sleep(1.5 * (attempt + 1))
            continue
        out["bytes"] = len(raw)          # what crossed the wire
        body = gzip.decompress(raw) if gz else raw
        if out["status"] != want_status:
            time.sleep(1.5 * (attempt + 1))
            continue
        if want_hash is None:
            out["ok"] = True
            return out
        m = HASH_RE.search(body.decode("utf-8", "replace"))
        out["hash"] = m.group(1) if m else None
        if out["hash"] == want_hash:
            out["ok"] = True
            return out
        time.sleep(1.5 * (attempt + 1))   # the first request after an expiry can still be the old page
    return out


def run(conn, base: str, dry_run: bool = False, verify_n: int = 100, max_expire: int = 7000,
        stamp: bool = True, log=print) -> dict:
    base = base.rstrip("/")
    receipt = {"base": base, "pages_changed": 0, "pages_expired": 0, "pages_verified": 0, "takedown_pages": 0,
               "index_pages_verified": 0, "retired_verified": 0, "site_bytes_fetched": 0, "failed": []}

    clash = collisions(conn)
    if clash:
        raise RuntimeError(f"company slugs collide with a category or a reserved path: {clash[:10]}")
    leaks = conn.execute("select count(*) from site.bad_permalinks").fetchone()[0]
    if leaks:
        log(f"  note: {leaks} stored permalinks are not Reddit comment links; their cards are left out")
    receipt["bad_permalinks"] = leaks

    # 1. what changed since the path was last expired. Takedown pages first: a brand named in a removal
    #    whose page has not been SEEN without the card. Those are fetched whatever the sample size.
    rows = conn.execute("""
        select s.brand_id, s.slug, s.page_hash,
               exists (select 1 from public.removals r
                        where r.revalidated_at is null and s.brand_id = any (r.brand_ids)) as takedown,
               s.expired_hash is distinct from s.page_hash as needs_expiry
          from site.brand_stats s
         where s.expired_hash is distinct from s.page_hash
            or (s.served_hash is distinct from s.page_hash
                and exists (select 1 from public.removals r
                             where r.revalidated_at is null and s.brand_id = any (r.brand_ids)))
         order by 4 desc, s.expired_at nulls first, md5(s.slug || current_date::text)""").fetchall()
    # After takedowns, the pages that have waited longest: with max_expire below the number changed (the cap
    # that bounds regeneration egress, ops/schedule.json), every page still comes round within a few days.
    receipt["pages_changed"] = len(rows)
    retired = [r[0] for r in conn.execute("select slug from site.retired_page where gone_at is null")]
    meta = conn.execute("select boards_hash, served_boards_hash, slugs_hash, served_slugs_hash from site.meta").fetchone()
    boards_changed = meta[0] != meta[1]
    slugs_changed = meta[2] != meta[3]

    takedown = [r for r in rows if r[3]]
    others = [r for r in rows if not r[3]]
    todo = takedown + others[:max(0, max_expire - len(takedown))]
    to_verify = takedown + others[:verify_n]
    receipt["takedown_pages"] = len(takedown)
    receipt["pages_deferred"] = len(rows) - len(todo)
    log(f"  {len(rows)} company pages changed ({len(takedown)} with a takedown), "
        f"{len(retired)} retired, boards {'changed' if boards_changed else 'unchanged'}, "
        f"page set {'changed' if slugs_changed else 'unchanged'}")
    if dry_run:
        return receipt

    index_paths = ["/"] + [f"/{s}/" for s in sorted(category_slugs())] if boards_changed else []
    file_paths = ["/freshness.json"] + (["/llms.txt"] if boards_changed or slugs_changed else []) \
        + (["/sitemap.xml"] if slugs_changed else [])

    # 2. expire, and remember which hash each path was expired at
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        expire(base, [f"/{r[1]}/" for r in chunk])
        if stamp:
            conn.execute("""update site.brand_stats s set expired_hash = v.h, expired_at = now()
                              from unnest(%s::bigint[], %s::text[]) as v(id, h)
                             where s.brand_id = v.id and s.page_hash = v.h""",
                         ([r[0] for r in chunk], [r[2] for r in chunk]))
    extra = [f"/{s}/" for s in retired] + index_paths + file_paths
    if extra:
        expire(base, extra)
    receipt["pages_expired"] = len(todo)

    # 3. fetch and read back
    def verify(jobs: list[tuple[str, str | None, int]]) -> list[dict]:
        with ThreadPoolExecutor(FETCHERS) as ex:
            return list(ex.map(lambda j: fetch(base, j[0], j[1], j[2]), jobs))

    ok_ids = []
    for i in range(0, len(to_verify), 200):
        chunk = to_verify[i:i + 200]
        res = verify([(f"/{r[1]}/", r[2], 200) for r in chunk])
        good = [(r[0], r[2]) for r, v in zip(chunk, res) if v["ok"]]
        receipt["site_bytes_fetched"] += sum(v["bytes"] for v in res)
        receipt["failed"] += [{"path": v["path"], "status": v["status"], "hash": v["hash"], "takedown": bool(r[3])}
                              for r, v in zip(chunk, res) if not v["ok"]]
        if good and stamp:
            # only where the row still holds the hash we verified: a refresh that landed meanwhile stays unserved
            conn.execute("""update site.brand_stats s set served_hash = v.h, served_at = now()
                              from unnest(%s::bigint[], %s::text[]) as v(id, h)
                             where s.brand_id = v.id and s.page_hash = v.h""",
                         ([g[0] for g in good], [g[1] for g in good]))
        ok_ids += [g[0] for g in good]
        log(f"    verified {len(ok_ids)}/{len(to_verify)} company pages", flush=True)
    receipt["pages_verified"] = len(ok_ids)
    receipt["verified_brand_ids"] = ok_ids

    if retired:
        res = verify([(f"/{s}/", None, 404) for s in retired])
        gone = [s for s, v in zip(retired, res) if v["ok"]]
        if gone and stamp:
            conn.execute("update site.retired_page set gone_at = now() where slug = any (%s)", (gone,))
        receipt["retired_verified"] = len(gone)
        receipt["failed"] += [{"path": v["path"], "status": v["status"], "want": 404} for v in res if not v["ok"]]

    if index_paths:
        res = verify([(p, meta[0], 200) for p in index_paths])
        receipt["index_pages_verified"] = sum(v["ok"] for v in res)
        receipt["site_bytes_fetched"] += sum(v["bytes"] for v in res)
        receipt["failed"] += [{"path": v["path"], "status": v["status"], "hash": v["hash"]} for v in res if not v["ok"]]
        if all(v["ok"] for v in res) and stamp:
            conn.execute("update site.meta set served_boards_hash = %s where boards_hash = %s", (meta[0], meta[0]))
    if slugs_changed:
        v = fetch(base, "/sitemap.xml", None, 200)
        if not v["ok"]:
            receipt["failed"].append({"path": "/sitemap.xml", "status": v["status"]})
        elif stamp:
            conn.execute("update site.meta set served_slugs_hash = %s where slugs_hash = %s", (meta[2], meta[2]))

    receipt["failed"] = receipt["failed"][:100]
    log(f"  published: {receipt['pages_expired']} company pages expired, {receipt['pages_verified']} fetched and "
        f"proven ({len(takedown)} takedown), {receipt['index_pages_verified']} index pages, "
        f"{receipt['retired_verified']} retired; {len(receipt['failed'])} failed")
    return receipt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("NEXT_PUBLIC_SITE_URL", "https://redditindex.com"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", type=int, default=100, help="company pages to fetch and prove, beyond takedowns")
    ap.add_argument("--max-expire", type=int, default=7000)
    ap.add_argument("--no-stamp", action="store_true",
                    help="expire and verify but record nothing (a preview or a local server)")
    a = ap.parse_args()
    import db
    with db.connect() as conn:
        conn.autocommit = True
        r = run(conn, a.base, a.dry_run, a.verify, a.max_expire, stamp=not a.no_stamp)
    print(json.dumps({k: v for k, v in r.items() if k not in ("failed", "verified_brand_ids")}),
          "| failed:", len(r["failed"]))
    return 2 if r["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
