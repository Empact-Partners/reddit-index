# Data Acquisition

## Bottom line

- 🔴 **The official Reddit API cannot reach history.** Every listing hard-caps at ~1,000 items. Measured live 2026-08-04: `/r/SaaS/new?limit=100` exhausted at **995 items across 10 pages**, then `after=None`. Scoped search capped at **250**.
- 🔴 **That reaches days, not years.** r/SaaS's posting rate was measured twice on 2026-08-04 by two methods (**122/day** and **~350/day**), which puts 995 reachable posts at **roughly 3 to 8 days of history**. Both ends kill the API as a backfill route.
- 🔴 **Reddit search indexes posts, not comment bodies.** The search `type` enum is `link`/`sr`/`user` only. Most brand opinion lives in comments, so per-brand search is a discovery and QA tool, never a census.
- 🟢 **Architectural verdict: ingest whole subreddits, then match brands locally.** Every other design fails one of the constraints above.
- 🟡 **Backfill comes from the Arctic Shift / Academic Torrents monthly dumps** (zst-compressed ndjson, 2005-06 through 2026-06, still shipping). Reddit grants no licence for them; the torrents carry empty `terms` and `license` fields.
- 🟢 **Volume is one machine, not a cluster.** A ~1,000-subreddit software corpus is roughly **200-400M items ≈ 0.5-1.5 TB raw JSON**, which is **50-150 GB** once stored as zstd-compressed Parquet on the fields we keep.
- 🟡 **Request volume is not the constraint; entitlement is.** ~11K requests/day covers 1,000 subs, about **8% of what one OAuth client id may issue**. Whether we may use the $0 tier at all is [01-legal.md](01-legal.md)'s question, so budget the commercial rate: **$79-144/mo**.

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

The search endpoint indexes submissions. There is no comment type in the `type` enum, so a query for "Bitwarden" returns threads whose titles or bodies match, not the thousands of comments where the actual opinion sits.

Search is also relevance-ranked and stem-matching, not exhaustive. Live test: "Descript" in r/VideoEditing returned 15 results of which roughly 8 matched the word "description" ([subreddit mapping research](04-subreddit-mapping.md)).

## 3. Architectural verdict

⚠️ **Ingest whole subreddits, then match brands locally.** Pull each mapped subreddit's full post timeline plus its comment trees into our own store, and run brand matching against that store. Never build a ranking from per-brand API search results.

Per-brand search keeps two legitimate jobs: seeding the brand list during category research, and spot-checking that local matching did not miss an obvious thread. Both are QA, neither is a census.

## 4. Backfill route: Arctic Shift monthly dumps

[Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift) is the live successor to Pushshift, whose public access was revoked in May 2023. It publishes monthly zst-compressed ndjson dumps indexed in [download_links.md](https://github.com/ArthurHeitmann/arctic_shift/blob/master/download_links.md), covering 2005-06 through 2026-06 and still shipping.

Verified by direct fetch 2026-08-04: the [2026-06 torrent](https://academictorrents.com/details/3bac8bd352bbb74bbb23df4273cf3da5d66ee5a5) is **70.38 GB** (`RC_2026-06.zst` 48.18 GB plus `RS_2026-06.zst` 22.20 GB); [2026-01](https://academictorrents.com/details/8412b89151101d88c915334c45d9c223169a1a60) is 61.63 GB.

**Per-subreddit split torrents exist** for the top-40k subreddits. That is how we take 1,000 subs without pulling multiple TB of whole-Reddit monthlies.

Arctic Shift's own API docs ask us not to bulk-pull: "If you want to process massive amounts of data, use the monthly dumps instead." Its `/api/time_series` endpoint gives exact per-subreddit counts and is the right tool for sizing, not harvesting.

⚠️ **Reddit grants no licence for these dumps.** The torrent metadata literally reads `terms= {}, license= {}`.

Anything ingested from a dump inherits a deletion duty. [Developer Terms §3.3](https://www.redditinc.com/policies/developer-terms) requires deleting or modifying content "as soon as possible" once it is deleted, removed, or edited upstream. Separately, the [Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki) "strongly recommend[s] routinely deleting any stored user data and content within 48 hours."

Neither is a 24-hour contractual figure, and no fixed interval should be quoted as one. The contract says "as soon as possible"; we implement a nightly delete-sync job ([08-architecture.md](08-architecture.md)).

Reddit sued Perplexity, SerpApi, Oxylabs, and AWMProxy on 2025-10-22 over "industrial-scale scraping" ([Search Engine Land](https://searchengineland.com/reddit-sues-perplexity-serpapi-scraping-google-463681)).

UGC Ranks displays full comment text with links back to the source thread. That is a deliberate, priced decision by the owner, taken with the contractual and copyright exposure on the table. This document does not rule on it; the clause-level reading and the risk register live in [01-legal.md](01-legal.md).

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

## 6. Incremental updates

Daily, per 1,000 subreddits:

| Step | Endpoint | Requests/day |
|---|---|---|
| New posts (twice for hottest subs) | `/r/{sub}/new?limit=100` | ~1,200 |
| Comment trees for new posts | `/comments/{id}` | 5,000-15,000 |
| Score/edit refresh, 100 ids per call | `/api/info?id=t3_a,t3_b,…` | ~3,000 |
| **Total** | | **~10,000-20,000** |

Rate limit is **100 queries per minute per OAuth client id**, averaged over a ten-minute window, per the [Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki). Stay under ~80 QPM. The limit is per client_id, not per user, so extra accounts do not multiply the budget.

At 100 QPM the daily ceiling is 144K requests, so ~11K/day is about **8% of what a single client id may issue**, finishing in roughly three hours at a polite 0.75s pacing. Throughput is not the binding constraint.

Price depends on which tier we are entitled to, and that is not this document's call. The free tier is non-commercial and lists at $0; the commercial rate is **$0.24 per 1,000 calls** ([TechTarget](https://www.techtarget.com/whatis/feature/Reddit-pricing-API-charge-explained)), so 11-20K calls/day is 330-600K/month, or **$79-144/mo**.

⚠️ Do not plan against the $0 line. [01-legal.md](01-legal.md) reads [Developer Terms §4.1](https://www.redditinc.com/policies/developer-terms) as barring access "by or on behalf of a business" regardless of tier, so the non-commercial tier is not a posture an Empact-operated site can occupy. Budget the commercial figure and treat entitlement as unresolved.

Add a monthly Arctic Shift dump pull as a reconciliation pass that repairs whatever the live crawl missed. Note the **36-hour settling window** before dump data matches the API. The ranking itself rebuilds weekly ([08-architecture.md](08-architecture.md)); the dump pull corrects the store underneath it.

## 7. Acquisition routes compared

This table compares **coverage, cost and effort**. It does not rate compliance. Every legality verdict belongs to [01-legal.md](01-legal.md), and none of these routes is clean for a business-operated product, because [Developer Terms §4.1](https://www.redditinc.com/policies/developer-terms) reaches business use whatever the source.

| Route | Coverage | What the route does and does not settle | Cost | Effort |
|---|---|---|---|---|
| Official API, free tier | Last ~1,000 items per listing; days, not years | First-party and attributable, so no redistribution question about the transport. Grants no history and no commercial permission; tier entitlement is unresolved | $0 list price | Low |
| Official API, commercial | Same cap, no history | Buys a rate, not a licence: Data API Terms §3.1 still requires a separate agreement with Reddit for commercial use | $79-144/mo at 11-20K calls/day | Low |
| **Arctic Shift dumps (per-sub torrents)** | **Complete, 2005 → 2026-06** | Settles history, and only history. Torrent metadata carries `terms= {}, license= {}`, so it conveys no permission of any kind | Bandwidth only | Medium |
| Arctic Shift API | Complete but rate-limited, times out on big subs | Same absence of permission as the dumps; the docs additionally ask you not to bulk-pull | $0 | Low, not scalable |
| [Bright Data datasets](https://brightdata.com/products/datasets/reddit) | Broad, refreshable monthly | Changes the counterparty, not the underlying permission. Reddit disputes the category and has sued vendors in it | $250 min order, up to $0.0025/record → **~$750K at 300M** | Very low |
| [Apify actors](https://apify.com/automation-lab/reddit-scraper) | Whatever you crawl, no deep history | Crawls the public site, so it inherits the scraping question rather than answering it | $0.58-3.40 per 1K | Low-medium |
| Licensed Reddit agreement | Full firehose plus history | The only route that actually grants the rights the others assume. Out of reach at this price | Google ~$60M/yr, OpenAI ~$70M/yr class ([CNBC](https://www.cnbc.com/2026/07/22/reddit-stock-google-ai-content-deal.html)) | Enterprise negotiation |

**Chosen shape:** Arctic Shift per-subreddit dumps for backfill, the official API for daily increments, a commercial vendor only for targeted gap-fills. Which API tier that increment runs on is an open legal question, not a settled build decision.

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
| Mutable fields | Score, edit state, and deletion status change after capture. Store `captured_at` per record and let the refresh pass overwrite them. |
| Deletion propagation | The refresh pass must record when a post or comment has been removed upstream. |

Resumability is what makes the backfill affordable: a crash on day four costs the current month-unit, not the run.

## Open questions

| Item | Status |
|---|---|
| Which r/SaaS posting-rate method is right (122/day vs ~350/day) | Unreconciled. Both stated above; history quoted as a range. Settle it by counting surviving posts across a fixed 7-day window |
| Whether an Empact-operated site may use the free API tier at all | Open, and it is [01-legal.md](01-legal.md)'s call, not this document's |
| Whether Reddit self-serve API registration closed in late 2025 | **NOT VERIFIED** — secondary source only |
| Oxylabs pricing | **NOT VERIFIED** — pricing page returned 404 |
| Socialgist availability | **NOT VERIFIED** — site returned 404 |
| PullPush.io post-2023 coverage completeness | **NOT VERIFIED** — community claim, untested |
| Exact per-subreddit item counts beyond the ten measured above | Not measured; use `/api/time_series` before committing storage |

---

[← Back to README](README.md) · [04-subreddit-mapping.md](04-subreddit-mapping.md) · [08-architecture.md](08-architecture.md) · [data/subreddit-map.csv](data/subreddit-map.csv)
