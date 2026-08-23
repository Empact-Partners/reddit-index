# SOP — Updating the Reddit Index

**The index has no scheduled jobs** ([decisions/0010](decisions/0010-manual-on-demand.md)). It updates when you run one command. "Update reddit index" means exactly this:

```bash
~/Projects/reddit-index/worker/update.sh
```

That is the whole procedure. The script wraps itself in `caffeinate -i` (safe to close other apps, don't sleep the Mac deliberately), runs six stages to completion, prints a verdict, and exits. Nothing runs afterward, nothing auto-resumes, nothing is scheduled.

## What it runs, in order

| # | Stage | What you'll see | Typical duration |
|---|---|---|---|
| 1 | **collect** — `daily.py --core-only` | per-subreddit lines: threads found, mentions inserted, watermark advance across the 527 core subs | ~2–3 h from a week's gap; minutes if recent |
| 2 | **classify** — `classify_api.py --deepseek 16 --haiku 0 --allow-metered` | batch commits, running items/min, spend estimate | ~1,100 items/min → 30K items ≈ 30 min |
| 3 | **score** — `score_db.py` | category scores written, calibration gate verdict, `load.py --scores`, prune | ~5–10 min |
| 4 | **delete-sync** — `delete_sync.py --limit 60000 --publish-follows` | docs probed, removals propagated (legal condition, decisions/0002 — never skip) | ~2 min |
| 5 | **publish** — `publish.py` | Vercel deployment id, poll to READY (falls back to git empty-commit push if the API refuses) | 10–40 min build |
| 6 | **verify** — `healthcheck.py --json` | 15 assertions + live-site check; **the script's exit code is this verdict** | seconds |

Exit 0 = the site is updated and healthy. Non-zero = read the verify block; the failing assertion names the broken stage.

## Rehearsal (before trusting a change)

```bash
worker/update.sh --rehearse     # ~15 min: 10-min collect cap, 800-item classify cap
```

Expected: healthcheck fails coverage/backlog assertions on a bounded rehearsal — that's the bound, not a defect. Reference rehearsal (2026-08-18, exit chain proven): collect 10.5 min → 1,777 threads / 2,277 mentions / 395 calls, zero errors · classify 410 items / $0.11 · score 4,264 rows (calibration gate quarantined 2 categories, by design) · delete-sync 22,647 docs ~6 min · Vercel publish READY in 5.0 min · total 27 min. Verify correctly flagged what a bounded run leaves undone (`sub_coverage` 5%, `revisit_backlog`, 106K label `backlog`) — the exit code is an honest verdict, not noise.

## Cost (DeepSeek, the only metered stage)

- **~$0.18 per 1,000 items.** A weekly-scale backlog (~30–50K items) ≈ **$6–9**. Reference: the 153,748-item historical backlog cost $27.22 (112 min, zero truncations).
- Key: auto-resolved from `~/.claude.json` (the parked `deepseek` MCP entry). If classify exits 1 immediately, the gate/key message above it says which it was.
- The classify stage prints its own running spend estimate (`SPEND`), and stage 2's summary line is the number to note.
- `qa_audit.py` (manual QA tool, not part of this chain) also spends DeepSeek credit ungated — know that before running it.

## Cadence guidance (not automation)

**Run at least weekly.** Collection is the only stage that loses data to waiting (decisions/0010): past ~7 days, `/new`'s reach is outrun by ~1 subreddit in 49 and threads leave the 72h comment-revisit window; past ~14 days, ~3 subs. Classify/score/publish lose nothing to waiting, ever.

## Adding a brand, or a whole category

There was no runbook for this until the never-replied expansion needed one
([decisions/0012](decisions/0012-never-replied-expansion.md)). The mechanics existed; the
order did not. Both procedures are **hand-run**, like everything else here (0010).

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
python3 worker/sweep.py --days 90 --only <core subs>
python3 worker/update.sh
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
python3 data/test_pipeline_supervisor.py         # 16 safety checks

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

**Re-run `worker/update.sh`.** Every stage is idempotent: collect resumes from watermarks, classify is an anti-join (already-labelled items are never re-paid; on-disk caches also skip entity-rejects), score is a full recompute, delete-sync walks a cursor, publish is a rebuild. There is no partial-state cleanup, ever.

- Chain is **not `set -e`**: one failed stage doesn't abort the rest — the site still publishes with the data it has. Check each `… exited N` line.
- classify exit 2 = argparse (flags bug) — nothing was labelled; exit 1 = gate/key refusal.
- publish fallback fires automatically (git empty commit → Vercel builds every push).
- DeepSeek down? One-off fallback: edit nothing, run `python3 worker/classify_api.py` (bare = 16 Haiku CLI workers on the Max plan) — knowing it draws the shared Claude quota. That trade is yours to make in the moment, not a default.

## What was retired (2026-08-18)

Seven launchd lanes (collector, classifier, publisher, watchdog, keepawake, daily, health → plists in `worker/launchd/retired-2026-08-18/`), the Railway collection cron (service Offline; `railway.json` cron removed), `daily_mac.sh` (chain lives inside `update.sh`), and the `claude-rq` auto-resume daemon (post-mortem: `~/.claude/scripts/retired/resume-on-reset-RETIRED-2026-08-18/RETIRED.md`). **Never reintroduce a scheduler or auto-resumer here without a new ruling — decisions/0010.**
