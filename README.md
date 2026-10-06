# Reddit Brand Index

**Live: [redditindex.com](https://redditindex.com)** (noindex while provisional).

## STATUS (kept current; last edit 2026-10-06 06:15 UTC)

| | |
|---|---|
| **Live?** | The site is up and serves its **2026-09-22** build. It is **not refreshing yet**: the daily sweep refreshes a protected preview until the go-live gates pass (earliest after the run of **7 Oct**). |
| **Old collector** | Parked since 2026-10-02 20:47 UTC and **proven stopped**: two nights (3 and 4 Oct) with no deployment of it and no write outside a receipt. |
| **The daily sweep** | Runs every day at 00:00 UTC on Railway (`reddit-index-sweep`, Virginia). First scheduled run, 4 Oct 00:03-05:24: 200,000 comments re-checked on Reddit (5,388 deleted, 288 edited there; 8,526 rows purged), 20,067 new mentions from 466 subreddits, 34,000 mentions classified, 3,262 pages refreshed, 5,872 scored, 728 pages proven on the preview (628 that had held a takedown). It ended **failed**: the classification step crashed on a Linux limit the laptop does not have. Fixed and redeployed 4 Oct 12:00 UTC, with two more fixes from the same night (every subreddit now comes round in turn; every page the run expires is rendered inside the run). |
| **Cost** | The whole day of the first run sent 0.89 GB out of the database (the egress watchdog's meter; the gate is under 1 GB). |
| **Reviewed** | 4 Oct: an independent second engine reviewed the nightly code twice (21 findings); the real ones are fixed and deployed, and a live test run after the fixes matched the database row for row. |
| **Storage** | Database 3,455 MB before cleanup. Step 1 done 4 Oct: 177,292 threads with no mention moved to the archive (kept 14 days, then removed). Step 3, one copy of each comment's text, runs in the room the nightly runs leave under the 1 GB daily total. |
| **Go-live gates** | Two consecutive scheduled nights finished ok, each under 1 GB, receipts matching the database. **6 Oct: passed** (0.62 GB, every count equal). 7 Oct: tonight. Go-live the morning of 7 Oct if it passes. Nights 1 and 2 failed on two bugs, both fixed. |
| **Labels** | 565,142 mentions wait for a label; the nightly run classifies up to 60,000. 171,263 links to a parent company's web address set aside as "not this product". |
| **What is happening** | Relaunch under Vlad's ruling of 2026-10-02. Draft decision: [decisions/0017](decisions/0017-daily-sweep.md) (on the sweep branch, PR #8). |
| **How to stop everything** | `python3 ops/ri.py stop "reason"` turns the daily sweep off and its database login off. The old collector cannot reach the database and runs a do-nothing image. |

> **Still frozen until decision 0017 is recorded** ([decisions/0016](decisions/0016-frozen.md)). Do not run
> `worker/update.sh`, deploy the old `Dockerfile` to Railway, or clear Vercel's Ignored Build Step.
>
> **The freeze of 2026-10-01 did not hold.** `railway down` removed the deployment and Railway redeployed
> it by itself at 02:01 UTC on 2026-10-02: 18,155 mentions and 8,258 threads were written until 07:43 UTC.
> The collector ran nightly at 02:00 UTC from 2026-08-19 to 2026-10-02 inclusive. What stopped it is in
> the addendum to decision 0016.

A public index of what Reddit actually says about software brands: one
**Reddit ❤️ Score** (0-100) per brand per category, computed from verbatim
Reddit comments and posts — a post counts as its title plus its body — every
one of them stored, classified, and linkable back to its source. Built by
[Empact Partners](https://empact.partners).

```
              ┌──────────────────────────────────────────────────────────┐
              │ A HUMAN runs worker/update.sh — that is the only trigger │
              │ (decisions/0010 · 2026-08-18 · no scheduled jobs at all) │
              └────────────────────────┬─────────────────────────────────┘
                                       ▼
Reddit API ──►┌──────────────────────────────────────────────────────────┐
 /new         │ 1· collect — worker/daily.py --core-only (Mac-side)      │
 /comments    │ the 527 core subreddits first, then the rest of 2,029    │
              │ fetch → qualify → resolve (rules only) → Supabase        │
              │ watermark-bounded · 24 trees/sub · stops clean on budget │
              └────────────────────────┬─────────────────────────────────┘
                                       ▼ threads · verbatim mentions · watermarks
                            ┌──────────────────────┐
                            │       Supabase       │ ◄── the single source of truth
                            └──────────┬───────────┘
                                       ▼
              ┌──────────────────────────────────────────────────────────┐
              │ 2· classify — classify_api.py, 16 DeepSeek API workers   │
              │ (deepseek-v4-flash · ~1,100 items/min · ~$0.18/1K items  │
              │  · --allow-metered passed explicitly · Haiku = fallback) │
              │ 3· score_db.py → 4· delete_sync.py → 5· publish          │
              │ 6· healthcheck.py — the chain's own exit verdict         │
              │ NOT `set -e`; every stage reports and the chain goes on  │
              └────────────────────────┬─────────────────────────────────┘
                                       ▼ Vercel forced rebuild (fallback: empty-commit push)
                            ┌──────────────────────┐
                            │    Vercel rebuild    │ ──► redditindex.com (static)
                            └──────────────────────┘
```

**Everything is on-demand** ([SOP.md](SOP.md), [decisions/0010](decisions/0010-manual-on-demand.md)):
no launchd lanes, no Railway cron (service Offline; retired plists archived in
`worker/launchd/retired-2026-08-18/`). Run at least weekly — collection is the
one stage that loses data to waiting (`/new` reach, the 72h revisit window).

Two things in that picture are there because of what happened without them.

The fetch walks the core subreddits first: a pass can carry a time budget and
stops cleanly when it expires, so what gets dropped is the tail, never the 527
subreddits that carry the categories. One pass has to cover the gap since the
last run, so the listing budget is 8 pages — 800 posts, past anything in this
set — and a subreddit busier than that holds its watermark instead of skipping
the overflow.

The verify stage exists because between 2026-08-16 and 2026-08-17 the daily
fetch collected **zero rows and every signal stayed green** — the cron ran, the
container exited 0, and `ingest_state` gained a fresh row with `status='ok'`.
(`ingest_state.watermark` is a TEXT column; `daily.py` read it back with
`float()`, which raised on every subreddit from the second run onward. Fixed in
`daily.py::as_epoch`, pinned by `tests/collect.test.mjs`.) A cron that runs,
exits 0 and collects nothing is invisible to every other signal, so the check
asks whether the index MOVED, not whether it ran.

## What's here

| Path | What |
|---|---|
| `app/`, `components/`, `lib/` | The Next.js site (static, direct SQL to a read-only role, no anon key) |
| `worker/` | The pipeline. Live: `daily.py` (the Railway fetch), `classify_api.py`, `score_db.py`, `delete_sync.py`, `healthcheck.py`, `backfill_posts.py`, `sweep.py`, `qa_audit.py`. `harvest.py` is no longer a driver — it survives as the shared document builders (`post_doc`, `tree_docs`) that `daily.py`, `sweep.py` and `backfill_posts.py` import between them. Several files are dead; see [Superseded](#superseded-do-not-run-these) |
| `data/` | The taxonomy (151 categories), brand gazetteer (10,510 brands), subreddit mapping, and their generators |
| `supabase/migrations/` | The schema: partitioned mentions, sentiment, scores, RLS + published views |
| `scripts/` | Build gates (`gates/` — seven of them: category constraints, icons, contrast, fonts, trade dress, slugs, CSS law; each proven by `pnpm gates:selftest` to fail when violated), plus `qa-sweep.mjs` (reads every built page) and `device-shot.mjs` (real device-metric screenshots) |
| `tests/` | `pnpm test`: vitest for the board and company components, `node:test` for the resolver and for the two collection defects fixed on 2026-08-17 |
| `docs/` | How it works (below) |
| `00-16*.md`, `decisions/` | The original design record (historical; `HANDOFF.md` tracks drift) |

## Docs

- [methodology.md](docs/methodology.md) — how the score is computed, tiers, floors
- [methodology-review.md](docs/methodology-review.md) — the score interrogated: what's sound, what's weak, what changed
- [taxonomy.md](docs/taxonomy.md) — all categories and their scoring subreddits (generated, never hand-edited)
- [entity-resolution.md](docs/entity-resolution.md) — how a word becomes a brand mention (and when it refuses)
- [sentiment.md](docs/sentiment.md) — the four-way verdict and the engines that produce it
- [worker.md](docs/worker.md) — the daily loop: fetch algorithm, watermarks, failure matrix, deployment
- [how-the-index-updates.md](docs/how-the-index-updates.md) — cadence, the no-history rule, why publish = rebuild
- [qa-platform.md](docs/qa-platform.md) — the full site sweep: every built page, the design gates, responsive, SEO
- [qa-audit.md](docs/qa-audit.md) — the corpus audit: invariants, recall, precision, entity resolution
- [depth-execution-plan.md](docs/depth-execution-plan.md) — **the collection spec.** Stage 3
  (90 days, category by category) plus "What ACTUALLY ran": the 150-tree-per-subreddit cap the
  shipped index was built with. **Read this before changing how collection runs**
- [post-mortem-2026-08-24.md](docs/post-mortem-2026-08-24.md) — the 51-category expansion: 21
  incidents, ~19h of measurable loss, what caused each, and the 13 that still have no
  regression test

## Operating it

```bash
pnpm build                       # site + all gates (prebuild + postbuild)
pnpm gates:selftest              # prove each gate fails when violated (after a build)
pnpm test                        # vitest + the node:test resolver/collection suites
node scripts/qa-sweep.mjs        # read every built page (after a build)

worker/update.sh                 # THE update — collect → … → verify (SOP.md)
worker/update.sh --rehearse      # bounded end-to-end rehearsal, ~15 min

# individual stages, by hand
python3 worker/daily.py --dry-run --only sysadmin   # fetch + resolve, write NOTHING
python3 worker/daily.py --core-only                 # the 527 core subreddits only
python3 worker/daily.py --max-minutes 60            # bounded pass
python3 worker/classify_api.py --deepseek 16 --haiku 0 --allow-metered  # the ruled lane
python3 worker/classify_api.py                      # FALLBACK: 16 Haiku CLI (Claude quota!)
python3 worker/score_db.py                               # re-score from Supabase + prune
python3 worker/delete_sync.py --dry-run                  # what Reddit has removed
python3 worker/backfill_posts.py --limit 2000            # re-read stored threads AS POSTS

python3 worker/healthcheck.py                  # 14 assertions, exit 1 on failure
python3 worker/healthcheck.py --json           # the same, machine-readable
python3 worker/qa_audit.py --only invariants   # the 6 SQL invariants, free
```

Classification is `worker/classify_api.py` on the **DeepSeek API**
(`deepseek-v4-flash`, 16 HTTP workers — ruled 2026-08-18,
[decisions/0010](decisions/0010-manual-on-demand.md), superseding the
free-Haiku ruling of 2026-08-17: "free" Haiku drew the shared Claude Max-plan
quota, and its bare `claude -p` calls spent ~95% of their tokens booting
context). It drains the backlog and exits: ~1,100 items/min, ~$0.18 per 1,000
items, measured on the 153,748-item/$27.22 production run. `--allow-metered`
stays as a gate so spend is always explicit at the call site — `update.sh`
passes it. The Haiku CLI pool remains a fallback for a DeepSeek outage. The
corpus carries labels from three engines (`claude-cli-absa-1`,
`deepseek-v4-flash-absa-1`, `haiku-4.5-absa-1`) with 85% pairwise agreement.

`worker/backfill_posts.py` is a repair, not a daily job: until 2026-08-17 the
post document was built from `selftext` alone, so a brand named only in a post
title resolved to nothing and a link post produced no document at all. The
collectors are fixed; this re-reads every stored thread through `/api/info` to
recover the historical ones. Resumable, idempotent, re-running is free.

### Superseded: do not run these

| Path | Why not |
|---|---|
| `worker/classify_codex.py`, `classify_daily.py`, `classify_daemon.py` | The Codex fleet classification lane, retired in `071de98`. `codex exec` is an agent session, not an API call: >600s on a 40-item batch against 108s for free `claude -p` Haiku. Do not delete two of them — `classify_api.py` imports `SYSTEM` from `classify_codex.py` and `Backlog`/`pg_text` from `classify_daemon.py` |
| `worker/depth_run.py`, `collector.py`, `publisher.py`, `watchdog.py`, `lanes.sh` | The continuous lanes built for the one-off 90-day depth sweep. That sweep is complete (527/527 core subreddits) and none of these is loaded any more |
| `worker/backfill_100.sh` | Runs superseded discovery (`data/discover.py`) and the retired Codex classifier |
| `worker/finalize.sh`, `pipeline.py`, `run_scoring.py` | The file-cache era (`resolve → classify → assemble → score → load`). Supabase is the corpus now and `score_db.py` replaced the whole chain |

## Two facts about what the site shows

**The display floor is not a constant.** `lib/data/boards.ts` gives each
category its own bar: the **median** opinionated-mention count across the
brands tracked in that category, clamped to `[3, 30]`. A company must carry at
least as much evidence as the typical brand it is being ranked against. The
pooled "All Categories" board demands that bar AND `n_op ≥ 10`, because ranking
across the whole index is a bigger claim than ranking inside one category.

**A company page shows a window of its mentions, and says so.** The rails are
the 80 newest comments and the 40 newest posts per brand — two rails, one per
document type, because a single newest-N window left post-heavy brands with a
Posts filter over noise. The stat tiles, the Posts/Comments filter counts and
the subreddit ledger are computed over the WHOLE corpus, not over that window.

Everything verbatim lives in Supabase at all times: mention bodies, authors,
permalinks, labels, scores. The site is a rendering of that database, and every
mention it renders links back to the Reddit comment or post that produced it.

Start at [HANDOFF.md](HANDOFF.md) for the build history and every recorded
deviation from the original design documents.
