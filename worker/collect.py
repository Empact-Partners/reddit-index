#!/usr/bin/env python3
"""The sweep's collection stage: new posts and recent comment trees from every scoring subreddit.

This is worker/daily.py's collection, reused function by function (listing, qualification, resolution,
insertion and the watermark rules are its, and each carries the incident it was written for), inside a loop
that can be stopped and bounded:

  * caps checked before every subreddit and every comment tree: Reddit calls, new mentions, wall time. A cap can
    therefore be passed by at most one subreddit's listing (up to 8 calls) or one subreddit's new mentions; the
    caps are safety bounds set well above a normal day, not exact quotas (review, 2026-10-03);
  * a stop check every 25 subreddits (public.sweep_control, and anything else the caller passes in);
  * a comment tree Reddit failed to return is NOT marked read (daily.py marked it read and lost it);
  * a quiet subreddit (no qualifying post on its last pass) is visited every third day, not every day;
  * a thread whose comment count and score did not change is not rewritten (each rewrite is shipped to
    backup storage and counted as egress);
  * the brand list and subreddit lists are the repository's, read at start: the old collector ran a
    19 August image for six weeks and never saw 4,471 brands added after it.

Two modes (decision 0029). "trees": comments come from the comment trees of stored threads, one thread a call.
"stream": comments come from the subreddit's comment listing, 100 a call whatever their thread, back to the newest
comment already read; a thread is stored only when it holds a mention, and the stage ends when the run's room for
new mentions is used.

Order: most overdue first. A core subreddit is due every day, any other every ROTATE_DAYS days, and each is
ranked by how many of its intervals have passed since its last visit (never visited: first). daily.py's order put
every core subreddit before every other one; the first scheduled run (2026-10-04) had time for 466 subreddits
with 553 core ones waiting, so under that order the other 1,354 would never have come round.
"""
from __future__ import annotations

import collections
import concurrent.futures
import contextlib
import datetime as dt
import time

import daily as d          # worker/daily.py: the collection helpers
import db
import reddit_client as rc
from harvest import post_doc, stream_docs, tree_docs, _abs

QUIET_DAYS = 3
# Work that cannot yield anything is not done (11 Oct, measured on one daytime pass of 541 subreddits: a listing call
# brought 12.9 mentions, a comment-tree call 0.61; 1,311 of 7,898 tree calls were for threads with no comment; 84% of
# the repeat reads of a thread found nothing; 69% of the 10,786 threads stored never held a mention, and each is a
# row written, stamped, and a week later archived and deleted; 1,609 of them were posts more than 400 days old).
HARVEST_DAYS = 400       # a post older than this when listed is not stored and its comments are not read: the
                         # score counts the trailing 365 days (docs/methodology.md), the labels 400
DEAD_AFTER_HOURS = 48    # a post that names no brand and has no comment at this age is not stored
CANDIDATES = 200         # threads of one subreddit weighed for a comment-tree read on one visit
ROTATE_DAYS = 3   # a non-core subreddit is due every third day, a core one every day

THREADS_UPSERT = (
    "INSERT INTO threads (id, subreddit_id, link_title, permalink, created_utc, num_comments, archived, score, "
    "first_seen_at) VALUES (%s,%s,%s,%s,to_timestamp(%s),%s,%s,%s,now()) "
    "ON CONFLICT (id) DO UPDATE SET num_comments = EXCLUDED.num_comments, score = EXCLUDED.score "
    "WHERE (threads.num_comments, threads.score) IS DISTINCT FROM (EXCLUDED.num_comments, EXCLUDED.score)")


# Decision 0029: comments are read from each subreddit's comment listing, 100 a call whatever thread they sit in,
# not one thread at a time (12 Oct, measured on 130 subreddits: 10.5 mention rows a listing call against 1.7 a
# comment-tree call, and the trees held 55% of the mentions the same pages showed).
STREAM_PAGES = 10        # pages of 100 comments read back toward the watermark on one visit: the listing's own end
FIRST_VISIT_PAGES = 3    # a subreddit's first visit under the listing reads its newest 300 comments
# A thread stored under the comment listing holds a mention already and its comments keep arriving through the
# listing: it is stamped as read, with the count Reddit shows, so a run still on comment trees (the night, until
# it moves too) reads its tree only if it grows. A thread already stored is left as it is: no rewrite, no log.
THREADS_STREAM_INSERT = (
    "INSERT INTO threads (id, subreddit_id, link_title, permalink, created_utc, num_comments, archived, score, "
    "first_seen_at, tree_fetched_at, tree_comments) VALUES (%s,%s,%s,%s,to_timestamp(%s),%s,%s,%s,now(),now(),%s) "
    "ON CONFLICT (id) DO NOTHING")


class Stop(Exception):
    """A cap or a stop switch: end the stage cleanly, keep everything committed so far."""


class Allowance(Stop):
    """The night's planned allowance is used (Reddit calls, or the time set aside for collection). This is how a
    normal night ends: collection rotates through the subreddits, core first, and the rest wait their turn. It is
    recorded on the receipt and it is NOT an alert. A real limit (the egress cap, an abnormal flood of new
    mentions, the stop switch) raises Stop and is."""


def without_vendor(names, vendor: set[str]) -> tuple[list[str], int]:
    """Drop the vendor-named subreddits (lower-case names in `vendor`); returns what is left and how many went."""
    kept = [n for n in names if n.lower() not in vendor]
    return kept, len(names) - len(kept)


MAX_TREE_WORKERS = 4


def fetch_trees(pool, revisit, before_each, waited: list):
    """(thread id, title, comment tree) for each thread of `revisit`, in its order.

    `pool` None: one request at a time, as collection always ran. With a pool, up to its width are in flight while
    the caller matches the trees that have arrived. Reddit sees the same rate either way: reddit_client lets one
    request START per period whichever thread asks. What changes is that a request's own seconds (a 500-comment tree
    takes one to two) and the matching and writing after it no longer add to every period. 10 Oct, one at a time:
    27 calls a minute by day against a declared 45, 32 by night against 50.
    `before_each` is called before every request is started and may raise (a cap, the deadline). `waited[0]` grows
    by the seconds the caller stood waiting for Reddit. However the caller leaves (the end, an error in a tree, an
    error of its own: close the generator), requests not yet started are cancelled, so one subreddit's failure
    leaves nothing queued behind the next one's requests."""
    if pool is None:
        for tid, title in revisit:
            before_each()
            t = time.time()
            tree = d.tree_fresh(tid.replace("t3_", ""))
            waited[0] += time.time() - t
            yield tid, title, tree
        return
    ahead: collections.deque = collections.deque()
    it = iter(revisit)

    def top_up() -> None:
        while len(ahead) < pool._max_workers:
            nxt = next(it, None)
            if nxt is None:
                return
            before_each()
            ahead.append((nxt[0], nxt[1], pool.submit(d.tree_fresh, nxt[0].replace("t3_", ""))))
    try:
        top_up()
        while ahead:
            tid, title, fut = ahead.popleft()
            t = time.time()
            tree = fut.result()
            waited[0] += time.time() - t
            top_up()   # before the caller starts matching this tree, so the pool stays full while it works
            yield tid, title, tree
    finally:
        for _tid, _title, fut in ahead:
            fut.cancel()


def worth_storing(post: dict, names_a_brand: bool, now_ts: float) -> bool:
    """A qualifying post is stored as a thread when it names a brand, has a comment to read, or is young enough to
    get one. Otherwise it is a row nobody will ever read, deleted a week later."""
    return (names_a_brand or int(post.get("num_comments") or 0) > 0
            or now_ts - float(post.get("created_utc") or 0) < DEAD_AFTER_HOURS * 3600)


def choose_trees(cands: list, current: dict, limit: int) -> tuple[list, dict]:
    """Which comment trees to read on this visit.

    cands: (thread id, title, comments stored at first sight, tree_fetched_at, comments when the tree was last read)
    current: thread id -> the comments Reddit shows now, where known (the listing just read, or /api/info).
    A thread never read is read when it has a comment (the count now, else the stored one). A thread already read
    is read again only when its count has grown since. Most comments first, then most growth.
    Returns ([(thread id, title)], {"no_comments": skipped, "unchanged": skipped})."""
    unread, grown, skipped = [], [], {"no_comments": 0, "unchanged": 0}
    for tid, title, stored, fetched_at, at_fetch in cands:
        now_n = current.get(tid)
        if fetched_at is None:
            n = now_n if now_n is not None else int(stored or 0)
            if n > 0:
                unread.append((n, tid, title))
            else:
                skipped["no_comments"] += 1
        elif now_n is not None and now_n > int(at_fetch or 0):
            grown.append((now_n - int(at_fetch or 0), tid, title))
        else:
            skipped["unchanged"] += 1
    unread.sort(key=lambda x: -x[0])
    grown.sort(key=lambda x: -x[0])
    return [(tid, title) for _n, tid, title in (unread + grown)[:limit]], skipped


def info_counts(ids: list) -> dict:
    """thread id -> the comment count Reddit shows now, for up to 100 threads in one call. {} when it fails."""
    r = rc.get("/api/info", {"id": ",".join(ids[:100]), "raw_json": 1}, bucket="stream", use_cache=False)
    if not isinstance(r, dict) or "_err" in r:
        return {}
    out = {}
    for k in r.get("data", {}).get("children", []):
        dd = k.get("data") or {}
        if k.get("kind") == "t3" and dd.get("name"):
            out[dd["name"]] = int(dd.get("num_comments") or 0)
    return out


def tree_count(tree) -> int | None:
    """The comment count on the post of a /comments response, or None."""
    try:
        return int(tree[0]["data"]["children"][0]["data"].get("num_comments") or 0)
    except Exception:  # noqa: BLE001
        return None


def info_posts(ids: list) -> dict | None:
    """thread id -> the post as Reddit shows it now, for up to 100 threads in one call. None when the call failed
    (ask again on the next visit); a thread missing from an answer is one Reddit no longer returns."""
    r = rc.get("/api/info", {"id": ",".join(ids[:100]), "raw_json": 1}, bucket="stream", use_cache=False)
    if not isinstance(r, dict) or "_err" in r:
        return None
    return {k["data"]["name"]: k["data"] for k in r.get("data", {}).get("children", [])
            if k.get("kind") == "t3" and (k.get("data") or {}).get("name")}


def thread_row(post: dict, sid: int) -> tuple | None:
    """The threads row of a post, for THREADS_STREAM_INSERT (the last value: its comment count, stamped as read).
    None when the post lacks what the row cannot do without (its id, its address, its time)."""
    pid, link, made = post.get("id"), post.get("permalink"), post.get("created_utc")
    if not (pid and link and made):
        return None
    n = int(post.get("num_comments") or 0)
    return (f"t3_{pid}", sid, (post.get("title") or "")[:500], _abs(link), made, n, bool(post.get("archived")),
            post.get("score") or 0, n)


def fetch_comments(sub: str, watermark_ts: float | None, floor_ts: float, pages: int,
                   before_each=lambda: None) -> dict:
    """A subreddit's newest comments, newest first, back to the newest one already read.

    watermark_ts: the time of the newest comment read on the last visit (None: never read under the listing).
    floor_ts: nothing older than this is kept (the 400-day window). pages: calls allowed on this visit.
    Stops on the comments' own times, never on a comment id: a listing anchored on a comment that was since deleted
    returns nothing, which would read as "no new comments" for ever.
    Returns {"docs": the scorable comments newer than the watermark (harvest.stream_docs), "ok": no page failed,
    "reached": the read got back to the watermark or to the listing's end, "calls", "comments": raw count listed,
    "newest": the newest comment time seen, or 0}."""
    out = {"docs": [], "ok": True, "reached": False, "calls": 0, "comments": 0, "newest": 0.0}
    stop_at = max(watermark_ts or 0.0, floor_ts)
    after = None
    for _ in range(max(1, pages)):
        before_each()
        r = rc.subreddit_comments(sub, limit=100, after=after)
        out["calls"] += 1
        if not isinstance(r, dict) or "_err" in r:
            out["ok"] = False
            break
        times = [float((k.get("data") or {}).get("created_utc") or 0)
                 for k in r.get("data", {}).get("children", []) if k.get("kind") == "t1"]
        if not times:
            out["reached"] = True
            break
        out["comments"] += len(times)
        out["newest"] = max(out["newest"], max(times))
        out["docs"].extend(x for x in stream_docs(r) if float(x.get("created_utc") or 0) > stop_at)
        after = r.get("data", {}).get("after")
        if min(times) <= stop_at or not after:
            out["reached"] = True
            break
    return out


def stream_visit(cur, sub: str, sid: int, qual: list, named: set, listed: dict, mrows: list, resolver, run_id: str,
                 matching: list, waited: list, cutoff: float, first_pages: int, pages: int,
                 before_each=lambda: None) -> dict:
    """One subreddit under the comment listing (decision 0029), inside the caller's transaction.

    Reads the comment listing back to the comment watermark, appends a row to `mrows` for every brand a comment
    names, stores the threads that now hold a mention (the posts in `qual` whose id is in `named`, and the thread of
    every comment mention: from the post listing just read when it is on those pages, else from /api/info, 100 a
    call) and moves the comment watermark when every call answered.
    Returns the visit's counts; the caller adds them to the receipt once the transaction is committed."""
    sv = {"rows": 0, "calls": 0, "comments": 0, "first": 0, "gap": 0, "failed": 0, "from_listing": 0,
          "from_info": 0, "info_calls": 0, "without_thread": 0}
    cwm = d.get_watermark(cur, sub, stage="comment_stream")
    t_r = time.time()
    got = fetch_comments(sub, cwm, cutoff, first_pages if cwm is None else pages, before_each)
    waited[0] += time.time() - t_r
    sv["calls"], sv["comments"], sv["first"] = got["calls"], got["comments"], int(cwm is None)
    ok = got["ok"]
    # the listing ended (about 1,000 comments) before the newest comment already read: the ones between are not
    # reachable through it any more. Counted and named on the receipt; the watermark moves on.
    sv["gap"] = int(cwm is not None and ok and not got["reached"])
    t_m = time.time()
    crows = []
    for doc in got["docs"]:
        for h in resolver.resolve(doc["body"], sub, doc["link_title"]):
            crows.append((doc["id"], 1, doc["link_id"], sid, doc["author"], doc.get("created_utc") or 0,
                          doc["permalink"], doc.get("score") or 0, doc["body"], h["conf"], h["alias"],
                          h["rule_fired"], run_id, h["brand_slug"]))
    matching[0] += time.time() - t_m
    rows: dict = {}
    for p in qual:
        if p.get("id") in named:
            r = thread_row(p, sid)
            if r:
                rows[r[0]] = r
    need = {r[2] for r in crows} - set(rows)
    if need:
        cur.execute("SELECT id FROM threads WHERE id = ANY(%s)", (sorted(need),))
        need -= {r[0] for r in cur.fetchall()}
    for tid in sorted(need):
        r = thread_row(listed[tid], sid) if tid in listed else None
        if r:
            rows[tid] = r
            sv["from_listing"] += 1
    ask = sorted(need - set(rows))
    unasked: set = set()
    for i in range(0, len(ask), 100):
        before_each()
        t_r = time.time()
        posts = info_posts(ask[i:i + 100])
        waited[0] += time.time() - t_r
        sv["info_calls"] += 1
        if posts is None:      # the call failed: these comments are read again on the next visit
            ok = False
            unasked |= set(ask[i:i + 100])
            continue
        for tid, post in posts.items():
            r = thread_row(post, sid) if tid in need else None
            if r:
                rows[tid] = r
                sv["from_info"] += 1
    lost = need - set(rows)
    if lost:
        # a thread Reddit no longer returns: its comments could not be shown with a title, so they are not stored
        sv["without_thread"] = sum(1 for r in crows if r[2] in lost and r[2] not in unasked)
        crows = [r for r in crows if r[2] not in lost]
    if rows:
        cur.executemany(THREADS_STREAM_INSERT, list(rows.values()))
    mrows.extend(crows)
    sv["rows"], sv["failed"] = len(crows), int(not ok)
    if ok and got["newest"]:
        d.set_watermark(cur, sub, dt.datetime.fromtimestamp(got["newest"], dt.timezone.utc), got["comments"],
                        stage="comment_stream")
    return sv


def mentions_room(egress_gb: float, bytes_per_mention: float, share: float = 0.9) -> int:
    """How many new mentions a run collects before it leaves the rest of its egress room to labelling them: the
    run's own cap on estimated egress, less a margin, over what one collected and labelled mention writes."""
    return max(0, int(egress_gb * 1e9 * share / max(1.0, bytes_per_mention)))


def merge_case(mapping: dict, core: set, last_visit: dict) -> tuple[dict, set, int]:
    """One entry per subreddit, whatever the letter case of its rows in the map.

    The map names 576 subreddits twice ("Accounting" and "accounting", from two discovery runs). Reddit and the
    subreddits table treat them as one; the watermark is kept per spelling, so each was listed twice and its comment
    trees fetched twice in every rotation. The spelling visited most recently is kept (its watermark goes on), with
    the categories of both and core if either is. `last_visit`: exact spelling -> time of its last listing.
    Returns the merged map, the merged core set, and how many second spellings were folded in."""
    groups: dict[str, list[str]] = {}
    for name in mapping:
        groups.setdefault(name.lower(), []).append(name)
    out, out_core, folded = {}, set(), 0
    for names in groups.values():
        names = sorted(names)
        keep = max(names, key=lambda n: (last_visit.get(n) is not None, last_visit.get(n) or 0))
        cats: list[str] = []
        for n in names:
            cats += [c for c in mapping[n] if c not in cats]
        out[keep] = cats
        if any(n in core for n in names):
            out_core.add(keep)
        folded += len(names) - 1
    return out, out_core, folded


def plan(conn, today: dt.datetime) -> tuple[list[str], dict, set, int, dict]:
    mapping = d.load_scoring_map()
    core = set(d.load_scoring_map(core_only=True))
    # A vendor-named subreddit (r/AZURE, r/ClaudeAI, r/hetzner) can never hold a mention: the database refuses the
    # row (reject_vendor_sub_mention, 13-algorithm.md section 2). 133 of them carry is_scoring in some category of
    # the map, so they were visited: a listing and up to 24 comment trees each, every mention then refused one row
    # at a time (10 Oct: 65 of the 962 subreddits visited by day). They are not visited.
    vendor = {r[0].lower() for r in conn.execute("SELECT name FROM subreddits WHERE is_vendor_sub").fetchall()}
    rows = conn.execute(
        "SELECT scope, finished_at, rows FROM ingest_state WHERE ym='daily' AND stage='new_listing' "
        "AND code_version=%s AND scope NOT LIKE '\\_%%'", (d.CODE_VERSION,)).fetchall()
    seen: dict = {}   # lower-case name -> (time, qualifying posts) of the latest listing under any spelling
    for scope, fin, n in rows:
        k = scope.lower()
        if k not in seen or (fin is not None and (seen[k][0] is None or fin > seen[k][0])):
            seen[k] = (fin, n)
    mapping, core, n_case = merge_case(mapping, core, {r[0]: r[1] for r in rows})
    candidates, n_vendor = without_vendor(list(mapping), vendor)
    # a subreddit with a thread still inside the comment-revisit window is never quiet: skipping it would leave
    # those threads' later comments unread until they aged out of the window (review, 2026-10-04)
    active = {r[0].lower() for r in conn.execute(
        "SELECT DISTINCT s.name FROM threads t JOIN subreddits s ON s.id = t.subreddit_id "
        "WHERE t.first_seen_at > now() - make_interval(hours => %s)", (d.REVISIT_HOURS,)).fetchall()}
    subs, quiet = [], 0
    for s in candidates:
        fin, n = seen.get(s.lower(), (None, None))
        if fin is not None and n == 0 and fin > today - dt.timedelta(days=QUIET_DAYS) and s.lower() not in active:
            quiet += 1
            continue
        subs.append(s)
    prio = partner_priority()
    ov = {x: overdue(seen.get(x.lower(), (None, 0))[0], x in core, today) for x in subs}
    # decision 0018: a due partner-priority subreddit (where an Empact partner is AI-cited, posted or named) goes
    # before every other due subreddit; then the most overdue, core before the rest
    subs.sort(key=lambda x: rank(ov[x], x.lower() in prio, x in core))
    return subs, mapping, core, quiet, {"vendor": n_vendor, "second_spelling": n_case}


def rank(overdue_by: float, priority: bool, is_core: bool) -> tuple:
    """Sort key: a due partner-priority subreddit first, then the most overdue, core before the rest."""
    return (0 if (priority and overdue_by >= 1) else 1, -overdue_by, not is_core)


def partner_priority() -> set[str]:
    """Scoring subreddits marked partner_priority=1 in data/category-subreddits.csv (decision 0018)."""
    import csv
    import os
    with open(os.path.join(d.REPO, "data", "category-subreddits.csv")) as f:
        return {r["subreddit"].lower() for r in csv.DictReader(f)
                if r.get("partner_priority") == "1" and r.get("is_scoring") == "True"}


def overdue(last_visit: dt.datetime | None, is_core: bool, today: dt.datetime) -> float:
    """How many due intervals have passed since the last visit; never visited is the most overdue."""
    if last_visit is None:
        return float("inf")
    days = (today - last_visit).total_seconds() / 86400
    return days / (1.0 if is_core else ROTATE_DAYS)


def run(conn, caps: dict, deadline: float, should_stop=lambda: None, log=print, run_id: str | None = None) -> dict:
    """caps: reddit_calls, mentions, and optionally tree_workers (comment trees in flight at once, 1 to 4; default
    1), mode ("trees", the default: comments from the comment trees of stored threads; "stream": from each
    subreddit's comment listing, decision 0029), mentions_room (new mentions after which the stage ends for this
    run, a planned end like the Reddit calls), stream_pages and first_visit_pages.
    should_stop(): returns a reason string to stop, or None. run_id: the sweep's
    receipt id, stamped on every mention this stage writes, so a mention can be traced to the run that wrote it
    (scripts/schedule_check.py matches them to receipts by it)."""
    t0 = time.time()
    calls0 = rc.stats()["calls"]
    now = dt.datetime.now(dt.timezone.utc)
    net0 = rc.stats()
    subs, mapping, core, quiet, never = plan(conn, now)
    matching = [0.0]   # seconds spent finding brand names in text; see rec["seconds"] at the end
    waited = [0.0]     # seconds the stage stood waiting for Reddit (a listing or a comment tree)
    workers = max(1, min(int(caps.get("tree_workers") or 1), MAX_TREE_WORKERS))
    stream = (caps.get("mode") or "trees") == "stream"
    stream_pages = max(1, min(int(caps.get("stream_pages") or STREAM_PAGES), STREAM_PAGES))
    first_pages = max(1, min(int(caps.get("first_visit_pages") or FIRST_VISIT_PAGES), STREAM_PAGES))
    room = caps.get("mentions_room")
    pool = (concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="tree")
            if workers > 1 and not stream else None)
    rec = {"subs_planned": len(subs) + quiet, "subs_skipped_quiet": quiet, "subs_skipped_vendor": never["vendor"],
           "subs_second_spelling_merged": never["second_spelling"],
           "subs_visited": 0, "posts_qualified": 0,
           "mentions_new": 0, "mentions_rejected": 0, "trees_fetched": 0, "trees_failed": 0,
           "trees_skipped_no_comments": 0, "trees_skipped_unchanged": 0, "info_calls": 0,
           "posts_older_than_window": 0, "posts_dead_not_stored": 0,
           "capped_listings": 0, "listings_failed": 0, "errors": 0, "reddit_calls": 0, "stopped": None,
           "allowance_used": None, "mode": "stream" if stream else "trees"}
    if stream:
        rec.update({"stream_calls": 0, "comments_listed": 0, "stream_first_visits": 0, "stream_gaps": 0,
                    "stream_gap_subs": [], "stream_failed": 0, "threads_from_listing": 0, "threads_from_info": 0,
                    "mentions_without_thread": 0, "mentions_room": room})

    brands = d.load_brands()
    alias_re = d.build_alias_re([b for bs in brands.values() for b in bs])
    resolver = d.Resolver()
    sub_ids = {name.lower(): sid for name, sid in conn.execute("SELECT name, id FROM subreddits").fetchall()}
    run_id = run_id or d.RUN_ID

    def check(where: str) -> None:
        used = rc.stats()["calls"] - calls0
        if used >= caps["reddit_calls"]:
            raise Allowance(f"the night's {caps['reddit_calls']} Reddit calls were used {where}")
        if rec["mentions_new"] >= caps["mentions"]:
            raise Stop(f"new-mention cap ({caps['mentions']}) reached {where}")
        if room is not None and rec["mentions_new"] >= room:
            raise Allowance(f"the {room:,} new mentions this run has room for were collected {where}")
        if time.time() > deadline:
            raise Allowance(f"the time set aside for collection ended {where}")

    failed_subs: set[str] = set()   # one entry per subreddit, however many ways it failed
    log(f"  collect: {len(subs)} subreddits to visit ({quiet} quiet ones skipped today; {never['vendor']} "
        f"vendor-named and {never['second_spelling']} second spellings never visited), {len(core & set(subs))} core")
    try:
        for si, sub in enumerate(subs, 1):
            check(f"before r/{sub} ({si}/{len(subs)})")
            if si % 25 == 1:
                reason = should_stop()
                if reason:
                    raise Stop(reason)
            sid = sub_ids.get(sub.lower())
            if sid is None:
                rec["errors"] += 1
                log(f"  r/{sub}: not in the subreddits table, skipped")
                continue
            sv = None   # the visit's counts under the comment listing, added to the receipt once it is committed
            try:
                with conn.transaction():
                    cur = conn.cursor()
                    wm = d.get_watermark(cur, sub)
                    seen: dict = {}   # thread id -> comments Reddit shows now, for every post on the pages read
                    listed: dict = {}  # thread id -> the post, for the same posts (the comment listing's threads)
                    t_r = time.time()
                    posts, listing_ok, capped = d.fetch_new(sub, wm, seen=seen, listed=listed if stream else None)
                    waited[0] += time.time() - t_r
                    if not listing_ok:
                        rec["listings_failed"] += 1
                        failed_subs.add(sub)
                    now_ts = time.time()
                    cutoff = now_ts - HARVEST_DAYS * 86400
                    fresh = [p for p in posts if (p.get("created_utc") or 0) >= cutoff]
                    rec["posts_older_than_window"] += len(posts) - len(fresh)
                    t_m = time.time()
                    qual = [p for p in fresh if d.content_qualify(p, mapping.get(sub, []), alias_re)]
                    # the watermark passes every post listed, the old ones too: they are not listed again
                    newest = max([p.get("created_utc") or 0 for p in posts], default=wm or 0)
                    # the posts themselves first: a post that names a brand is kept whatever its comments
                    mrows, named = [], set()
                    for p in qual:
                        doc = post_doc(p)
                        if not doc:
                            continue
                        for h in resolver.resolve(doc["body"], sub, p.get("title") or ""):
                            named.add(p.get("id"))
                            mrows.append((doc["id"], 2, doc["id"], sid, doc["author"], doc.get("created_utc") or 0,
                                          doc.get("permalink") or "", doc.get("score") or 0, doc["body"],
                                          h["conf"], h["alias"], h["rule_fired"], run_id, h["brand_slug"]))
                    matching[0] += time.time() - t_m
                    n_comment_rows, fetched = 0, []
                    if stream:
                        # comments from the subreddit's comment listing; a thread is stored when it holds a mention
                        sv = stream_visit(cur, sub, sid, qual, named, listed, mrows, resolver, run_id, matching,
                                          waited, cutoff, first_pages, stream_pages,
                                          lambda: check(f"inside r/{sub}"))
                        n_comment_rows = sv["rows"]
                    else:
                        keep = [p for p in qual if worth_storing(p, p.get("id") in named, now_ts)]
                        rec["posts_dead_not_stored"] += len(qual) - len(keep)
                        if keep:
                            cur.executemany(THREADS_UPSERT, [
                                (f"t3_{p['id']}", sid, (p.get("title") or "")[:500],
                                 "https://www.reddit.com" + (p.get("permalink") or ""), p.get("created_utc") or 0,
                                 p.get("num_comments") or 0, bool(p.get("archived")), p.get("score") or 0)
                                for p in keep])
                        cur.execute(
                            "SELECT id, link_title, num_comments, tree_fetched_at, tree_comments FROM threads "
                            "WHERE subreddit_id=%s AND first_seen_at > now() - make_interval(hours => %s) "
                            "AND created_utc > to_timestamp(%s) "
                            "ORDER BY tree_fetched_at NULLS FIRST, num_comments DESC LIMIT %s",
                            (sid, d.REVISIT_HOURS, cutoff, CANDIDATES))
                        cands = cur.fetchall()
                        current = {c[0]: seen[c[0]] for c in cands if c[0] in seen}
                        # not on the pages just read: a thread already read (has it grown?) or one stored with no
                        # comment (has it got one?) is asked about in ONE call for up to 100 of them
                        unknown = [c[0] for c in cands if c[0] not in current and (c[3] is not None or not (c[2] or 0))]
                        if unknown:
                            check(f"inside r/{sub}")
                            t_r = time.time()
                            current.update(info_counts(unknown))
                            waited[0] += time.time() - t_r
                            rec["info_calls"] += 1
                        revisit, skipped = choose_trees(cands, current, d.TREES_PER_SUB)
                        rec["trees_skipped_no_comments"] += skipped["no_comments"]
                        rec["trees_skipped_unchanged"] += skipped["unchanged"]
                        fetched = []
                        with contextlib.closing(fetch_trees(pool, revisit, lambda: check(f"inside r/{sub}"),
                                                            waited)) as trees:
                            for tid, title, tree in trees:
                                if not isinstance(tree, list) or (isinstance(tree, dict) and "_err" in tree):
                                    rec["trees_failed"] += 1      # asked again on the next pass
                                    continue
                                t_m = time.time()
                                docs, _ = tree_docs(tree)
                                n_now = tree_count(tree)
                                fetched.append((tid, n_now if n_now is not None else int(current.get(tid) or 0)))
                                for doc in docs:
                                    body = doc.get("body") or ""
                                    for h in resolver.resolve(body, sub, title):
                                        mrows.append((doc["id"], doc.get("doc_type", 1), tid, sid, doc.get("author") or "",
                                                      doc.get("created_utc") or 0, doc.get("permalink") or "",
                                                      doc.get("score") or 0, body, h["conf"], h["alias"],
                                                      h["rule_fired"], run_id, h["brand_slug"]))
                                matching[0] += time.time() - t_m
                    ins = rej = 0
                    if mrows:
                        ins, rej = d.insert_mentions(cur, mrows)
                    if fetched:   # read now, and how many comments it had: the next visit reads it again only if more
                        cur.execute("UPDATE threads t SET tree_fetched_at = now(), tree_comments = v.n "
                                    "FROM unnest(%s::text[], %s::int[]) AS v(id, n) WHERE t.id = v.id",
                                    ([f[0] for f in fetched], [f[1] for f in fetched]))
                    # the watermark moves only after a COMPLETE listing (daily.py's rule)
                    if newest and listing_ok and not capped:
                        # quiet (plan) means nothing at all on the last visit: no qualifying post, and under the
                        # comment listing no comment mention either
                        d.set_watermark(cur, sub, dt.datetime.fromtimestamp(newest, dt.timezone.utc),
                                        len(qual) + n_comment_rows)
                    elif capped:
                        rec["capped_listings"] += 1
                rec["subs_visited"] += 1
                rec["posts_qualified"] += len(qual)
                rec["mentions_new"] += ins
                rec["mentions_rejected"] += rej
                rec["trees_fetched"] += len(fetched)
                if sv:
                    rec["stream_calls"] += sv["calls"]
                    rec["comments_listed"] += sv["comments"]
                    rec["stream_first_visits"] += sv["first"]
                    rec["stream_failed"] += sv["failed"]
                    rec["threads_from_listing"] += sv["from_listing"]
                    rec["threads_from_info"] += sv["from_info"]
                    rec["info_calls"] += sv["info_calls"]
                    rec["mentions_without_thread"] += sv["without_thread"]
                    if sv["gap"]:
                        rec["stream_gaps"] += 1
                        if len(rec["stream_gap_subs"]) < 30:
                            rec["stream_gap_subs"].append(sub)
            except Stop:
                raise
            except Exception as e:  # noqa: BLE001 - one subreddit's failure must not end the run
                rec["errors"] += 1
                failed_subs.add(sub)
                log(f"  !! r/{sub}: {type(e).__name__}: {str(e)[:160]}")
                if db.is_transient(e):
                    raise
            if si % 100 == 0:
                log(f"    {si}/{len(subs)} subreddits, {rec['mentions_new']} new mentions, "
                    f"{rc.stats()['calls'] - calls0} calls, {(time.time() - t0) / 60:.0f} min", flush=True)
    except Allowance as s:
        rec["allowance_used"] = str(s)
        log(f"  collect ended for tonight: {s}")
    except Stop as s:
        rec["stopped"] = str(s)
        log(f"  collect stopped: {s}")
    finally:
        if pool is not None:   # requests still in flight finish (a few seconds); none is started after this
            pool.shutdown(wait=True, cancel_futures=True)
    rec["reddit_calls"] = rc.stats()["calls"] - calls0
    # Reddit failing most requests is not a quiet night: it is a failure the owner must hear of (review 4 Oct)
    tried = rec["subs_visited"] + rec["errors"]
    if tried >= 20 and len(failed_subs) * 2 > tried:
        rec["error"] = (f"{rec['listings_failed']} subreddit listings failed and {rec['errors']} subreddits raised, "
                        f"of {tried} tried")
    elif rec["trees_fetched"] + rec["trees_failed"] >= 50 and rec["trees_failed"] * 2 > rec["trees_fetched"] + rec["trees_failed"]:
        rec["error"] = f"{rec['trees_failed']} of {rec['trees_fetched'] + rec['trees_failed']} comment trees failed"
    elif stream and rec["subs_visited"] >= 20 and rec["stream_failed"] * 2 > rec["subs_visited"]:
        rec["error"] = f"the comment listing failed for {rec['stream_failed']} of {rec['subs_visited']} subreddits"
    # threads stored for the first time by this stage, read back (the receipt used to count every qualifying post
    # in the listings, including threads already stored: 13,586 against 11,476 new on 2026-10-04)
    rec["threads_new"] = conn.execute("select count(*) from public.threads where first_seen_at >= to_timestamp(%s)",
                                      (t0,)).fetchone()[0]
    rec["minutes"] = round((time.time() - t0) / 60, 1)
    # Where the stage's time went, in seconds (10 Oct: 27 calls a minute by day against a declared 45, and nothing
    # on the receipt said why). The first three add up to the stage: waiting_for_reddit (the stage stood waiting for
    # a listing or a comment tree), matching (finding brand names in the text), database_and_rest. `of_reddit` says
    # what the requests themselves spent, summed over every request (so with trees in flight side by side it can
    # exceed the waiting): network, pacing_sleep (held back to the declared pace), rate_limit_waits (the app's
    # window was used up).
    net1 = rc.stats()
    rec["tree_workers"] = workers
    rec["seconds"] = {
        "waiting_for_reddit": round(waited[0]), "matching": round(matching[0]),
        "database_and_rest": round(max(0.0, time.time() - t0 - waited[0] - matching[0])),
        "of_reddit": {"network": round(net1["net_s"] - net0["net_s"]),
                      "pacing_sleep": round(net1["paced_s"] - net0["paced_s"]),
                      "rate_limit_waits": round(net1["limit_wait_s"] - net0["limit_wait_s"])}}
    return rec
