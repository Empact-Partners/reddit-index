# 0017 — The index refreshes itself once a day, inside declared budgets

**Status:** Proposed — accepted when the go-live gates below are all measured and met · **Date:** 2026-10-03 ·
**Decided by:** Vlad Shvets (ruling of 2026-10-02), executed by Claude

**Supersedes:** [0016](0016-frozen.md) (frozen) and [0010](0010-manual-on-demand.md) (manual, on demand).

## Bottom line

redditindex.com is refreshed by one job a day, `worker/run_daily.py`, at 00:00 UTC, on its own Railway service.
The site reads small precomputed rows and changes a page only when that page's data changed; data never
rebuilds the site. Every stage is bounded by a cap declared in `ops/schedule.json`, and Vlad is messaged only when
a run fails or stops at a real limit (the egress cap, an abnormal flood of mentions, the purge brake, an unproven
takedown). A stage that uses up its planned nightly allowance ends normally and records it. Stopping it is one command: `python3 ops/ri.py stop "reason"`.

Vlad, 2026-10-02: "Reddit index must go live and start refreshing itself, but you're supposed to fix all the
issues and optimize the whole mechanics and the whole mechanism behind it."

## What was wrong (docs/investigation-2026-10.md)

- The site was the cost. From 3 to 17 September every page view re-read the corpus (about 800 GB of the 819 GB
  the Empact organisation used against a 250 GB allowance). After that, every build read the corpus twice.
- The collector everyone believed retired ran every night from 19 August to 2 October on a 19 August image that
  knew 6,040 of 10,511 brands, while classification, scoring and the deletion check had stopped on 25 August.
  959,245 of 1,437,879 mentions had no label; the site served a 22 September build.
- About one stored mention in four was not about its brand; 155,371 were links to a parent company's web address
  filed under one of its products.

## What changed

| Area | Now |
|---|---|
| Site reads | schema `site`: one row per page plus its cards, recomputed inside the database when the data changes (`site.refresh_brand`); role `ri_site` can read nothing else, 5-second timeout; a build gate fails on any query outside it |
| Site writes | none. The sweep posts the paths whose fingerprint changed to `/api/revalidate/` and fetches the ones that must be proven |
| Scores and ranks | computed by the sweep (`worker/site_score.py`), one number per page, the same on page and board |
| Takedowns | every comment shown is re-checked daily, then the longest-unchecked; a batch Reddit did not answer is "not checked", never "deleted"; a receipt only after the page was fetched without the card; a brake above 15% gone |
| Collection | the current brand list (redeployed with the data), quiet subreddits every third day, an unchanged thread not rewritten, a failed comment tree not marked read |
| Classification | a rule (a web address names a product only when it names the whole product), then Jev, then GLM-5.3, calibrated against each other (`docs/classify-backlog.md`); "not this product" recorded and not counted (methodology 2.3.0) |
| Storage | `docs/retention.md`: one copy of each comment's text, threads and rejected rows aged out through an archive |
| Schedule | declared once (`ops/schedule.json`), set on the service by `ops/deploy_sweep.py`, proven from the data by `scripts/schedule_check.py` |
| Stop | `ops/ri.py stop` turns the switch off and the sweep's database login off |
| Legal | the non-affiliation notice is in the footer of every page (it was on /methodology only). Takedown rules unchanged |

## Budgets (per run unless stated)

| | Ceiling | Normal day (measured) |
|---|---|---|
| Reddit API calls | 15,000 (2,000 takedowns, 13,000 collection), 50 a minute | _to fill_ |
| New mentions | 40,000 | _to fill_ |
| Run time | 5.5 hours, window 00:00–05:30 UTC | _to fill_ |
| Database egress | the run stops at 0.8 GB estimated; gate: under 1 GB a day measured | _to fill_ |
| GLM-5.3 | 3,000 credits | _to fill_ |
| Jev | $1 | _to fill_ |
| Vercel | one build per code change; none for data | 0 builds a day |

One-time, already declared: the classification backlog (60,000 GLM credits, $60 of Jev, 1.5 GB egress, 0.5 GB a
day) and retention step 3 (1.0 GB egress, 0.4 GB a day).

## Measured before the scheduled runs (3 October)

| Run | What it did | Egress (node counter) |
|---|---|---|
| Pilot `69be2c4b`, small caps, as `ri_sweep` | 20,000 on-page comments checked (564 deleted, 2 edited on Reddit; 1,058 rows purged); 400 Reddit calls of collection (18 subreddits); 2,000 mentions classified (146 GLM credits, $0.02); 5,907 pages refreshed and scored; on the preview, 5,907 pages expired, 697 fetched and proven (597 that had held a takedown), 152 boards, 110 retired pages answering 404; 0 failures; 39.7 minutes | 185 MB, including a 20-minute tail |
| Takedown catch-up `8f2c3213` | 70,000 on-page comments checked, 3,227 deleted and 230 edited on Reddit since 25 August, 6,173 rows purged; stopped by the switch to yield the shared Reddit app to another session (the stop worked as designed: it purged what it had found and published nothing) | 70 MB during the run |
| Takedown catch-up `df78760d`, after the other session's Reddit job ended | 196,548 comments checked (every one on a page, then the longest-unchecked), 7,274 deleted and 978 edited on Reddit, 20,097 rows purged; 5,801 pages refreshed and scored; 2,618 pages that had held a takedown expired, fetched and proven; 152 boards; 106 retired pages answering 404. Marked "failed" by a publisher bug (its 100-page sample came from pages left for later, over the cap), fixed the same hour | 559 MB, including a 20-minute tail: almost all of it the 2,618 page fetches, a one-time catch-up |

By the end of 3 October, 12,275 comments found deleted (11,065) or edited (1,210) on Reddit since 25 August were
purged, and every page that had shown one was fetched afterwards and seen without it (on the preview; production
serves its 22 September build until go-live, when it renders from the purged data).

What the pilot taught, and what changed because of it:

- A company page re-render reads about 0.2 MB (its numbers and 120 cards of full text). The publisher now
  expires at most 2,000 pages a day, longest-waiting first, takedown pages always on top of the cap: page
  regeneration stays under about 0.4 GB a day even if every expired page is visited.
- Collection spends about 22 Reddit calls a subreddit, most of them re-reading recent comment trees. 13,000
  calls cover the core subreddits daily and the rest in rotation.
- Refresh costs about 0.25-0.5 seconds a brand on the 1 GB instance (Notion: 1.9 s for 1,484 mentions). During
  the backlog most brands change daily; afterwards about 2,000 a day.
- The one-copy text trigger met a NOT NULL constraint within a minute of collection; fixed (migration 0021),
  22 dropped rows restored.

## Go-live gates

| Gate | Measured | Met |
|---|---|---|
| A full run plus the day's page regeneration under 1 GB of egress | _to fill_ | |
| Two consecutive scheduled runs, unattended, receipts matching the database | _to fill_ | |
| The site shows the latest run's data and its date | _to fill_ | |
| The egress watchdog's baseline re-recorded after the planned work | _to fill_ | |

## Not changed

The Supabase project (nrsyqcttpijxhwtdtoct, Empact organisation). `01-legal.md`. The `published.*` views other
tools read (same names, columns and results; text served from the comment's one stored copy). The index is not
wired into the Reddit boards or partner panels. The site stays noindex.

## Owner step

A dedicated Reddit API app for the index (`01-legal.md` asks for credentials separate from every other tool;
today the sweep uses the shared app). Swapping it is two Railway variables.
