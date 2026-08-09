# The daily worker

The index refreshes every day through a two-machine loop, split by capability:
Railway can fetch but cannot run our LLMs; the Mac runs the LLM engines
(Codex fleet, Claude subscriptions) but should not be a 24/7 fetch box.

```
04:00 UTC  Railway cron container      worker/daily.py
           Reddit /new listings  ->  qualify  ->  72h revisit trees
           ->  rules-only resolve  ->  Supabase (threads, mentions, watermarks)

07:30 UTC  Mac launchd (com.reddit-index.daily)   worker/daily_mac.sh
           classify_daily.py   label every unlabelled mention (Codex fleet)
           score_db.py         re-score every category FROM Supabase, prune history
           deploy hook         Vercel rebuild = the publish step
```

## The fetch algorithm (Railway, `worker/daily.py`)

Per scoring subreddit (see [taxonomy.md](taxonomy.md) for the list):

1. `GET /r/{sub}/new?limit=100`, watermark-bounded (up to 3 pages while every
   item is newer than the stored watermark).
2. **Content-qualify** each post: a brand alias or an owning category's noun
   in the title or selftext; not removed, not locked. The backfill's
   `num_comments >= 3` floor is deliberately dropped — a fresh thread
   legitimately has no comments yet.
3. Upsert qualifying threads (`num_comments`/`score` refresh on conflict).
4. **Revisit window**: fetch full comment trees for this sub's threads first
   seen in the last **72 hours**, up to **12 per sub per day**, busiest
   first. A thread gets tree-fetched up to ~4 times across its window;
   `ON CONFLICT DO NOTHING` on the mentions PK makes re-fetches free while
   catching every comment that arrived since the last visit.
5. Resolve mentions (the same rules-only Aho-Corasick resolver as the
   backfill — word boundaries, qualified forms, stop-contexts; nothing
   guessed), insert verbatim bodies, **commit per sub**, then advance the
   watermark. A mid-run death costs nothing committed.

Budget: ~600 listing calls + a few thousand tree calls ≈ 45-90 min at the
80 req/min discipline.

### Watermarks (`ingest_state`)

| column | value |
|---|---|
| scope | subreddit name (plus one `_run` summary row) |
| ym | `'daily'` (constant — this lane is not month-scoped) |
| stage | `'new_listing'` |
| code_version | `'daily-v1'` (bump = clean restart, by PK) |
| watermark | newest `created_utc` ingested for that sub |

A sub that errors keeps its old watermark and self-heals next run (a
100-deep listing covers several days on most communities).

## Classification (Mac, `worker/classify_daily.py`)

Anti-join: every mention with **no** `mention_sentiment` row (any
model_version) inside the trailing 400 days. Items go to the Codex fleet
(gpt-5.6-luna, 40-item batches, 40 wide) through the shared item-level label
cache — a re-run never re-spends a model call. `entity_ok=false` verdicts
drop the mention (an entity decision, not a sentiment one). Labels upsert
with the pipeline's `model_version` constant; the engine is recorded
per-item in the cache.

## Scoring (Mac, `worker/score_db.py`)

Supabase is the corpus — the local file caches are backfill machinery, not
the source of truth. Per category: labelled mentions from its scoring subs in
the trailing 365 days, **restricted to brands whose category membership
includes it** (a mention of Google Drive in r/CRM stays on Google Drive's
page and out of the CRM leaderboard). `score_category()` — the EB-shrunk
estimator, unchanged — then upsert into `brand_category_scores` and **delete
every older `week_start` row**: the table holds exactly one truthful set.
No deltas, no history, by design.

## Publish

`curl -X POST $DEPLOY_HOOK` — a Vercel rebuild. The site is fully static
(`force-static`, `dynamicParams=false`): a rebuild re-reads Supabase once,
re-renders every route, and new brands get pages. There is no cache
revalidation path that refreshes this site without a build; the hook IS the
publish mechanism.

## Failure matrix

| scenario | outcome |
|---|---|
| Railway ran, Mac didn't | unclassified mentions wait; next Mac run's anti-join sweeps them |
| Mac ran, Railway didn't | anti-join ≈ empty; identical scores re-upserted; harmless |
| double runs (either side) | watermarks + PK conflicts + label cache → zero duplicates, zero re-spend |
| Railway dies mid-run | finished subs committed; unfinished resume from their watermark |
| batch insert hits the vendor-sub trigger | bisect to row-by-row, reject journaled, run continues |
| month boundary | monthly partitions pre-created at run start, this month + next |

## Deployment

- **Railway**: `Dockerfile` at the repo root (python:3.12-slim +
  `psycopg[binary]` + `pyahocorasick`; CSVs baked into the image so mapping
  updates ship with a push). Cron service, `0 4 * * *`, restart policy off.
  Env: `REDDIT_CLIENT_ID/SECRET/USER_AGENT`, `SUPABASE_PROJECT_REF`,
  `SUPABASE_DB_PASSWORD` (+ optional `SUPABASE_DB_HOST/USER/REGION`),
  `RI_CACHE=/tmp/ri-cache`. Transport is the Supavisor **session** pooler
  (`aws-0-us-east-1.pooler.supabase.com:5432`, IPv4) — the direct DB host is
  IPv6-only and unreachable from Railway, and the org-wide Supabase PAT
  never enters the container.
- **Mac**: `~/Library/LaunchAgents/com.reddit-index.daily.plist` runs
  `worker/daily_mac.sh` daily; the deploy-hook URL lives in
  `~/.claude/.reddit-index.json` under `deploy_hook` (0600).
