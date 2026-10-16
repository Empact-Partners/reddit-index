# 0038 — The disk on every night's receipt

Date: 2026-10-16. Status: accepted. Follows decision 0036 (checkpoints every six hours), whose cost on the disk it
records.

## Context

Measured on 15 and 16 Oct (Management API `/config/disk/util`, the node metrics, `pg_ls_waldir()`, `pg_stat_wal`):

| | |
|---|---|
| Data disk | 8.42 GB (Supabase's 8 GB, gp3), **6.53 GB used (77.6%)** at 18:08 UTC on 15 Oct, 1.86 GB free at 01:36 on 16 Oct |
| The database | 3,705 MB at 18:10 UTC, 3,730 MB at 01:36 (with 3,578 MB on 14 Oct 05:53 after migration 0038) |
| The log directory | **2,336 MB, 147 segments of 16 MB** |
| Log actually written | 407 MB in the 20.7 hours from 15 Oct 04:52 to 16 Oct 01:36 (`pg_stat_wal.wal_bytes`) |

The log directory is six times the log written. `archive_timeout` is 120 s, so whenever anything is written the
server closes its 16 MB segment within two minutes and starts the next, mostly empty. The counter follows the log
written (0036), not the segments. A checkpoint is due by distance when about
`max_wal_size / (1 + checkpoint_completion_target)` = 4,096 / 1.9 = 2.15 GB of segments have passed: with six-hour
checkpoints (0036) that now comes first, on 15 Oct at 16:15 and 21:39 UTC (requested checkpoints 75 → 77; the
other requested ones are the daily backups). Postgres keeps recycled segments for the next stretch, so the directory
sits between about 2 and 4 GB where it held about 1 GB (`min_wal_size`) at one checkpoint an hour. Decision 0036 said
six hours of log is under 0.6 GB; of log written, it is. Of disk, it is not.

Supabase grows the disk by half when it is 90% used (8 → 12 GB), at most four times in 24 hours and four hours apart,
and the database stops taking writes at 95% when it cannot grow (docs, "Understanding Database and Disk Size", read 15
Oct). 90% of this disk is 7.57 GB: about 1 GB above where it stands, which one stretch of log between checkpoints can
fill. Disk beyond the plan's 8 GB is billed per GB-month, a small fraction of what 0036 saves on the egress line.

Nothing on the index read the disk. A disk that did not grow would have been found by a failed night.

## Decision

1. **0036 stays, and the disk is allowed to grow.** Shorter checkpoints would put the full-page images back on the
   egress line (0036's table) to save disk that costs far less.
2. **Every night's receipt carries `storage`**: the disk's size, free bytes and share used, read from the same node
   metrics text the counter comes from (`meter.parse_disk`, no read of its own), and the database's size
   (`pg_database_size`). Nights only: the disk moves by megabytes a day.
3. **At 92% used at the end of a night, Vlad gets one DM** saying the disk did not grow and how to grow it
   (Project Settings, Compute and Disk). It is a warning, not a problem: the run stays ok and nothing else changes.
   `ops/schedule.json` `storage.disk_warn_used_pct`.

## To watch: the database grows, and so does the weekly full backup

At 60,000 to 85,000 new mentions a day (comment listings by day and night since 13 Oct, 0029), the database grows by
about 100 to 150 MB a day once the space retention step 3 freed inside the tables (11 Oct) is used up: `mentions` holds
2,623 MB for 1.77 million rows (1.46 GB heap, 0.84 GB text out of line, 0.35 GB indexes), about 1.5 KB a row, and
`mention_sentiment` about 0.3 KB more. Nothing of it ages out for a year: the score reads the trailing 365 days and
pages count the whole corpus (`docs/methodology.md`).

Supabase's full backup every seventh day sends about 0.37 of the database on the egress counter (1,285 MB of 3,578 MB
on 14 Oct). Decision 0035 holds max(1.4 GB, 0.37 × the database) on that day. **At about 5.4 GB, near 1 November at
this rate, the full backup alone is the whole 2 GB line**: that day's passes do not start and that night collects and
labels nothing (0035's night room reaches zero; takedowns, refresh and publish still run). One day in seven of
collection, and a busy subreddit can then lose comments past its newest 100 (`stream_gaps` on the next receipts).
Before then the line on a full-backup day is for Vlad: count it over the week, or accept the lost day.

## How it is judged

The night of 17 Oct's receipt shows `storage` with the disk and the database; `scripts/schedule_check.py` stays clean.
When Supabase grows the disk, the next receipt shows the new size and nobody had to do anything. The database's size
night by night against 100 to 150 MB a day decides when the full-backup question above is due.
