# 0035 — The line follows the watchdog's day

Date: 2026-10-15. Status: accepted (the commission: full speed under the egress line). Supersedes the clock-only
release of decision 0033 and the 24-hour window of decision 0025; their other parts stand.

## Context

The Empact watchdog (command-center `sync/admin/supabase_watchdog.py`) reads every project's node counter once a day,
at about 07:01 UTC, and speaks when a day's pair of readings comes to more than 2 GB. The index's guard (decision 0025)
judged a different window: the 24 hours to now. Two things went wrong with that on 14 Oct.

**A weekly full backup.** Supabase's daily physical backup normally ships the pages changed since the one before (249
MB on 12 Oct, 390 MB on 13 Oct). On 14 Oct it shipped the whole database: **1,285 MB in four minutes, 12:21 to 12:25
UTC** (its record says 12:25:02), against a 3,578 MB database (0.36). The pass running then stopped at 2.34 GB in the
24 hours, and in a 24-hour window the backup then stood in the way of every pass until 12:25 the next day: nothing ran
from 12:25 to 21:30 on 14 Oct, and the morning of 15 Oct would have stood idle too. The readings before it are
consistent with one every seventh day (the watchdog read 2.33 GB on 8 Oct, the window of 7 Oct).

**The night was never asked to make room.** The night's run is not stopped by the line (takedowns are a duty), and
nothing else held room for it. On the watchdog's day of 14 Oct the node had sent 1.573 GB by 00:52 on 15 Oct, before
the night's collection; with its 30,000 mentions, labelling and publish, the day reads about 2.2 GB at 07:01.

| 14 Oct, watchdog's day (07:00 to 07:00 UTC) | GB |
|---|---|
| passes, 09:02 to 12:25 (18,161 mentions collected, 12,902 labelled) | 0.19 |
| the full backup, 12:21 to 12:25 | 1.285 |
| the night's takedowns, 00:00 to 00:52 | 0.05 |
| the night's collection, labelling, refresh and publish | about 0.6 |

## Decision

**The line is judged on the watchdog's own day**, from the newest counter reading at or before 07:00 UTC (an older one
makes the day longer and the figure higher, never lower). What is still to come in the day is counted as sent
(`worker/meter.py` `ledger`):

- **the day's backup**, until the counter shows it: an interval after 10:30 UTC that sent at least 0.1 GB more than a
  pass sends at its fastest (3 MB a minute; passes measured 1 to 3, backups 249 MB in 17 to 32 minutes and 1,285 MB in
  4). Held: 0.3 of what the node sent since 11:30 UTC the day before, the backup before taken out (at least 0.15 GB),
  or on a full-backup day (every 7 days from `backup.full_last`, 14 Oct) the larger of 1.4 GB and 0.37 of the
  database's size. With no backup seen by 14:00 UTC nothing is held after it.
- **tonight's run**, from 07:00 to midnight: the largest of the last three nights on the counter (00:00 to 06:00
  UTC), at least 0.6 GB.

A daytime pass starts when that leaves 0.15 GB under 1.9 GB (the tick, `ops/day_tick.py`), and stops itself when it is
reached (the counter every 3 minutes, as before).

**The night takes the rest of the day.** At the start of collection the night's room for new mentions is the smaller of
`night_mentions` (30,000) and what the day has left once refresh, score and publish are counted
(`night.publish_reserve_gb`, 0.35; 14 Oct: 0.043 refresh, 0.299 publish), at 13 KB a mention collected and labelled,
less the waiting queue's share (decision 0032). Labelling takes what is left after collection, at 4 KB a label.
Takedowns, refresh and publish always run. A night with no room collects nothing and says why on its receipt
(`collect.room_why`, `night_room`), as a planned allowance, not an alert.

`scripts/schedule_check.py` checks what this rests on: a backup outside 10:30 to 14:00 UTC, a full one (a burst of
at least half of 1.4 GB) on a day the schedule does not call full, or a full day of the last week without one, is a
finding that names the setting to move.

## What it changes

| | 24 hours to now (until today) | the watchdog's day |
|---|---|---|
| a normal day | about the same room: the night was in the window after it happened, now it is held before | same |
| a full-backup day | passes stop from the backup to 12:25 the next day; the night comes on top and the watchdog speaks | passes stop for that day; the night collects only what the day has left; passes resume at 07:00 the next day |
| the watchdog | reads up to 2.2 GB once a week | the line is its own day: it reads under 2 GB unless a backup is larger than held or comes on a day not predicted, and the check names that |

Replayed on the readings of 13 to 15 Oct (`tests/test_sweep_units.py`): on 14 Oct the rule holds the full backup and
tonight's run from the morning, no pass starts, and the night's room is under zero (the night after a full backup
collects nothing); from 07:00 on 15 Oct a pass has about 1.05 GB of room, with 0.24 GB held for that day's backup (0.3
of the 0.79 GB sent since 11:30 on 14 Oct, the full backup taken out) and 0.6 GB for the night.

## What is given up

On a full-backup day, that day's collection: the backup takes 1.3 GB of the watchdog's 2. Over a week this is the
same budget as before, spent so that the watchdog never reads over its line. Only a smaller database makes the full
backup smaller.

## How it is judged

The watchdog's reading each morning (the index under 2 GB a day, every day), the passes from 07:00 on the day after
a full backup (the next on 21 Oct), and `schedule_check.py` with no finding about the backups.
