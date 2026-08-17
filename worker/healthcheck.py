#!/usr/bin/env python3
"""Is the index still collecting? One command, one exit code.

WHY THIS EXISTS
    On 2026-08-16 the daily fetch stopped writing a single row. Every signal a
    human would have looked at stayed green: the Railway cron ran on schedule,
    the container exited 0, `ingest_state` gained a fresh `_run` row with
    status='ok', and the site kept serving. The only trace was `rows=0` on that
    row, and nobody reads a row for a zero.

    So the check is not "did it run". It is "did it MOVE" — every assertion
    below compares a clock or a count against what a healthy pass produces, and
    every one of them would have failed on 2026-08-17 04:13.

    python3 worker/healthcheck.py            # human output, exit 1 on failure
    python3 worker/healthcheck.py --json     # machine output
    python3 worker/healthcheck.py --slack    # post to Slack on state CHANGE

SLACK
    Off unless `slack_channel` is set in ~/.claude/.reddit-index.json (the bot
    token is read from ~/.claude.json). It posts when the state CHANGES —
    on the transition into failure and on recovery — never the same alarm every
    hour. State lives in worker/.cache/health.json.
"""
import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import db  # noqa: E402

STATE_FP = os.path.join(HERE, ".cache", "health.json")
CRED_FP = os.path.expanduser("~/.claude/.reddit-index.json")

# The fetch runs ONCE a day (railway.json: 0 2 * * *) with up to a 10-hour
# budget. Everything below is sized so a single late or slow pass is not an
# alarm and a missed day is: 36 hours is a full cycle plus the budget plus
# room, and nothing healthy ever reaches it.
MAX_RUN_AGE_H = 36            # hours since the last completed pass
MIN_RUN_MENTIONS = 200        # NEW mentions a healthy pass writes
MIN_SUB_COVERAGE = 0.80       # share of scoring subs touched in the window
MAX_SUB_ERRORS = 100
MIN_MENTIONS_WRITTEN = 1000   # rows landed in the window, by OUR clock
MAX_LABEL_AGE_H = 36          # hours since the classifier last committed
BACKLOG_WARN = 60_000
BACKLOG_FAIL = 250_000
WINDOW_H = 36


SITE = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://redditindex.com") + "/"


def site_check():
    """What a VISITOR gets. Every other assertion here reads Postgres, and the
    database was perfectly healthy on 2026-08-17 while the site answered every
    request with a 403 challenge page: Vercel's automatic mitigation
    (`x-vercel-mitigated: challenge`, logged as `system-action`) had switched
    itself on, and nothing in this project could see it. Clear it with
    `python3 scripts/attack-mode.py --off`.

    Returns (name, ok, detail) tuples — reachability and speed, measured from
    outside, because the honest question is not "is the data good" but "does
    the page load".
    """
    req = urllib.request.Request(SITE, headers={
        "User-Agent": "reddit-index-healthcheck/1 (+https://redditindex.com)"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            hdrs = {k.lower(): v for k, v in r.headers.items()}
            code = r.status
    except urllib.error.HTTPError as e:
        hdrs = {k.lower(): v for k, v in (e.headers or {}).items()}
        body, code = b"", e.code
    except Exception as e:
        return [("site_reachable", False, f"{SITE} did not answer: {e}"),
                ("site_unchallenged", False, "not reachable, so not measurable")]
    ms = (time.time() - t0) * 1000
    mitigated = hdrs.get("x-vercel-mitigated")
    return [
        ("site_reachable", code == 200 and len(body) > 5000,
         f"HTTP {code}, {len(body):,} bytes, {ms:.0f} ms"),
        ("site_unchallenged", not mitigated,
         f"x-vercel-mitigated: {mitigated} — visitors are getting Vercel's "
         f"interstitial; run scripts/attack-mode.py --off"
         if mitigated else "no Vercel interstitial in front of the site"),
    ]


def q1(cur, sql, params=None):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None


def checks(conn):
    """Every check as (name, ok, detail). ok=None means 'warn, not fail'."""
    out = []
    with conn.cursor() as cur:
        # ---- the fetch lane -------------------------------------------------
        age = q1(cur, "SELECT extract(epoch from now() - max(finished_at))/3600 "
                      "FROM ingest_state WHERE scope='_run'")
        out.append(("fetch_ran", age is not None and age < MAX_RUN_AGE_H,
                    f"last pass {age:.1f}h ago (limit {MAX_RUN_AGE_H}h)"
                    if age is not None else "no _run row has ever been written"))

        row = q1(cur, "SELECT rows FROM ingest_state WHERE scope='_run' "
                      "ORDER BY finished_at DESC LIMIT 1")
        out.append(("fetch_collected", (row or 0) >= MIN_RUN_MENTIONS,
                    f"{row or 0} new mentions on the last pass "
                    f"(floor {MIN_RUN_MENTIONS}) — THE 2026-08-16 SIGNAL"))

        status = q1(cur, "SELECT status FROM ingest_state WHERE scope='_run' "
                         "ORDER BY finished_at DESC LIMIT 1")
        out.append(("fetch_status", status == "ok", f"last pass status={status!r}"))

        touched = q1(cur, "SELECT count(*) FROM ingest_state WHERE ym='daily' "
                          "AND scope NOT LIKE '\\_%%' "
                          "AND finished_at > now() - make_interval(hours => %s)",
                     (WINDOW_H,))
        total = q1(cur, "SELECT count(*) FROM ingest_state WHERE ym='daily' "
                        "AND scope NOT LIKE '\\_%%'")
        share = (touched or 0) / max(total or 1, 1)
        out.append(("sub_coverage", share >= MIN_SUB_COVERAGE,
                    f"{touched}/{total} subreddits advanced in {WINDOW_H}h "
                    f"({share:.0%}, floor {MIN_SUB_COVERAGE:.0%})"))

        errs = q1(cur, "SELECT count(*) FROM ingest_state WHERE ym='daily' "
                       "AND status='error' AND finished_at > now() - "
                       "make_interval(hours => %s)", (WINDOW_H,))
        out.append(("sub_errors", (errs or 0) <= MAX_SUB_ERRORS,
                    f"{errs} subreddits errored in {WINDOW_H}h (limit {MAX_SUB_ERRORS})"))

        # loaded_at is OUR clock. created_utc is Reddit's, and a backfill of old
        # content would make a dead lane look busy.
        written = q1(cur, "SELECT count(*) FROM mentions WHERE loaded_at > now() - "
                          "make_interval(hours => %s)", (WINDOW_H,))
        out.append(("mentions_written", (written or 0) >= MIN_MENTIONS_WRITTEN,
                    f"{written:,} mentions written in {WINDOW_H}h "
                    f"(floor {MIN_MENTIONS_WRITTEN:,})"))

        # ---- posts are still being read as posts ----------------------------
        posts = q1(cur, "SELECT count(*) FROM mentions WHERE doc_type=2 AND "
                        "loaded_at > now() - make_interval(hours => %s)", (WINDOW_H,))
        out.append(("posts_collected", (posts or 0) > 0,
                    f"{posts:,} POST mentions in {WINDOW_H}h — zero means the "
                    "post document regressed to selftext-only again"))

        # ---- the revisit queue is fair --------------------------------------
        unread = q1(cur, "SELECT count(*) FROM threads WHERE first_seen_at > "
                         "now() - interval '72 hours' AND tree_fetched_at IS NULL")
        window = q1(cur, "SELECT count(*) FROM threads WHERE first_seen_at > "
                         "now() - interval '72 hours'")
        out.append(("revisit_backlog", (unread or 0) <= max(2000, (window or 0) * 0.6),
                    f"{unread:,} of {window:,} threads in the 72h window still "
                    "have no comment tree"))

        # ---- classification -------------------------------------------------
        lag = q1(cur, "SELECT extract(epoch from now() - max(scored_at))/3600 "
                      "FROM mention_sentiment")
        out.append(("labels_fresh", lag is not None and lag < MAX_LABEL_AGE_H,
                    f"last label {lag:.1f}h ago (limit {MAX_LABEL_AGE_H}h)"
                    if lag is not None else "no labels at all"))

        backlog = q1(cur, "SELECT count(*) FROM mentions m LEFT JOIN "
                          "mention_sentiment ms ON ms.doc_id=m.doc_id AND "
                          "ms.brand_id=m.brand_id WHERE ms.doc_id IS NULL")
        out.append(("backlog", True if (backlog or 0) < BACKLOG_WARN
                    else (None if backlog < BACKLOG_FAIL else False),
                    f"{backlog:,} unlabelled (warn {BACKLOG_WARN:,}, "
                    f"fail {BACKLOG_FAIL:,})"))

        # ---- scoring + publish ----------------------------------------------
        wk = q1(cur, "SELECT max(week_start) FROM brand_category_scores")
        fresh = wk is not None and (datetime.date.today() - wk).days <= 7
        out.append(("scores_fresh", fresh, f"scores keyed {wk}"))

        n_scores = q1(cur, "SELECT count(*) FROM brand_category_scores")
        out.append(("scores_present", (n_scores or 0) > 1000, f"{n_scores:,} score rows"))

        # A PARTIAL load is the dangerous shape, not an empty one. The site
        # reads `week_start = max(week_start)`, so a scoring run killed halfway
        # through its load leaves a newer key holding a fraction of the rows and
        # the boards silently lose everything missing. Happened on 2026-08-17:
        # 2,973 of 4,034 rows landed and the prune never ran, so the previous
        # complete key was still there — invisible, and unused.
        pair = q1(cur, """
            SELECT string_agg(n::text, '/' ORDER BY week_start DESC)
            FROM (SELECT week_start, count(*) n FROM brand_category_scores
                  GROUP BY 1 ORDER BY 1 DESC LIMIT 2) x""")
        counts = [int(x) for x in (pair or "0").split("/") if x]
        ok_load = len(counts) < 2 or counts[0] >= counts[1] * 0.9
        out.append(("scores_complete", ok_load,
                    f"newest/previous week_start row counts {pair} "
                    "(a short newest key means a load died mid-write)"))

        # ---- the view that has silently blanked the site once ---------------
        pinned = q1(cur, "SELECT pg_get_viewdef('published.mentions'::regclass, true) "
                         "LIKE '%%sentiment_model_version%%'")
        out.append(("view_unpinned", not pinned,
                    "published.mentions is pinned to one model_version"
                    if pinned else "published.mentions reads every engine"))

        visible = q1(cur, "SELECT count(*) FROM published.mentions WHERE label IS NOT NULL")
        out.append(("labels_visible", (visible or 0) > 0,
                    f"{visible:,} labelled mentions reach the site"))

    # Last, and from outside: the database can be perfect while the site is not.
    out.extend(site_check())
    return out


def load_state():
    try:
        return json.load(open(STATE_FP))
    except Exception:
        return {"failing": False, "since": None}


def save_state(st):
    os.makedirs(os.path.dirname(STATE_FP), exist_ok=True)
    with open(STATE_FP + ".tmp", "w") as f:
        json.dump(st, f, indent=1)
    os.replace(STATE_FP + ".tmp", STATE_FP)


def slack(text):
    """Post only if a channel is configured. No channel, no post — a health
    check must never be the thing that surprises a shared workspace."""
    try:
        chan = json.load(open(CRED_FP)).get("slack_channel")
    except Exception:
        chan = None
    if not chan:
        print("  (slack: no `slack_channel` in ~/.claude/.reddit-index.json — skipped)")
        return
    try:
        env = json.load(open(os.path.expanduser("~/.claude.json")))
        token = (env["projects"]["/Users/vladshvets/.claude"]["mcpServers"]
                 ["slack-empact"]["env"]["SLACK_BOT_TOKEN"])
    except Exception as e:
        print(f"  (slack: no bot token — {e})")
        return
    body = json.dumps({"channel": chan, "text": text}).encode()
    req = urllib.request.Request("https://slack.com/api/chat.postMessage", data=body,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=20).read())
        print(f"  (slack: {'posted' if r.get('ok') else r.get('error')})")
    except Exception as e:
        print(f"  (slack: {e})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--slack", action="store_true", help="post on state change")
    args = ap.parse_args()

    conn = db.connect()
    try:
        results = checks(conn)
        failed = [c for c in results if c[1] is False]
        warned = [c for c in results if c[1] is None]

        # Record the verdict where the pipeline already looks.
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ingest_state (scope, ym, stage, code_version, watermark, "
                "rows, status, finished_at) VALUES ('_health','daily','healthcheck',"
                "'health-v1',%s,%s,%s,now()) ON CONFLICT (scope, ym, stage, code_version) "
                "DO UPDATE SET watermark=EXCLUDED.watermark, rows=EXCLUDED.rows, "
                "status=EXCLUDED.status, finished_at=now()",
                (", ".join(c[0] for c in failed) or "all checks pass",
                 len(failed), "error" if failed else "ok"))
        conn.commit()
    finally:
        conn.close()

    if args.json:
        print(json.dumps({"ok": not failed,
                          "checks": [{"name": n, "ok": o, "detail": d}
                                     for n, o, d in results]}, indent=1))
    else:
        for name, ok, detail in results:
            mark = "PASS" if ok else ("WARN" if ok is None else "FAIL")
            print(f"  [{mark}] {name:18} {detail}")
        print(f"\n{len(failed)} failed, {len(warned)} warned, "
              f"{len(results) - len(failed) - len(warned)} passed")

    if args.slack:
        st = load_state()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        if failed and not st["failing"]:
            slack("*Reddit Index — collection is not healthy*\n"
                  + "\n".join(f"• `{n}` — {d}" for n, _, d in failed))
            save_state({"failing": True, "since": now})
        elif not failed and st["failing"]:
            slack(f"*Reddit Index — recovered.* All checks pass "
                  f"(was failing since {st.get('since')}).")
            save_state({"failing": False, "since": None})

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
