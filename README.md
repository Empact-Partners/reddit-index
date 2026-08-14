# Reddit Brand Index

**Live: [redditindex.com](https://redditindex.com)** (noindex while provisional).

A public index of what Reddit actually says about software brands: one
**Reddit ❤️ Score** (0-100) per brand per category, computed from verbatim
Reddit comments and post bodies, every one of them stored, classified, and
linkable back to its source. Built by [Empact Partners](https://empact.partners).

```
                ┌────────────────────────────────────────────────┐
Reddit API ───► │ Railway cron (daily 04:00 UTC)  worker/daily.py│
 /new + trees   │ fetch → qualify → resolve (rules-only)         │
                └───────────────┬────────────────────────────────┘
                                ▼ verbatim mentions, threads, watermarks
                        ┌──────────────┐
                        │   Supabase   │  ◄── the single source of truth
                        └──────┬───────┘
                               ▼
                ┌────────────────────────────────────────────────┐
                │ Mac launchd (daily 07:30 UTC) worker/daily_mac │
                │ classify (Codex fleet) → score → prune history │
                └───────────────┬────────────────────────────────┘
                                ▼ POST deploy hook
                        ┌──────────────┐
                        │Vercel rebuild│ ── redditindex.com (static)
                        └──────────────┘
```

## What's here

| Path | What |
|---|---|
| `app/`, `components/`, `lib/` | The Next.js site (static, direct SQL to a read-only role, no anon key) |
| `worker/` | The pipeline: harvest, resolve, classify, score, load, verify, the daily worker |
| `data/` | The taxonomy, brand gazetteer, subreddit mapping, and their generators |
| `supabase/migrations/` | The schema: partitioned mentions, sentiment, scores, RLS + published views |
| `scripts/gates/` | Build gates — trade dress, contrast, palette constraints, CSS law, slugs — each proven to fail when violated |
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

## Operating it

```bash
pnpm build                            # site + all gates (pre and post)
node scripts/gates/__selftest__.mjs   # prove each gate fails when violated

worker/backfill_100.sh                # the full backfill chain (resumable)
worker/daily_mac.sh                   # the Mac half of the daily loop, manually
python3 worker/daily.py --dry-run --only sysadmin   # test the fetch, write nothing

python3 data/discover_v2.py --stage status    # subreddit discovery/qualification
python3 worker/depth_run.py --days 90         # the 90-day depth sweep, all categories
python3 worker/depth_run.py --status          # per-category progress table
python3 worker/sweep.py --days 90 --only crm  # one subreddit, by hand
```

Everything verbatim lives in Supabase at all times: mention bodies, authors,
permalinks, labels, scores. The site is a rendering of that database, and
every number on it can be clicked through to the Reddit comment that
produced it.

Start at [HANDOFF.md](HANDOFF.md) for the build history and every recorded
deviation from the original design documents.
