# 0023 — Checkpoints every 30 minutes instead of every 5

Date: 2026-10-10. Status: accepted (the commission: keep the index running at full speed, under the 1.9 GB daily line).

## Context

Every page Postgres changes for the first time after a checkpoint is written to the write-ahead log in full (a
full-page image), not just the change. The log is shipped off the database for backups, and that shipping counts toward
the egress the watchdog measures. The index writes a lot: a new mention costs about 20 KB of log, and each mentions
partition carries seven indexes, each touched on every insert.

Measured on 10 Oct, 22:40 UTC, from `pg_stat_wal` and `pg_stat_checkpointer` (both counting since 24 Jul):

| | |
|---|---|
| log records | 67,629,337 |
| of which full-page images | 8,263,828 (12% of records, a much larger share of bytes: each is a whole 8 KB page before compression) |
| log written | 29.7 GB |
| checkpoints | 18,998 on the timer, 70 forced by log volume; one every 5.9 minutes |
| settings | `checkpoint_timeout` 300 s, `max_wal_size` 4,096 MB, `wal_compression` zstd, `full_page_writes` on |

With a checkpoint every five minutes, a page touched in two passes ten minutes apart pays for its image twice. The
collect and classify stages revisit the same index pages and the same `classify_queue` pages for hours.

## Decision

`checkpoint_timeout` goes from 300 s to 1,800 s, set through the Management API's Postgres config
(`PUT /v1/projects/{ref}/config/database/postgres`, `restart_database: false`). It is a reload setting: live at once,
no restart, confirmed by `pg_settings` (`1800`, `pending_restart` false).

- Nothing else changes. `max_wal_size` stays 4 GB, so a burst still forces a checkpoint before the log grows past it.
- The cost: after a crash, Postgres replays up to 30 minutes of log instead of 5 before it opens. A busy half hour
  here is under 200 MB of log, seconds to replay. Disk holds at most the log since the last checkpoint, bounded by
  `max_wal_size`.
- Baseline kept at `~/Library/Logs/reddit-index/wal-baseline-2026-10-10.json` (records, images, bytes, time).

## How it is judged

Over the next three nights and their daytime passes, from the receipts (`wal_mb` per stage) and `pg_stat_wal`:

1. full-page images per record, against 12% before;
2. log per new mention in the collect stage, against about 20 KB before;
3. the day's egress on the watchdog's counter, at a comparable mention count.

If none of the three moves, the setting goes back to 300 s (`PUT` with `"checkpoint_timeout": "300"`) and this record
says so. If they move, the saving goes into more daytime collection under the same line.
