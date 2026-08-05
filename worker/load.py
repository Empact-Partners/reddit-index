#!/usr/bin/env python3
"""Seed reference data + load scored mentions into Supabase.

Usage:
    python3 worker/load.py --seed       # categories, subreddits, brands, aliases
    python3 worker/load.py --mentions   # scored mentions from worker/.cache/corpus/
    python3 worker/load.py --scores     # brand_category_scores from _all_scores.json
"""
import argparse, csv, json, os, sys, time, urllib.error, urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

REF = json.load(open(os.path.expanduser("~/.claude/.reddit-index.json")))["project_ref"]
TOKEN = open(os.path.expanduser("~/.claude/.supabase-empact.token")).read().strip()


def sql(query, label=""):
    """Execute raw SQL via the Supabase Management API."""
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as f:
            result = json.loads(f.read())
        if isinstance(result, dict) and "message" in result:
            print(f"  SQL ERROR ({label}): {result['message'][:200]}")
            return None
        return result
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} ({label}): {e.read().decode()[:200]}")
        return None


def esc(s):
    return str(s).replace("'", "''")

def lit(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (list, tuple)):
        return "ARRAY[" + ",".join(f"'{esc(s)}'" for s in v) + "]::text[]"
    return "'" + esc(v) + "'"


def seed_categories():
    print("seeding categories…")
    rows = list(csv.DictReader(open(os.path.join(REPO, "data", "categories.csv"))))
    values = []
    for r in rows:
        values.append(f"({lit(r['slug'])}, {lit(r['category'])}, {lit(r['icon'])}, "
                      f"{lit(r['hex'])}, {lit(r['threshold_tier'])}, "
                      f"{int(r['precision_target_pp'])}, {int(r['n_min'])}, 'published')")
    q = ("INSERT INTO categories (slug, name, icon, hex, threshold_tier, precision_target_pp, n_min, status) VALUES\n"
         + ",\n".join(values) + "\nON CONFLICT (slug) DO UPDATE SET name=EXCLUDED.name, hex=EXCLUDED.hex, "
         "threshold_tier=EXCLUDED.threshold_tier, n_min=EXCLUDED.n_min, status='published';")
    sql(q, "categories")
    print(f"  {len(rows)} categories")


def seed_subreddits():
    print("seeding subreddits…")
    rows = list(csv.DictReader(open(os.path.join(REPO, "data", "category-subreddits.csv"))))
    subs = {}
    for r in rows:
        name = r["subreddit"]
        if name.lower() not in subs:
            subs[name.lower()] = r

    values = []
    for name, r in subs.items():
        values.append(f"({lit(r['subreddit'])}, {lit(r['rule_posture'])}, "
                      f"{r['is_vendor_sub'] == 'True'}, "
                      f"{int(r.get('subscribers') or 0)}, "
                      f"{float(r.get('comments_per_hour') or 0)})")
    for batch in [values[i:i + 50] for i in range(0, len(values), 50)]:
        q = ("INSERT INTO subreddits (name, rule_posture, is_vendor_sub, subscribers, comments_per_hour) VALUES\n"
             + ",\n".join(batch) + "\nON CONFLICT (name) DO UPDATE SET "
             "rule_posture=EXCLUDED.rule_posture, is_vendor_sub=EXCLUDED.is_vendor_sub;")
        sql(q, "subreddits")
    print(f"  {len(subs)} subreddits")


def seed_category_subreddits():
    print("seeding category_subreddits…")
    raw = list(csv.DictReader(open(os.path.join(REPO, "data", "category-subreddits.csv"))))
    # A subreddit can appear twice in one category under different casing, and
    # Postgres refuses an ON CONFLICT that touches the same row twice in one
    # statement. Keep the scoring row where there is one.
    dedup = {}
    for r in raw:
        k = (r["category_slug"], r["subreddit"].lower())
        if k not in dedup or r["is_scoring"] == "True":
            dedup[k] = r
    rows = list(dedup.values())
    q = ("INSERT INTO category_subreddits (category_id, subreddit_id, is_scoring, bb_per_hour) "
         "SELECT c.id, s.id, v.is_scoring, v.bb_per_hour FROM (VALUES\n")
    values = []
    for r in rows:
        values.append(f"  ({lit(r['category_slug'])}, {lit(r['subreddit'])}, "
                      f"{r['is_scoring'] == 'True'}, {float(r.get('bb_per_hour') or 0)})")
    q += ",\n".join(values)
    q += ("\n) AS v(cat_slug, sub_name, is_scoring, bb_per_hour)\n"
          "JOIN categories c ON c.slug = v.cat_slug\n"
          "JOIN subreddits s ON s.name = v.sub_name\n"
          "ON CONFLICT (category_id, subreddit_id) DO UPDATE SET "
          "is_scoring=EXCLUDED.is_scoring, bb_per_hour=EXCLUDED.bb_per_hour;")
    sql(q, "category_subreddits")
    print(f"  {len(rows)} rows")


def seed_brands():
    print("seeding brands…")
    rows = list(csv.DictReader(open(os.path.join(REPO, "data", "brands.csv"))))
    for batch in [rows[i:i + 20] for i in range(0, len(rows), 20)]:
        values = []
        for r in batch:
            domains = [d.strip() for d in (r.get("domains") or "").split(";") if d.strip()]
            stops = [s.strip() for s in (r.get("stop_contexts") or "").split(";") if s.strip()]
            values.append(
                f"({lit(r['slug'])}, {lit(r['brand'])}, {lit(r['primary_category_slug'])}, "
                f"{lit(r['ambiguity_class'])}, {lit(r['surface_class'])}, "
                f"{r['require_context'] == 'True'}, {int(r['min_corroborating'])}, "
                f"{lit(domains)}, {lit(stops)}, {lit(r.get('ambiguity_note') or '')}, 'published')")
        q = ("INSERT INTO brands (slug, name, primary_category_id, ambiguity_class, surface_class, "
             "require_context, min_corroborating, domains, stop_contexts, ambiguity_note, status) "
             "SELECT v.slug, v.name, c.id, v.amb, v.cls, v.req_ctx, v.min_c, v.doms, v.stops, v.note, v.status FROM (VALUES\n"
             + ",\n".join(values)
             + "\n) AS v(slug, name, cat_slug, amb, cls, req_ctx, min_c, doms, stops, note, status)\n"
             "JOIN categories c ON c.slug = v.cat_slug\n"
             "ON CONFLICT (slug) DO UPDATE SET name=EXCLUDED.name, primary_category_id=EXCLUDED.primary_category_id, "
             "ambiguity_class=EXCLUDED.ambiguity_class, status='published';")
        sql(q, "brands")
    print(f"  {len(rows)} brands")


def seed_aliases():
    print("seeding brand_aliases…")
    rows = list(csv.DictReader(open(os.path.join(REPO, "data", "brand-aliases.csv"))))
    for batch in [rows[i:i + 30] for i in range(0, len(rows), 30)]:
        values = []
        for r in batch:
            values.append(
                f"({lit(r['alias'])}, {lit(r['brand_slug'])}, {lit(r['alias_type'])}, "
                f"{lit(r['surface_class'])}, {int(r['min_corroborating'])}, "
                f"{r['bare_disabled'] == 'True'})")
        q = ("INSERT INTO brand_aliases (alias, brand_id, alias_type, surface_class, min_corroborating, bare_disabled) "
             "SELECT v.alias, b.id, v.atype, v.cls, v.min_c, v.disabled FROM (VALUES\n"
             + ",\n".join(values)
             + "\n) AS v(alias, bslug, atype, cls, min_c, disabled)\n"
             "JOIN brands b ON b.slug = v.bslug\n"
             "ON CONFLICT (alias, brand_id) DO NOTHING;")
        sql(q, "aliases")
    print(f"  {len(rows)} aliases")


def load_mentions():
    """Load resolved + classified mentions.

    The vendor-subreddit trigger on `mentions` will REJECT any row from a
    vendor-named community, which is the point: BUILD-PROMPT's gate says vendor
    subreddits contribute zero scoring mentions, and an assertion that passes
    because the data never arrived is not a proof. Here it cannot arrive.
    """
    import datetime
    scored_dir = os.path.join(HERE, ".cache", "scored")
    if not os.path.isdir(scored_dir):
        print("  no scored corpus"); return
    total = 0
    for fn in sorted(os.listdir(scored_dir)):
        if not fn.endswith(".json"):
            continue
        payload = json.load(open(os.path.join(scored_dir, fn)))
        ms = payload["mentions"]
        if not ms:
            continue

        # threads first — mentions reference them
        threads = {}
        for m in ms:
            tid = m.get("thread_id")
            if tid and tid not in threads:
                threads[tid] = m
        for batch in [list(threads.values())[i:i + 40] for i in range(0, len(threads), 40)]:
            vals = []
            for m in batch:
                ts = datetime.datetime.utcfromtimestamp(float(m["created_utc"])).isoformat()
                vals.append(f"({lit(m['thread_id'])}, {lit(m['subreddit'])}, "
                            f"{lit((m.get('link_title') or '')[:400])}, "
                            f"{lit(m.get('permalink') or '')}, {lit(ts)}::timestamptz)")
            q = ("INSERT INTO threads (id, subreddit_id, link_title, permalink, created_utc) "
                 "SELECT v.id, s.id, v.title, v.permalink, v.ts FROM (VALUES\n"
                 + ",\n".join(vals)
                 + "\n) AS v(id, sub, title, permalink, ts)\n"
                 "JOIN subreddits s ON s.name = v.sub\n"
                 "ON CONFLICT (id) DO NOTHING;")
            sql(q, "threads")

        for batch in [ms[i:i + 25] for i in range(0, len(ms), 25)]:
            vals = []
            for m in batch:
                ts = datetime.datetime.utcfromtimestamp(float(m["created_utc"])).isoformat()
                perma = m.get("permalink") or ""
                if perma.startswith("/"):
                    perma = "https://www.reddit.com" + perma
                vals.append(
                    f"({lit(m['brand_slug'])}, {lit(m['doc_id'])}, {lit(ts)}::timestamptz, "
                    f"{int(m.get('doc_type') or 1)}, {lit(m.get('thread_id'))}, "
                    f"{lit(m.get('subreddit'))}, {lit(m.get('author') or '?')}, "
                    f"{lit(perma)}, {int(m.get('score') or 0)}, {lit(m.get('body') or '')}, "
                    f"{float(m.get('match_conf') or 0)}, {lit(m.get('matched_form') or '')}, "
                    f"{lit(m.get('rule_fired') or '')})")
            q = ("INSERT INTO mentions (brand_id, doc_id, created_utc, doc_type, thread_id, "
                 "subreddit_id, author, permalink, score, body, match_conf, matched_form, "
                 "rule_fired, run_id) "
                 "SELECT b.id, v.doc_id, v.ts, v.doc_type, v.thread_id, s.id, v.author, "
                 "v.permalink, v.score, v.body, v.conf, v.form, v.rule, "
                 "'00000000-0000-0000-0000-000000000001'::uuid FROM (VALUES\n"
                 + ",\n".join(vals)
                 + "\n) AS v(bslug, doc_id, ts, doc_type, thread_id, sub, author, permalink, "
                 "score, body, conf, form, rule)\n"
                 "JOIN brands b ON b.slug = v.bslug\n"
                 "JOIN subreddits s ON s.name = v.sub\n"
                 "ON CONFLICT (brand_id, doc_id, created_utc) DO NOTHING;")
            sql(q, "mentions " + fn)

            vals = []
            for m in batch:
                vals.append(
                    f"({lit(m['doc_id'])}, {lit(m['brand_slug'])}, {lit(m['model_version'])}, "
                    f"{int(m['label'])}, {float(m.get('intensity') or 0)}, "
                    f"{float(m.get('conf') or 0)}, {int(m.get('stage') or 3)}, "
                    f"{bool(m.get('is_comparative'))}, {bool(m.get('is_recommendation'))}, "
                    f"{bool(m.get('is_category_gripe'))}, {lit(m.get('evidence_span') or '')})")
            q = ("INSERT INTO mention_sentiment (doc_id, brand_id, model_version, label, "
                 "intensity, conf, stage, is_comparative, is_recommendation, is_category_gripe, "
                 "evidence_span) "
                 "SELECT v.doc_id, b.id, v.mv, v.label, v.intensity, v.conf, v.stage, "
                 "v.comp, v.rec, v.gripe, v.ev FROM (VALUES\n"
                 + ",\n".join(vals)
                 + "\n) AS v(doc_id, bslug, mv, label, intensity, conf, stage, comp, rec, gripe, ev)\n"
                 "JOIN brands b ON b.slug = v.bslug\n"
                 "ON CONFLICT (doc_id, brand_id, model_version) DO NOTHING;")
            sql(q, "sentiment " + fn)
        total += len(ms)
        print(f"  {fn[:-5]:<24} {len(ms)} mentions")
    print(f"  {total} mentions loaded")


def load_scores():
    """brand_category_scores from worker/.cache/index/*.json."""
    idx = os.path.join(HERE, ".cache", "index")
    if not os.path.isdir(idx):
        print("  no index"); return
    today = time.strftime("%Y-%m-%d")
    total = 0
    for fn in sorted(os.listdir(idx)):
        if not fn.endswith(".json"):
            continue
        rows = json.load(open(os.path.join(idx, fn)))["rows"]
        for batch in [rows[i:i + 12] for i in range(0, len(rows), 12)]:
            vals = []
            for s in batch:
                n = lambda k: (s[k] if s.get(k) is not None else "NULL")  # noqa: E731
                vals.append(
                    f"({lit(s['brand_slug'])}, {lit(s['category_slug'])}, {lit(today)}::date, "
                    f"{s['pos']}, {s['neg']}, {s['neu']}, {s['abstain']}, {s['n']}, {s['n_op']}, "
                    f"{n('n_eff')}, {n('deff')}, {n('deff_thread')}, {n('deff_author')}, "
                    f"{n('icc_thread')}, {n('icc_author')}, {bool(s.get('icc_estimated'))}, "
                    f"{n('alpha0')}, {n('beta0')}, {n('reddit_love_score')}, {n('polarization')}, "
                    f"{n('neutral_share')}, {n('abstain_share')}, {n('ci_low')}, {n('ci_high')}, "
                    f"{s['n_authors']}, {s['n_subreddits']}, {s['n_threads']}, "
                    f"{n('max_thread_share')}, {n('max_author_share')}, {n('max_subreddit_share')}, "
                    f"{n('rank_desc')}, {n('rank_asc')}, {bool(s['eligible'])}, "
                    f"{lit(s.get('failed_test'))}, {lit(s.get('failed_observed'))}, "
                    f"{lit(s.get('failed_required'))}, {lit(s['window_start'])}::date, "
                    f"{lit(s['window_end'])}::date, '1.0.0-provisional')")
            q = ("INSERT INTO brand_category_scores (brand_id, category_id, week_start, pos, neg, "
                 "neu, abstain, n, n_op, n_eff, deff, deff_thread, deff_author, icc_thread, "
                 "icc_author, icc_estimated, alpha0, beta0, reddit_love_score, polarization, "
                 "neutral_share, abstain_share, ci_low, ci_high, n_authors, n_subreddits, "
                 "n_threads, max_thread_share, max_author_share, max_subreddit_share, rank_desc, "
                 "rank_asc, eligible, failed_test, failed_observed, failed_required, "
                 "window_start, window_end, methodology_version) "
                 "SELECT b.id, c.id, v.ws, v.pos, v.neg, v.neu, v.abstain, v.n, v.n_op, v.n_eff, "
                 "v.deff, v.dt, v.da, v.it, v.ia, v.ie, v.a0, v.b0, v.rls, v.pol, v.ns, v.abs, "
                 "v.cl, v.ch, v.na, v.nsub, v.nth, v.mts, v.mas, v.mss, v.rd, v.ra, v.el, "
                 "v.ft, v.fo, v.fr, v.wstart, v.wend, v.mv FROM (VALUES\n"
                 + ",\n".join(vals)
                 + "\n) AS v(bslug, cslug, ws, pos, neg, neu, abstain, n, n_op, n_eff, deff, dt, "
                 "da, it, ia, ie, a0, b0, rls, pol, ns, abs, cl, ch, na, nsub, nth, mts, mas, "
                 "mss, rd, ra, el, ft, fo, fr, wstart, wend, mv)\n"
                 "JOIN brands b ON b.slug = v.bslug\n"
                 "JOIN categories c ON c.slug = v.cslug\n"
                 "ON CONFLICT (brand_id, category_id, week_start) DO UPDATE SET "
                 "reddit_love_score=EXCLUDED.reddit_love_score, eligible=EXCLUDED.eligible, "
                 "n=EXCLUDED.n, n_op=EXCLUDED.n_op, n_eff=EXCLUDED.n_eff, deff=EXCLUDED.deff, "
                 "pos=EXCLUDED.pos, neg=EXCLUDED.neg, neu=EXCLUDED.neu, abstain=EXCLUDED.abstain, "
                 "ci_low=EXCLUDED.ci_low, ci_high=EXCLUDED.ci_high, rank_desc=EXCLUDED.rank_desc, "
                 "failed_test=EXCLUDED.failed_test, failed_observed=EXCLUDED.failed_observed, "
                 "failed_required=EXCLUDED.failed_required;")
            sql(q, "scores " + fn)
        total += len(rows)
    print(f"  {total} score rows loaded")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--scores", action="store_true")
    ap.add_argument("--mentions", action="store_true")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    if args.seed or args.all:
        seed_categories()
        seed_subreddits()
        seed_category_subreddits()
        seed_brands()
        seed_aliases()

    if args.mentions or args.all:
        load_mentions()

    if args.scores or args.all:
        load_scores()

    # Verify
    print("\nverifying…")
    for table, _ in [("categories", 20), ("subreddits", 0), ("brands", 0),
                     ("brand_aliases", 0), ("category_subreddits", 0),
                     ("threads", 0), ("mentions", 0), ("mention_sentiment", 0),
                     ("brand_category_scores", 0)]:
        r = sql(f"SELECT count(*)::int n FROM {table}")
        if r:
            print(f"  {table}: {r[0]['n']} rows")


if __name__ == "__main__":
    main()
