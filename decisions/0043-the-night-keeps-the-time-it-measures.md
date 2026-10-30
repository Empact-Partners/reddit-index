# 0043 — The night keeps the time it measures, proves the site's front first, and always exits 0

Date: 2026-10-30. Status: accepted. Decided by Claude on Vlad Shvets's instruction ("investigate and fix the root
causes", after Railway's crash mail for the night of 30 Oct). Amends the reserves of decision 0024 and the exit code of
PR #94. PR #99 (a page the run's end kept from being fetched is not checked, not failed) stands: it fixed how the end of
the run is counted, this fixes why the run reaches its end.

## What happened

Night of 30 Oct, run `3aa0b5d1`, 00:02 to 05:30 UTC, window end 05:30:

| Stage | Minutes | Note |
|---|---|---|
| Takedowns | 41.5 | |
| Collect | 175.0 | 36,008 mentions, the night's room (decision 0041's line gave it 1.93 GB) |
| Classify | 66.0 | 26,016 labelled, stopped by its own limit, 8,085 left. **First night it used all its time** |
| Refresh | 32.9 | 2,184 brands |
| Publish | 12.1 | 3,452 of 5,062 pages proven, 0 index pages, 0 retired |

## The causes

1. **The reserve was a fixed number and the work had grown past it.** `reserve_minutes_after_classify` = 45 was set on
   11 Oct from refresh 18 minutes and publish 11 minutes at 9 pages a second. By 30 Oct refresh took 33 minutes and
   publish fetched under 5 pages a second, so the two need about 55. Every night since has fitted only because labelling
   finished early. The first night with a full labelling queue ran out of time.
2. **Refresh slowed as the database outgrew its memory.** Micro compute: 1 GB of memory and a 256 MB cache, for a database
   that went from 3.0 GB to 4.6 GB and from 1.44 to 2.38 million mentions in a month. A refresh chunk averages 15.6 s and
   misses the cache on about 6% of its pages, about 1,700 reads a second, which is where its time appears to go. **Why
   publish slowed is not established:** 469 pages a minute on 12 Oct, about 240 since 18 Oct, while the page's main query
   still averages 67 ms and a page takes about 1.7 s across 8 fetchers. Neither is fixed here. A larger compute costs
   money, which is Vlad's call, and its gain is not measured (Small is 2 GB, about $15 a month against $10). The measured
   reserves below hold whichever way these move.
3. **The publisher proved the site's front last.** Retired pages, the home and category pages and the sitemap queued
   behind every company page, so a run short of time proved none of them. A takedown's receipt waits on retired pages,
   and an unproven takedown older than 36 hours fails the night (decision 0002).
4. **The night exited 1 when it failed.** Railway then marks the deployment crashed, and a crashed cron deployment can
   start nothing until the next deploy: the day service lost 53 hours that way (PR #94). A stalled night cron stops the
   takedown duty. `os._exit(3)` at the hard deadline and any error outside the stages had the same effect on both services.

## The change

1. **Measured reserves** (`worker/run_daily.py`, `ops/schedule.json` `time_reserve`). Time kept after labelling = longest
   refresh of the last three nights + slowest minutes a page × most pages changed + 5, at least the schedule's 45, at
   most 150. Collection keeps that plus 30 for labelling, at least the schedule's 105. The receipt's `time_reserve` shows
   what was used. On the receipts of 26, 29 and 30 Oct this is 66 and 105.
2. **Publish order** (`worker/site_publish.py`): takedown pages, retired, home and category pages, sitemap, then the other
   company pages. `not_checked` now also counts the pages whose batch never started (30 Oct: 148 counted of 1,462).
3. **A scheduled run always exits 0**, including the hard exit and errors outside the stages. A run by hand keeps its
   exit code.
4. **The sentinel reads the night's receipt** (`check_ri_night`, `~/.claude/sentinel`), because the crash mail that
   dispatched a fix session no longer comes. From 05:45 UTC: no receipt, a failed one, or one still open at 06:00 opens a
   fix session. It also sees a stalled cron, which no mail ever reported. A pause or a held lock is a receipt, not a fault.

## What it costs

On a night with a long queue labelling stops about 20 minutes earlier: about 8,000 fewer labels that night (about 394 a
minute on 30 Oct). They wait for the day's passes, which label beside their collection (decision 0037). A page shows an
unlabelled mention as neutral until then.

## How to judge it

The night of 31 Oct: receipt `time_reserve.after_classify` about 66, `publish.not_checked` 0, `index_pages_verified` 160,
status ok, `site.meta.last_success_at` moves, no crash mail. If `not_checked` is above 0 again, read which stage grew.
