# Technical Architecture

## Bottom line

- 🟢 **Three vendors, one of which is the CDN.** Next.js App Router on Vercel, Supabase Postgres plus Supabase Storage for data, one long-lived worker for the pipeline. Push to `main` deploys. Nothing else is in the serving path.
- 🟡 **Vercel's Hobby plan is for personal, non-commercial use** ([Vercel pricing](https://vercel.com/pricing)), so this site needs **Pro at $20/seat/month** at or before launch. A second, harder blocker applies immediately: Hobby teams cannot connect to a repository owned by a GitHub organization at all ([Vercel limits](https://vercel.com/docs/limits)), and the repo is `Empact-Partners/reddit-index`.
- 🟢 **The raw corpus never enters Postgres.** 200-400M items live as Hive-partitioned Parquet in Supabase Storage and are scanned in-process by DuckDB during pipeline runs. Postgres holds roughly 4M derived rows at Phase 1 and 38M at full scale, against a design ceiling of 200M.
- 🟢 **Roughly 5,000 pages on a weekly data refresh is an SSG-with-on-demand-revalidation problem**, not a per-request-rendering one. The pipeline calls `revalidateTag`; a full rebuild is reserved for code and schema changes.
- 🟡 **Supabase Storage bills egress at $0.09/GB past 250 GB** ([Supabase pricing](https://supabase.com/pricing)), where Cloudflare R2 billed none. Cache shards on the worker's local NVMe and treat Supabase Storage as the durable copy, not the working set.
- 🟢 **Cost is ≈ $74/month at Phase 1 and ≈ $301/month at full scale.** Line items in §9.

---

## 1. Flow

```
SOURCES                     COMPUTE (one long-lived worker)        STORES                        SERVE
──────────────────────────────────────────────────────────────────────────────────────────────────────────
Arctic Shift / Academic ─┐
Torrents .zst dumps      │  S0 acquire ──► S1 normalize ────────►  Supabase Storage (S3 API)
(archives, monthly)      ├─►                                        corpus/raw/{sub}/{ym}.zst
                         │       │                                  corpus/posts/sub=*/ym=*/
Reddit Data API         ─┘       │                                  corpus/comments/sub=*/ym=*/
(app-only OAuth, live)           ▼
                            S2 candidates (Aho-Corasick) ───────►  corpus/candidates/…
                                 ▼
                            S3 entity resolution ───────────────►  corpus/resolved/…
                                 ▼
                            S4 sentiment (ONNX + LLM tail) ─────►  corpus/scored/…
                                 ▼
                            S5 COPY ────────────────────────────►  Supabase Postgres
                                 ▼                                  mentions (monthly partitions)
                            S6 aggregate (SQL) ─────────────────►  brand_category_scores
                                 ▼                                  leaderboards · brand_pages
                            S7 publish
                                 │
                                 │  POST /api/revalidate ─────────────────────────►  Next.js on Vercel
                                 │  (revalidateTag per brand + category)              App Router · ISR
                                 │                                                          │
                                 └─ deploy hook (code / schema only) ──────────►  build ─────┤
                                                                                             ▼
                                                                                    Vercel CDN → reader

delete-sync (nightly): Postgres doc_ids ─► Reddit /api/info ─► purge rows ─► write removals ─► revalidateTag
```

S1 through S4 read and write Parquet through DuckDB's `httpfs` extension pointed at Supabase Storage's S3-compatible endpoint, `https://{project_ref}.storage.supabase.co/storage/v1/s3` ([Supabase S3 auth](https://supabase.com/docs/guides/storage/s3/authentication)).

Both halves of that path are documented by their vendors. The combination is **NOT VERIFIED end to end by us** — benchmark a Hive-partitioned scan against a real bucket during Phase 0 before the sizing in §9 is treated as firm.

## 2. The storage split, and why

The corpus is 200-400M items, 0.5-1.5 TB as raw ndjson and 50-150 GB as zstd-compressed Parquet on the fields we keep ([02-data-acquisition.md](02-data-acquisition.md)). Postgres is the wrong home for it at any price.

Supabase can technically hold it, but a 2 TB database wants a 4XL instance at $1.32/hour, roughly $960/month ([compute and disk](https://supabase.com/docs/guides/platform/compute-and-disk)). Needing that instance is the signal that raw data landed in the wrong store, not a budget line.

So: **Parquet in Supabase Storage for everything the pipeline scans, Postgres for everything the site reads.** The boundary is stage S5. Parquet is append-only and immutable per shard; Postgres is the only mutable store and everything in it is derived.

**Derived row counts, the number that governs the split:**

| Postgres table | Phase 1 | Full scale |
|---|---:|---:|
| `mentions` | ~1.8M | ~17M |
| `mention_sentiment` | ~1.8M | ~17M |
| `threads` | ~0.3M | ~3M |
| `leaderboards` | ~52K | ~1.0M |
| `brand_category_scores` | ~26K | ~390K |
| everything else | <10K | <100K |
| **Total** | **≈ 4M** | **≈ 38M** |

Full scale assumes ~325K new mentions per week ([13-algorithm.md](13-algorithm.md)) over a trailing 12-month window ([07-index-methodology.md](07-index-methodology.md)). Phase 1 assumes ~35K per week. Both are *inference from the modelled rates, not measured*.

**Breakpoints — where "Postgres holds only derived rows" stops being true:**

| Derived rows | Compute | What you do |
|---|---|---|
| < 10M | Micro $10 or Small $15 | Single tables, no partitioning needed. Phase 1 sits here |
| 10M-50M | Small $15 to Medium $60 | Partition `mentions` by month. Full scale sits here |
| 50M-200M | Large $110 + ~100 GB gp3 | The ceiling this design is sized against. Hot indexes must still fit 8 GB RAM |
| 200M-1B | XL $210 or 2XL $410 | Drop `mentions.body` from Postgres and read bodies from Parquet at publish time |
| > 1B | Wrong store | The corpus leaked into Postgres. Fix upstream; a bigger instance buys months, not a design |

Prices from [Supabase compute and disk](https://supabase.com/docs/guides/platform/compute-and-disk). Three things push you across a line:

- **Storing every ingested comment rather than only brand-bearing ones.** That is 200-400M rows on day one. It is the single mistake that invalidates the whole split.
- **Widening the window from a trailing 12 months to all-time.** At full scale that adds ~34M rows a year across `mentions` and `mention_sentiment`, so year six crosses 200M.
- **A 3× miss on the mention rate.** 325K/week modelled against 1M/week actual crosses 200M inside four years.

## 3. Schema

**Supabase Postgres** — derived only. Every table has RLS enabled (§5).

| Table | Key columns | Index / constraint | Kind |
|---|---|---|---|
| `subreddits` | `id`, `name`, `rule_posture`, `comments_per_hour`, `poll_interval_h`, `rules_hash`, `checked_at` | `UNIQUE(name)` | base |
| `categories` | `id`, `slug`, `name`, `parent_id`, `base_rate_c numeric`, `status` | `UNIQUE(slug)` | base |
| `category_subreddits` | `category_id`, `subreddit_id`, `is_scoring bool`, `worth numeric` | `PK(category_id, subreddit_id)`; partial index `WHERE is_scoring` | base |
| `brands` | `id`, `slug`, `name`, `primary_category_id`, `require_context bool`, `stop_contexts text[]`, `domains text[]` | `UNIQUE(slug)`; GIN on `domains` | base |
| `brand_aliases` | `brand_id`, `alias`, `alias_type`, `is_ambiguous bool` | `UNIQUE(alias, brand_id)`; feeds the Aho-Corasick automaton | base, **service-role only** |
| `threads` | `id text PK` (t3 fullname), `subreddit_id`, `link_title`, `permalink`, `created_utc`, `num_comments`, `archived bool` | `(subreddit_id, created_utc DESC)` | base |
| `mentions` | `id bigserial`, `brand_id`, `doc_type smallint`, `doc_id text` (fullname), `thread_id`, `subreddit_id`, `author`, `created_utc timestamptz`, `permalink`, `score int`, `body text`, `match_conf real`, `run_id uuid` | `PARTITION BY RANGE(created_utc)` monthly; `UNIQUE(brand_id, doc_id)`; `(brand_id, created_utc DESC)`; `(thread_id)`; `(brand_id, author)` | base, partitioned |
| `mention_sentiment` | `mention_id`, `model_version`, `label smallint`, `intensity real`, `conf real`, `stage smallint` | `PK(mention_id, model_version)` | base |
| `brand_category_scores` | `brand_id`, `category_id`, `week_start date`, `pos`, `neg`, `neu`, `abstain`, `n`, `n_eff`, `deff`, `love_score`, `hate_score`, `polarization`, `ci_low`, `ci_high`, `n_authors`, `n_subreddits`, `max_thread_share`, `max_author_share`, `eligible bool`, `failed_test text` | `PK(brand_id, category_id, week_start)` | **materialised** by S6 |
| `leaderboards` | `category_id`, `week_start`, `board` (`love`/`hate`), `brand_id`, `rank int`, `tied_with int[]`, `score numeric`, `rank_delta int` | `PK(category_id, week_start, board, brand_id)` | **materialised** from `brand_category_scores` |
| `brand_pages` | `brand_id PK`, `payload jsonb`, `content_hash`, `updated_at` | joined from `brands` by slug | **materialised** render payload |
| `removals` | `doc_id text PK`, `doc_type smallint`, `brand_ids bigint[]`, `reason`, `detected_at`, `purged_at`, `revalidated_at` | `(detected_at)`; `(revalidated_at) WHERE revalidated_at IS NULL` | tombstone ledger |
| `ingest_state` | `subreddit`, `ym`, `stage`, `code_version`, `file_hash`, `rows`, `status`, `finished_at` | `PK(subreddit, ym, stage, code_version)` | resumability ledger |

**Supabase Storage** — Hive-partitioned Parquet, append-only, `sub={name}/ym={YYYY-MM}/`:

| Dataset | Path | Key columns |
|---|---|---|
| `posts` | `corpus/posts/sub=*/ym=*/` | `id`, `subreddit`, `author`, `created_utc`, `title`, `selftext`, `permalink`, `score` |
| `comments` | `corpus/comments/sub=*/ym=*/` | `id`, `link_id`, `parent_id`, `subreddit`, `author`, `created_utc`, `body`, `permalink`, `score`, `depth` |
| `candidates` | `corpus/candidates/sub=*/ym=*/` | `doc_id`, `doc_type`, `alias_hit`, `char_offset` |
| `resolved` | `corpus/resolved/sub=*/ym=*/` | `doc_id`, `brand_id`, `match_conf`, `rule_fired` |
| `scored` | `corpus/scored/sub=*/ym=*/` | `doc_id`, `brand_id`, `label`, `conf`, `model_version` |

Three notes on the tables that are not obvious.

`removals` is a tombstone ledger, not an audit trail. Its job is to stop a purged `doc_id` being re-ingested from a stale archive shard on the next monthly reconcile, and to carry `revalidated_at` as the receipt that the cached page was invalidated too.

`brand_aliases` is service-role only because the alias, stop-context and ambiguity table is a working recipe for gaming the index. [07-index-methodology.md](07-index-methodology.md) §10 item 9 requires stating that countermeasures exist without publishing them.

`mentions.body` stores and displays full comment text. That is a priced, accepted risk, recorded with its clause citations in [01-legal.md](01-legal.md).

## 4. Next.js on Vercel

App Router, React Server Components, no client-side data fetching in the reader path. Route families follow [10-seo-aeo.md](10-seo-aeo.md) §4, where a brand page is **global and flat** — `/category/{cat}/brand/{brand}` is not a route and must never be generated.

| Route | Count (Phase 1 → full) | Strategy | Revalidation |
|---|---:|---|---|
| `/` | 1 | Prerendered at build | `revalidateTag('leaderboards')` on publish |
| `/category/[slug]` | 50 → ~1,000 | `generateStaticParams` over eligible categories, prerendered | `revalidateTag('category:{slug}')`; `revalidate = 86400` floor |
| `/brand/[slug]` | ~1,000 → ~5,000 | `generateStaticParams` over the **published** set only; `dynamicParams = true` for the tail | `revalidateTag('brand:{slug}')` on publish and on delete-sync |
| `/brand/[slug]/mentions/[page]` | paginated | Prerender pages 1-3, rest on first request | `revalidateTag('brand:{slug}')` |
| `/methodology` | 1 | Fully static, no data fetch, version-frozen | Rebuild only |
| `/sitemap.xml` + `/sitemap/[category].xml` | 1 + N | Route handlers, `revalidate = 3600` | `revalidateTag('sitemap')` |
| `/api/revalidate` | 1 | Route handler, `POST`, `dynamic = 'force-dynamic'`, bearer-secret gated | — |

### Why SSG with on-demand revalidation, and not per-request rendering

Reader-facing pages change once a week. Per-request rendering would pay a Supabase round trip on every view for data that is byte-identical between refreshes, and would put a 2-core Postgres in the request path of every Googlebot and AI-crawler hit.

The prices settle it. ISR reads cost $0.0004 per 1K and writes $0.004 per 1K ([Vercel limits](https://vercel.com/docs/limits)). Revalidating 5,000 pages weekly is ~20K writes a month, or $0.08. A million page views is a million reads, or $0.40. Both are rounding errors.

SSR moves the same traffic onto Function Invocations at $0.60 per million plus Active CPU from $0.128/hour, and turns Supabase compute into a variable that scales with traffic instead of a fixed monthly line. It buys nothing, because the data has not changed.

### How the pipeline triggers a refresh

Two mechanisms, deliberately separated:

1. **`revalidateTag` via `POST /api/revalidate`** — the default. S7 sends the changed category and brand slugs with `Authorization: Bearer $REVALIDATE_SECRET`; the handler calls `revalidateTag()` per slug. It takes seconds, touches only what changed, and needs no deployment.
2. **A Vercel deploy hook** — reserved for code, schema and methodology-version changes, where the whole site has to be rebuilt. Vercel allows 5 deploy hooks per project and 60 triggers per hour ([Vercel limits](https://vercel.com/docs/limits)).

Weekly data does not justify a rebuild. Use mechanism 1 for every ordinary cycle.

### The 45-minute build cap

Build time is capped at **45 minutes per deployment on every plan, Hobby and Pro alike** ([Vercel limits](https://vercel.com/docs/limits)). A 5,000-page build at 20-40 ms of render per page is roughly 2-4 minutes plus install and compile (*inference, not benchmarked*), so the headroom is wide. Five things to do, in order, if it stops being wide:

1. **Fetch once, not per page.** One query returning every `brand_pages.payload` into a module-scoped map makes the build CPU-bound instead of 5,000 network round trips. This is the single biggest lever.
2. **Return only the published set from `generateStaticParams`.** Brands failing the `n_eff ≥ 400` gate render on demand; they are linked from the below-threshold block, not crawled hard.
3. **Cap `generateStaticParams` at the top N by traffic and keep `dynamicParams = true`.** The tail generates on first request and stays cached until its tag is invalidated.
4. **Move to a larger build machine.** Build CPU Minutes bill at $0.0035 per CPU-minute, so more CPU is cheap next to a failed deploy.
5. **Split into two Vercel projects** — category surfaces and brand surfaces — behind one domain. Last resort; it doubles the deployment surface.

Vercel's own guidance is that builds slow past roughly 100,000 output files and that ISR is the fix. At ~5,000 pages that is headroom, not a plan.

## 5. Supabase

### Connection pooling

| Client | Mode | Port | Why |
|---|---|---:|---|
| The pipeline worker | Direct connection | 5432 | Long-lived process. Supports prepared statements and `COPY`. IPv6 by default; if the worker's network is IPv4-only, use Supavisor session mode on 5432 or buy the IPv4 add-on |
| Vercel build and revalidate | Supavisor transaction mode | 6543 | Many short-lived clients. **Prepared statements must be disabled** (`prepare: false` / `?pgbouncer=true`) or connections error |

Source: [connecting to Postgres](https://supabase.com/docs/guides/database/connecting-to-postgres). Connection ceilings bind before anything else: Small allows 90 direct and 400 pooler clients, Large allows 160 and 800 ([compute and disk](https://supabase.com/docs/guides/platform/compute-and-disk)). Cap the build's pool at ~10 and prefer the single bulk fetch from §4.

### RLS posture

RLS is enabled on every table in `public`. What is public and what is not:

| Access | Tables |
|---|---|
| **Public read** (`SELECT` policy for `anon`) | `categories`, `subreddits`, `category_subreddits`, `brands`, `threads`, `brand_category_scores`, `leaderboards`, `brand_pages`, and `mentions` filtered to rows whose brand is published |
| **Service-role only** (no `anon` policy at all) | `brand_aliases`, `ingest_state`, `removals`, plus `mentions.run_id` and `mentions.match_conf`, exposed only through a view that omits them |

**Preferred posture: the site does not ship the anon key at all.** Build and revalidate read through a dedicated `site_reader` Postgres role holding `SELECT` on the published views only. RLS then works as defence in depth rather than as the sole control, and the browser bundle carries no database credential of any kind.

### The free tier, and exactly where it bites

| Free limit | Value | Where it bites |
|---|---|---|
| Database size | 500 MB | Phase 1 `mentions` alone is ~1 GB. Bites on the first production load |
| File storage | 1 GB | The corpus is 60-150 GB. Bites at 60× |
| Egress | 5 GB | One weekly delta scan is 10-30 GB. Bites in week one |
| Project pausing | Paused after 1 week of inactivity | A paused project fails the nightly delete-sync silently |
| Active projects | 2 | Never binds |

Source: [Supabase pricing](https://supabase.com/pricing). **Upgrade to Pro ($25/month) before the first production ingest.** Free is good for a schema spike and nothing beyond it.

### Pro allowances and the one overage that matters

Pro includes 8 GB disk (then $0.125/GB), 100 GB file storage (then $0.0213/GB), 250 GB egress (then $0.09/GB), and a $10/month compute credit covering one Micro instance.

⚠️ **Egress is the real cost of consolidating onto one vendor.** Weekly delta scans of 10-30 GB stay comfortably inside 250 GB. A full-corpus re-scan is 150 GB, so two in one month lands ~50 GB over, at $0.09/GB. Keep the working set on the worker's local NVMe; Supabase Storage is the durable copy.

One setup step that is easy to miss: Storage's global file-size limit defaults to 50 MB and is configurable up to 500 GB on Pro ([file limits](https://supabase.com/docs/guides/storage/uploads/file-limits)). Parquet shards run 100-500 MB, so raise it before the first S1 write.

## 6. Deployment

Push to `main` is production. A pull request gets a preview deployment on its own URL. That is the whole flow, and it is the flow because it needs no operator.

⚠️ **The Vercel ↔ GitHub link is gated on an OAuth grant that no API can perform.** The Vercel GitHub App must be installed on the `Empact-Partners` organization by an org owner, in a browser. Verified 2026-08-04: `GET /orgs/Empact-Partners/installations` returns `{"total_count": 0, "installations": []}`. Nothing is installed today.

There are two independent blockers here, and fixing one does not fix the other. Hobby teams cannot connect to org-owned repositories at all ([Vercel limits](https://vercel.com/docs/limits)), so **Pro is a prerequisite for the Git link itself**, quite apart from the non-commercial licence term in §Bottom line.

**Step 1 — install the App.** Open `https://github.com/apps/vercel/installations/new`, select the `Empact-Partners` organization, and grant access to `reddit-index` specifically rather than "All repositories."

**Step 2 — link the project.**

```bash
curl -X POST "https://api.vercel.com/v9/projects/reddit-index/link?teamId=$VERCEL_TEAM_ID" \
  -H "Authorization: Bearer $VERCEL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"type":"github","repo":"Empact-Partners/reddit-index"}'
```

Endpoint live-verified in this estate on the MarketSplash project; it is not in Vercel's public REST reference. The documented alternative is `POST /v11/projects` with a `gitRepository` object at create time, which carries the same App prerequisite.

**`repo_not_found` on create or link means the App is not installed on the org.** It is not a typo in the repo name and not a missing token scope. Check the installation first, every time.

Two rules for previews. Give preview deployments the read-only `site_reader` connection string and no service-role key, so a branch can never write to production. And keep GitHub Actions off the site build entirely — Vercel owns that; Actions runs lint, typecheck and schema-diff on pull requests, and nothing heavier.

The pipeline never runs on Actions either. The 6-hour job cap kills a TB-scale scan ([Actions limits](https://docs.github.com/en/actions/reference/limits)), which is why the worker is long-lived in the first place.

## 7. Environment variables

Never commit a value. Vercel env vars are set per environment (Production, Preview, Development); worker vars live in Railway.

**Browser-exposed** (`NEXT_PUBLIC_*`, shipped in the client bundle):

| Name | Purpose |
|---|---|
| `NEXT_PUBLIC_SITE_URL` | Canonical origin for canonicals, OG tags and the sitemap |
| `NEXT_PUBLIC_SUPABASE_URL` | Project URL. Public by design, and only needed if a client component ever queries Supabase directly |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Publishable key. **The current design does not need it** — see the preferred RLS posture in §5. Do not add it speculatively |

**Vercel, server-only** (no `NEXT_PUBLIC_` prefix, never reaches the browser):

| Name | Purpose |
|---|---|
| `DATABASE_URL_READONLY` | Supavisor transaction-mode URL (port 6543) for the `site_reader` role, used at build and revalidate time |
| `REVALIDATE_SECRET` | Bearer token the pipeline presents to `POST /api/revalidate` |

**Worker-only** (Railway, never set on Vercel):

| Name | Purpose |
|---|---|
| `SUPABASE_DB_URL` | Direct connection on port 5432 for `COPY` and the S6 rollups |
| `SUPABASE_SERVICE_ROLE_KEY` | Bypasses RLS for the pipeline's writes and for `removals` |
| `SUPABASE_S3_ENDPOINT`, `SUPABASE_S3_REGION` | `https://{project_ref}.storage.supabase.co/storage/v1/s3` and the project region |
| `SUPABASE_S3_ACCESS_KEY_ID`, `SUPABASE_S3_SECRET_ACCESS_KEY` | DuckDB `httpfs` credentials. These bypass RLS across all buckets — server-side only |
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` | App-only OAuth for Lane B and delete-sync |
| `SENTIMENT_API_KEY` | Stage-2 LLM tail ([06-sentiment.md](06-sentiment.md)) |
| `REVALIDATE_SECRET` | Same value as the Vercel side; the worker is the caller |
| `VERCEL_DEPLOY_HOOK_URL` | Full-rebuild trigger, used only for code and schema changes |

## 8. What runs when

The weekly cycle from [13-algorithm.md](13-algorithm.md) §7, mapped onto this infrastructure.

| Cadence | Step | Where | Notes |
|---|---|---|---|
| Adaptive, 1-24 h per subreddit | 2. `poll_comment_streams` | Worker | The bulk of API calls. Watermark per sub in `ingest_state`; writes land in Supabase Storage |
| Daily | 3. `poll_new` · 4. `qualify_threads` · 5. `fetch_trees` | Worker | Trees only for threads that earned one |
| Weekly | 1. `refresh_subreddit_meta` | Worker → Postgres | Rule-hash drift updates `subreddits.rule_posture` |
| Weekly | 6. `boosters` | Worker | Scoped search, both sorts, plus the recurring-thread registry |
| Weekly | 8. `detect_mentions` · 9. `resolve_entities` · 10. `classify_sentiment` | Worker + DuckDB; LLM tail via Batch API | Parquet in, Parquet out. Delta shards only |
| Weekly | S5 load | Worker → Postgres, direct 5432 | `COPY` then `ON CONFLICT DO NOTHING`; `UNIQUE(brand_id, doc_id)` makes a re-run safe |
| Weekly | 11. `compute_index` | Postgres SQL | Full recompute of the affected week partitions into `brand_category_scores`, `leaderboards`, `brand_pages` |
| Weekly | 12. `publish` | Worker → `POST /api/revalidate` | `revalidateTag` per changed brand and category. Seconds, not a rebuild |
| Monthly | 7. `reconcile_archive` | Worker | New dump shards fill `more` gaps; dump rows are authoritative and upsert over API rows |
| Nightly | 13. `delete_sync` | Worker | `/api/info` over stored `doc_id`s → purge `mentions` and children → write `removals` → `revalidateTag` per affected brand |
| On merge to `main` | Site build | Vercel | Code, schema and methodology-version changes only |

Every stage writes its artifact before it writes its ledger row, keyed `(stage, subreddit, ym, code_version)`. On start a stage lists existing keys and skips them, so a job that dies at hour 9 resumes at hour 9 and the worst case is one lost sub-month shard.

⚠️ **Purging Postgres is half the job.** A cached page keeps serving a removed comment until its tag is invalidated, so `delete_sync` owns the revalidate call, and `removals.revalidated_at` is the receipt that it happened. A row with `purged_at` set and `revalidated_at` null is an open defect.

## 9. Cost

| Line item | Phase 1 (~50 categories, ~500 brands, ~200 subs, ~1k pages) | Full scale (~5k brands, 1k subs, ~5k pages) |
|---|---|---|
| Vercel Pro seat | **$20** | **$20** |
| Vercel usage: build CPU minutes, ISR reads and writes, Fast Data Transfer | **~$1** | **~$2** |
| Supabase Pro | **$25** | **$25** |
| Supabase compute | Small → **$15** | Large → **$110** |
| Supabase compute credit included in Pro | **−$10** | **−$10** |
| Supabase disk (8 GB included, then $0.125/GB) | within allowance → **$0** | ~100 GB → **$11.50** |
| Supabase Storage (100 GB included, then $0.0213/GB) | ~60 GB → **$0** | ~150 GB → **$1** |
| Supabase egress (250 GB included, then $0.09/GB) | ~40-120 GB → **$0** | ~120-200 GB → **$0** |
| Worker on Railway Pro ($20 incl. $20 credits; $0.0278/vCPU-hr + $0.0139/GB-hr) | 4 vCPU / 8 GB, ~26 h/mo = $6 usage → **$20** | 16 vCPU / 64 GB, ~90 h/mo = $120 usage → **$120** |
| Stage-2 LLM tail, nano-class at $15 per 1M mentions | ~150K/mo → **$2** | ~1.4M/mo → **$21** |
| Domain registration, amortised | **$1** | **$1** |
| **Total** | 20 + 1 + 25 + 15 − 10 + 0 + 0 + 0 + 20 + 2 + 1 = **≈ $74/mo** | 20 + 2 + 25 + 110 − 10 + 11.50 + 1 + 0 + 120 + 21 + 1 = **≈ $301/mo** |

Prices from [Vercel pricing](https://vercel.com/pricing), [Vercel limits](https://vercel.com/docs/limits), [Supabase pricing](https://supabase.com/pricing), [Supabase compute and disk](https://supabase.com/docs/guides/platform/compute-and-disk) and [Railway pricing](https://railway.com/pricing), all fetched 2026-08-04.


Four caveats on the table:

**The Stage-2 line is the largest discretionary swing.** It assumes the nano-class cascade at the top of its $8-15 per 1M band. Haiku batch instead moves it to $45-85 per 1M, so $7-13/mo at Phase 1 and $63-119/mo at full scale ([06-sentiment.md](06-sentiment.md)).

**Worker sizing is list-price arithmetic, not a benchmark.** A Hetzner dedicated box with a 2 TB NVMe is the cheaper alternative once the corpus is cached locally, and it removes the egress exposure in §5 almost entirely — *Hetzner pricing NOT VERIFIED, check before committing*.

**The Vercel usage line is inference.** 5,000 ISR writes a week is 20K/mo at $0.004 per 1K = $0.08. A million page views is a million reads at $0.0004 per 1K = $0.40. A 4-minute build on a 4-CPU machine is 16 CPU-minutes at $0.0035 = $0.06 per deploy.

**Egress is the line to watch, not storage.** Storage at full scale is $1. A month with two full-corpus re-scans is the only realistic way this table moves by more than ten dollars without a scope change.

---

[← Back to README](README.md) · [13-algorithm.md](13-algorithm.md) · [07-index-methodology.md](07-index-methodology.md)
