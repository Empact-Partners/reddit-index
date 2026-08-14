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

## The 90-day depth sweep (Mac, `worker/sweep.py` + `worker/depth_run.py`)

The daily loop keeps the present current; the depth sweep is what makes each
category deep. `sweep.py --days 90` paginates `/r/{sub}/new` until posts age
past the cutoff — a complete 90-day census for any subreddit under ~11
posts/day, which is nearly all of them. A subreddit whose `/new` listing cap
(~1,000 posts) is *younger* than the cutoff is marked
`coverage: "approximate"` and gets supplements: `/top t=month`, `/top t=year`,
and per-noun scoped search, all client-filtered to the window.

Thread qualification in this mode: a brand surface form (the **full**
20,798-alias automaton via `Resolver.has_alias`, not the low-ambiguity regex
the daily loop uses) or an owning-category noun in title/selftext, not
removed, not locked, `num_comments >= 2`. Over-qualification is deliberate —
a false qualify costs one tree fetch, a false reject drops a thread forever,
and extraction still runs the fully gated `resolve()`.

State is per subreddit in `worker/.cache/sweep/<sub>.json` (schema 2) and
records the mode it was collected under, so a resume never mixes a 90-day
pass with an all-time one. Two rate-limit guards matter: a listing page that
comes back `_err` never lets the sub be marked `listings_done` (a truncated
listing used to look complete), and a tree that errors is counted in
`failed_trees` and retried rather than recorded as swept.

`depth_run.py` orchestrates it category by category — mention volume
descending, order frozen on first run — sweeping each category's subs, then
running that category's classify burn, then scoring and publishing, so
categories come online whole rather than everything half-done at once. A
subreddit shared by several categories is swept once and credited to all.

```bash
nohup caffeinate -is python3 -u worker/depth_run.py --days 90 \
    --allow-git-publish > /tmp/ri-depth.log 2>&1 &
python3 worker/depth_run.py --status              # per-category table
python3 worker/depth_run.py --list-approximate    # the busy-sub coverage list
```

Kill it at any instant; re-run the identical command to resume.

## Classification (Mac, `worker/classify_daily.py`)

Anti-join: every mention with **no** `mention_sentiment` row (any
model_version) inside the trailing 400 days. Items go to the Codex fleet
(gpt-5.6-luna, 40-item batches, 40 wide) through the shared item-level label
cache — a re-run never re-spends a model call. `entity_ok=false` verdicts
drop the mention (an entity decision, not a sentiment one). Labels upsert
with the pipeline's `model_version` constant; the engine is recorded
per-item in the cache.

The nightly run is **capped** (`CLASSIFY_DAILY_CAP`, default 30,000, newest
first) because it is unattended. A supervised burn is the same code
uncapped and category-scoped: `--category <slug> --cap 0 --loop`, draining
until the anti-join returns nothing. Scoping is by **subreddit** membership,
not brand: `score_db` builds a category's corpus from its scoring subs and
then filters brands by `also_in` in Python, so sub-scoping is what
guarantees everything the scorer will read is already labelled. A burn holds
`worker/.cache/codex-absa/burn.lock`; the nightly job sees it and skips
classification (it still scores and publishes), because both processes
compute the same content-addressed batch ids and would delete each other's
in-flight out-files.

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
