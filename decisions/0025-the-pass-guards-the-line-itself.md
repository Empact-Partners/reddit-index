# 0025 — A daytime pass guards the egress line itself, on the node counter

Date: 2026-10-11. Status: accepted (the commission: run at full speed, under the watchdog's 2 GB line).

## What happened

| When (UTC) | What |
|---|---|
| 11 Oct 05:45-06:28 | Retention step 3, its last run: 0.797 GB on the node counter, planned and inside its declared budget |
| 06:30 | The first daytime pass starts with a cap of 0.36 GB on its own estimate |
| 07:04 | The watchdog's daily reading: 2.24 GB in the 24 hours to then (10 Oct's daytime passes, the night, step 3). It posts in #empact-operations |
| 11:15 | The daily physical backup completes |
| about 11:30 to 12:13 | The laptop that requests passes and holds the day guard is on battery and asleep |
| 11:55 | The pass ends: 0.251 GB by its own estimate |
| 12:13 | The laptop wakes: 2.42 GB on the counter since midnight |

Since the night's run ended at 05:09 the node had sent 1.93 GB: step 3 0.80, the pass about 0.25 to 0.3, two test
publishes 0.03, and about 0.85 that no receipt carried.

## What was not known

1. **A physical backup runs every day at about 11:15 UTC** (`GET /v1/projects/{ref}/database/backups`: one a day
   since 4 Oct, 11:14 to 11:21). It ships the pages changed since the one before. A bulk step is therefore paid
   twice: once as write-ahead log when it runs, once in the next backup. Step 3 rewrote most pages of the May to
   August partitions at 06:00; the 11:15 backup carried them. The same on 10 Oct: the pass that ran through 11:21
   estimated 0.17 GB while the counter moved 0.73 (the September partition, rewritten on 9 Oct). Every "the
   estimate reads low" on record (6, 7 and 10 Oct) is a pass that ran through the backup.
2. **The watchdog judges 07:00 to 07:00, not the calendar day.** The day guard counted from midnight: a heavy
   afternoon and a heavy next morning each stay under 1.9 GB and add up to more.
3. **The guard ran on the laptop.** A pass caps itself on its own estimate, which cannot see the backup or anything
   else on the node; the counter was read only by the script that requested the pass.
4. **Reading the counter is itself egress**: 165 KB a read uncompressed, once a minute for as long as a pass ran,
   about 0.16 GB a day. It is 18 KB compressed (PR #56).

## Decision

- The sweep reads the node counter itself (`worker/meter.py`, the metrics endpoint with the key in
  `SUPABASE_METRICS_KEY`) and keeps every reading in `public.egress_counter` (migration 0033).
- **A daytime pass stops itself when the node has sent 1.9 GB in the 24 hours to now** (`day_line_gb`), judged on its
  first reading and then at most every three minutes. The 24 hours run from the newest reading at least 24 hours
  old: a gap in the readings makes the window longer, so the figure can only read high. A counter that cannot be
  read stops nothing and is counted on the receipt (`meter.unread`).
- The night's run is never stopped by the line: takedowns are a duty (decision 0002). It reads the counter at the
  start and end of each stage, so its receipt carries what it really sent (`egress_measured_gb`, `sent_mb` a stage).
- The laptop's guard stays as a second one when it is awake, and now takes the larger of the calendar day and the
  24 hours (`ops/day_passes.py used_today`).
- The key: the metrics endpoint of this project answers only the service key (a dedicated secret key answered 401
  and was deleted again). It is a Railway variable of the sweep service, beside the database password it already
  holds.

## Also decided today, on the same evidence

`checkpoint_timeout` goes from 1,800 s to 3,600 s (decision 0023 judged). Per statement, since the change to 30
minutes: the sweep's main mention insert writes 6.36 KB of log and 1.72 full-page images a row (6,793 rows on 11 Oct)
against 10.05 KB and 3.32 before (131,994 rows, 3 to 10 Oct); its second form 10.04 KB and 3.30 against 13.11 and
4.55. The night's aggregate (12.6% of records full-page images against 12.2%) hid it behind step 3.

## Not changed

The 2 GB line, the 1.9 GB guard, what a pass collects, takedowns.

## How it is judged

A daytime pass requested with the line already reached ends at once as capped, with the figure on its receipt
(tested on Railway on 11 Oct, below). From 12 Oct: no day over 2 GB on the watchdog's reading; the size of a normal
day's 11:15 backup read from the readings either side of it.
