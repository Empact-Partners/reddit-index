# 0036 — Checkpoints every six hours

Date: 2026-10-15. Status: accepted (the commission: full speed under the egress line). Follows decisions 0023 (5 to
30 minutes) and 0025 (30 to 60 minutes).

## Context

What the database node sends follows its write-ahead log almost byte for byte: the log is shipped off the node for
backups, and the node counter the line is judged on counts it. Measured on 15 Oct, 02:27 to 02:51 UTC, inside the
night's collection, two minutes at a time (`pg_stat_wal` against the counter): 7.0 MB sent for 6.5 MB of log in the
first eight minutes, and the checkpoint's segment shipped the next interval.

Most of that log is full-page images: the first change to a page after a checkpoint writes the whole page. At one
checkpoint an hour, an hour of collection touches nearly every page of the October partition's four mention indexes
(54 MB, about 6,700 pages) and of the queue and label indexes, so each pays its image once an hour whatever the
number of mentions. The checkpoint at about 02:35 UTC showed it: **4,912 full-page images and 16.1 MB of log in the
next two minutes**, against 0.4 to 0.8 thousand images and 1.5 to 2.5 MB in the minutes either side.

| Per mention insert, the sweep's role (`pg_stat_statements`) | log | full-page images |
|---|---|---|
| 3 to 10 Oct, checkpoint every 5 minutes | 10.05 KB | 3.32 |
| 11 Oct, every 30 minutes | 6.36 KB | 1.72 |
| 14 Oct 05:50 to 15 Oct 02:40, every 60 minutes, index dropped (0038) | 3.9 and 6.0 KB (the two forms) | 0.91 and 1.85 |

Each step so far took a large share of the images off; the cost left is the per-checkpoint sweep of every touched page.

## Decision

`checkpoint_timeout` goes from 3,600 s to 21,600 s through the Management API's Postgres config
(`PUT /v1/projects/{ref}/config/database/postgres`, a reload setting, no restart), after the night's run of 15 Oct.

- `max_wal_size` stays 4 GB: a burst of log still forces a checkpoint before it grows past that. Six hours of this
  index's log is under 0.6 GB on its busiest days.
- The cost: after a crash, Postgres replays up to six hours of log before it opens, under 0.6 GB, a minute or two.
- Whether Supabase's backup asks for an immediate checkpoint or waits on a spread one is not visible from here (the
  daily ones complete at 11:15 to 11:21 UTC, 14 Oct's full one at 12:25, its whole upload in 12:21 to 12:25). If the
  longer interval delayed it, `scripts/schedule_check.py` names a backup that moves out of 10:30 to 14:00 UTC
  (decision 0035), and the setting goes back.

## How it is judged

The two mention-insert statements' log and images a row on the day passes of 15 Oct against the table above; the
log of the night of 16 Oct per stage (receipts' `wal_mb`); and, with the line unchanged, more mentions collected per
GB on the counter. If the images a row do not fall, the setting goes back to 3,600 s and this record says so.
