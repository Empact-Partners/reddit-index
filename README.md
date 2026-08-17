# Reddit Brand Index

**Live: [redditindex.com](https://redditindex.com)** (noindex while provisional).

A public index of what Reddit actually says about software brands: one
**Reddit ❤️ Score** (0-100) per brand per category, computed from verbatim
Reddit comments and posts — a post counts as its title plus its body — every
one of them stored, classified, and linkable back to its source. Built by
[Empact Partners](https://empact.partners).

```
Reddit API ──►┌──────────────────────────────────────────────────────────┐
 /new         │ Railway cron · 02:00 UTC daily · worker/daily.py         │
 /comments    │ the 527 core subreddits first, then the rest of 2,029    │
              │ fetch → qualify → resolve (rules only) → Supabase        │
              │ RI_MAX_MINUTES=600 (stops clean at 10h) · 24 trees/sub   │
              └────────────────────────┬─────────────────────────────────┘
                                       ▼ threads · verbatim mentions · watermarks
                            ┌──────────────────────┐
                            │       Supabase       │ ◄── the single source of truth
                            └──────────┬───────────┘
                                       ▼
              ┌──────────────────────────────────────────────────────────┐
              │ Mac launchd · 04:30 America/Santiago (08:30 UTC)         │
              │ worker/daily_mac.sh — NOT `set -e`; every stage reports  │
              │ classify_api.py  16 free `claude -p` Haiku workers, and  │
              │ nothing metered — the DeepSeek pool needs a flag it is   │
              │ never given                                              │
              │ → score_db.py → delete_sync.py → publish → healthcheck   │
              └────────────────────────┬─────────────────────────────────┘
                                       ▼ POST Vercel deploy hook
                            ┌──────────────────────┐
                            │    Vercel rebuild    │ ──► redditindex.com (static)
                            └──────────────────────┘

              ┌──────────────────────────────────────────────────────────┐
              │ Mac launchd · every 3h · worker/healthcheck.py --slack   │
              │ 14 assertions read Supabase on their OWN clock, so a     │
              │ broken chain cannot also break its own alarm.            │
              │ Slack on a CHANGE of state only — into failure, and out. │
              └──────────────────────────────────────────────────────────┘
```

Two things in that picture are there because of what happened without them.

The fetch runs **once** a day and walks the core subreddits first: a pass has a
10-hour budget and stops cleanly when it expires, so what gets dropped is the
tail, never the 527 subreddits that carry the categories. One pass has to cover
a full day, so the listing budget is 8 pages — 800 posts, past anything in this
set — and a subreddit busier than that holds its watermark instead of skipping
the overflow.

The health lane exists because between 2026-08-16 and 2026-08-17 the daily
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
| `data/` | The taxonomy (100 categories), brand gazetteer, subreddit mapping, and their generators |
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

## Operating it

```bash
pnpm build                       # site + all gates (prebuild + postbuild)
pnpm gates:selftest              # prove each gate fails when violated (after a build)
pnpm test                        # vitest + the node:test resolver/collection suites
node scripts/qa-sweep.mjs        # read every built page (after a build)

# the fetch (Railway runs this; these are the by-hand forms)
python3 worker/daily.py --dry-run --only sysadmin   # fetch + resolve, write NOTHING
python3 worker/daily.py --core-only                 # the 527 core subreddits only
python3 worker/daily.py --max-minutes 60            # bounded pass (Railway sets 600)

worker/daily_mac.sh              # the whole Mac chain, by hand
python3 worker/classify_api.py                      # drain the label backlog (free Haiku)
python3 worker/score_db.py                               # re-score from Supabase + prune
python3 worker/delete_sync.py --dry-run                  # what Reddit has removed
python3 worker/backfill_posts.py --limit 2000            # re-read stored threads AS POSTS

python3 worker/healthcheck.py                  # 14 assertions, exit 1 on failure
python3 worker/healthcheck.py --json           # the same, machine-readable
python3 worker/qa_audit.py --only invariants   # the 6 SQL invariants, free
```

Classification is `worker/classify_api.py`: 16 free `claude -p` Haiku workers
on the Max plan. It drains the backlog and exits. The metered DeepSeek pool is
still in the file — it is how the throughput ceiling was measured — but it
refuses to start without `--allow-metered`, because classification runs free
(ruled 2026-08-17). The corpus carries labels from three engines
(`claude-cli-absa-1`, `deepseek-v4-flash-absa-1`, `haiku-4.5-absa-1`); the
DeepSeek ones are from one deliberate $27 backlog run and are history, not
policy.

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
the 200 newest comments and the 100 newest posts per brand — two rails, one per
document type, because a single newest-N window left post-heavy brands with a
Posts filter over noise. The stat tiles, the Posts/Comments filter counts and
the subreddit ledger are computed over the WHOLE corpus, not over that window.

Everything verbatim lives in Supabase at all times: mention bodies, authors,
permalinks, labels, scores. The site is a rendering of that database, and every
mention it renders links back to the Reddit comment or post that produced it.

Start at [HANDOFF.md](HANDOFF.md) for the build history and every recorded
deviation from the original design documents.
