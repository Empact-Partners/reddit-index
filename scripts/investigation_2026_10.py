#!/usr/bin/env python3
"""Recompute every number in docs/investigation-2026-10.md.

Read-only. Every query runs inside a READ ONLY transaction through the session
pooler (worker/db.py), aggregates on the server and brings back small result
sets. The one exception is `--sample`, which brings back 200 short text
windows for the hand check.

  python3 scripts/investigation_2026_10.py            # all series -> docs/investigation-2026-10/*.csv
  python3 scripts/investigation_2026_10.py --only daily storage
  python3 scripts/investigation_2026_10.py --sample   # quality sample -> worker/.cache/ (never committed: Reddit text)
  python3 scripts/investigation_2026_10.py --egress 300   # two counter readings N seconds apart

Reads ~/.claude/.reddit-index.json (database), ~/.railway/config.json,
~/.claude/.vercel-empact.json, ~/.claude/.supabase-empact.token. Prints no
credential.
"""
from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "investigation-2026-10")
sys.path.insert(0, os.path.join(ROOT, "worker"))

REF = "nrsyqcttpijxhwtdtoct"
RAILWAY = {"p": "90cd4c29-797c-4552-90d9-81c3b9914ffa",
           "s": "ff501aef-926d-4e24-8ef8-476855cd41b9",
           "e": "f3a7784c-7cd9-4cb8-a9ea-05efe657a7ff"}
VERCEL_PROJECT = "prj_OhSRGKEKFeN2A9JU1BTeebdR6E29"
SINCE = "2026-08-01"
UA = "Mozilla/5.0 (reddit-index investigation)"

# ---------------------------------------------------------------- queries
Q: dict[str, tuple[str, str]] = {}

Q["daily_activity"] = ("daily", f"""
with days as (select d::date d from generate_series('{SINCE}'::date, (now() at time zone 'utc')::date, '1 day') d),
th as (select first_seen_at::date d, count(*) n from public.threads where first_seen_at >= '{SINCE}' group by 1),
me as (select loaded_at::date d, count(*) n, sum(octet_length(body)) body_bytes,
              to_char(min(loaded_at),'HH24:MI') first_write, to_char(max(loaded_at),'HH24:MI') last_write,
              count(distinct run_id) runs
       from public.mentions where loaded_at >= '{SINCE}' group by 1),
la as (select scored_at::date d, count(*) n,
              count(*) filter (where model_version like 'deepseek%') deepseek,
              count(*) filter (where model_version like 'haiku%') haiku,
              count(*) filter (where model_version like 'claude-cli%') claude_cli
       from public.mention_sentiment where scored_at >= '{SINCE}' group by 1),
rm as (select detected_at::date d, count(*) n from public.removals where detected_at >= '{SINCE}' group by 1),
dc as (select delete_checked_at::date d, count(*) n from public.mentions where delete_checked_at >= '{SINCE}' group by 1),
sc as (select computed_at::date d, count(*) n from public.brand_category_scores group by 1)
select days.d as day,
       coalesce(th.n,0) threads_first_seen, coalesce(me.n,0) mentions_stored,
       coalesce(me.body_bytes,0) mention_text_bytes, me.first_write, me.last_write, coalesce(me.runs,0) collector_runs,
       coalesce(la.n,0) mentions_classified, coalesce(la.deepseek,0) by_deepseek, coalesce(la.haiku,0) by_haiku,
       coalesce(la.claude_cli,0) by_claude_cli,
       coalesce(sc.n,0) score_rows_computed, coalesce(rm.n,0) removals_detected, coalesce(dc.n,0) delete_probes
from days left join th using (d) left join me using (d) left join la using (d)
          left join rm using (d) left join dc using (d) left join sc using (d)
order by 1""")

Q["run_receipts"] = ("daily", """
select scope, ym, stage, code_version, left(watermark, 200) watermark, rows, status, finished_at
from public.ingest_state where scope like '\\_%' order by finished_at desc nulls last""")

Q["site_vs_db_summary"] = ("site", """
with meta as (select refreshed_at, mentions_max, rail_rows, mentions_rows, sentiment_max from public.mention_rail_meta),
per as (
  select b.id, b.slug,
         count(m.*) mentions_held,
         count(m.*) filter (where m.loaded_at > (select refreshed_at from meta)) mentions_after_build,
         max(m.created_utc) newest_held
  from public.brands b left join public.mentions m on m.brand_id = b.id group by 1,2)
select (select refreshed_at from meta) as rail_refreshed_at,
       (select mentions_max from meta) as newest_mention_in_served_build,
       (select max(created_utc) from public.mentions) as newest_mention_held,
       (select mentions_rows from meta) as mentions_at_build,
       (select count(*) from public.mentions) as mentions_now,
       (select sentiment_max from meta) as newest_label_at_build,
       (select max(scored_at) from public.mention_sentiment) as newest_label_now,
       count(*) filter (where mentions_held > 0) as brands_with_mentions,
       count(*) filter (where mentions_after_build > 0) as pages_with_newer_data_than_served,
       count(*) filter (where mentions_held > 0 and mentions_after_build = 0) as pages_unchanged_since_build,
       sum(mentions_after_build) as mentions_not_on_site,
       percentile_disc(0.5) within group (order by mentions_after_build) filter (where mentions_after_build > 0) as median_new_mentions_per_stale_page,
       max(mentions_after_build) as max_new_mentions_on_one_page
from per""")

Q["site_vs_db_per_brand"] = ("site", """
with meta as (select refreshed_at from public.mention_rail_meta),
rail as (select brand_slug, max(created_utc) newest_served, count(*) cards from public.mention_rail_mv group by 1)
select b.slug, count(m.*) mentions_held,
       count(m.*) filter (where m.loaded_at > (select refreshed_at from meta)) mentions_after_build,
       max(m.created_utc)::date newest_held, r.newest_served::date newest_served, coalesce(r.cards,0) cards_served
from public.brands b join public.mentions m on m.brand_id = b.id left join rail r on r.brand_slug = b.slug
group by b.slug, r.newest_served, r.cards
having count(m.*) filter (where m.loaded_at > (select refreshed_at from meta)) > 0
order by 3 desc""")

Q["storage_tables"] = ("storage", """
select coalesce(p.relname, c.relname) as relation,
       count(*) as parts,
       sum(pg_total_relation_size(c.oid)) as total_bytes,
       sum(pg_relation_size(c.oid)) as heap_bytes,
       sum(pg_indexes_size(c.oid)) as index_bytes,
       sum(pg_total_relation_size(c.oid)) - sum(pg_relation_size(c.oid)) - sum(pg_indexes_size(c.oid)) as toast_bytes,
       sum(c.reltuples)::bigint as est_rows,
       sum(s.n_dead_tup) as dead_rows,
       max(greatest(s.last_vacuum, s.last_autovacuum)) as last_vacuum
from pg_class c join pg_namespace n on n.oid = c.relnamespace
left join pg_inherits i on i.inhrelid = c.oid left join pg_class p on p.oid = i.inhparent
left join pg_stat_user_tables s on s.relid = c.oid
where n.nspname = 'public' and c.relkind in ('r','m')
group by 1 order by 3 desc""")

Q["storage_partitions"] = ("storage", """
select c.relname as partition, pg_total_relation_size(c.oid) as total_bytes, pg_relation_size(c.oid) as heap_bytes,
       pg_indexes_size(c.oid) as index_bytes, c.reltuples::bigint as est_rows, s.n_dead_tup as dead_rows
from pg_inherits i join pg_class c on c.oid = i.inhrelid join pg_class p on p.oid = i.inhparent
left join pg_stat_user_tables s on s.relid = c.oid
where p.relname = 'mentions' and pg_total_relation_size(c.oid) > 16384 order by 1""")

Q["storage_indexes"] = ("storage", """
select s.relname as table_name, s.indexrelname as index_name, pg_relation_size(s.indexrelid) as bytes, s.idx_scan as scans
from pg_stat_user_indexes s where s.schemaname = 'public' and pg_relation_size(s.indexrelid) > 1048576
order by 3 desc limit 60""")

Q["storage_text"] = ("storage", """
with rail as (select b.id brand_id, r.doc_id from public.mention_rail_mv r join public.brands b on b.slug = r.brand_slug),
m as (select m.doc_id, m.brand_id, octet_length(m.body) bytes, m.doc_type, (r.doc_id is not null) on_site
      from public.mentions m left join rail r on r.doc_id = m.doc_id and r.brand_id = m.brand_id)
select count(*) mention_rows, count(distinct doc_id) distinct_documents,
       sum(bytes) text_bytes_as_stored,
       (select sum(mx) from (select max(bytes) mx from m group by doc_id) x) text_bytes_one_copy_per_document,
       count(*) filter (where on_site) rows_shown_on_site, sum(bytes) filter (where on_site) text_bytes_shown_on_site,
       count(*) filter (where not on_site) rows_not_shown, sum(bytes) filter (where not on_site) text_bytes_not_shown,
       round(avg(bytes)) avg_text_bytes, max(bytes) max_text_bytes,
       count(*) filter (where doc_type = 2) posts, count(*) filter (where doc_type = 1) comments
from m""")

Q["storage_duplicates"] = ("storage", """
select (select count(*) from (select brand_id, doc_id from public.mentions group by 1,2 having count(*) > 1) x) as brand_doc_pairs_stored_twice,
       (select count(*) from (select doc_id from public.mentions group by 1 having count(*) > 1) x) as documents_matching_several_brands,
       (select max(n) from (select count(*) n from public.mentions group by doc_id) x) as most_brands_on_one_document,
       (select count(*) from (select doc_id, brand_id from public.mention_sentiment group by 1,2 having count(*) > 1) x) as pairs_labelled_more_than_once,
       (select count(*) from public.threads t where not exists (select 1 from public.mentions m where m.thread_id = t.id)) as threads_without_any_mention,
       (select count(*) from public.threads) as threads_total,
       (select count(*) from public.mention_sentiment s where not exists
            (select 1 from public.mentions m where m.doc_id = s.doc_id and m.brand_id = s.brand_id)) as labels_without_a_mention""")

Q["labels_by_month"] = ("storage", """
select to_char(date_trunc('month', m.loaded_at), 'YYYY-MM') loaded_month, count(*) mentions,
       count(*) filter (where s.doc_id is not null) labelled,
       count(*) filter (where s.doc_id is null) unlabelled
from public.mentions m left join lateral (select doc_id from public.mention_sentiment s
       where s.doc_id = m.doc_id and s.brand_id = m.brand_id limit 1) s on true
group by 1 order by 1""")

Q["labels_by_engine"] = ("storage", """
select model_version, count(*) labels, min(scored_at)::date first_day, max(scored_at)::date last_day,
       count(*) filter (where label = 0) neutral, count(*) filter (where label = 1) positive,
       count(*) filter (where label = 2) negative, count(*) filter (where label = 3) abstain
from public.mention_sentiment group by 1 order by 2 desc""")

Q["cost_statements"] = ("cost", """
select r.rolname as role, s.calls, s.rows, round(s.total_exec_time / 1000) as total_seconds,
       left(regexp_replace(s.query, '\\s+', ' ', 'g'), 150) as query
from extensions.pg_stat_statements s join pg_roles r on r.oid = s.userid
where s.dbid = (select oid from pg_database where datname = current_database())
order by s.rows desc limit 25""")

Q["cost_rows_by_role"] = ("cost", """
select r.rolname as role, sum(s.calls) calls, sum(s.rows) rows_returned, round(sum(s.total_exec_time) / 1000) total_seconds,
       (select stats_reset from extensions.pg_stat_statements_info) as counted_since
from extensions.pg_stat_statements s join pg_roles r on r.oid = s.userid
where s.dbid = (select oid from pg_database where datname = current_database())
group by 1 order by 3 desc""")

Q["quality_brands"] = ("quality", """
with per as (select b.id, b.surface_class, b.created_at >= '2026-08-19' as added_in_expansion,
                    count(m.*) n, count(m.*) filter (where m.loaded_at >= '2026-09-01') n_since_sep
             from public.brands b left join public.mentions m on m.brand_id = b.id group by 1,2,3)
select surface_class, added_in_expansion, count(*) brands, count(*) filter (where n = 0) brands_with_no_mentions,
       count(*) filter (where n between 1 and 9) brands_with_1_to_9, count(*) filter (where n >= 10) brands_with_10_plus,
       sum(n) mentions, sum(n_since_sep) mentions_loaded_since_1_sep
from per group by 1,2 order by 1,2""")

Q["quality_rules"] = ("quality", """
select m.rule_fired, count(*) mentions, count(distinct m.brand_id) brands,
       count(s.doc_id) labelled, count(*) filter (where s.label = 0) neutral,
       count(*) filter (where s.label = 1) positive, count(*) filter (where s.label = 2) negative
from public.mentions m left join lateral (select s.doc_id, s.label from public.mention_sentiment s
       where s.doc_id = m.doc_id and s.brand_id = m.brand_id order by s.scored_at desc limit 1) s on true
group by 1 order by 2 desc""")

Q["quality_top_forms"] = ("quality", """
select lower(m.matched_form) matched_form, b.slug brand, b.surface_class, count(*) mentions,
       count(s.doc_id) labelled, count(*) filter (where s.label in (1,2)) opinionated
from public.mentions m join public.brands b on b.id = m.brand_id
left join lateral (select s.doc_id, s.label from public.mention_sentiment s
       where s.doc_id = m.doc_id and s.brand_id = m.brand_id order by s.scored_at desc limit 1) s on true
group by 1,2,3 order by 4 desc limit 150""")

Q["quality_domain_forms"] = ("quality", """
select lower(m.matched_form) as matched_web_address, b.slug as brand, b.name as brand_name, count(*) as mentions,
       count(*) filter (where m.loaded_at >= '2026-09-01') as mentions_loaded_since_1_sep
from public.mentions m join public.brands b on b.id = m.brand_id
where m.matched_form ~ '^[a-z0-9.-]+\\.[a-z]{2,}$'
group by 1,2,3 order by 4 desc limit 120""")

Q["quality_scores"] = ("quality", """
select count(*) score_rows, count(distinct brand_id) brands_scored, max(week_start) week_start,
       max(computed_at) computed_at, count(*) filter (where eligible) eligible_rows,
       min(window_start) window_start, max(window_end) window_end, max(methodology_version) methodology_version
from public.brand_category_scores""")

RANK_SQL = """
with lab as (
  select m.brand_id, m.subreddit_id, m.created_utc, s.label
  from public.mentions m
  join lateral (select s.label from public.mention_sentiment s where s.doc_id = m.doc_id and s.brand_id = m.brand_id
                order by s.scored_at desc limit 1) s on true)
select b.slug, b.primary_category_id as cat,
       count(*) filter (where label = 1) pos_all, count(*) filter (where label = 2) neg_all,
       count(*) filter (where label in (0,3)) neu_all,
       count(*) filter (where label = 1 and created_utc >= now() - interval '365 days' and cs.is_scoring) pos_win,
       count(*) filter (where label = 2 and created_utc >= now() - interval '365 days' and cs.is_scoring) neg_win
from lab join public.brands b on b.id = lab.brand_id
left join public.category_subreddits cs on cs.category_id = b.primary_category_id and cs.subreddit_id = lab.subreddit_id
where b.primary_category_id is not null
group by 1,2
"""


SAMPLE_SQL = """
with strata(rule_like, short_only, n) as (values
   ('safe_word_boundary', true, 60), ('safe_word_boundary', false, 30), ('domain_autoaccept', false, 20),
   ('ambiguous_corroborated%', false, 50), ('hostile_corroborated%', false, 40)),
pool as (
  select m.doc_id, m.brand_id, m.rule_fired, m.matched_form, m.doc_type, m.body, m.thread_id, m.subreddit_id, m.created_utc,
         (length(m.matched_form) <= 6 and m.matched_form !~ '[^A-Za-z]') as short_form
  from public.mentions m tablesample system (4) where m.loaded_at >= '2026-06-01')
select st.rule_like, st.short_only, p.doc_id, b.slug brand_slug, b.name brand_name, b.surface_class, c.name category,
       p.rule_fired, p.matched_form, p.doc_type, sr.name subreddit, left(t.link_title, 160) thread_title,
       p.created_utc::date created,
       substr(p.body, greatest(1, position(lower(p.matched_form) in lower(p.body)) - 350), 800) as text_window,
       (select s.label from public.mention_sentiment s where s.doc_id = p.doc_id and s.brand_id = p.brand_id
        order by s.scored_at desc limit 1) as stored_label
from strata st
cross join lateral (
  select * from pool p where p.rule_fired like st.rule_like and (not st.short_only or p.short_form)
  order by md5(p.doc_id || '2026-10') limit st.n) p
join public.brands b on b.id = p.brand_id
left join public.categories c on c.id = b.primary_category_id
left join public.subreddits sr on sr.id = p.subreddit_id
left join public.threads t on t.id = p.thread_id
"""


# Web addresses that belong to a parent company or a marketplace but are stored in the
# gazetteer as an alias of ONE of its products. Judged by hand on 2026-10-02 from the
# top 120 address forms; every link to the address is counted as a mention of that product.
PARENT_ADDRESS_AS_ONE_PRODUCT = {
    "github.com": "github-actions", "google.com": "google-sheets", "apple.com": "keynote",
    "store.steampowered.com": "steam-game-recording", "apps.apple.com": "snapseed", "instagram.com": "edits",
    "chromewebstore.google.com": "boomerang-soap-and-rest-client", "microsoft.com": "dynamics-365-field-service",
    "deviantart.com": "dreamup", "wordpress.org": "arforms", "learn.microsoft.com": "azure-resource-manager",
    "mozilla.org": "mozilla-vpn", "proton.me": "proton-drive", "tiktok.com": "tiktok-one",
    "addons.mozilla.org": "wizdler", "aws.amazon.com": "amazon-aurora", "gitlab.com": "gitlab-ci-cd",
    "nvidia.com": "nvidia-app", "adobe.com": "adobe-acrobat", "linkedin.com": "linkedin-sales-navigator",
    "python.org": "idle", "apps.shopify.com": "ph-multi-carrier-shipping-label", "app.link": "appointlet",
    "docker.com": "docker-desktop", "ui.com": "unifi-network", "amd.com": "amd-software-adrenalin-edition",
    "gnu.org": "gnu-emacs", "duckduckgo.com": "duck-ai", "roblox.com": "roblox-studio",
    "nintendo.com": "game-builder-garage", "jotform.com": "jotform-sign", "cloud.google.com": "bigquery",
    "zillow.com": "zillow-rental-manager", "oracle.com": "oracle-aconex", "developer.apple.com": "xcode",
    "dell.com": "dell-wyse-management-suite", "elevenlabs.io": "elevenlabs-scribe",
    "apartments.com": "apartments-com-rental-manager",
}

# ---------------------------------------------------------------- helpers
def write_csv(name: str, rows: list[dict]) -> None:
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + ".csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        if not rows:
            f.write("")
            return
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})
    print(f"  {name}.csv  {len(rows)} rows")


def run_sql(groups: set[str] | None) -> None:
    import db  # worker/db.py
    with db.connect() as conn:
        conn.autocommit = True
        for name, (group, sql) in Q.items():
            if groups and group not in groups:
                continue
            t0 = time.time()
            with conn.transaction():
                conn.execute("set transaction read only")
                conn.execute("set local statement_timeout = '15min'")
                cur = conn.execute(sql)
                cols = [d.name for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            if name == "quality_domain_forms":
                for r in rows:
                    hit = PARENT_ADDRESS_AS_ONE_PRODUCT.get(r["matched_web_address"]) == r["brand"]
                    r["parent_address_stored_as_one_product"] = "yes" if hit else ""
            write_csv(name, rows)
            print(f"      ({time.time() - t0:.1f}s)")


def _get(url: str, headers: dict, data: bytes | None = None) -> dict:
    req = urllib.request.Request(url, data=data, headers={**headers, "User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=90).read())


def railway_deployments() -> None:
    subprocess.run(["railway", "whoami"], capture_output=True, timeout=60)
    tok = json.load(open(os.path.expanduser("~/.railway/config.json")))["user"]["accessToken"]
    rows, after = [], None
    while True:
        q = ("query($p:String!,$s:String!,$e:String!,$a:String){ deployments(first:50, after:$a, input:"
             "{projectId:$p, serviceId:$s, environmentId:$e}){ pageInfo { hasNextPage endCursor } "
             "edges { node { id status createdAt updatedAt meta } } } }")
        d = _get("https://backboard.railway.com/graphql/v2",
                 {"Authorization": "Bearer " + tok, "Content-Type": "application/json"},
                 json.dumps({"query": q, "variables": {**RAILWAY, "a": after}}).encode())["data"]["deployments"]
        for e in d["edges"]:
            n = e["node"]
            m = n.get("meta") or {}
            sm = m.get("serviceManifest") or {}
            rows.append({"deployment": n["id"][:8], "status": n["status"], "created_utc": n["createdAt"],
                         "last_change_utc": n["updatedAt"], "reason": m.get("reason"),
                         "dockerfile": (sm.get("build") or {}).get("dockerfilePath"),
                         "cron_in_manifest": (sm.get("deploy") or {}).get("cronSchedule")})
        if not d["pageInfo"]["hasNextPage"]:
            break
        after = d["pageInfo"]["endCursor"]
    write_csv("railway_deployments", rows)


def vercel_deployments() -> None:
    tok = json.load(open(os.path.expanduser("~/.claude/.vercel-empact.json")))["token"]
    rows, until = [], None
    while True:
        url = f"https://api.vercel.com/v6/deployments?projectId={VERCEL_PROJECT}&limit=100" + (f"&until={until}" if until else "")
        d = _get(url, {"Authorization": "Bearer " + tok})
        for x in d.get("deployments", []):
            rows.append({"deployment": x.get("uid", "")[:16], "state": x.get("state"), "target": x.get("target") or "preview",
                         "created_utc": dt.datetime.fromtimestamp(x["created"] / 1000, dt.timezone.utc).isoformat(timespec="seconds"),
                         "commit": (x.get("meta") or {}).get("githubCommitSha", "")[:7], "source": x.get("source")})
        nxt = (d.get("pagination") or {}).get("next")
        if not nxt:
            break
        until = nxt
    write_csv("vercel_deployments", rows)
    by_day: dict[str, dict] = {}
    for r in rows:
        day = r["created_utc"][:10]
        b = by_day.setdefault(day, {"day": day, "builds_ready": 0, "production_ready": 0, "canceled": 0, "errored": 0})
        if r["state"] == "READY":
            b["builds_ready"] += 1
            b["production_ready"] += r["target"] == "production"
        elif r["state"] == "CANCELED":
            b["canceled"] += 1
        elif r["state"] == "ERROR":
            b["errored"] += 1
    write_csv("vercel_builds_by_day", sorted(by_day.values(), key=lambda r: r["day"]))


def _mgmt_token() -> str:
    tok = open(os.path.expanduser("~/.claude/.supabase-empact.token")).read().strip()
    try:
        j = json.loads(tok)
        return j.get("token") or j.get("access_token")
    except ValueError:
        return tok


def _metrics() -> dict[str, float]:
    """node_exporter series for this project. The key is fetched and used in memory only."""
    keys = _get(f"https://api.supabase.com/v1/projects/{REF}/api-keys?reveal=true",
                {"Authorization": "Bearer " + _mgmt_token()})
    # The secret key comes back masked from ?reveal on this project; the legacy
    # service_role JWT is the one the metrics endpoint accepts. Try in order.
    cands = [k.get("api_key") for k in keys if k.get("type") == "secret"] + \
            [k.get("api_key") for k in keys if k.get("name") == "service_role"]
    text = None
    for secret in [c for c in cands if c]:
        auth = base64.b64encode(("service_role:" + secret).encode()).decode()
        req = urllib.request.Request(f"https://{REF}.supabase.co/customer/v1/privileged/metrics",
                                     headers={"Authorization": "Basic " + auth, "User-Agent": UA})
        try:
            text = urllib.request.urlopen(req, timeout=90).read().decode()
            break
        except urllib.error.HTTPError:
            continue
    if text is None:
        raise RuntimeError("no project key opens the metrics endpoint")
    out: dict[str, float] = {}
    for line in text.splitlines():
        if line.startswith("#") or " " not in line:
            continue
        name, val = line.rsplit(" ", 1)
        try:
            v = float(val)
        except ValueError:
            continue
        if name.startswith("node_network_transmit_bytes_total") and 'device="lo"' not in name:
            out["transmit_bytes"] = out.get("transmit_bytes", 0) + v
        elif name.startswith("node_network_receive_bytes_total") and 'device="lo"' not in name:
            out["receive_bytes"] = out.get("receive_bytes", 0) + v
        elif name.startswith("node_filesystem_size_bytes") and 'mountpoint="/data"' in name:
            out["data_disk_bytes"] = v
        elif name.startswith("node_filesystem_avail_bytes") and 'mountpoint="/data"' in name:
            out["data_disk_free_bytes"] = v
        elif name.startswith("node_memory_MemTotal_bytes"):
            out["memory_bytes"] = v
        elif name.startswith("node_boot_time_seconds"):
            out["boot_time"] = v
    return out


def egress(seconds: int) -> None:
    a, ta = _metrics(), time.time()
    time.sleep(seconds)
    b, tb = _metrics(), time.time()
    span = tb - ta
    sent = b["transmit_bytes"] - a["transmit_bytes"]
    row = {"read_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "window_seconds": round(span), "bytes_sent_in_window": round(sent),
           "gb_per_day_at_this_rate": round(sent / span * 86400 / 1e9, 3),
           "counter_total_gb_since_boot": round(b["transmit_bytes"] / 1e9, 1),
           "data_disk_gb": round(b.get("data_disk_bytes", 0) / 1e9, 2),
           "data_disk_free_gb": round(b.get("data_disk_free_bytes", 0) / 1e9, 2),
           "memory_gb": round(b.get("memory_bytes", 0) / 1e9, 2)}
    path = os.path.join(OUT, "egress_readings.csv")
    new = not os.path.exists(path)
    os.makedirs(OUT, exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if new:
            w.writeheader()
        w.writerow(row)
    print(json.dumps(row))


def sample() -> None:
    import db
    cache = os.path.join(ROOT, "worker", ".cache", "investigation")
    os.makedirs(cache, exist_ok=True)
    with db.connect() as conn:
        conn.autocommit = True
        with conn.transaction():
            conn.execute("set transaction read only")
            conn.execute("set local statement_timeout = '15min'")
            conn.execute("select setseed(0.2026)")
            cur = conn.execute(SAMPLE_SQL)
            cols = [d.name for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    path = os.path.join(cache, "quality_sample.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for i, r in enumerate(rows, 1):
            r["n"] = i
            f.write(json.dumps(r, default=str, ensure_ascii=False) + "\n")
    print(f"  {len(rows)} sampled mentions -> {path} (Reddit text: never committed)")


def ranking() -> None:
    """Score every brand two ways and compare the boards.

    site   = what the build does (decisions/0011): all collected opinionated
             mentions, every subreddit, prior from the brand's primary category.
    method = what docs/methodology.md says: trailing 365 days, the category's
             scoring subreddits only, same estimator and prior.
    """
    import db
    from numerics import beta_quantile, PRIOR_K, PRIOR_P0_SMOOTH  # worker/numerics.py
    with db.connect() as conn:
        conn.autocommit = True
        with conn.transaction():
            conn.execute("set transaction read only")
            conn.execute("set local statement_timeout = '15min'")
            cur = conn.execute(RANK_SQL)
            cols = [d.name for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    def scores(key_pos: str, key_neg: str) -> dict[str, float | None]:
        by_cat: dict[int, list] = {}
        for r in rows:
            by_cat.setdefault(r["cat"], []).append(r)
        out = {}
        for cat, rs in by_cat.items():
            tp = sum(r[key_pos] for r in rs)
            tn = sum(r[key_pos] + r[key_neg] for r in rs)
            for r in rs:
                pos, neg = r[key_pos], r[key_neg]
                if pos + neg == 0 and (key_pos == "pos_win" or r["neu_all"] == 0):
                    out[r["slug"]] = None
                    continue
                op, on = tp - pos, tn - pos - neg
                p0 = (op + PRIOR_P0_SMOOTH / 2) / (on + PRIOR_P0_SMOOTH)
                q = beta_quantile(pos + PRIOR_K * p0, neg + PRIOR_K * (1 - p0), 0.10)
                out[r["slug"]] = float(int(100 * q + 0.5))
        return out

    site, meth = scores("pos_all", "neg_all"), scores("pos_win", "neg_win")
    cat_rows = {}
    for r in rows:
        cat_rows.setdefault(r["cat"], []).append(r)
    summary = []
    for cat, rs in cat_rows.items():
        def top(sc, n_key_p, n_key_n):
            ranked = [x for x in rs if sc.get(x["slug"]) is not None]
            ranked.sort(key=lambda x: (-sc[x["slug"]], -(x[n_key_p] + x[n_key_n])))
            return [x["slug"] for x in ranked[:10]], len(ranked)
        t_site, n_site = top(site, "pos_all", "neg_all")
        t_meth, n_meth = top(meth, "pos_win", "neg_win")
        diffs = [abs(site[x["slug"]] - meth[x["slug"]]) for x in rs
                 if site.get(x["slug"]) is not None and meth.get(x["slug"]) is not None]
        summary.append({"category_id": cat, "brands_scored_site_way": n_site, "brands_scored_method_way": n_meth,
                        "top10_shared": len(set(t_site) & set(t_meth)),
                        "same_number_one": bool(t_site and t_meth and t_site[0] == t_meth[0]),
                        "mean_abs_score_gap": round(sum(diffs) / len(diffs), 1) if diffs else "",
                        "max_abs_score_gap": max(diffs) if diffs else ""})
    write_csv("ranking_site_vs_methodology", sorted(summary, key=lambda r: r["category_id"]))
    per = [{"slug": r["slug"], "category_id": r["cat"], "pos_all": r["pos_all"], "neg_all": r["neg_all"],
            "score_site_way": site.get(r["slug"]), "pos_365d_scoring_subs": r["pos_win"],
            "neg_365d_scoring_subs": r["neg_win"], "score_methodology_way": meth.get(r["slug"])} for r in rows]
    write_csv("ranking_per_brand", sorted(per, key=lambda r: (r["category_id"], -(r["score_site_way"] or -1))))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="groups: daily site storage cost quality deployments")
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--egress", type=int, metavar="SECONDS")
    ap.add_argument("--ranking", action="store_true")
    a = ap.parse_args()
    if a.sample:
        sample()
        return 0
    if a.egress:
        egress(a.egress)
        return 0
    if a.ranking:
        ranking()
        return 0
    groups = set(a.only) if a.only else None
    run_sql(groups)
    if not groups or "deployments" in groups:
        railway_deployments()
        vercel_deployments()
    return 0


if __name__ == "__main__":
    sys.exit(main())
