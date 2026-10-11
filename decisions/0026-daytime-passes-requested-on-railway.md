# 0026 — The daytime passes are requested on Railway, not from a laptop

Date: 2026-10-11. Status: accepted (the commission: one bounded daily job off the laptop).

## Context

Since 6 Oct the daytime passes ran on Railway but were requested, one after another, by a script on a laptop
(`ops/day_passes.py`, decision 0017's amendment). The laptop slept on 11 Oct while on battery: no pass was requested
for as long as it slept, and the guard it held was asleep with it (decision 0025). A restart of the laptop ends the
script until someone starts it again.

## Decision

A second Railway service in the index's project, `reddit-index-day`, the same image as the sweep with another start
command (`ops/day_tick.py`) on its own cron, every 30 minutes from 06:00 to 21:30 UTC.

A tick:

1. reads the database node's transmit counter and keeps the reading (`public.egress_counter`);
2. starts nothing outside 06:15 to 21:30 UTC, beside a run or a retention step, when the sweep is switched off, or
   when the counter cannot be read or no reading is 24 hours old;
3. starts a pass when the database sent at least 0.15 GB less than the day's line (1.9 GB) in the 24 hours to now:
   it writes the request row and becomes the pass (`worker/run_daily.py` in the same container), capped at
   (room - 0.05) / 1.25 on the pass's own estimate, ending by 23:15 UTC.

Railway does not start a cron execution while the one before it still runs, so a pass in progress is never
doubled; the sweep's lock covers the night's run. A pass stops itself at the line on the counter (decision 0025).

`ops/schedule.json` declares the service (`day`), `ops/deploy_sweep.py` deploys both services from one build
folder, and `scripts/schedule_check.py` fails if the day service is missing, carries another cron, or does not
start the tick. Migration 0034 lets the sweep's login write the request row.

## What this replaces

`ops/day_passes.py` stays as a tool to request one pass by hand. The laptop runner that looped over it until 31 Oct
(`~/Library/Logs/reddit-index/day-collect.sh`) is stopped once the service has run its first pass. The laptop is
no longer part of the daily collection: it deploys, and it reads.

## How it is judged

12 Oct: ticks in the service's log every 30 minutes; the first pass starts on its own once the 24 hours since
11 Oct's overage have cleared (about 12:20 UTC); no day over 2 GB on the watchdog's reading.
