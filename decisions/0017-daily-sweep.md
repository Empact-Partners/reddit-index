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
| Database egress | the run stops at 0.7 GB estimated before publishing, which adds at most 1,000 page renders (about 0.2 GB); one day total of 1 GB for every index job together (`ops/day_egress.py`); gate: under 1 GB a day measured | _to fill_ |
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

## The first scheduled run (4 October)

Run `eef79c86`, 00:03-05:24 UTC, unattended. Takedowns: 200,000 comments checked (every one on a page, then the
longest-unchecked), 5,388 deleted and 288 edited on Reddit, 8,526 rows purged. Collection: 7,550 Reddit calls,
466 subreddits, 20,067 new mentions, ended by its time allowance. Classification: 34,000 mentions judged (25,125
labelled, 5,270 "not this product"; 1,969 GLM credits, $0.68 of Jev). 3,262 pages refreshed, 5,872 scored, 2,000
expired, 728 fetched and proven on the preview (628 that had held a takedown), 0 failures. The egress
watchdog's meter read **0.89 GB** for the whole day, 07:01 to 07:01 UTC (an upper bound for the run).

It ended **failed**, and does not count toward the gates. What it taught, fixed the same day:

- The classification step died on `Argument list too long`: the GLM prompt was passed as a program argument,
  Linux caps one argument at 128 KB, and a batch of long comments passed it (macOS allows 1 MB, so the laptop
  never saw it). The prompt now goes in on stdin (a 187 KB batch tested); a job that cannot start costs its own
  items, and an error inside the stage keeps the counts of what it already wrote. The crash also took the
  stage's counts off the receipt; the gate meter's reconciliation caught it (labels: receipt none, database
  25,125).
- Collection's order put all 553 waiting core subreddits before any other; with time for 466 a night, the other
  1,354 (522 never visited, the subreddits behind the August brands) would never have come round. Now each is
  ranked by how many of its due intervals have passed (core: a day, others: three).
- The shared Reddit app ran out of quota 12 times in the night (another tool was using it): about 30 minutes of
  collection lost. The dedicated app (owner step below) removes that.
- The publisher expired 2,000 pages and fetched 728: the other 1,272 would have re-rendered on their first
  visit, outside any measurement. It now expires at most 1,000 a night and fetches every one, and the receipt's
  estimate counts those renders.
- The receipt counted qualifying posts in the listings as "new threads" (13,586 against 11,476 stored for the
  first time); it now reads the new threads back.

### Independent review before the gate nights (4 October)

Two rounds by a second engine (Codex `gpt-6-astra`, low effort, no web search; about 0.3M tokens each): 16
findings on the run path, then 5 on the day's own fixes. Adjudicated here; fixed the same afternoon:

- a GLM outage (every job that started failed) ends classification with an error and leaves the items their
  five tries; no GLM job starts or runs past the stage's deadline
- label and rejection counts are the rows actually written, so the receipt equals the table
- a scheduled run ends at 05:30 UTC however late it starts; refresh stops 8 minutes before the end (what is
  left waits, oldest first, so a takedown's brands go first) and the publisher starts no request after it
- every page whose served fingerprint differs from its data comes round again (night 1 left 1,485 expired and
  never seen); a takedown is never stamped proven for a brand still waiting for its refresh; an unproven
  takedown older than 36 hours fails the run whatever stages ran
- a quiet subreddit with threads inside the comment-revisit window is still visited; a night where most
  subreddits fail is an error, not a quiet night
- time: collection ends 95 minutes before the run's end and classification 35 (refresh took 15 minutes on
  night 1), so the night finishes inside its window

Not changed, by decision: takedown pages are always published, over the 1,000-page cap (a legal duty before a
budget); requests Reddit refused are not counted as calls (the 15,000 cap is far from binding).

A live pilot after the fixes (`1bae1e4d`, by hand, tiny caps, no publish) finished ok with its receipt equal to
the database: 256 labels, 44 "not this product", 33 mentions, 34 threads.

## Night 2 (5 October)

Run `6d98d9bc`, 00:03-04:42 UTC, unattended. Takedowns: 200,000 checked, 6,329 deleted and 422 edited on Reddit,
9,095 rows purged. Collection: 256 subreddits (the never-visited ones first), 10,525 new mentions, 8,176 new
threads. Classification: 46,000 taken, 19,419 labelled, 4,174 "not this product". 1,673 pages refreshed, 5,901
scored; 1,000 pages expired, fetched and proven on the preview (519 that had held a takedown), 152 boards, 0
failures. Every stage finished inside the window.

It ended **failed** and does not count: from 04:13 UTC a growing share of GLM jobs came back empty, and at 04:24
a whole batch failed (17 of 17), so the new outage guard stopped classification (the items kept their tries,
as designed). The other session that shares the Z.ai plan logged "Rate limit reached for requests" at 04:25: the
plan's request-rate limit, hit by both sessions at once. Fixed the same morning: a refused job is retried after
1, 2 and 4 minutes at half the width, a limit that still holds ends classification for the night as a planned
limit (not an alert), any other failure is still a fault, the provider's error text goes on the receipt, and at
most 6 GLM jobs run at once (was 8). The gate nights move to 6 and 7 October.

### Daytime, 5 October: what a label costs

Night 2 measured **0.616 GB** on the laptop window (23:50 to 05:05 UTC), every receipt count equal to the
database. The daytime backlog run that followed (`e0ce48ac`, 10:02-11:11 UTC) wrote 51,794 results (46,154
labelled, 5,640 "not this product") and cost about **0.45 GB, 8.7 KB a mention**, four times the 2 October
measurement; it stopped when its connection dropped (the laptop most likely slept), and its meter, refreshed every
10 minutes, would have let it pass its 0.38 GB room by about 0.1 GB (now every minute). A quiet half hour with
no job of ours read 0.22 GB a day: nothing else was reading the database.

Why a label cost so much: `wal_compression` is already `zstd` and `checkpoint_timeout` is 5 minutes, so after
each checkpoint the first change to any page ships the whole page. Newest-first, a batch's inserts and deletes
landed on random pages of three large indexes (mention_sentiment's two, 65 and 70 MB, and the queue's, 59 MB).
From 5 October the backlog runs in brand order (new arrivals of the last 26 hours still first) and each batch is
written in brand order, so two of the three indexes are touched in adjacent pages. Tonight's run measures it.
Lengthening the checkpoint interval (Supabase project config) would cut this for every write; not changed while
the gates run.

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
