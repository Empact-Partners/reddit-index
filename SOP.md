# SOP: running the Reddit Index

**The index refreshes itself once a day** ([decisions/0017](decisions/0017-daily-sweep.md), which replaces
0010's "run update.sh by hand" and 0016's freeze). Nobody runs anything for a normal day. This page is what to do
when you want to look, stop it, change it, or catch up.

## What runs, and when

One job, `worker/run_daily.py`, on its own Railway service `reddit-index-sweep` (project `reddit-index`,
Virginia, next to the database), at **00:00 UTC**, inside a window that ends **05:30 UTC**. The schedule is
declared once, in `ops/schedule.json`. Stages, each resumable from what the database says:

| # | Stage | What it does | Bounded by |
|---|---|---|---|
| 1 | takedowns | every comment on a page re-checked against Reddit, then the longest-unchecked; deleted, removed or edited ones purged (`worker/takedown.py`) | 2,000 Reddit calls; a brake refuses to purge if over 15% look gone |
| 2 | collect | new posts and recent comment trees from every scoring subreddit (`worker/collect.py`) | 13,000 calls, 40,000 new mentions, ends an hour before the deadline |
| 3 | classify | new mentions labelled: a rule, then Jev, then GLM-5.3 (`worker/classify_sweep.py`, `docs/classify-backlog.md`) | 60,000 mentions, 3,000 GLM credits, $1 of Jev, never 06:00-10:00 UTC |
| 4 | refresh | every brand whose data changed recomputed inside the database (`site.refresh_brand`) | |
| 5 | score | score and rank every page (`worker/site_score.py`) | |
| 6 | publish | changed pages expired on the site and the ones that must be proven fetched (`worker/site_publish.py`); a takedown's receipt is stamped only after its page was SEEN without the card | 7,000 pages |
| 7 | receipt | one row in `public.pipeline_runs` (stage `sweep`) with every count; the site's "Data refreshed" date | |

Whole run: 50 Reddit calls a minute, 5.5 hours, stops at 0.8 GB of estimated database egress. Vlad gets **one Slack
DM only when a run fails, hits a real limit (the egress cap, an abnormal flood of new mentions), brakes a purge, or
cannot prove a takedown**. Never a daily report. Using up a planned nightly allowance is how a normal night ends
(collection rotates through the subreddits inside its Reddit calls; classification works through the backlog
inside its credits): it is written on the receipt as `allowances_used` and alerts nobody.

## Look

```bash
python3 ops/ri.py status            # switch, login, last runs, queue, next run
python3 scripts/schedule_check.py   # Railway manifests vs ops/schedule.json, a receipt per night, no stray writes
python3 ops/classify_backlog.py --status
python3 ops/retention.py status
```

## Stop, start

```bash
python3 ops/ri.py stop "reason"     # switch off AND the sweep's database login off; the site keeps serving
python3 ops/ri.py start
python3 ops/ri.py publish off       # keep collecting, stop telling the site
```

A running sweep reads the switch before every stage and every 25 subreddits.

## Change it

- Code or schedule: edit, then `python3 ops/deploy_sweep.py`. It builds a clean folder (never the repository
  root, whose `railway.json` belongs to the parked old collector), sets the service's cron, region and restart
  policy from `ops/schedule.json` (Railway ignores them in the file), and deploys. Then run
  `scripts/schedule_check.py`. A deploy does not start a run; the next 00:00 UTC does.
- Database: a numbered file in `supabase/migrations/`, applied with `python3 ops/migrate.py --apply <prefix>`.
  The sweep logs in as `ri_sweep` (grants in 0015/0016/0020, row-level-security policies in 0018); the site
  as `ri_site` (schema `site` only, 5 s timeout). `ops/sweep_role.py --check` proves the sweep's role.
- A run by hand, outside the window: `worker/run_daily.py --manual` (pilot caps: `--max-calls`,
  `--takedown-calls`, `--max-mentions`, `--classify-items`).

## One-time and periodic jobs

- **Classification backlog** (mentions collected 25 Aug to 2 Oct with no label): `ops/classify_backlog.py
  --until 05:30`, inside its declared budget (60,000 GLM credits, $60 of Jev, 1.5 GB egress, 0.5 GB a day). It
  shares the sweep's lock, so run it outside 00:00-05:30 or after the night's run.
- **Retention** (`docs/retention.md`): `ops/retention.py threads | rejected | one-copy <partition> | expire-archive`.

## Before you change how collection runs — READ THE SPEC

`docs/depth-execution-plan.md` is the collection methodology. It specifies Stage 3 in full:
`--days 90`, category by category, classify/score/publish after each so categories come online
whole. On 2026-08-24 that document was NOT read before the 51-category expansion was designed,
and the resulting invented scheme (30-day waves across all categories at once) cost most of a
day. `docs/post-mortem-2026-08-24.md` is the receipt.

Two things that document now states and did not before:

- **`--tree-cap` is mandatory on every sweep.** `sweep.py`'s default is 100000 — effectively
  uncapped — but the shipped index was built at **150 trees per subreddit**, a number that
  lived only in `worker/.cache/depth/mode.json` and appeared in no doc. Omitting it runs ~50x
  the work per subreddit. See `decisions/0014`.
- **Use `data/run_depth90.py`** for a batch of new categories. It reads the cap from the pinned
  mode file and refuses to run if that pin is missing, rather than inheriting the default.

## Adding a brand, or a whole category

There was no runbook for this until the never-replied expansion needed one
([decisions/0012](decisions/0012-never-replied-expansion.md)). The mechanics existed; the
order did not. Both procedures are **hand-run**; the daily sweep only collects for what they produce.

**After any change to `data/` (brands, aliases, subreddits), redeploy the sweep**: `python3 ops/deploy_sweep.py`.
The sweep's image carries its own copy of the brand data; until the redeploy, the new brands are not collected.
(The old collector ran a 19 August image for six weeks and never collected for 4,471 brands added after it.)

**The daily sweep is a Reddit client too.** Never run these hand tools between 00:00 and 05:30 UTC.

**Serialize anything that touches Reddit.** `daily.py`, `sweep.py`, `backfill_posts.py` and
`discover_v2.py --stage evidence` each drive `worker/reddit_client.py`, and a second
concurrent client stacks a second 0.75 s floor over the ~100 req/min app budget. Run them one
at a time. Nothing in this section may be backgrounded alongside another Reddit stage.

### A brand, into a category that already exists

```bash
# 1. append a row to data/brand-seed-expand.csv (or use data/import_roster.py for a roster)
python3 data/gen_brands.py                    # append-only merge, 6 gates
python3 worker/load.py --seed                 # the category row must already exist
python3 data/expansion_status.py --parity     # seed_brands drops missing-category rows SILENTLY
python3 worker/backfill_posts.py              # ~30 min: historical POST mentions, re-resolved
python3 worker/classify_brands.py --slugs-file /tmp/slugs.txt --allow-metered
```

`backfill_posts.py` is the whole historical recovery for a new brand, and it only recovers
posts. Comment bodies are never stored unless they resolved to a brand at collection time, so
a new brand has no comment history and nothing local to re-scan. Comments accrue from the next
`update.sh`. Re-sweeping trees to recover them costs 31+ hours of API time for a number that
arrives free by waiting — don't.

**Always run the parity check.** `seed_brands()` inserts through
`JOIN categories c ON c.slug = v.cat_slug`, so a brand whose category is not seeded is
filtered out of the VALUES join with no error and no warning.

### A category

```bash
# 1. taxonomy row, then colour + icon + the TS module
#    (append to data/taxonomy-100.csv — the file may only GROW; a removal orphans a
#     published page and gen-categories throws on it)
node scripts/gen-categories-100.mjs           # existing rows are byte-frozen; only new placed
pnpm gen                                      # re-stamps CATEGORIES_SOURCE_SHA256
pnpm gates:pre && pnpm gates:post && pnpm test

# 2. the brand roster for it
python3 data/enumerate_brands.py --expand --only <slug>
python3 data/gen_brands.py

# 3. subreddits  [REDDIT API — serialize]
python3 data/discover_v2.py --stage enumerate --category <slug>
#   ... evidence, rescue, siblings, candidates, then qualify --dry-run before the real one

# 4. core subs — ADDITIVE, never the global mode
python3 data/select_core_subs.py --add-categories <slug>[,<slug>...] --apply

# 5. seed, then depth  [REDDIT API — serialize]
python3 worker/load.py --seed
# --tree-cap is MANDATORY. sweep.py's default is 100000 (effectively uncapped); the
# shipped index was built at 150/sub. Omitting it runs ~50x the work per subreddit —
# see decisions/0014 and docs/post-mortem-2026-08-24.md.
python3 worker/sweep.py --days 90 --tree-cap 150 --only <core subs>
python3 worker/update.sh

# ...or, for a whole batch of new categories, the Stage 3 driver, which reads the cap
# from worker/.cache/depth/mode.json and refuses to run if that pin is missing:
python3 data/run_depth90.py --plan     # category order + cost
python3 data/run_depth90.py
```

**Never run `select_core_subs.py --apply` globally to add a category.** It reallocates the
entire thread budget from scratch and evicts existing core slots to fund the new floors —
existing categories' collection narrows and their scores drift, silently. `--add-categories`
freezes every existing `is_core` row and counts already-core subs as swept, so a shared sub
costs the incremental budget nothing.

**`update.sh` alone is not enough for a new category.** `daily.py` reads `/new` plus a 72 h
revisit window, so a brand-new subreddit launches its board on days of data. One
`sweep.py --days 90` per new category is what gives it a real corpus.

**Colour is a finite resource.** 151 categories sit at min pairwise ΔE 0.0308 against a
0.030 floor. `gen-categories-100.mjs` throws rather than placing a colour it cannot separate,
and that throw is correct — it means the next expansion needs a decisions-level call, not a
code change.

## Fleet safety (added 2026-08-21, after an OOM)

The Mac hit "out of application memory" during this project. The cause was a detached
`/tmp/discovery_chain.sh` looping for hours, resubmitting 25-minute-timeout jobs on top of
in-flight ones, on a box already carrying eight Claude Code sessions. Three rules came out of
it, and they are not optional.

**Preflight before any fan-out.** `~/.claude/scripts/fleet-preflight.py` refuses on swap
>= 70%, load >= 40, a wave larger than the fleet cap, or codex processes already running.
Run it, or import `preflight()`. `data/run_discovery_all.py` does both for you, per stage.

**Reconcile before resubmitting.** A killed Bash call does NOT kill fleet jobs — the harness
SIGTERMs the submitter's process tree while the worker keeps going. Cancel the superseded job
ids first (`fleet_preflight.reconcile()`), or the retry lands on top of live work. That is
precisely how a retry loop becomes a memory bomb.

**One stage per invocation, never a loop.** `data/run_discovery_safe.py --stage <name>` runs
one stage and exits; progress is on disk. A long unattended loop around a fleet is the wrong
shape regardless of how small each wave is.

Supporting facts worth keeping:

- `FLEET_MAX_CONCURRENCY` is **12** in `~/.codex-openai/fleet.env` (was 60). Raise it only
  deliberately, and never while other sessions share the box.
- `MAX_INFLIGHT` in `discover_v2.py` is now `RI_FLEET_WIDTH`. The old hardcoded 40 was
  measured on an idle machine in August; on a loaded one it put **80 enumerate jobs into the
  25-minute timeout with zero completions**. The sessions were starved, not stuck. Widths
  that actually worked here under load: 5 to 8.
- **Two fleet lanes deadlock each other.** Discovery and a brand-expansion run submitting
  into the same slots both stalled, and each driver's "no progress" timer kept resubmitting
  for progress the other was equally unable to make. Serialize fleet lanes the same way the
  Reddit lane is serialized.
- Detached work must use `subprocess.Popen(..., start_new_session=True)`. `nohup ... &` dies
  with the tool call's process-group SIGTERM.
- `caffeinate -i -m -s`, started the same way, keeps a long collection alive through an idle
  screen.
- When the worker reports `codex=unavailable: 'codex --version' timed out`, that is the box,
  not the binary. Do not start a wave.

## Running unattended (decisions/0013)

Two launchd agents exist, and they are not the same kind of thing.

`com.vladshvets.caffeinate` is **permanent**. It keeps the Mac awake with `caffeinate -i -m -s`
under `KeepAlive`. Start caffeinate from inside a tool call and the harness SIGTERMs it when
the call ends — that is how a nine-hour run was lost to the lid-open machine sleeping on mains
power on 2026-08-22.

`com.vladshvets.reddit-index-pipeline` is **temporary and self-removing**. It carries one
already-started multi-day run to its end and then deletes its own plist. It starts nothing
while a lane is alive, is capped at 6 attempts counted on disk (a SIGKILL and a launchd revival
do not reset it), and preflights RAM before each attempt. This is the narrow exception to
0010's ban on watchdogs; read 0013 before touching it.

**Never `launchctl kickstart` the supervisor while a lane is alive.** It kills the whole job
including its children. Lanes now start in their own session so they survive it, but a
supervisor running older code does not have that yet — check `--status` for a live lane first.
Code edits need no restart: they apply at the next lane spawn.

Two budgets, and the difference matters. `attempts` (cap 6) is the runaway guard for GENUINE
failures. `net_attempts` (cap 40) absorbs dropped links, which are not a bug in the pipeline —
six bad wifi moments must not stop a multi-day run. Which budget a failure charges is decided
from the log TAIL after the fact.

```bash
python3 data/pipeline_supervisor.py --status     # what stage, what is alive, budgets spent
tail -f data/.pipeline/pipeline.log              # the run itself
python3 data/test_pipeline_supervisor.py         # 24 safety checks

# stop supervision by hand
launchctl bootout gui/$UID/com.vladshvets.reddit-index-pipeline
rm ~/Library/LaunchAgents/com.vladshvets.reddit-index-pipeline.plist
```

**After a long run, check the pipeline agent is gone.** It should uninstall itself; if
`launchctl print gui/$UID/com.vladshvets.reddit-index-pipeline` still returns something once
the run is finished, remove it. A supervisor that outlives its job is the thing 0010 bans.

The full sequence it drives, each a finite sequence that aborts rather than retries:
`data/run_discovery_all.py` (subreddit mapping, core selection, seed) ->
`data/run_collection_all.py` (90-day sweep, classify, score, delete-sync, publish) ->
`data/run_finish_all.py` (outreach-pool expansion, wave-2 queues, gates).

## When something fails

Read the DM, then `python3 ops/ri.py status`. Every stage resumes from the database, so the next night's run
picks up where the failed one stopped; nothing needs cleaning up by hand. A run by hand inside a day is safe:
`worker/run_daily.py --manual`.

- No receipt for a night: the schedule did not fire, or the run died before it could write. Railway's
  deployment logs say which (`scripts/schedule_check.py` names the night).
- A takedown not proven within 36 hours: the run says so in its DM. The site page still showed the card when
  it was fetched; the next run expires and fetches it again.
- The brake fired: more than 15% of checked comments looked gone at once. Nothing was purged. Usually an API
  hiccup; if it repeats, look at a sample by hand before lowering the brake.

## What was retired

2026-08-18: seven launchd lanes and `daily_mac.sh`. 2026-10-02/03: `worker/update.sh` (the hand-run chain),
`worker/delete_sync.py` (replaced by `worker/takedown.py`, which never reads a failed batch as "deleted"),
`worker/publish.py` (a full rebuild per update; the site now regenerates only the pages that changed), the
DeepSeek lane (provider retired), and the old Railway collector service (parked on a do-nothing image, its
database password rotated; decision 0016's addendum).
