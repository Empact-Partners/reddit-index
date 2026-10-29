# 0041 — Four gigabytes a day for the batch's backfill, and one requester of passes at a time

Date: 2026-10-29. Status: accepted. Decided by Vlad Shvets (the partner-development follow-up batch, 29 Oct 2026
~00:30 Chile), executed by Claude. Amends decision 0035 (the line) for three named days and decision 0026 (who
requests a daytime pass); everything else in them stands.

## What Vlad decided

> "you definitely can publish the same day, the normal process publishes them itself"

and, in the same session, to raise the index's daily egress line from about 2 GB to **4 GB a day for 29, 30 and 31
October**, so that decision 0039's backfill (295 core subreddits of the batch's 42 categories) runs in about one or two
days instead of a week: about 6 GB more over the three days, inside the org plan's 250 GB (the watchdog projected about
205 GB for the cycle), so no extra bill.

## Where things stood (29 Oct, 03:00 UTC)

- The 56 brands of 0039 and the 7 page-less ones have no stored mention; none has a page.
- The sweep was paused 26 Oct and resumed 28 Oct 20:57 UTC. The night of 29 Oct (`9a7a29ef`) collected nothing: 28 Oct
  was the weekly full-backup day and left no room.
- **The day service had started no pass since 24 Oct 15:33 UTC.** Its Railway logs: the pass `b0c62ee1` failed on a
  GLM content-filter refusal and exited 1; Railway marked the deployment crashed and its cron started no tick for 53
  hours, until the next deploy (26 Oct 20:38 UTC). From 26 Oct 21:00 every tick ran and found the sweep switched off
  (the pause), and on 28 Oct 21:04 it found no room (the full-backup day). The fix, a failed daytime pass exits 0
  (#94), merged 26 Oct 23:52 UTC, three hours after that deploy, so it is first deployed with this change.
- The 0039 runner requests backfill passes from the laptop (`ops/day_passes.py`) while the day service requests its
  own. Two requesters collide on the sweep's lock: the loser's receipt reads `skipped`, and `day_passes.py` stopped on
  any receipt that was not ok or capped. It also judged the 24 hours to now, which the passes stopped using on 15 Oct
  (0035): on the morning after a full backup it read no room while the watchdog's day had plenty.

## Decision

1. **A dated line.** `ops/schedule.json` `day_line_overrides` names 4.0 GB for the watchdog's days that start at 07:00
   UTC on 29, 30 and 31 Oct. `worker/meter.py` `day_line_gb` gives the line of the day `now` falls in, and the pass
   (`run_daily`), the tick (`day_tick`), the night's room and the laptop's passes all read it there. The day that
   starts at 07:00 on 1 Nov is back on `day_line_gb` (1.9) with no change to make. 05:30 to 07:00 on 29 Oct is still
   28 Oct's day, on 1.9.
2. **One requester at a time.** `ops/day_passes.py` keeps each counter reading as `day passes (laptop)`, at least
   every three minutes while it runs. The tick starts no pass while the newest such reading is younger than
   `day.laptop_quiet_minutes` (15); if the laptop stops, the tick resumes by itself. `day_passes.py` waits while any
   run is open, asks again after a receipt that stood aside for the lock, and tries once more after one failed pass.
3. **The laptop judges the line as the pass does**: the watchdog's day with the day's backup and tonight's run held
   (`meter.ledger_from` over the readings of the last four days), not the 24 hours to now. When the room is used it
   waits for the next watchdog's day if that starts before `--until`.
4. **Same-day pages.** After every backfill pass a laptop job (outside this repository, under launchd) drains
   `site.dirty_brand`, scores and publishes with `--max-expire 300 --verify 300`, new pages first, so a brand's page
   appears the day its first mention is labelled instead of after the next night. It does not run between 23:30 and
   05:30 UTC (the night refreshes and publishes then) and not when the day's room is under 0.3 GB.

The egress watchdog (command-center `supabase_watchdog.py`) is told the same three days, so a deliberate 4 GB day does
not message Vlad (his rule: a message only when a person must act).

## What it costs

At most 4.0 GB on each of the three days on the node counter, the line the passes stop at. Measured backfill passes
(7 Oct, before the six-hour checkpoints of 0036 halved what a mention sends): 55 subreddits and 13,300 mentions in 150
minutes, 0.22 GB on the run's estimate.

## How it is judged

The watchdog's readings for 29, 30 and 31 Oct under 4.0 GB, and 1 Nov's under 2; every 0039 subreddit in a receipt's
`stages.backfill.done`; each batch brand's page live the day its first labelled mention is stored.
