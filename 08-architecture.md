# Technical Architecture

## Bottom line

- 🟢 **The raw corpus does not go in Postgres.** Reddit posts and comments live as Hive-partitioned Parquet on Cloudflare R2 at $0.015/GB-month with zero egress fees ([R2 pricing](https://developers.cloudflare.com/r2/pricing/)), queried in-process by DuckDB 1.5.5, released 2026-07-22 ([DuckDB news](https://duckdb.org/news/)).
- 🟢 **Supabase Postgres holds only derived rows** — mentions and aggregates. That keeps it under 200M rows at full scale, which a $110/mo Large instance serves comfortably ([Supabase compute & disk](https://supabase.com/docs/guides/platform/compute-and-disk)).
- 🟢 **Serving is fully static Astro, not ISR.** Roughly 5,000 pages on a weekly refresh is a build-once problem. Static output costs $0 in ISR reads and writes ([Vercel limits](https://vercel.com/docs/limits)).
- 🟡 **Ingestion runs on one long-lived worker, never GitHub Actions.** The 6-hour job cap kills a TB-scale decompress ([Actions limits](https://docs.github.com/en/actions/reference/limits)). Actions is fine for the site build only.
- 🟢 **Cost is roughly $85/month for the Phase 1 MVP and roughly $330/month at full scale.** Line items at the end.
- 🔴 **A nightly delete-sync job is not optional.** Developer Terms §3.3 requires deleting removed content "as soon as possible" ([Developer Terms](https://www.redditinc.com/policies/developer-terms)). See [01-legal.md](01-legal.md).

---

## 1. Flow

```
SOURCES                      COMPUTE (one worker)               STORES               SERVE
──────────────────────────────────────────────────────────────────────────────────────────
Arctic Shift / Academic ─┐
Torrents .zst dumps      │   S0 acquire ──► S1 normalize ────► R2 /raw/{sub}/{ym}.zst
(backfill, monthly)      ├──►                                  R2 /parquet/sub=/ym=/
                         │        │
Reddit Data API         ─┘        ▼
(app-only OAuth, weekly)     S2 Aho-Corasick candidates ─────► R2 candidates.parquet
                                  ▼
                             S3 disambiguation ──────────────► R2 resolved.parquet
                                  ▼
                             S4 sentiment (ONNX, CPU) ───────► R2 scored.parquet
                                  ▼
                             S5 COPY ───────────────────────► Supabase Postgres
                                  ▼                            mention (partitioned)
                             S6 aggregate (SQL) ─────────────► brand_week, category_week,
                                                               brand_page (jsonb)
                                  ▼
                             S7 export JSON snapshot ────────► GitHub Actions
                                                                    ▼
                                                               Astro static build
                                                                    ▼
                                                               CDN → ugcranks.com

delete-sync (nightly): Postgres doc_ids ─► Reddit /api/info ─► purge missing ─► flag rebuild
```

## 2. Storage breakpoints

Pick the tier by row count and by whether a human needs sub-second ad-hoc queries. UGC Ranks does not — it needs a weekly batch pass and a fast single-row read at build time.

| Scale | Raw corpus | Derived rows | 2026 price |
|---|---|---|---|
| To ~100M rows / ~200GB | Postgres is fine | Postgres | $25/mo Pro + compute ([Supabase pricing](https://supabase.com/pricing)) |
| 100M–1B rows | **Parquet on R2 + DuckDB** ✅ our target | Postgres | $0.015/GB-mo, $0 egress ([R2](https://developers.cloudflare.com/r2/pricing/)) |
| >1B rows, interactive human analytics | ClickHouse Cloud | ClickHouse | $0.2985/compute-unit-hr Scale + $25.30/TB-mo ≈ $218/mo per always-on unit ([ClickHouse](https://clickhouse.com/pricing)) |
| >1B rows, weekly batch only | BigQuery | Postgres | $6.25/TiB scanned, 1 TiB/mo free ([BigQuery](https://cloud.google.com/bigquery/pricing)) |

⚠️ For weekly batch, **BigQuery beats ClickHouse because idle costs nothing**. A 500GB weekly full scan is about $6.25/month. ClickHouse is justified by interactive querying, never by row count alone.

Supabase can technically hold the raw corpus, but a 2TB database wants a 4XL instance at $1.32/hr, roughly $960/month ([compute & disk](https://supabase.com/docs/guides/platform/compute-and-disk)). Needing that instance is the signal that raw data landed in the wrong store.

## 3. Schema sketch

Two stores, one boundary. Parquet is append-only and immutable per shard. Postgres is the only mutable store, and everything in it is derived.

**Parquet on R2** — Hive-partitioned `sub={name}/ym={YYYY-MM}/`:

| Dataset | Key columns | Notes |
|---|---|---|
| `posts` | `id`, `subreddit`, `author`, `created_utc`, `title`, `selftext`, `permalink`, `score` | From dumps; API rows upserted then corrected by the next dump |
| `comments` | `id`, `link_id`, `parent_id`, `subreddit`, `author`, `created_utc`, `body`, `permalink`, `score` | The bulk of the corpus, roughly 10:1 vs posts ([02-data-acquisition.md](02-data-acquisition.md)) |
| `candidates` | `doc_id`, `doc_type`, `alias_hit`, `char_offset` | S2 output, one row per raw string hit |
| `resolved` | `doc_id`, `brand_id`, `match_conf`, `rule_fired` | S3 output after disambiguation |
| `scored` | `doc_id`, `brand_id`, `sentiment`, `sentiment_conf` | S4 output, loaded to Postgres |

**Supabase Postgres** — derived only:

| Table | Key columns | Index / constraint |
|---|---|---|
| `category` | `id`, `slug`, `name`, `parent_id` | `UNIQUE(slug)` |
| `brand` | `id`, `slug`, `name`, `category_id`, `aliases text[]`, `stop_contexts text[]`, `require_context bool` | `UNIQUE(slug)`, GIN on `aliases` |
| `brand_alias` | `brand_id`, `alias`, `alias_type`, `is_ambiguous bool` | `UNIQUE(alias, brand_id)`; feeds the Aho-Corasick automaton |
| `subreddit` | `id`, `name`, `category_id`, `weight numeric` | `UNIQUE(name)` |
| `mention` | `id bigserial`, `brand_id`, `doc_type smallint`, `doc_id text`, `subreddit_id`, `created_utc timestamptz`, `permalink`, `author`, `score int`, `body text`, `match_conf real`, `run_id uuid` | `PARTITION BY RANGE (created_utc)` monthly; `UNIQUE(brand_id, doc_id)`; `(brand_id, created_utc DESC)`; `(subreddit_id, created_utc DESC)` |
| `mention_sentiment` | `mention_id`, `sentiment smallint`, `sentiment_conf real`, `model_version` | `PRIMARY KEY(mention_id, model_version)` |
| `brand_category_scores` | `brand_id`, `category_id`, `week_start date`, `mentions`, `pos`, `neg`, `neu`, `unique_authors`, `subreddit_count`, `index_score numeric` | `PRIMARY KEY(brand_id, category_id, week_start)` |
| `category_leaderboard` | `category_id`, `week_start`, `brand_id`, `rank int`, `share numeric`, `index_score`, `rank_delta int` | `PRIMARY KEY(category_id, week_start, brand_id)` |
| `brand_page` | `brand_id PK`, `payload jsonb`, `updated_at` | The exact render payload |
| `ingest_state` | `subreddit`, `ym`, `stage`, `file_hash`, `rows`, `status`, `finished_at` | `PRIMARY KEY(subreddit, ym, stage)` — the resumability ledger |

`mention.body` is where the priced risk sits. Storing and displaying full comment text breaches Data API Terms §2.4 and §4.1 and adds per-commenter copyright exposure. The owner accepted this knowingly; it is documented in [01-legal.md](01-legal.md), not defended here.

`brand_page.payload` is the reason the build is fast. The static build does 5,000 single-row reads, not 5,000 joins.

## 4. Pipeline: staged, idempotent, resumable

Every stage writes its artifact to R2 first, keyed `(stage, subreddit, ym, code_version)`, then writes a row to `ingest_state`. On start, a stage lists existing keys and skips them.

| Stage | Work | Runs on | Idempotency key | Resume unit |
|---|---|---|---|---|
| S0 acquire | Torrent or API pull to `.zst` | Worker | file hash in `ingest_state` | one sub-month |
| S1 normalize | `zstd -dc` streamed to Parquet | Worker (DuckDB) | output object exists | one sub-month |
| S2 candidates | Aho-Corasick over every body | Worker | output object exists | one sub-month |
| S3 disambiguation | Context window, negative regex, subreddit priors | Worker | output object + `code_version` | one sub-month |
| S4 sentiment | Local ONNX classifier, batched | Worker (CPU) | output object + `model_version` | one shard |
| S5 load | `COPY` then `ON CONFLICT DO NOTHING` | Supabase | `UNIQUE(brand_id, doc_id)` | one shard |
| S6 aggregate | SQL rollups into scores and leaderboards | Supabase | full recompute per week partition | one week |
| S7 export | JSON snapshot for the build | GitHub Actions | content hash | whole snapshot |

⚠️ **A job that dies at hour 9 must not restart from zero.** That is what the `(stage, subreddit, ym)` key buys: the worst case is losing one sub-month shard, and shards are sized to finish in minutes.

S2 is the only pass that touches every row. `pyahocorasick` over roughly 5,000 aliases runs at about 50–200 MB/s/core (*inference, not benchmarked*), so 300GB across 8 cores is single-digit hours. Never decompress to disk — stream `zstd -dc` into the matcher.

S3 is where the real difficulty lives: "Apple" in r/gardening, "Notion" as a common noun. Rules and per-subreddit priors first, escalate only the ambiguous tail. Method detail is in [05-entity-resolution.md](05-entity-resolution.md).

S4 uses a local ONNX classifier on the worker at zero marginal cost, not an LLM per mention. An LLM adjudication lane over the ambiguous minority is optional and must be costed separately — current model pricing is **NOT VERIFIED** here.

## 5. Serving

Fully static Astro output pushed to a CDN. Roughly 5,000 pages builds in an estimated 2–6 minutes (*inference*), well inside Vercel Pro's 45-minute cap.

| Vercel Pro limit | Value | Our headroom |
|---|---|---|
| Build time | 45 min/deployment | 🟢 wide |
| Routes | 2,048/deployment (route **patterns**, not pages) | 🟢 a handful of dynamic patterns |
| Output files | Builds slow past ~100k | 🟢 roughly 5k pages plus assets |
| ISR reads / writes | $0.0004/1k and $0.004/1k | 🟢 $0, static output |

Source: [Vercel limits](https://vercel.com/docs/limits), updated 2026-07-01. ISR only earns its keep if pages are added continuously between refreshes. They are not — the corpus refreshes weekly. Cloudflare Pages is the cheaper target given R2 is already in the stack.

## 6. Weekly refresh

Reddit's listing endpoints cap at roughly 1,000 items, so weekly freshness comes from polling `/new` and `/comments` per subreddit under app-only OAuth ([02-data-acquisition.md](02-data-acquisition.md)). Monthly dumps lag and later correct the same rows.

| Step | Scope | Estimate |
|---|---|---|
| API pull | ~1,000 subs, trailing week | ~11K requests/day at full scale |
| S2–S6 | Delta shards only | 1–3 h worker time, 10–30 GB scanned (*inference*) |
| S7 + static build | Full site | minutes on Actions |
| Marginal cost | — | a few dollars of worker compute |

Dump-derived rows are authoritative and upsert over API rows. Both carry the same `UNIQUE(brand_id, doc_id)` constraint, so re-running a week is safe.

## 7. Delete-sync

Required by Developer Terms §3.3 and §7.3, and by the Public Content Policy bar on displaying content Reddit or a Redditor removed. Full clause text in [01-legal.md](01-legal.md).

| Property | Design |
|---|---|
| Cadence | Nightly. Reddit's Data API Wiki recommends deleting removed content within 48 hours ([Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki)) |
| Detection | Re-fetch stored `doc_id` fullnames via `/api/info`; a missing id, an `author` of `[deleted]`, or a body of `[removed]` marks the row dead |
| Batch size | 100 fullnames per call (*inference from standard Reddit API behavior — NOT VERIFIED against a primary source*) |
| Action | Hard-delete the `mention` row and its `mention_sentiment` child; never soft-delete text |
| Downstream | Mark the brand and category dirty, recompute S6 for affected weeks, flag a rebuild |
| Ordering | Oldest-checked-first, so every row is revisited on a bounded cycle |

⚠️ Purging text is not enough on its own — the static page must be rebuilt, or the deleted comment stays live on the CDN. The delete-sync job owns the rebuild trigger.

## 8. Cost

| Line item | Phase 1 MVP (~50 categories, ~500 brands, ~200 subs, ~1k pages) | Full scale (~5k brands, 1k subs, 5k pages) |
|---|---|---|
| R2 storage | 200 GB → **$3** | 1.5 TB → **$23** |
| R2 operations | **~$1** | **~$3** |
| Worker (Railway, or a Hetzner box — *both secondary-source prices, verify before committing*) | 4 vCPU / 8 GB, ~26 h/mo → **$20** | 16 vCPU / 64 GB, ~90 h/mo → **~$135** |
| Supabase | Pro $25 + Small compute $15 → **$40** | Pro $25 + Large $110 + ~100 GB disk $11.50 → **~$147** |
| Vercel Pro | **$20** | **$20** (static, ISR ~$0) |
| Cloudflare CDN and DNS | **$0** | **$0–5** |
| GitHub Actions | included (3,000 min/mo) | included |
| **Total** | **≈ $84/mo** | **≈ $328/mo** |

Swap-ins: BigQuery instead of DuckDB adds roughly $12–30/mo at these volumes. ClickHouse Cloud Scale adds roughly $220–450/mo and only pays for itself if a human is querying interactively.

---

[← Back to README](README.md) · [02-data-acquisition.md](02-data-acquisition.md) · [01-legal.md](01-legal.md)
