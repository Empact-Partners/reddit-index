# Reddit Brand Index

**Live: [redditindex.com](https://redditindex.com)** (noindex while provisional).

## STATUS (kept current; last edit 2026-10-11 13:10 UTC)

| | |
|---|---|
| **Live?** | **Yes, refreshing daily.** redditindex.com runs the read path since 2026-10-06 11:25 UTC (decision 0017). Last successful night run 11 Oct 04:46 UTC: the footer, `/freshness.json`, `/llms.txt` and the sitemap show it. Noindex while provisional. |
| **How it updates** | Nothing of it runs on a laptop. One scheduled run a night at 00:00 UTC on Railway (`reddit-index-sweep`): takedowns, collection, classification, refresh, scores, then the changed pages proven on the site. Daytime passes (service `reddit-index-day`, a tick every 30 minutes) collect and label while the last 24 hours stay under the egress line. The three generated files refresh on their own timers (5 min, 1 h, 1 h; decision 0022), because an expiry never reached them. |
| **Labels** | Queue empty on 10 Oct 22:45 UTC: 1,212,699 labels. Jev settles what it can, GLM-5.3 the rest again since 10 Oct 16:00 UTC (the Claude Max lane ran 9-10 Oct while GLM's allowance was used up; decision 0021). |
| **Cost** | A 2 GB daily line of database egress for every job together; passes stop at 1.9 GB in any 24 hours. **11 Oct went over: 2.42 GB by midday** (the last de-duplication run, 0.8 GB, was shipped a second time by the 11:15 backup, and the guard was on a sleeping laptop); the watchdog posted at 07:04 UTC. Daytime collection is stopped until the 24 hours clear. Since then the pass guards the line itself (decision 0025), the meter is read compressed, and checkpoints are hourly (6.4 KB of log a new mention against 10.0). |
| **Pages** | Until 11 Oct the publisher sent 1,000 changed pages a night of about 5,700, so the median page was 3.1 days behind its data. A page costs about 20 KB of database egress, not the 0.2 MB the cap assumed (measured 11 Oct), so from the night of 12 Oct every changed page goes out every night (decision 0024). |
| **Storage** | 9 Oct: the old site's rail view dropped (3,774 to 3,554 MB), retention steps 1 and 2 run every night, step 3 (one copy of each comment's text) finished on 11 Oct, every partition verified. The database is 3,644 MB on an 8.4 GB disk; the freed space stays inside the tables (handing it back would cost about 1.5 GB of egress for disk nobody is short of). 10 Oct: retention runs as a stage of the night sweep, and an index nothing read was dropped (migration 0031). The old collector's Railway service is deleted. |
| **Open** | A dedicated Reddit API app for the index is the owner step that doubles collection. |
| **How to stop everything** | `python3 ops/ri.py stop "reason"` turns the sweep off and its database login off. |

A public index of what Reddit actually says about software brands: one
**Reddit ❤️ Score** (0-100) per brand per category, computed from verbatim
Reddit comments and posts — a post counts as its title plus its body — every
one of them stored, classified, and linkable back to its source. Built by
[Empact Partners](https://empact.partners).

```
 00:00 UTC, Railway service reddit-index-sweep (ops/schedule.json; hard stop 05:30)
   │  worker/run_daily.py, one receipt in public.pipeline_runs, stop switch public.sweep_control
   ▼
 1 takedowns   worker/takedown.py      every card on the site re-probed; deleted or edited comments purged
 2 collect     worker/collect.py       the core subreddits first; caps 15,000 Reddit calls, 40,000 mentions
 3 classify    worker/classify_sweep.py  Jev first, GLM-5.3 on what Jev cannot settle (decision 0017)
 4 refresh     site.refresh_brand()    one row per company page in schema `site`, recomputed in Postgres
 5 score       worker/site_score.py    scores and ranks stored, so a board and a page cannot disagree
 6 publish     worker/site_publish.py  changed pages expired, fetched, and their hash proven on the site
 7 retention   ops/retention.py        steps 1 and 2 of docs/retention.md, archive first
   │
   ▼
 redditindex.com (Next.js on Vercel): every page reads one row of schema `site` and changes only when step 6
 names it; /freshness.json, /llms.txt and /sitemap.xml refresh on 5-minute and hourly timers (decision 0022);
 a build happens only on a code change (scripts/vercel-ignore.sh)
```

The whole index shares one daily line: **2 GB of database egress**, measured on the node transmit counter (the
number the Supabase watchdog and the bill follow). A normal night is about 0.6 GB. One command stops everything:
`python3 ops/ri.py stop "reason"`.

What runs on the laptop, and only there: migrations (`ops/migrate.py`), deploys (`ops/deploy_sweep.py`),
retention step 3 (`ops/retention.py one-copy`), and until 14 Oct 2026 the labelling lane for what Jev cannot settle,
on Claude Sonnet 5.5 through Vlad's Max plan while GLM's allowance was used up (`ops/codex_lane.py --model claude-sonnet-5-5`, decision 0021; GLM is back since 10 Oct). Daytime passes
are requested on Railway by the index's second service (`reddit-index-day`, `ops/day_tick.py`, every 30 minutes, decision 0026; `ops/day_passes.py` requests one by hand) and collect from 06:15 to 23:15 UTC at most 45 Reddit
calls a minute and label what they collect (the night refreshes, scores and publishes it): the night reaches
only 300-400 of the subreddits it plans, and collection is most overdue first, so the day reaches the rest. The map
names 5,568 subreddits; 4,991 are distinct (576 appear under two spellings and are one visit since 11 Oct), and the
vendor-named ones, whose mentions the database refuses, are not visited. The collect receipt says where its time
went (`seconds`: waiting for Reddit, matching, the database and the rest, and what the requests themselves spent).
Comment trees can be fetched a few at a time (`collect.tree_workers` in `ops/schedule.json`, 1 to 4; Reddit still
sees one request start per pacing period). It is 1 until measured: a daytime pass takes its width from the number in
`~/Library/Logs/reddit-index/tree-workers` when that file exists, so two passes of one day can be compared. A pass stops itself when the database has sent 1.90 GB in the 24 hours to now, read by the pass on the node counter every three minutes (decision 0025; until 11 Oct only the laptop held that guard, and it slept). A physical backup at about 11:15 UTC every day ships the pages changed since the last one: a bulk rewrite is paid again there. The 90-day backfill of the partner
categories finished on 9 Oct.

## What's here

| Path | What |
|---|---|
| `app/`, `components/`, `lib/` | The site. One file opens a database connection (`lib/data/site-db.ts`), as a role that can read schema `site` only; `scripts/gates/bounded-reads.mjs` fails the build otherwise |
| `worker/` | The sweep: `run_daily.py` and what it imports (`takedown`, `collect`, `daily`, `harvest`, `sweep`, `resolve`, `classify_sweep`, `rubric`, `site_score`, `numerics`, `site_publish`, `reddit_client`, `db`). Everything else in the folder is the old pipeline; see below |
| `ops/` | Running it: `schedule.json` (the one schedule), `deploy_sweep.py`, `migrate.py`, `ri.py` (stop/start), `day_passes.py`, `retention.py`, `codex_lane.py`, `alias_blocklist.py`, `go_live.py` |
| `data/` | The taxonomy, the brand gazetteer, the subreddit map, the alias blocklist |
| `supabase/migrations/` | The schema, applied by `ops/migrate.py` (ledger: `public.schema_migrations`) |
| `scripts/` | Build gates (`gates/`, each proven to fail by its self-test) and the investigation script |
| `decisions/` | Every ruling; 0017 (the daily sweep) to 0028 (the takedown check's slow lap by position) describe today's system |

## Docs

- [how-the-index-updates.md](docs/how-the-index-updates.md) — the nightly run, stage by stage
- [retention.md](docs/retention.md) — what the index keeps, for how long, and the state of each step
- [investigation-2026-10.md](docs/investigation-2026-10.md) — why the index was frozen and what was fixed
- [methodology.md](docs/methodology.md) — how the score is computed, tiers, floors
- [taxonomy.md](docs/taxonomy.md) — all categories and their scoring subreddits (generated)
- [entity-resolution.md](docs/entity-resolution.md) — how a word becomes a brand mention (and when it refuses)
- [sentiment.md](docs/sentiment.md) — the four-way verdict
- [worker.md](docs/worker.md) — collection: fetch algorithm, watermarks, failure matrix
- [go-live/RUNBOOK.md](docs/go-live/RUNBOOK.md) — how the read path went live on 6 Oct 2026

## Operating it

```bash
python3 ops/ri.py stop "reason"         # the one-step stop (sweep off, its database login off)
python3 ops/deploy_sweep.py             # deploy the sweep; never while a pass runs (check pipeline_runs)
python3 ops/migrate.py --status         # what is applied; --apply 0030 applies one file in one transaction
python3 ops/retention.py status         # sizes and what each retention step would remove
python3 scripts/schedule_check.py       # every write since the last check matches a receipt

pnpm build                              # site + every gate
pnpm test                               # vitest, the resolver and collection suites, the sweep units
```

### The old pipeline: do not run these

`worker/update.sh` and the files `run_daily.py` does not reach (`classify_api.py`, `classify_codex.py`,
`classify_daily.py`, `classify_daemon.py`, `score_db.py`, `delete_sync.py`, `healthcheck.py`, `publish.py`,
`publisher.py`, `leases.py`, `collector.py`, `depth_run.py`, `pipeline.py`, `run_scoring.py`, `watchdog.py` and the
rest) are the manual, laptop-run pipeline of August 2026 (decisions 0010 and 0016, superseded by 0017). They
read and write the same database without the sweep's caps, receipts or stop switch.

## Two facts about what the site shows

**Who is on a board.** Every brand with a score is ranked on its primary category's board; score, rank and board
size are computed by the sweep (`worker/site_score.py`) and stored, so a board and a company page cannot disagree.
The pooled "All Categories" board also demands at least 10 opinionated mentions (`lib/data/boards.ts`), because
ranking across the whole index is a bigger claim than ranking inside one category. The live methodology page
(redditindex.com/methodology) is the authority on gates and floors.

**A company page shows a window of its mentions, and says so.** The rails are
the 80 newest comments and the 40 newest posts per brand — two rails, one per
document type, because a single newest-N window left post-heavy brands with a
Posts filter over noise. The stat tiles, the Posts/Comments filter counts and
the subreddit ledger are computed over the WHOLE corpus, not over that window.

Everything verbatim lives in Supabase at all times: mention bodies, authors,
permalinks, labels, scores. The site is a rendering of that database, and every
mention it renders links back to the Reddit comment or post that produced it.

The build history and every recorded deviation from the original design documents: [HANDOFF.md](HANDOFF.md)
(to August 2026) and `decisions/` (since).
