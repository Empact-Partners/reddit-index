# 0032 — Mentions waiting for a label come before new ones

Date: 2026-10-13. Status: accepted (the commission: full speed under the egress line).

## Context

Under the comment listing (decision 0029) a run's collection ends when its room for new mentions is used, the room
being what its egress cap can carry once each new mention is collected and labelled (13 KB a mention). Two things
were missing:

1. **The mentions already waiting for a label.** Labelling one costs about 3.8 KB of the run's estimate (12 Oct:
   40.9 MB of log and 28.1 MB read for 18,177), and the room ignored them, so a run could collect its full room on
   top of any queue.
2. **GLM's peak hours.** The classifier labels nothing from 06:00 to 10:00 UTC (Z.ai's peak, the estate's rule):
   on 13 Oct the 06:32 pass collected 23,958 mentions in 109 minutes and labelled none, and the 08:30 tick started a
   second pass that could only add to them.

## Decision

1. **The waiting mentions take their share of the room first**: each counts as `label_bytes_per_mention` (4,000)
   over `bytes_per_mention` (13,000) of a new one (`collect.room_after_queue`), by night and by day. A run with no
   room left visits no subreddit and says so on its receipt (`no room for new mentions this run: N wait to be
   labelled first`), a planned end. The receipt carries `labelling_queue`.
2. **In the peak hours no daytime pass starts while 20,000 or more mentions wait for a label**
   (`day.peak_queue_max`, `ops/day_tick.py`). With a shorter queue a pass still starts: it collects, and its mentions
   are labelled by the first pass after 10:00 UTC or by the night.

## What is given up

Some collection in the morning when the queue is long; the same egress then goes to labelling, so the day's total
under the 1.9 GB line is unchanged and the site's pages, published by night, carry fewer unlabelled mentions.

## Review

An independent read by Codex (gpt-6-astra, read-only, no search; GLM was in its peak hours) found one fault, taken:
the queue was counted whole, but an entry tried five times waits for a person and the classifier never picks it
again, so enough of them would have held the room at zero on every run. Both places now count what the classifier
still takes (`classify_sweep.LABELLABLE_SQL`, `attempts < 5`).
