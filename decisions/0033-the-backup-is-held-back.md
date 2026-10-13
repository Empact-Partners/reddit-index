# 0033 — The day's backup is held back from the egress line

Date: 2026-10-13. Status: accepted (the commission: full speed under the egress line).

## Context

Daytime passes stop at 1.9 GB sent by the database node in the 24 hours to now (decision 0025, the node's own
counter). Supabase's daily backup, between 11:15 and 11:21 UTC on 10 to 13 Oct, ships the pages changed since the
backup before, and the same counter counts it. No pass held room for it.

On 13 Oct three passes on the comment listing (decision 0029) collected 48,450 mentions and labelled 29,889 between
06:32 and 11:13 UTC, up to the line. The backup then sent 390 MB and the 24 hours to 11:30 read **2.20 GB**; until
the window rolled, no pass could start (1.93 to 1.95 GB from 12:00 to 13:30).

| Backup | Sent by the node since the backup before | Backup | Share |
|---|---|---|---|
| 12 Oct, 11:00 to 11:32 | not read | 249 MB | |
| 13 Oct, 11:13 to 11:30 | 1.556 GB | 390 MB | 0.25 |

## Decision

Before 11:45 UTC, a daytime pass and its tick count the coming backup as already sent: 0.3 of what the node sent
since 11:45 UTC the day before (at least 0.15 GB; 0.4 GB when that reading is missing), `meter.backup_reserve`,
`ops/schedule.json` `backup`. From 11:45 the backup is in the counter and nothing is held. The pass's receipt carries
`meter.backup_held_gb`; the tick logs what it held and why. The night's run is not stopped by the line, as before
(decision 0025). Across a node restart the 24 hours are not known, so no pass starts and a running pass is left to
its own estimate cap (decision 0025, unchanged).

The hold rests on when Supabase runs the backup, so that is checked: `scripts/schedule_check.py` reads the project's
backups and names any of the last three that ran outside the hour before 11:45 UTC, and a gap of more than 30 hours
(10 to 13 Oct: 11:15, 11:20, 11:21).

## What is given up

Morning collection, where the line was already full: on 13 Oct the 06:32 and 08:33 passes would not have started.
The day's total under the line is the same; it moves to the hours after the backup. A larger backup than expected
(a share above 0.3) still lands over the line, and is read on the next day.

## How it is judged

The 24 hours to 11:30 UTC on the next days against 1.9 GB, and the share of each backup against 0.3.

## Review

An independent read by GLM-5.3 (clean clone, read-only), three findings, all taken: the decision claimed a restart
was covered by the default hold, which the callers never reach (corrected: a restart leaves the 24 hours unknown and
no pass starts); the hold trusted the clock alone (the backups' own record is now checked against it); and the tests
of the pass's line depended on the time of day they ran at (the pass's clock is pinned in them, before and after
11:45, and the tick's figure has its own test).
