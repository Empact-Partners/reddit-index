# 0010 — Manual on-demand updates; classification on the DeepSeek API

**Status:** Accepted · **Date:** 2026-08-18 · **Decided by:** Vlad Shvets

**Supersedes:** the daily-cadence ruling of 2026-08-17 (HANDOFF, "collect daily, classify daily, publish daily") and the free-Haiku-only classification ruling of 2026-08-17 (`classify_api.py` docstring, README, docs/sentiment.md, docs/worker.md).

## Bottom line

The Reddit Index has **no scheduled jobs**. It updates when a human runs **`worker/update.sh`** — collect → classify → score → delete-sync → publish → verify, run to completion, exit. Classification runs on the **DeepSeek API** (`deepseek-v4-flash`), never on the Claude Max plan. Nothing in this project may auto-fire a Claude session, resume one, or run on a timer.

## Context

Two things forced this on 2026-08-18.

**The auto-resume runaway.** The `claude-rq` daemon (built during this project's development to restart limit-cut sessions at the reset minute) re-fired 153 dead Reddit Index sessions across one day. 97 of 97 resumed sessions hit the usage limit again with **zero completions** — each resume paid ~96K tokens of context re-ingestion for ~4.3K tokens of output before dying at the same spot. Its retry accounting refunded attempts on a mid-run re-cap, making the loop unbounded by construction. CLI-priced cost of the resume fleet: **$513 all-time, $448 of it Opus**, for nothing. The daemon is retired permanently (archive + post-mortem: `~/.claude/scripts/retired/resume-on-reset-RETIRED-2026-08-18/`).

**"Free Haiku" was never free.** The 2026-08-17 ruling put classification on `claude -p` Haiku because it costs no money on the Max plan. But Max-plan Haiku draws from the same 5-hour and weekly quota buckets as all interactive work — and each bare `claude -p` call booted the full MCP fleet and global config, so ~95% of every call's tokens were context, not labels. On 2026-08-17 the Haiku lane alone moved ~715M tokens through the account; across Aug 17–18 Reddit Index was 59–64% of total account token draw, and the weekly gauge reached 56%. The index was crowding out the account that pays for it.

## The decision

1. **All seven launchd lanes retired** (collector, classifier, publisher, watchdog, keepawake, daily, health) — plists archived in `worker/launchd/retired-2026-08-18/`. The Railway collection cron is removed (`railway.json`) and the service taken Offline.
2. **`worker/update.sh` is the only trigger.** It is `daily_mac.sh`'s chain with collection prepended (Mac-side `daily.py`, using the same credential fallbacks) and verification appended. Every stage is idempotent; an interrupted run is re-run by hand.
3. **DeepSeek is the classification lane.** Measured in this repo's own production run of 2026-08-16: **153,748 items in 112 minutes (~1,100 items/min) for $27.22** (~$0.18 per 1,000 items), zero truncations in 1,307 batches, 85% agreement with the reference labels and an identical label distribution — against ~310 items/min for the Haiku CLI lane. It is ~3.5× faster and takes the load off the Claude quota entirely. The `--allow-metered` gate stays in `classify_api.py`: spend is acknowledged explicitly at the call site (`update.sh` passes it), never inherited as a default. The Haiku lane remains as a fallback for a DeepSeek outage.
4. **No replacement automation.** No budget gates, no watchdogs, no schedulers. The ruling is on the mechanism: anything that spends quota without a human pressing enter is out.

## The cost, stated honestly

The 2026-08-17 daily ruling was made for a real reason: collection loss. Its own numbers stand: past ~7 days between runs, `/new`'s ~1,000-post reach is outrun by roughly 1 subreddit in 49, and threads leave the 72-hour comment-revisit window with whatever comments they had; past ~14 days, ~3 subreddits. **Guidance, not automation: run `worker/update.sh` at least weekly to keep collection lossless.** A skipped fortnight costs a sliver of comment depth in the busiest subreddits — accepted as the price of an index that can never again outspend its owner.

## Consequences

- The operating procedure lives in `SOP.md` (repo root). "Update reddit index" = run `worker/update.sh`.
- `worker/daily_mac.sh` removed (its chain lives on inside `update.sh`).
- `healthcheck.py` runs unchanged as the SOP's final stage — its freshness assertions hold immediately after a run. The standalone 3-hourly health job is gone with the rest.
- The published methodology's lane description (`freeze_methodology.py`) now names the DeepSeek engine.
- `qa_audit.py`'s precision section also spends DeepSeek credit (ungated) — manual-only tool, documented in SOP.
