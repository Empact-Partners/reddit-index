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

Expected: healthcheck may grumble about run size (`MIN_RUN_MENTIONS=200`) on a tiny rehearsal — that's the bound, not a defect.

## Cost (DeepSeek, the only metered stage)

- **~$0.18 per 1,000 items.** A weekly-scale backlog (~30–50K items) ≈ **$6–9**. Reference: the 153,748-item historical backlog cost $27.22 (112 min, zero truncations).
- Key: auto-resolved from `~/.claude.json` (the parked `deepseek` MCP entry). If classify exits 1 immediately, the gate/key message above it says which it was.
- The classify stage prints its own running spend estimate (`SPEND`), and stage 2's summary line is the number to note.
- `qa_audit.py` (manual QA tool, not part of this chain) also spends DeepSeek credit ungated — know that before running it.

## Cadence guidance (not automation)

**Run at least weekly.** Collection is the only stage that loses data to waiting (decisions/0010): past ~7 days, `/new`'s reach is outrun by ~1 subreddit in 49 and threads leave the 72h comment-revisit window; past ~14 days, ~3 subs. Classify/score/publish lose nothing to waiting, ever.

## When something fails

**Re-run `worker/update.sh`.** Every stage is idempotent: collect resumes from watermarks, classify is an anti-join (already-labelled items are never re-paid; on-disk caches also skip entity-rejects), score is a full recompute, delete-sync walks a cursor, publish is a rebuild. There is no partial-state cleanup, ever.

- Chain is **not `set -e`**: one failed stage doesn't abort the rest — the site still publishes with the data it has. Check each `… exited N` line.
- classify exit 2 = argparse (flags bug) — nothing was labelled; exit 1 = gate/key refusal.
- publish fallback fires automatically (git empty commit → Vercel builds every push).
- DeepSeek down? One-off fallback: edit nothing, run `python3 worker/classify_api.py` (bare = 16 Haiku CLI workers on the Max plan) — knowing it draws the shared Claude quota. That trade is yours to make in the moment, not a default.

## What was retired (2026-08-18)

Seven launchd lanes (collector, classifier, publisher, watchdog, keepawake, daily, health → plists in `worker/launchd/retired-2026-08-18/`), the Railway collection cron (service Offline; `railway.json` cron removed), `daily_mac.sh` (chain lives inside `update.sh`), and the `claude-rq` auto-resume daemon (post-mortem: `~/.claude/scripts/retired/resume-on-reset-RETIRED-2026-08-18/RETIRED.md`). **Never reintroduce a scheduler or auto-resumer here without a new ruling — decisions/0010.**
