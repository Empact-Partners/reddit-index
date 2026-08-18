# The worker

**The index updates on demand** — a human runs `worker/update.sh` and that is
the only trigger (decisions/0010, 2026-08-18; the two-machine daily loop below
is retired: Railway is Offline, all launchd lanes are booted out with plists
archived in `worker/launchd/retired-2026-08-18/`). Operating procedure:
[SOP.md](../SOP.md).

```
worker/update.sh — one chain, run to completion, exit:
  1 collect       worker/daily.py --core-only  (Mac-side now)
                  /new listings -> qualify -> posts + 72h revisit trees
                  -> rules-only resolve -> Supabase (threads, mentions,
                  watermarks); stops cleanly on --max-minutes
  2 classify      classify_api.py --deepseek 16 --haiku 0 --allow-metered
  3 score         score_db.py    recompute every category from Supabase
  4 delete-sync   delete_sync.py purge what Reddit's authors deleted
  5 publish       publish.py     the Vercel rebuild IS the publish
  6 verify        healthcheck.py --json — the chain's exit verdict
```

Every write is `ON CONFLICT DO NOTHING` or a full recompute, so an interrupted
run costs nothing but a re-run of the same command.

## The fetch algorithm (Railway, `worker/daily.py`)

Subreddits are walked **core first**: `sorted(mapping, key=lambda s: (s not in
core, s))` puts the 527 `is_core` subreddits ahead of the other 1,502. `core`
is a fetch-ORDER filter only — `is_scoring` still decides what counts — so a
pass that runs out of time, dies or gets throttled has spent what it had on the
subreddits that actually carry the categories, and loses only the tail.

Per subreddit, in this order:

1. **Watermark.** `get_watermark` reads `ingest_state` through `as_epoch`,
   which accepts a Postgres timestamp string, an ISO string, a `datetime` or a
   bare epoch. It returns `None` for anything it cannot parse instead of
   raising — see the worked example below for why that sentence exists.

2. **`/r/{sub}/new`, watermark-bounded.** 100 posts per page, at most
   `MAX_PAGES` (4, `RI_MAX_PAGES`). The loop stops early on the first page
   whose oldest post is at or below the watermark, on an empty page, or when
   Reddit stops handing back an `after` cursor. A sub with no watermark yet
   reads exactly one page.

   Two failure shapes are distinguished, and both **hold** the watermark:

   - `ok=False` — a page came back `_err`. An error used to collapse into an
     empty page, indistinguishable from a clean end of listing, and the caller
     advanced past posts it had never seen. Reproduced: a drop on page 2 of 250
     new posts skipped 150 forever, and the next healthy run returned nothing
     because the watermark had already moved.
   - `capped=True` — the page budget ran out while the listing was still ahead
     of the watermark. This is the one this lane actually walks into.
     r/pcmasterrace publishes ~512 posts a day; a 300-post read covers 14 hours
     of a 24-hour gap, and the ~210 posts below it were unreachable for good.
     Every day. A capped read is an incomplete read, so the watermark stays put
     and the next pass re-walks the same pages.

3. **Content-qualify.** Not removed, not locked, and either a brand alias (the
   low-ambiguity regex) or an owning category's noun in **title or selftext**.
   The backfill's `num_comments >= 3` floor is deliberately dropped: a fresh
   thread legitimately has no comments yet, and the revisit queue is what
   collects its discussion later.

4. **Thread upsert.** `ON CONFLICT (id) DO UPDATE` refreshes `num_comments` and
   `score`; `first_seen_at` is stamped once, at insert, and is what the revisit
   window is measured from. A subreddit missing from the `subreddits` table is
   skipped loudly and counted as an error — no row, no foreign key, no
   mentions, and a whole community going dark must be visible. Names are folded
   to lowercase on lookup: Reddit names are case-preserving but
   case-insensitive, and most stored rows carry capitals (r/CRM, r/SaaS).

5. **Posts, resolved straight off the listing.** `harvest.post_doc` builds the
   post document as **title + selftext** (doc_type 2) and `resolver.resolve`
   runs over it. Zero extra Reddit calls — the listing is already in hand.
   Before this, a post became a mention only if its thread also won one of the
   day's revisit slots, so on any busy subreddit most post mentions were
   dropped on the floor while their comments were kept. And the document itself
   was selftext alone, so a brand named only in the title resolved to nothing
   and a link post produced no document at all.

6. **Revisit queue.** Threads in this subreddit first seen in the last
   `REVISIT_HOURS` (72), `ORDER BY tree_fetched_at NULLS FIRST, num_comments
   DESC`, `LIMIT TREES_PER_SUB` (24, `RI_TREES_PER_SUB`). Each one gets a
   `/comments/{id}` fetch at depth 6, limit 200, sort top.

   The ordering key is the whole point. This used to be `ORDER BY num_comments
   DESC LIMIT 12` with no memory of what had been fetched, and `num_comments`
   is refreshed on every pass — so the ordering was stable and the same twelve
   threads were re-read for three days while the thirteenth aged out of the
   window having never been read at all. Measured over 2026-08-10..15: 48,171
   of 75,511 threads (64%) never had their comments collected, and comments are
   the large majority of the corpus (about three quarters of it on 2026-08-17). `tree_fetched_at` plus NULLS FIRST means nothing is read
   twice until everything in the window has been read once, which is also why
   the per-sub budget could go from 12 to 24 without waste. A thread whose tree
   comes back empty is still marked read, so it cannot hold a slot the rest of
   the window needs.

7. **Insert, under savepoints.** `insert_mentions` writes in batches of 50 with
   `ON CONFLICT (brand_id, doc_id, created_utc) DO NOTHING`, and falls back to
   row-by-row when a batch is rejected — the vendor-sub trigger is the usual
   culprit. Every failure is contained in a `SAVEPOINT`. The first version
   called `cur.connection.rollback()`, a connection-level rollback that threw
   away the caller's open transaction: the subreddit's entire `threads` upsert
   and every batch that had already succeeded. `main()` then advanced the
   watermark and committed, so one rejected row silently cost a subreddit's
   whole pass and made the loss permanent. A helper must never commit or roll
   back a transaction it does not own.

   The returned count is **real insertions** — `rowcount`, which
   `ON CONFLICT DO NOTHING` reports as 0 for a duplicate — not `len(batch)`.
   The dead-run detector reads this number, and `len(batch)` made a
   duplicates-only run look productive.

8. **Mark and advance.** `UPDATE threads SET tree_fetched_at = now()` for every
   tree actually fetched, then the watermark, then `conn.commit()` — **per
   subreddit**, so a mid-run death costs nothing already committed. The
   watermark moves only when `newest and listing_ok and not capped`.

Monthly `mentions` partitions for this month and next are created at run start,
before any row could land in `mentions_default` (Postgres refuses a partition
whose range overlaps rows already in the default).

### Watermarks (`ingest_state`)

| column | value |
|---|---|
| scope | subreddit name, plus `_run` and `_run_coverage` summary rows |
| ym | `'daily'` (constant — this lane is not month-scoped) |
| stage | `'new_listing'` |
| code_version | `'daily-v1'` (bump = clean restart, by PK) |
| watermark | newest `created_utc` ingested for that sub, written as ISO-8601 |
| rows | qualifying threads on the last pass (`tot_mentions` on `_run`) |
| status | `'ok'` or `'error'` |

The column is **TEXT**. `set_watermark` writes `isoformat()` explicitly rather
than leaning on psycopg's datetime adaptation, and `as_epoch` is the only place
that parses it back, so no caller can reintroduce the assumption that it holds
a number.

A sub that errors keeps its old watermark and self-heals next pass. `_run`
carries the run-level verdict; `_run_coverage` carries a human summary
(`"1240/2029 subs · 3411 threads · 4 errors · 2 capped"`). A `--only`
invocation is a test and deliberately writes neither: it used to overwrite the
global `_run` marker, so a three-subreddit smoke test made the health check
believe a full pass had just finished.

The run exits 1 — and stamps `status='error'` — when errors exceed
`max(20, 5% of subs attempted)`, or when more than 50 subreddits were attempted
and the pass produced zero threads and zero mentions. Before that, a run that
raised on every single subreddit still printed DONE and exited 0, and Railway
showed a green cron for two days while the index froze.

## What one pass costs

The pacing floor is in `reddit_client`: `SLEEP = 0.75s`, applied
**start-to-start**, not end-to-start. Request latency (~0.6s from Chile) used
to stack on top of the floor, so a 0.75s gap produced ~44 req/min against a
~100 QPM budget. As a period it gives 60 / 0.75 = **80 calls per minute**, run
deliberately under the ~100 budget. It widens on its own when
`x-ratelimit-remaining` drops below 30, because the app-level budget is shared
across every process using this client_id.

Against 2,029 scoring subreddits (527 of them core):

| item | calls | at 0.75s |
|---|---|---|
| one listing page per sub (the floor) | 2,029 | 25 min |
| eight listing pages per sub (the ceiling nobody reaches) | 16,232 | 3.4 h |
| 24 trees per sub (the ceiling) | 48,696 | 10.1 h |
| **what `RI_MAX_MINUTES=600` buys** | **48,000** | **10 h** |

Both ceilings are theoretical. A listing stops paging the moment it reaches the
watermark, so a quiet subreddit costs exactly one call and only a genuinely
busy one spends eight; and the revisit query only returns threads first seen in
the last 72 hours, so a subreddit with four new threads asks for four trees,
not 24. Real passes land far below the table.

The shape that matters is the ORDER. The 527 core subs, saturated at 24 trees
each, cost 527 + 12,648 = 13,175 calls — about 2.7 hours, comfortably inside
the budget — and they are walked first, so the head of the index is always
fully collected and the tail absorbs any truncation. A pass that runs out of
clock loses subreddits nobody ranks on, not categories.

One pass a day at 02:00 UTC, with a 10-hour budget (`RI_MAX_MINUTES=600`),
means the fetch is finished by 12:00 UTC at the very latest and normally hours
earlier. The Mac chain starts at 08:30 UTC into whatever the pass has already
committed — collection commits per subreddit, so there is nothing to wait for
and nothing to coordinate. A pass that is still running when the chain starts
costs only that the last subreddits' mentions are classified tomorrow.

Once a day is the owner's ruling (2026-08-17) and it fits: a subreddit's 24
hours of new posts is covered by 8 listing pages, and the 72-hour revisit
window means every thread still gets multiple chances to have its comments
read as its discussion accumulates.

Listing and tree calls both pass `use_cache=False`. The disk cache exists for
resumable one-off harvests, not for a lane whose whole job is to see what
changed.

## Classification (Mac, `worker/classify_api.py`)

Anti-join: every mention with no `mention_sentiment` row for its
`(doc_id, brand_id)`, any model_version. It drains the backlog and exits — it
is not a daemon.

Providers are pools, and **the lane is DeepSeek** (`deepseek-v4-flash`,
sixteen HTTP workers): ~1,100 items/min at ~$0.18 per 1,000 items, measured on
the 153,748-item / $27.22 / 112-minute production run of 2026-08-16 — zero
truncations in 1,307 batches. Ruled 2026-08-18 (decisions/0010), superseding
the free-Haiku ruling of 2026-08-17: "free" Haiku drew the shared Claude
Max-plan quota and each bare `claude -p` call spent ~95% of its tokens booting
context rather than labelling.

`--allow-metered` stays as a hard gate — `--deepseek N` alone exits with a
message — so spending money is always explicit at the call site; `update.sh`
passes it. The sixteen-worker Haiku CLI pool remains a fallback for a DeepSeek
outage, knowing what it draws from. The corpus carries `claude-cli-absa-1`,
`deepseek-v4-flash-absa-1` and `haiku-4.5-absa-1`.

Concurrency is chosen on measured throughput, never on a resource gauge. The
Codex fleet at 100 concurrent looked fine on memory (119 procs, 1.8 GB) and
returned zero batches in 13 minutes, because a local agent process costs kernel
scheduling, not RAM. HTTP providers cost almost nothing locally and can go
wide; the CLI pool is one local process per worker and gets ramped carefully.

Three protections that each cost something to learn:

- `_claude_bin()` resolves the CLI absolutely and raises if it is missing.
  launchd hands a job `PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin`
  and the CLI lives in `~/.local/bin`, so bare `claude` raised
  `FileNotFoundError` inside every worker thread, got swallowed by the generic
  handler, and an unattended run labelled nothing while looking busy. The
  `daily` plist also puts `~/.local/bin` on PATH.
- `load_judged()` reads the on-disk caches and skips items any lane has already
  decided. Entity-rejected items never get a `mention_sentiment` row, so the
  anti-join returns them forever: 34,432 of them against 5,568 genuinely
  unprocessed items on one measured run, i.e. 86% of a naive second pass would
  be money spent re-learning a decision already on disk.
- Model output is cached to disk **before** the DB write, so a crash never
  loses paid work, and a poison row falls back to one-by-one so it cannot block
  the other 39.

`entity_ok=false` verdicts drop the mention. That is an entity decision, not a
sentiment one.

## Scoring (Mac, `worker/score_db.py`)

Supabase is the corpus. The local file caches under `worker/.cache/` are
backfill machinery, not the source of truth.

Per category: labelled mentions from its scoring subreddits over the trailing
365 days, restricted to brands whose category membership (primary or `also_in`)
includes this category — the fix for "Google Workspace tops the CRM board".
`score_category()` is the frozen EB-shrunk estimator, unchanged.

Then three gates before anything is published:

- **Calibration.** `gate_calibration.check_rows` refuses a run whose ordering
  contradicts its own raw data. Quarantine is **per category**: a violating
  board keeps its last-good numbers on disk (`<slug>.json.lastgood`), is listed
  in `.cache/index/_blocked.json`, and every other category publishes.
  Aborting the whole load on one category blocked the entire site for hours on
  a single email-providers tie. More than `max(3, len(cats)//20)` blocked
  categories is systemic and refuses the load outright.
- **No prune after an incomplete load.** `week_start` is stamped today, so a
  partial load moves `max(week_start)` forward and the prune would then delete
  the last complete published set.
- **No score outlives its evidence.** `load.py` upserts and the prune only
  removes older `week_start`s, so a (brand, category) that scored yesterday and
  has no mentions today would keep its stale row at today's `week_start`
  forever. Purging 30,858 false-positive mentions left 44 such rows live. The
  stale-score sweep deletes anything at the current `week_start` that this run
  did not just compute.

`brand_category_scores` then holds exactly one truthful set. No deltas, no
history, by design.

## Delete-sync

`delete_sync.py --publish-follows` probes stored `doc_id`s through `/api/info`,
purges mentions whose author deleted them on Reddit, writes `removals`, and
calls `revalidateTag`. This is not deferrable: Reddit's Developer Terms require
deletions to propagate as soon as possible, and `decisions/0002` makes it a
condition of displaying full comment text at all.

Purging Postgres is half the job — a cached page keeps serving a removed
comment until its tag is invalidated, which is why delete_sync owns the
revalidate call. A row with `purged_at` set and `revalidated_at` null is an
open defect, and `gate_checks.sql` asserts it.

## Publish

`python3 worker/publish.py` — a Vercel rebuild of the CURRENT production
commit. The site is fully static (`force-static`, `dynamicParams=false`): a
rebuild re-reads Supabase once, re-renders every route, and new brands get
pages. There is no cache revalidation path that refreshes the score pages
without a build, so the rebuild IS the publish mechanism.

It used to publish by pushing an empty commit, because a deploy hook has to be
created by hand in the dashboard and never was. That works — Vercel builds
every push — but daily publishing would write 365 commits a year recording no
change to the code. `publish.py` asks the API directly (`POST /v13/deployments`
with the previous deployment's id), waits for `READY`, and reports the
deployment id, so a failed publish appears in the chain's log instead of being
inferred from a stale site. The empty-commit push remains as the fallback when
that call fails.

    python3 worker/publish.py             # rebuild, wait for READY
    python3 worker/publish.py --status    # what is live right now

`update.sh` is deliberately **not** `set -e` (a lesson inherited from
`daily_mac.sh`): a stalled classifier used to abort the script before scoring
and publishing — one slow lane and the site stopped updating with data it
already had. Each stage reports its exit code and the chain continues.

## The health check (`worker/healthcheck.py`)

It exists because of a failure that is invisible to every other signal. On
2026-08-16 the fetch stopped writing a single row and everything a human would
look at stayed green: the cron ran on schedule, the container exited 0,
`ingest_state` gained a fresh `_run` row with `status='ok'`, and the site kept
serving. The only trace was `rows=0` on that row, and nobody reads a row for a
zero.

So the question it asks is not "did it run" but "did it MOVE". Fourteen
assertions, each comparing a clock or a count against what a healthy pass
produces, all sized against the once-daily cadence: 36 hours is a full cycle
plus the 10-hour budget plus room, so a late pass is not an alarm and a missed
day is:

| assertion | what it proves |
|---|---|
| `fetch_ran` | a pass finished within 20h |
| `fetch_collected` | the last pass wrote ≥200 new mentions — the 2026-08-16 signal |
| `fetch_status` | the last pass stamped `status='ok'` |
| `sub_coverage` | ≥80% of scoring subs advanced their watermark in 30h |
| `sub_errors` | ≤100 subreddits errored in 30h |
| `mentions_written` | ≥1,000 rows landed in 30h, by `loaded_at` (our clock, not Reddit's) |
| `posts_collected` | doc_type 2 rows are still arriving — zero means the post document regressed to selftext-only |
| `revisit_backlog` | unread threads in the 72h window have not run away |
| `labels_fresh` | the classifier committed within 30h |
| `backlog` | unlabelled count under 60k (warn) / 250k (fail) |
| `scores_fresh` | `max(week_start)` within 7 days |
| `scores_present` | >1,000 score rows exist |
| `view_unpinned` | `published.mentions` is not pinned to one model_version |
| `labels_visible` | labelled mentions actually reach the site |

It writes its verdict to `ingest_state` under scope `_health`, exits 1 on any
failure, and with `--slack` posts only on a **change** of state — into failure
and again on recovery. A long outage is one message, not one every three hours.
State is `worker/.cache/health.json`; the channel is `slack_channel` in
`~/.claude/.reddit-index.json`, and with no channel configured it posts nothing.

```bash
python3 worker/healthcheck.py            # human output, exit 1 on failure
python3 worker/healthcheck.py --json     # machine output
```

## Failure matrix

Every row below is a real failure this pipeline has had, and the guard is in
the code now. The point of the table is the diagnosis path, not the guard.

| what breaks | symptom | caught by | what to run |
|---|---|---|---|
| **Watermark unreadable** (TEXT read as float) | cron green, exit 0, `_run` rows=0, no sub advances, log shows an exception per subreddit | `fetch_collected`, `mentions_written`, `sub_coverage` | `node --test tests/collect.test.mjs`; the parse lives only in `daily.py::as_epoch` |
| **Listing budget exhausted** before the watermark | `r/x: 400 posts still short of the watermark — held`; `capped` count in `_run_coverage` | nothing fails: the watermark is held and the pass re-walks | raise `RI_MAX_PAGES` (default 8 = 800 posts/day) — a sub publishing more than that in a day cannot be covered by one pass |
| **Listing page errored** mid-fetch | `r/x: listing incomplete — watermark held` | `sub_errors` if it raised; otherwise self-heals | nothing; the next pass re-reads from the same floor |
| **Revisit starvation** (no `tree_fetched_at`) | comment mentions stop arriving while thread counts look fine; unread threads pile up in the 72h window | `revisit_backlog` | check `threads.tree_fetched_at IS NULL` inside 72h; raise `RI_TREES_PER_SUB` |
| **Rejected row rolls back the caller** | a subreddit's threads and mentions vanish while its watermark advances | `fetch_collected`, `mentions_written` | savepoints in `insert_mentions`; the reject reason is printed for the first 5 |
| **Container gazetteer drift** | Railway resolves different mentions than the Mac for identical text | the Docker **build** fails; `resolve.py` raises at import | `docker build .` — the parity assert wants ≥40 blocked pairs and >200k dictionary words |
| **Post document regresses** to selftext-only | zero doc_type 2 rows; titles stop producing mentions | `posts_collected` | `node --test tests/collect.test.mjs`; repair the corpus with `worker/backfill_posts.py` |
| **`published.mentions` re-pinned** to one model_version | site shows no sentiment at all while labels exist in the DB | `view_unpinned`, `labels_visible` | re-apply `supabase/migrations/0003` |
| **`claude` not on launchd PATH** | classify run "looks busy" and labels nothing | `labels_fresh`, `backlog` | `_claude_bin()` raises loudly; check the `PATH` key in `com.reddit-index.daily.plist` |
| **Mac asleep, chain missed** | labels stale, `week_start` old, fetch fine | `labels_fresh`, `scores_fresh` | nothing — launchd runs a missed calendar job once on wake |
| **Calibration quarantine** | one board keeps yesterday's numbers | not a health assertion | read `worker/.cache/index/_blocked.json` |
| Railway ran, Mac didn't | unclassified mentions wait | `labels_fresh` | next Mac run's anti-join sweeps them |
| Mac ran, Railway didn't | anti-join ≈ empty, identical scores re-upserted | `fetch_ran` | harmless |
| Double runs, either side | — | — | watermarks + PK conflicts + the judged-set cache give zero duplicates and zero re-spend |
| Railway dies mid-run | — | — | finished subs are committed; unfinished resume from their own watermark |
| Month boundary | — | — | partitions for this month and next are created at run start |

### The worked example: 2026-08-16 to 2026-08-17

`ingest_state.watermark` is a TEXT column. psycopg writes a `datetime` into it
as `'2026-08-15 10:02:29+00'` and reads it back as that **string**.
`daily.py` read it with `float(wmv) if wmv else None`, which raised
`ValueError` on every subreddit from the second run onward.

It survived its own smoke test because the first run for a subreddit reads
`None` — no row yet — and works perfectly. Only the second run is dead.

The cron ran on schedule, the container exited 0, a fresh `_run` row landed
with `status='ok'`, and the site kept serving stale data. Two full days
collected zero rows before anyone noticed.

Three things came out of it, and all three are in the repo:

1. `as_epoch` accepts every form the column has ever held and returns `None`
   for anything unparseable, never an exception. `tests/collect.test.mjs` pins
   it against the exact string Postgres returns.
2. `main()` now fails a pass that produced nothing across more than 50
   subreddits, in its exit code and in `ingest_state.status`.
3. `healthcheck.py` exists, runs on its own three-hour schedule, and every one
   of its assertions would have failed on 2026-08-17 04:13.

## Which script is current

Everything in `worker/`. A dead lane must not be runnable by accident.

| script | status |
|---|---|
| `daily.py` | **current** — the collection pass (stage 1 of `update.sh`; ran on Railway until 2026-08-18) |
| `update.sh` | **current** — THE chain: collect, classify, score, delete-sync, publish, verify (replaced `daily_mac.sh`) |
| `healthcheck.py` | **current** — the verify stage at the end of the chain |
| `classify_api.py` | **current** — the classifier: 16 DeepSeek API workers (decisions/0010); the Haiku CLI pool is the fallback, and `--deepseek` still needs `--allow-metered` |
| `score_db.py` | **current** — scoring from Supabase, calibration gate, prune |
| `delete_sync.py` | **current** — deletion propagation + revalidate |
| `backfill_posts.py` | **current** — one-off, resumable: re-reads every stored thread through `/api/info` so historical post TITLES finally resolve |
| `backfill_labels.py` | **current** — recovery: commits labels that exist in the on-disk cache but never reached Postgres |
| `qa_audit.py` | **current** — invariants, recall, precision, entity audit |
| `reddit_client.py` `db.py` `resolve.py` `score.py` `gate_calibration.py` `load.py` `classify.py` | **current libraries.** `load.py --scores` is called by `score_db.py`; its `--seed`/`--mentions` legs are backfill machinery. `classify.py` supplies `MODEL_VERSION`, `LABEL_CODE`, `mark_target`; its own CLI is the retired serial `claude -p` lane |
| `harvest.py` | **library, not a driver.** It survives as the shared document builders `post_doc` / `tree_docs` (plus `CATEGORY_NOUNS`, `build_alias_re`, `load_brands`) that `daily.py`, `sweep.py` and `backfill_posts.py` all import — they must agree byte for byte, because the mentions PK is `(brand_id, doc_id, created_utc)` and the stored body is what the site renders. Its `--category/--all` Lane D CLI is retired |
| `sweep.py` | the 90-day depth sweep engine. **The sweep is complete** (527/527 core subs); still the right tool for a newly added subreddit, nothing runs it on a schedule |
| `classify_codex.py` `classify_daily.py` `classify_daemon.py` | **superseded** — the Codex fleet lane, retired in `071de98`. `codex exec` is an agent session, not an API call: >600s on a 40-item batch against 108s for `claude -p` Haiku, with identical label distributions. `classify_daemon.py` still supplies `Backlog` / `pg_text` to `classify_api.py`, and `classify_codex.py` still supplies the `SYSTEM` prompt; neither is run |
| `depth_run.py` `collector.py` `publisher.py` `watchdog.py` `lanes.sh` | **superseded** — the continuous lanes built to drive the one-off 90-day depth sweep. That sweep is done and none of these is loaded. `lanes.sh install` would bootstrap four launchd jobs that no longer have work |
| `leases.py` `status.py` `depth_progress.py` | support for those dormant lanes — `leases.py` is the flock primitive, the other two are read-only observers |
| `backfill_100.sh` | **superseded** — runs the old discovery chain and the retired classifier |
| `finalize.sh` `pipeline.py` `run_scoring.py` | **superseded** — the file-cache era (`resolve -> classify -> assemble -> score -> load`). Supabase is the corpus now; `score_db.py` replaced the whole chain |
| `verify.py` `freeze_methodology.py` | one-off evidence producers. `freeze_methodology.py` ran before the first production crawl and re-running it is a methodology version bump, not a refresh |
| `bench_deepseek.py` | benchmark: finds the fastest DeepSeek config that does not degrade labels |
| `gate_checks.sql` | the SQL assertions `verify.py` and delete-sync are checked against |

Loaded launchd jobs are exactly ZERO (2026-08-18). All seven retired plists
are archived in `worker/launchd/retired-2026-08-18/`; nothing may be
re-bootstrapped without a new ruling (decisions/0010).

### The site can be down while the database is perfect

Every assertion above reads Postgres. On 2026-08-17 at 21:05 UTC the database
was healthy and every request to redditindex.com came back `403` with
`x-vercel-mitigated: challenge`: Vercel's automatic mitigation had switched
itself on. Nobody configured it — the project's firewall config was empty the
whole time and the firewall event log records it as `system-action` — and to a
visitor it looks like the site is broken and slow.

So the health lane ends by fetching the homepage from outside and asserting two
things: `site_reachable` (HTTP 200, a real body) and `site_unchallenged` (no
`x-vercel-mitigated` header). To clear it:

```bash
python3 scripts/attack-mode.py          # what is the site serving right now?
python3 scripts/attack-mode.py --off    # clear the challenge, then re-probe
```

## Deployment

### Railway (the fetch)

`railway.json` is the whole configuration:

```json
{
  "build": { "builder": "DOCKERFILE", "dockerfilePath": "Dockerfile" },
  "deploy": { "cronSchedule": "0 2 * * *", "restartPolicyType": "NEVER" }
}
```

`restartPolicyType: NEVER` matters — a cron container that restarts on exit
would re-run the pass immediately.

The `Dockerfile` is python:3.12-slim plus `psycopg[binary]` and
`pyahocorasick`, and it copies `worker/` and **six** data files:
`categories.csv`, `category-subreddits.csv`, `brands.csv`, `brand-aliases.csv`,
`alias-blocklist.csv`, `english-words.txt`.

The last two were missing, and the container therefore resolved against a
different gazetteer than the Mac: 41 blocklisted alias→brand pairs the entity
gate rejects (`aws`→amazon-route-53, `app`→astro-pixel-processor) resolved
anyway, and slim images have no `/usr/share/dict/words`, so 31 aliases that the
plain-word guard should have caught resolved bare. Two guards now:
`resolve.py` **raises** when either input is absent rather than silently
changing behaviour, and the image build asserts parity, so a wrong gazetteer
fails the **build** rather than a 02:00 cron:

```dockerfile
RUN python3 -c "import sys; sys.path.insert(0,'/app/worker'); import resolve; \
    assert len(resolve._BLOCKED) >= 40, resolve._BLOCKED; \
    assert len(resolve._ENGLISH) > 200000, len(resolve._ENGLISH)"
```

Deploy:

```bash
cd ~/Projects/reddit-index && railway up
```

`.railwayignore` keeps the Next app, `node_modules`, caches and docs out of the
build context — the image is the worker and its CSVs, nothing else.

Environment on the cron service:

| var | value | why |
|---|---|---|
| `REDDIT_CLIENT_ID` / `_SECRET` / `_USER_AGENT` | app-only OAuth | `reddit_client` raises at import without all three |
| `SUPABASE_PROJECT_REF` | project ref | becomes the pooler user `postgres.<ref>` |
| `SUPABASE_DB_PASSWORD` | db password | scoped to this one database; the org-wide Supabase PAT never enters the container |
| `RI_CACHE` | `/tmp/ri-cache` | the image is read-only elsewhere |
| `RI_MAX_MINUTES` | `600` | the code default is 0 (no budget) — 10h lives here, not in the source |
| `RI_CLASSIFY_LIMIT` | unset | caps the nightly classifier; set it only to rehearse the chain end to end |
| `RI_TREES_PER_SUB` | `24` | revisit budget per sub per pass |
| optional | `RI_MAX_PAGES`, `RI_SLEEP`, `RI_NET_MAX_WAIT`, `RI_DB_CONNECT_TRIES`, `SUPABASE_DB_HOST/PORT/USER/NAME/REGION` | |

Transport is the Supavisor **session** pooler
(`aws-0-<region>.pooler.supabase.com:5432`), which resolves to IPv4. The direct
DB host is IPv6-only and unreachable from a Railway container.

### Mac (the whole chain)

There is nothing to deploy on the Mac: no plists are installed
(decisions/0010). The chain is run by hand:

```bash
cd ~/Projects/reddit-index
worker/update.sh              # the update
worker/update.sh --rehearse   # bounded end-to-end rehearsal
```

The retired plists are archived in `worker/launchd/retired-2026-08-18/` for
topology reference only — do not copy them back into `~/Library/LaunchAgents/`.

`update.sh` holds the machine awake itself (`caffeinate -i` around the run) and
logs to the terminal; keep a copy with `worker/update.sh |& tee` if you want a
file. The old scheduled-era logs (`~/Library/Logs/reddit-index-daily.log`,
`-health.log`) are frozen history.

Credentials on the Mac are `~/.claude/.reddit-index.json` (0600):
`project_ref`, `db_password`, `region`, `deploy_hook`, `slack_channel`. The
Supabase management token for `load.py` and `delete_sync.py` is
`~/.claude/.supabase-empact.token`.

### Running a pass by hand

```bash
python3 worker/daily.py --dry-run --only crm --only sysadmin   # writes nothing
python3 worker/daily.py --core-only --max-minutes 60           # the 527 core subs
python3 worker/daily.py                                        # a full pass
```

`--only` never writes the `_run` markers, so a smoke test cannot fool the
health check.
