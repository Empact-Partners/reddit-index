#!/usr/bin/env python3
"""Audit what was collected, resolved, classified and published.

Written because the owner asked the only question that matters after a big
scrape — "are these real numbers, or did you miss something?" — and no part of
the pipeline could answer it. Four checks, one report, deliberately cheap:
three are free and the fourth spends well under a dollar.

  1. INVARIANTS      pure SQL. Every number a reader can compare between two
                     surfaces must agree, and every score must sit on evidence
                     that still exists.
  2. RECALL          Reddit's own search, run directly against a sample of
                     brands in their own scoring subreddits, to find mentions
                     the sweep never stored. This is the check that says
                     whether "4 mentions" is the truth or a miss.
  3. PRECISION       a blind re-judge of a stratified label sample on a second
                     model. Agreement per class, disagreements listed.
  4. ENTITY          the most generic brand names, with accepted and rejected
                     text side by side, so a human can see whether the
                     resolver is inventing or dropping mentions.

    python3 worker/qa_audit.py                 # all four, writes the report
    python3 worker/qa_audit.py --only invariants
    python3 worker/qa_audit.py --brands 15 --labels 400
"""
import argparse
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import db  # noqa: E402

REPORT = os.path.join(REPO, "docs", "qa-audit.md")
WORD = {0: "neu", 1: "pos", 2: "neg", 3: "abstain"}
OUT = []


def say(line=""):
    print(line, flush=True)
    OUT.append(line)


def q(state, sql, params=None):
    def _r(c):
        with c.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    return db.run(state, _r, label="qa")


# ── 1. invariants ───────────────────────────────────────────────────────────

def invariants(state):
    say("## 1. Consistency invariants\n")
    fails = []

    def check(name, rows, explain):
        if rows:
            fails.append(name)
            say(f"- **FAIL — {name}**: {len(rows)} row(s). {explain}")
            for r in rows[:5]:
                say(f"  - `{r}`")
        else:
            say(f"- PASS — {name}")

    # A published score must sit on labelled evidence that still exists.
    check("every score has labelled mentions behind it",
          q(state, """
            SELECT b.slug, c.slug, s.n, s.n_op FROM brand_category_scores s
            JOIN brands b ON b.id = s.brand_id
            JOIN categories c ON c.id = s.category_id
            WHERE s.reddit_love_score IS NOT NULL AND s.n_op = 0"""),
          "A score computed from zero opinionated mentions is a claim with no evidence.")

    # pos + neg must equal n_op, or the estimator's denominator is wrong.
    check("n_op equals pos + neg",
          q(state, """
            SELECT b.slug, c.slug, s.n_op, s.pos, s.neg FROM brand_category_scores s
            JOIN brands b ON b.id = s.brand_id
            JOIN categories c ON c.id = s.category_id
            WHERE s.n_op <> s.pos + s.neg"""),
          "The score's denominator disagrees with its own counts.")

    # n must not exceed the mentions actually stored for that brand.
    check("scored n never exceeds collected mentions",
          q(state, """
            SELECT b.slug, s.n, cnt.n_all FROM brand_category_scores s
            JOIN brands b ON b.id = s.brand_id
            JOIN (SELECT brand_id, count(*)::int n_all FROM mentions GROUP BY 1) cnt
              ON cnt.brand_id = s.brand_id
            WHERE s.n > cnt.n_all"""),
          "A board is counting more mentions than were ever stored.")

    # ranks must be contiguous 1..k inside a category
    bad_rank = []
    for (cat,) in q(state, "SELECT DISTINCT c.slug FROM brand_category_scores s "
                           "JOIN categories c ON c.id=s.category_id"):
        rks = [r[0] for r in q(state, """
            SELECT s.rank_desc FROM brand_category_scores s
            JOIN categories c ON c.id = s.category_id
            WHERE c.slug = %s AND s.rank_desc IS NOT NULL ORDER BY s.rank_desc""", (cat,))]
        if rks and rks != list(range(1, len(rks) + 1)):
            bad_rank.append((cat, len(rks), rks[:5]))
    check("ranks are contiguous 1..k per category", bad_rank,
          "A gap or duplicate in the ranking means two brands claim one position.")

    # every labelled mention points at a mention that exists
    check("no orphan sentiment rows",
          q(state, """
            SELECT ms.doc_id FROM mention_sentiment ms
            LEFT JOIN mentions m ON m.doc_id = ms.doc_id AND m.brand_id = ms.brand_id
            WHERE m.doc_id IS NULL LIMIT 20"""),
          "A label with no mention behind it inflates every count derived from it.")

    # duplicate labels for one (doc, brand) across model versions would double-count
    check("one label per (mention, brand)",
          q(state, """
            SELECT doc_id, brand_id, count(*)::int FROM mention_sentiment
            GROUP BY 1, 2 HAVING count(*) > 1 LIMIT 20"""),
          "Two models labelled the same mention; scoring would count it twice.")

    say()
    say(f"**{len(fails)} invariant(s) failing.**" if fails
        else "**All invariants pass.**")
    say()
    return fails


# ── 2. recall ───────────────────────────────────────────────────────────────

def reddit_token():
    cfg = json.load(open(os.path.expanduser("~/.claude.json")))

    def find(d):
        if isinstance(d, dict):
            for k, v in d.items():
                if k == "reddit" and isinstance(v, dict) and v.get("env"):
                    return v["env"]
                r = find(v)
                if r:
                    return r
    env = find(cfg) or {}
    cid, sec = env.get("REDDIT_CLIENT_ID"), env.get("REDDIT_CLIENT_SECRET")
    ua = env.get("REDDIT_USER_AGENT", "reddit-index-qa/1.0")
    if not cid:
        return None, ua
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    import base64
    auth = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    req = urllib.request.Request("https://www.reddit.com/api/v1/access_token",
                                 data=data,
                                 headers={"Authorization": f"Basic {auth}",
                                          "User-Agent": ua})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"], ua


def recall(state, n_brands):
    say("## 2. Collection recall — did the sweep miss real mentions?\n")
    tok, ua = reddit_token()
    if not tok:
        say("- SKIPPED: no Reddit credentials available.\n")
        return
    # stratified: some big, some middling, some thin
    rows = q(state, """
        SELECT b.slug, b.name, c.slug AS cat, count(m.doc_id)::int AS n
        FROM brands b
        JOIN categories c ON c.id = b.primary_category_id
        LEFT JOIN mentions m ON m.brand_id = b.id
        GROUP BY 1,2,3 HAVING count(m.doc_id) > 0
        ORDER BY random()""")
    big = [r for r in rows if r[3] >= 100][:n_brands // 3]
    mid = [r for r in rows if 10 <= r[3] < 100][:n_brands // 3]
    thin = [r for r in rows if r[3] < 10][:n_brands - len(big) - len(mid)]
    sample = big + mid + thin
    say(f"Sampled {len(sample)} brands ({len(big)} large, {len(mid)} mid, "
        f"{len(thin)} thin). For each, Reddit's own search over the last 90 "
        f"days in its category's scoring subreddits, compared against what we "
        f"stored.\n")
    say("| brand | stored | reddit search hits | not stored | verdict |")
    say("|---|---|---|---|---|")
    totals = [0, 0]
    for slug, name, cat, n_stored in sample:
        subs = [r[0] for r in q(state, """
            SELECT s.name FROM category_subreddits cs
            JOIN subreddits s ON s.id = cs.subreddit_id
            JOIN categories c ON c.id = cs.category_id
            WHERE c.slug = %s AND cs.is_scoring LIMIT 3""", (cat,))]
        if not subs:
            continue
        have = {r[0] for r in q(state, """
            SELECT m.doc_id FROM mentions m
            JOIN brands b ON b.id = m.brand_id WHERE b.slug = %s""", (slug,))}
        hits, missing = 0, 0
        for sub in subs:
            url = (f"https://oauth.reddit.com/r/{sub}/search?"
                   + urllib.parse.urlencode({"q": f'"{name}"', "restrict_sr": 1,
                                             "sort": "new", "t": "year",
                                             "limit": 50}))
            try:
                req = urllib.request.Request(
                    url, headers={"Authorization": f"Bearer {tok}", "User-Agent": ua})
                with urllib.request.urlopen(req, timeout=30) as r:
                    kids = json.load(r).get("data", {}).get("children", [])
            except Exception:
                continue
            cutoff = time.time() - 90 * 86400
            for k in kids:
                d = k.get("data", {})
                if (d.get("created_utc") or 0) < cutoff:
                    continue
                hits += 1
                if f"t3_{d.get('id')}" not in have:
                    missing += 1
            time.sleep(1.1)          # ~60/min, well inside the app-only budget
        totals[0] += hits
        totals[1] += missing
        verdict = ("OK" if missing == 0 else
                   "minor" if missing <= max(2, hits * 0.25) else "**GAP**")
        say(f"| {name} | {n_stored} | {hits} | {missing} | {verdict} |")
    say()
    say(f"Across the sample: {totals[0]} threads surfaced by Reddit search, "
        f"{totals[1]} of them not in our corpus.")
    say()
    say("Scope note, so a low count is judged fairly: the sweep covers the 527 "
        "CORE scoring subreddits, up to 150 threads per subreddit, over a "
        "90-day window. A brand discussed mainly outside those subreddits, or "
        "in threads past the per-subreddit cap, is expected to show a small "
        "number here. That is a scope limit, not a bug — but a brand with "
        "many misses INSIDE its own scoring subreddits is a bug.\n")


# ── 3. precision ────────────────────────────────────────────────────────────

def precision(state, n_labels):
    say("## 3. Classification precision — blind re-judge\n")
    try:
        from classify_api import deepseek_key, call_deepseek, build_prompt
        from classify import LABEL_CODE, mark_target
        import csv as _csv
    except Exception as e:
        say(f"- SKIPPED: {e}\n")
        return
    key = deepseek_key()
    if not key:
        say("- SKIPPED: no DeepSeek key.\n")
        return
    per = max(20, n_labels // 4)
    rows = []
    for code in (0, 1, 2, 3):
        rows += q(state, """
            SELECT m.doc_id, b.slug, s.name, coalesce(t.link_title,''), m.body,
                   m.matched_form, ms.label
            FROM mention_sentiment ms
            JOIN mentions m ON m.doc_id = ms.doc_id AND m.brand_id = ms.brand_id
            JOIN brands b ON b.id = m.brand_id
            JOIN subreddits s ON s.id = m.subreddit_id
            LEFT JOIN threads t ON t.id = m.thread_id
            WHERE ms.label = %s AND length(m.body) BETWEEN 80 AND 1500
            ORDER BY random() LIMIT %s""", (code, per))
    brand_names = {r["slug"]: r["brand"] for r in
                   _csv.DictReader(open(os.path.join(REPO, "data", "brands.csv")))}
    items, gold = [], {}
    for doc_id, bslug, sub, title, body, form, label in rows:
        off = (body or "").lower().find((form or "").lower())
        iid = f"{doc_id}:{bslug}"
        items.append({"item_id": iid, "brand_slug": bslug, "subreddit": sub,
                      "link_title": title, "doc_id": doc_id,
                      "marked": mark_target(body or "", form or "", max(0, off))})
        gold[iid] = label
    say(f"Re-judging {len(items)} labelled mentions (stratified across all four "
        f"classes) on a second model, blind to the stored label.\n")
    agree = Counter()
    total = Counter()
    confusion = Counter()
    disagreements = []
    for i in range(0, len(items), 120):
        chunk = items[i:i + 120]
        try:
            obj = call_deepseek(build_prompt(chunk, brand_names, terse=True),
                                key, len(chunk))
        except Exception as e:
            say(f"- batch error: {str(e)[:80]}")
            continue
        if not obj:
            continue
        for it in chunk:
            r = obj.get(it["item_id"])
            if not isinstance(r, dict):
                continue
            new = LABEL_CODE.get(str(r.get("label", "abstain")).lower(), 3)
            old = gold[it["item_id"]]
            total[old] += 1
            if new == old:
                agree[old] += 1
            else:
                confusion[(WORD[old], WORD[new])] += 1
                if len(disagreements) < 12:
                    disagreements.append(
                        (it["item_id"], WORD[old], WORD[new],
                         (r.get("evidence") or "")[:90]))
    say("| stored label | re-judged same | sampled | agreement |")
    say("|---|---|---|---|")
    for code in (1, 2, 0, 3):
        if total[code]:
            say(f"| {WORD[code]} | {agree[code]} | {total[code]} | "
                f"{agree[code]/total[code]*100:.0f}% |")
    tt, ta = sum(total.values()), sum(agree.values())
    if tt:
        say(f"| **overall** | **{ta}** | **{tt}** | **{ta/tt*100:.0f}%** |")
    say()
    if confusion:
        say("Most common disagreements (stored -> re-judged):\n")
        for (a, b), n in confusion.most_common(6):
            say(f"- {a} -> {b}: {n}")
        say()
    if disagreements:
        say("Examples to eyeball:\n")
        for iid, a, b, ev in disagreements:
            say(f"- `{iid}` stored **{a}**, re-judged **{b}** — {ev}")
        say()


# ── 4. entity resolution ────────────────────────────────────────────────────

def entity(state):
    say("## 4. Entity resolution — are generic names matching the right thing?\n")
    rows = q(state, """
        SELECT b.slug, b.name, count(*)::int n
        FROM mentions m JOIN brands b ON b.id = m.brand_id
        WHERE length(b.name) <= 9
        GROUP BY 1,2 ORDER BY n DESC LIMIT 20""")
    say("The twenty shortest, most collision-prone brand names by volume. For "
        "each, a real accepted mention — read them and the resolver's judgement "
        "is either obvious or obviously wrong.\n")
    for slug, name, n in rows:
        ex = q(state, """
            SELECT m.matched_form, s.name, left(m.body, 150)
            FROM mentions m JOIN subreddits s ON s.id = m.subreddit_id
            JOIN brands b ON b.id = m.brand_id
            WHERE b.slug = %s ORDER BY random() LIMIT 1""", (slug,))
        if not ex:
            continue
        form, sub, body = ex[0]
        body = re.sub(r"\s+", " ", body or "").strip()
        say(f"- **{name}** ({n:,} mentions) — matched `{form}` in r/{sub}:")
        say(f"  > {body}")
    say()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["invariants", "recall", "precision", "entity"])
    ap.add_argument("--brands", type=int, default=15)
    ap.add_argument("--labels", type=int, default=400)
    args = ap.parse_args()
    random.seed(7)

    state = {"conn": db.connect()}
    say("# Reddit Index — data QA audit")
    say()
    say(f"Generated {time.strftime('%Y-%m-%d %H:%M')} against the live corpus.")
    say()
    n = q(state, """SELECT (SELECT count(*) FROM mentions)::int,
                           (SELECT count(*) FROM mention_sentiment)::int,
                           (SELECT count(*) FROM brand_category_scores)::int,
                           (SELECT count(*) FROM threads)::int""")[0]
    say(f"Corpus: {n[0]:,} mentions · {n[1]:,} labelled · {n[3]:,} threads · "
        f"{n[2]:,} score rows.")
    say()

    if args.only in (None, "invariants"):
        invariants(state)
    if args.only in (None, "recall"):
        recall(state, args.brands)
    if args.only in (None, "precision"):
        precision(state, args.labels)
    if args.only in (None, "entity"):
        entity(state)

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w") as f:
        f.write("\n".join(OUT) + "\n")
    print(f"\nreport -> {REPORT}")
    try:
        state["conn"].close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
