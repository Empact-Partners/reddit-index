# Data Acquisition

## Bottom line

- 🔴 **The official Reddit API cannot reach history.** Every listing hard-caps at ~1,000 items. Measured live 2026-08-04: `/r/SaaS/new?limit=100` exhausted at **995 items across 10 pages**, then `after=None`. Scoped search capped at **250**.
- 🔴 **That reaches days, not years.** r/SaaS's posting rate was measured twice on 2026-08-04 by two methods (**122/day** and **~350/day**), which puts 995 reachable posts at **roughly 3 to 8 days of history**. Both ends kill the API as a backfill route.
- 🔴 **Reddit search indexes posts, not comment bodies.** The search `type` enum is `link`/`sr`/`user` only. Per-brand Reddit search is a discovery and QA tool, never a census.
- 🟢 **External search engines *can* reach comment text**, because they crawl the rendered thread pages. That is Lane C in [13-algorithm.md](13-algorithm.md) §3 — a targeted probe with unknown coverage, never a census either.
- 🟢 **Architectural verdict: ingest whole subreddits, then match brands locally.** Every other design fails one of the constraints above.
- 🟡 **Backfill comes from the Arctic Shift / Academic Torrents monthly dumps** (zst-compressed ndjson, 2005-06 through 2026-06, still shipping).
- 🟢 **Volume is one machine, not a cluster.** A ~1,000-subreddit software corpus is roughly **200-400M items ≈ 0.5-1.5 TB raw JSON**, which is **50-150 GB** once stored as zstd-compressed Parquet on the fields we keep.
- 🟢 **Ingest is continuous; scoring and publishing run once a day.** Steady state is **~180 API calls per category per day**, ~9,000/day across 50 categories, under 2 hours of wall clock — about 8% of one app-only client's daily ceiling.
- 🟢 **Multireddit bucketing verified to 40 subreddits in a single call.** `/r/a+b+c/comments` merges quiet subs into one page and removes their per-call overhead.
- 🟡 **Request volume is not the constraint; entitlement is.** At the commercial rate 9,000 calls/day is **~$65/mo**; a 1,000-sub corpus at 11-20K calls/day is **$79-144/mo**. Which tier we may occupy is unresolved and not settled in this document.

---

## 1. Constraint one: the listing cap

Reddit's own client library states it plainly: "Most of Reddit's listings contain a maximum of 1000 items, and are returned 100 at a time" ([PRAW docs](https://praw.readthedocs.io/en/stable/code_overview/other/listinggenerator.html)). A Reddit admin confirmed the same in [r/redditdev](https://www.reddit.com/r/redditdev/comments/30a7ap/does_reddit_api_limit_total_listings_returned_to/).

We measured it rather than trusting it. Walking the `after` cursor to exhaustion on our own OAuth client, 2026-08-04:

| Endpoint | Pages | Items returned | Terminal state |
|---|---|---|---|
| `/r/SaaS/new?limit=100` | 10 | **995** | `after=None` |
| `/r/SaaS/search?q=pricing&restrict_sr=1&sort=new&t=all` | 3 | **250** | `after=None` |

The cap applies to every listing type: `new`, `top`, `hot`, and `search`.

How much history 995 posts buys depends on the subreddit's posting rate, and r/SaaS was measured twice on 2026-08-04 by two different methods:

| Method | r/SaaS posts/day | 995 posts covers |
|---|---|---|
| Span of the last 100 posts in `/new` | **122** | ~8 days |
| Extrapolation from the 10 newest posts in `/new` ([subreddit mapping](04-subreddit-mapping.md)) | **~350** | ~3 days |

The second figure runs high because the newest posts have not yet been through moderation removal, so part of what it counts will not survive. Quote reachable history as **roughly 3 to 8 days**, never "8 days" as a measured fact.

The verdict is identical at either end of that range: the API is a maintenance tool, not an acquisition tool. Nothing downstream depends on which measurement is right.

## 2. Constraint two: search does not see comments

The Reddit search endpoint indexes submissions. There is no comment type in the `type` enum, so a query for "Bitwarden" returns threads whose titles or bodies match, not the thousands of comments where the actual opinion sits.

Search is also relevance-ranked and stem-matching, not exhaustive. Live test: "Descript" in r/VideoEditing returned 15 results of which roughly 8 matched the word "description" ([subreddit mapping research](04-subreddit-mapping.md)).

The gap has one partial escape. External search engines index the rendered thread pages, so they *can* match on comment text — verified 2026-08-04 via Brave, `site:reddit.com "switched from hubspot to"`, returning real comment bodies. See §7 and [13-algorithm.md](13-algorithm.md) §3 Lane C.

## 3. Architectural verdict

⚠️ **Ingest whole subreddits, then match brands locally.** Pull each mapped subreddit's full post timeline plus its comment trees into our own store, and run brand matching against that store. Never build a ranking from per-brand API search results.

Per-brand search keeps two legitimate jobs: seeding the brand list during category research, and spot-checking that local matching did not miss an obvious thread. Both are QA, neither is a census.

## 4. Backfill route: Arctic Shift monthly dumps

[Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift) is the live successor to Pushshift, whose public access was revoked in May 2023. It publishes monthly zst-compressed ndjson dumps indexed in [download_links.md](https://github.com/ArthurHeitmann/arctic_shift/blob/master/download_links.md), covering 2005-06 through 2026-06 and still shipping.

Verified by direct fetch 2026-08-04: the [2026-06 torrent](https://academictorrents.com/details/3bac8bd352bbb74bbb23df4273cf3da5d66ee5a5) is **70.38 GB** (`RC_2026-06.zst` 48.18 GB plus `RS_2026-06.zst` 22.20 GB); [2026-01](https://academictorrents.com/details/8412b89151101d88c915334c45d9c223169a1a60) is 61.63 GB.

**Per-subreddit split torrents exist** for the top-40k subreddits. That is how we take 1,000 subs without pulling multiple TB of whole-Reddit monthlies.

Arctic Shift's own API docs ask us not to bulk-pull: "If you want to process massive amounts of data, use the monthly dumps instead." Its `/api/time_series` endpoint gives exact per-subreddit counts and is the right tool for sizing, not harvesting.

⚠️ The torrent metadata carries `terms= {}, license= {}`, and anything ingested inherits a deletion duty: [Developer Terms §3.3](https://www.redditinc.com/policies/developer-terms) requires deleting or modifying content "as soon as possible" once it is deleted, removed, or edited upstream, and the [Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki) "strongly recommend[s] routinely deleting any stored user data and content within 48 hours."

Neither is a 24-hour contractual figure, and no fixed interval should be quoted as one. We implement a nightly delete-sync job ([08-architecture.md](08-architecture.md)).

## 5. Measured corpus volume

Method: `GET https://arctic-shift.photon-reddit.com/api/time_series?key=r/{sub}/{posts|comments}/count&precision=year`, summed over all years, run 2026-08-04.

| Subreddit | Posts (lifetime) | Comments (lifetime) | Total items | Comments : posts |
|---|---|---|---|---|
| r/sysadmin | 332,119 | 7,113,871 | 7.45M | 21× |
| r/Entrepreneur | 592,802 | 3,539,863 | 4.13M | 6× |
| r/webdev | 364,062 | 2,775,112 | 3.14M | 8× |
| r/ExperiencedDevs | 38,558 | 1,284,308 | 1.32M | 33× |
| r/SaaS | 146,083 | 935,932 | 1.08M | 6× |
| r/devops | 69,630 | 700,113 | 0.77M | 10× |
| r/kubernetes | 47,469 | 307,667 | 0.36M | 6× |

Global reference from the same API: all of Reddit is **3.33B posts + 24.09B comments = 27.4B items**.

**INFERENCE (power-law decay, not measured):** a ~1,000-subreddit software corpus lands around **240M items**, and a 500-sub Phase 1 corpus around 100-200M. That is under 1.5% of Reddit, which is consistent with these being niche B2B communities.

Storage, derived from the dumps at ~221 bytes/item compressed and ~2.0-2.5 KB/item raw: **240M items ≈ 53 GB zst, ~550 GB raw ndjson, 60-120 GB Parquet+zstd** on the fields we keep. This fits one 2 TB NVMe. It is one machine, not a cluster.

The genuinely expensive layer is embeddings if we ever add them: 240M items at 384-dim fp16 is roughly **185 GB of vectors** before any index, and chunking multiplies that 2-3×. Out of scope for Phase 1.

## 6. Incremental updates — continuous ingest, daily publish

Two rhythms, deliberately separated ([13-algorithm.md](13-algorithm.md) §7). **Ingestion is continuous**, each multireddit bucket polled on its own 1-24h cadence, because the comment stream and the 1,000-item cap force it. **Scoring and publishing run once a day**, ~03:00 UTC, so the site is never more than 24 hours stale.

Daily publishing is nearly free because stages 5-8 of the pipeline process only the **delta** — comments arriving since the last run. Total classified volume per month is unchanged; only the number of publish events rises.

Serving does not rebuild ~5,000 pages every day. The daily job calls `revalidateTag` for only the brands and categories whose scores actually moved, typically tens of pages. Full rebuilds stay reserved for code and schema changes ([08-architecture.md](08-architecture.md)).

Steady state, per category, per day, across 8 scoring subreddits:

| Stage | Calls/day | Basis |
|---|---:|---|
| Comment streams (Lane B) | ~90 | rate-bucketed multireddits; quiet subs share a bucket |
| `/new` polling | ~16 | 2 pages × 8 subs |
| Subreddit meta | ~16 | 2 × 8 subs, rule-drift detection |
| Comment trees | ~45 | qualifying threads only |
| Boosters (Lanes C + D) | ~10 | external probes + scoped Reddit search, rotated |
| **Total** | **~180/day** | ≈ 1,250/week |

**50 categories ≈ 9,000 calls/day**, under 2 hours of wall clock, interruptible at any point.

Rate limit is **100 queries per minute per OAuth client id**, averaged over a ten-minute window, per the [Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki). Run at ≤80 QPM, which is ~115,000 calls/day. 9,000/day is about **8% of one app-only client's budget**. The limit is per client_id, not per user, so extra accounts do not multiply it.

⚠️ Ingest is per-subreddit, not per-category. **Dedupe the ingest set before scheduling** or the overlap is paid twice: 187 candidate slots across the 20 tested categories collapse to 132 unique subreddits, and r/Entrepreneur alone serves 7 of them ([14-category-tests.md](14-category-tests.md) §7).

At the commercial rate of **$0.24 per 1,000 calls** ([TechTarget](https://www.techtarget.com/whatis/feature/Reddit-pricing-API-charge-explained)), 9,000/day is ~270K/month ≈ **$65/mo**. A larger 1,000-sub corpus at 11-20K calls/day is **$79-144/mo**. Do not plan against the $0 line; tier entitlement is unresolved.

### Multireddit bucketing

The comment stream accepts a `+`-joined subreddit list and returns one merged feed. **Verified live 2026-08-04, scaling to at least 40 subreddits in a single call:**

| Subs in one call | URL length | Comments returned | Distinct subs seen | Span of the page |
|---:|---:|---:|---:|---:|
| 8 | 64 chars | 100 | 7 | 64.8 min |
| 15 | 131 chars | 100 | 14 | 18.3 min |
| 25 | 211 chars | 100 | 17 | 16.7 min |
| 40 | 360 chars | 100 | 23 | 7.5 min |

The merged rate is the **sum** of the member rates, so merging does **not** reduce the number of comments you must retrieve. What it removes is per-call overhead on quiet subreddits: eight sleepy subs polled separately burn eight calls to collect a handful of comments each, while merged they fill one page.

⚠️ So the rule is **bucket by rate, not by category.** Quiet subs are packed together until a bucket fills roughly one page per interval; loud subs stay solo on their own cadence. Never exceed ~40 members or ~400 URL characters per bucket, and split any bucket whose page stops covering its interval.

Bucket sizing needs a measured comments/hour figure per subreddit. [14-category-tests.md](14-category-tests.md) carries those rates for 132 subreddits ([data/subreddit-measurements.csv](data/subreddit-measurements.csv)) — they span three orders of magnitude, from 0.5h to 3.3 years per 100-comment page, which is exactly why a fixed cadence fails.

### Monthly reconciliation

Add a monthly Arctic Shift dump pull as a reconciliation pass. It fills `more`-branch gaps, catches deletions the live crawl missed, and repairs any window a poll under-covered. Note the **36-hour settling window** before dump data matches the API.

## 7. Acquisition routes compared

This table compares **coverage, cost and effort**. It does not rate compliance: every legality verdict for every route belongs to [01-legal.md](01-legal.md), and this document defers to it without exception.

| Route | Coverage | Legality | Cost | Effort |
|---|---|---|---|---|
| Official API, free tier | Last ~1,000 items per listing; days, not years. First-party and attributable | Not rated here | $0 list price | Low |
| Official API, commercial | Same cap, no history. Buys a rate, not a licence | Not rated here | $65/mo at 9K calls/day; $79-144/mo at 11-20K | Low |
| **Arctic Shift dumps (per-sub torrents)** | **Complete, 2005 → 2026-06.** Settles history, and only history | Not rated here | Bandwidth only | Medium |
| Arctic Shift API | Complete but rate-limited, times out on big subs; docs ask you not to bulk-pull | Not rated here | $0 | Low, not scalable |
| **External search index (Lane C)** | **Comment-level text no Reddit endpoint can search.** Coverage is whatever the engine indexed: **unknown, unstable, unauditable.** Opportunistic probe only — never a census, never a denominator | Not rated here | Metered per query; ~10 probes/category/day | Low |
| [Bright Data datasets](https://brightdata.com/products/datasets/reddit) | Broad, refreshable monthly. Changes the counterparty, not the underlying data | Not rated here | $250 min order, up to $0.0025/record → **~$750K at 300M** | Very low |
| [Apify actors](https://apify.com/automation-lab/reddit-scraper) | Whatever you crawl, no deep history | Not rated here | $0.58-3.40 per 1K | Low-medium |
| Licensed Reddit agreement | Full firehose plus history | Not rated here | Google ~$60M/yr, OpenAI ~$70M/yr class ([CNBC](https://www.cnbc.com/2026/07/22/reddit-stock-google-ai-content-deal.html)) | Enterprise negotiation |

**Chosen shape:** Arctic Shift per-subreddit dumps for backfill, the official API on multireddit buckets for continuous increments, the external index as a targeted booster, a commercial vendor only for gap-fills.

⚠️ Lane C output is a **thread URL, not a stored comment.** The snippet is a lead only; the comment is always re-fetched from Reddit's API so stored text and permalinks come from the authoritative source ([13-algorithm.md](13-algorithm.md) §3).

## 8. Working around the 1,000-item cap

Where the API must be used for history (a subreddit missing from the split torrents, or a gap between the last dump and today), slice the query by time window instead of paging deeper.

Issue the same scoped search repeatedly with a moving `t=` filter so each window returns well under 1,000 items. Every window is an independent listing with its own cap.

⚠️ The API exposes **six presets only** (`hour`/`day`/`week`/`month`/`year`/`all`). Arbitrary timestamp bounds are not available on this endpoint, so anything finer than an hour has to be reached by narrowing the query text instead, which is why slicing multiplies request count so fast.

⚠️ This multiplies request count and **never guarantees completeness**. Any window that returns exactly its cap must be split further and re-run before the range is marked complete. Treat slicing as gap-fill, not as a backfill strategy.

## 9. Idempotency and resumability

The ingestion job runs for days and will be interrupted. Design for that from the first commit, not after the first crash.

| Requirement | Rule |
|---|---|
| Disk first | Write each fetched batch to disk before any parsing or matching. Never hold a run's output only in memory. |
| Skip if done | Before fetching a `(subreddit, time-window)` unit, check for its completed artifact on disk and skip it. |
| Unit granularity | One artifact per subreddit per month. Small enough to redo cheaply, large enough to avoid millions of files. |
| Natural keys | Upsert on Reddit's own `t3_`/`t1_` fullnames. Re-ingesting the same dump twice must produce an identical store. |
| Completion marker | A unit is complete only when a sentinel file is written after the final byte. A partial file without a sentinel is discarded and re-fetched. |
| Watermarks | One `before` fullname per multireddit bucket. A poll that returns a full page without reaching it means the cadence was too slow: halve the interval and flag the window. |
| Mutable fields | Score, edit state, and deletion status change after capture. Store `captured_at` per record and let the refresh pass overwrite them. |
| Deletion propagation | The refresh pass must record when a post or comment has been removed upstream. |

Resumability is what makes the backfill affordable: a crash on day four costs the current month-unit, not the run.

## Open questions

| Item | Status |
|---|---|
| Which r/SaaS posting-rate method is right (122/day vs ~350/day) | Unreconciled. Both stated above; history quoted as a range. Settle it by counting surviving posts across a fixed 7-day window |
| Whether an Empact-operated site may use the free API tier at all | Open, and not this document's call |
| Lane C coverage — what share of qualifying comments any external index actually holds | **NOT VERIFIED**, and probably unmeasurable. This is why Lane C is capped at opportunistic use |
| External search API pricing at Lane C probe volume | **NOT VERIFIED** — verified functionally 2026-08-04, never priced at scale |
| Steady-state calls/day at full taxonomy scale after dedupe | Modelled from the 20-category study, not measured end to end |
| Whether Reddit self-serve API registration closed in late 2025 | **NOT VERIFIED** — secondary source only |
| Oxylabs pricing | **NOT VERIFIED** — pricing page returned 404 |
| Socialgist availability | **NOT VERIFIED** — site returned 404 |
| PullPush.io post-2023 coverage completeness | **NOT VERIFIED** — community claim, untested |
| Exact per-subreddit item counts beyond the ten measured above | Not measured; use `/api/time_series` before committing storage |

---

[← Back to README](README.md) · [The algorithm](13-algorithm.md) · [Category tests](14-category-tests.md) · [Subreddit mapping](04-subreddit-mapping.md) · [Architecture](08-architecture.md) · [data/subreddit-map.csv](data/subreddit-map.csv)
