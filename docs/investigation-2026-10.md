# What the Reddit Index actually did, August to October 2026

**Written 2026-10-02. Read-only: nothing in the database, the site or the schedule was changed to produce it.**
Every number comes from [`scripts/investigation_2026_10.py`](../scripts/investigation_2026_10.py), which
recomputes all of it into flat files under [`investigation-2026-10/`](investigation-2026-10/). The one change made
the same evening, stopping the collector, is recorded in the addendum to
[decision 0016](../decisions/0016-frozen.md), not here.

## The findings, in one screen

1. **It was collecting every night and nobody knew.** One Railway deployment ran the collector at 02:00 UTC on 45
   consecutive nights, 19 August to 2 October, including the night after it was "frozen". It stored 672,528
   mentions after the last time anything was scored.
2. **Nothing downstream of collection ran after 25 August.** No sentiment labels, no scores, no purge of deleted
   comments. 959,245 of 1,437,879 stored mentions (67%) have no label. Rankings on the site are the 25 August
   rankings.
3. **The collector was running a 19 August copy of the brand list.** The 4,471 brands added in the August
   expansion received zero new mentions after 1 September. 4,497 of 10,511 brands have no mentions at all.
4. **The cost was the site, not the collector.** The site's database user was sent 3.80 billion rows since
   5 August; every other use of the database combined was sent 0.11 billion. A page regenerating, or a build,
   re-read the whole corpus. The organisation's September cycle closed near 873 GB against 250 GB.
5. **A quarter of what is stored as a "mention" is not about the brand it is filed under.** 155,371 mentions
   (10.8% of the corpus) are links to a parent company's web address filed under one of its products: every
   `github.com` link is a mention of "GitHub Actions". In a hand check, common-word brand names were wrong 30% to
   40% of the time.
6. **The site publishes two different scores for the same brand on the same page**, and neither matches the
   written methodology.
7. **More than half the stored text is duplicate.** 1,965 MB of comment text is stored; one copy per document
   would be 828 MB. The site shows 11% of the rows.

## 1. Was it updating? Day by day

Full series: [`daily_activity.csv`](investigation-2026-10/daily_activity.csv) (one row per day since 1 August),
[`railway_deployments.csv`](investigation-2026-10/railway_deployments.csv),
[`vercel_builds_by_day.csv`](investigation-2026-10/vercel_builds_by_day.csv).

Terms: a *thread* is a Reddit post the collector looked at. A *mention* is one (document, brand) pair it stored.
*Classified* means a sentiment label was written for a mention. A *site build* is a full rebuild of the public
site on Vercel.

| Period | Threads seen per day | Mentions stored per day | Classified per day | Scores computed | Deleted-comment probes | Site builds |
|---|---|---|---|---|---|---|
| 5 to 18 Aug (build-out, by hand) | 600 to 57,000 | 0 to 194,000 | 0 to 222,000 | not recorded | 87,197 on 17 and 18 Aug | 1 to 18 a day |
| 19 to 25 Aug (expansion) | 7,000 to 19,500 | 15,000 to 62,500 | 0 to 16,726 | 25 Aug (5,724 rows) | 35,900 / 36,900 / 103,152 on 21, 24, 25 Aug | 1 to 28 a day |
| **26 Aug to 16 Sep** | 6,900 to 8,900 | 15,500 to 19,300 | **0** | **none** | **0** | **0** |
| 17 Sep | 8,466 | 18,747 | 0 | none | 0 | 2 |
| 18 to 21 Sep | 6,850 to 8,170 | 15,600 to 18,000 | 0 | none | 0 | 0 |
| 22 Sep | 8,128 | 18,301 | 0 | none | 0 | 6 (3 to production) |
| 23 Sep to 2 Oct | 7,060 to 8,670 | 15,900 to 20,100 | 0 | none | 0 | 0 (4 pushes cancelled) |

What started and stopped, and why:

| Date (UTC) | Event | Evidence |
|---|---|---|
| 9 Aug | Railway cron `0 4 * * *` first deployed. The schedule enters through `railway.json`. | deployment `f382c3ad`, manifest |
| 17 Aug | Cron moved to `0 2 * * *`. | deployments `33196b76`, `b2c3f31e`, `6c81a36c` |
| 18 Aug | Decision 0010: "no scheduled jobs". The cron key is deleted from `railway.json` and the deployment removed at 14:11. **No deployment is ever made from the cron-less file.** | deployment `49e4c9b9` removed 14:11 |
| **19 Aug 02:04** | Railway creates a new deployment by itself, reason `redeploy`, manifest still `0 2 * * *`. It runs every night for 43 nights. | deployment `59d502b0`; one run per night in `daily_activity.csv`, first write 02:00 to 02:05, last write 07:37 to 08:53 |
| 25 Aug 18:11 | **Last sentiment label.** 25 Aug 18:41: last score computation. 25 Aug 09:59: last deleted-comment probe. These only ran inside `worker/update.sh`, which a person had to start. Nobody started it again. | `mention_sentiment.scored_at`, `brand_category_scores.computed_at`, `mentions.delete_checked_at` |
| 30 Aug 15:08 | Someone ran the health check. It recorded `error: labels_fresh, backlog`. Nothing followed. | `ingest_state` row `_health` |
| 17 Sep | The page-regeneration leak is fixed (the site becomes fully static). 2 builds. | commit 9287083 |
| 22 Sep 11:37 | **Last site build.** The site has served it ever since. | Vercel `dpl_BccgdBGq` |
| 1 Oct 11:24 | Decision 0016: the deployment is removed again with `railway down`. | deployment `59d502b0` removed |
| **2 Oct 02:01** | Railway recreates it by itself again. 18,155 mentions, 8,258 threads, 2,029 of 2,029 subreddits, finished 07:43. | deployment `434856fe`; `ingest_state` rows `_run`, `_run_coverage` |
| 2 Oct 20:47 | The service is given a do-nothing image with no cron, and the database password it holds is revoked. | deployment `97c81269`; addendum to decision 0016 |

The collector's last receipt reports 2,029 subreddits. The repository's lists hold 2,649. That gap is finding 3:
the image on Railway was built on 19 August, three days before the expansion to 151 categories, and was never
rebuilt. Its brand list had 6,040 brands. See [`quality_brands.csv`](investigation-2026-10/quality_brands.csv):
brands added after 19 August hold 26,335 mentions in total and gained **0** after 1 September, in every class.

## 2. What the site showed against what the database held

[`site_vs_db_summary.csv`](investigation-2026-10/site_vs_db_summary.csv),
[`site_vs_db_per_brand.csv`](investigation-2026-10/site_vs_db_per_brand.csv) (2,643 pages).

| | Served by the site | Held in the database |
|---|---|---|
| Newest mention | 22 Sep 07:52 | 2 Oct 07:31 |
| Mentions | 1,258,315 | 1,437,879 |
| Newest sentiment label | 25 Aug | 25 Aug |
| Scores and ranks | 25 Aug labels | 25 Aug labels |

- **2,643 company pages** have newer mentions in the database than the page shows; 3,371 are unchanged since the
  build. 179,564 mentions are not on the site. The median stale page is missing 4 mentions; the worst
  (`/reddit/`) is missing 20,166.
- **Every score and rank is stale since 25 August (38 days)**: no mention collected after that date carries a
  label, and only positive and negative labels enter the score.
- Earlier, the same thing happened for longer: the commit that fixed the leak on 17 September notes pages had
  been stuck on 27 August data, and `/hubspot/` had been 21.8 days stale while its regeneration kept failing.
- **Deleted comments.** The site says a deleted comment "disappears from here on the next nightly sync"
  (`app/methodology/page.tsx:247-249`). No sync has run since 25 August. Whatever was deleted on Reddit after
  that date and is among the 162,491 cards on the site is still displayed.

## 3. Storage

[`storage_tables.csv`](investigation-2026-10/storage_tables.csv),
[`storage_partitions.csv`](investigation-2026-10/storage_partitions.csv),
[`storage_text.csv`](investigation-2026-10/storage_text.csv),
[`storage_duplicates.csv`](investigation-2026-10/storage_duplicates.csv),
[`storage_indexes.csv`](investigation-2026-10/storage_indexes.csv),
[`labels_by_month.csv`](investigation-2026-10/labels_by_month.csv).

The database is 3,007 MB on an 8.4 GB disk (4.7 GB free), on the smallest compute size (1 GB of memory).

| Table | Size | Rows | What it is |
|---|---|---|---|
| `mentions` (49 monthly partitions) | 2,455 MB | 1,437,879 | one row per (document, brand), with the full text |
| `threads` | 247 MB | 596,878 | one row per Reddit post looked at |
| `mention_rail_mv` | 231 MB | 162,491 | a second copy of the cards the site shows |
| `mention_sentiment` | 147 MB | 481,373 | labels (90 MB of it is indexes) |
| `category_subreddits` | 33 MB | 283,152 | |
| everything else | under 20 MB | | 6 tables are empty and were never used |

- **Growth:** 17,700 mentions and 29 MB of text a day in September. The September partition is 972 MB. At that
  rate the free disk lasts about four and a half months.
- **Duplicate text.** 1,965 MB of text is stored. A document that matches several brands stores its text once per
  brand: 285,804 documents match more than one brand, and one matches 96. One copy per document would be 828 MB,
  so **1,137 MB (58%) is repetition.** No (brand, document) pair is stored twice.
- **What the site reads.** It shows 162,491 rows carrying 211 MB of text: 11% of the rows, 11% of the text. The
  other 1,754 MB of text is read by nothing except the classifier (once) and on-demand exports. The build
  nevertheless read every thread title (596,878 rows) and aggregated every mention, twice per build.
- **Threads nobody needs.** 184,102 threads (31%) have no mention attached.
- **Unlabelled.** August: 478,634 of 869,945 mentions labelled. September: 0 of 531,004. October: 0 of 36,930.
- **Dead rows** are low (39,144 in `mentions`, 75,696 in `threads`); the automatic cleanup is keeping up.
- **Indexes.** One unused index over 1 MB (`mention_rail_mv_key`, 8 MB). `mention_sentiment`'s indexes are
  larger than its data.

## 4. Cost

[`cost_rows_by_role.csv`](investigation-2026-10/cost_rows_by_role.csv),
[`cost_statements.csv`](investigation-2026-10/cost_statements.csv),
[`egress_watchdog_daily.csv`](investigation-2026-10/egress_watchdog_daily.csv),
[`egress_readings.csv`](investigation-2026-10/egress_readings.csv).

*Egress* here means bytes the database server sends out. Supabase bills it per organisation: 250 GB a month is
included for all sixteen Empact projects together, in cycles that start on the 3rd.

**Who was sent the data** (rows returned since the database was created on 5 August):

| Database user | Rows returned | Share |
|---|---|---|
| `site_reader` (the public site's builds and page regenerations) | 3,804,944,686 | 97% |
| `postgres` (collector, classifier, scripts, exports) | 113,588,413 | 3% |
| everything else | 401,125 | 0% |

Two statements make up 93% of the site's rows: "every thread title" (2.36 billion rows over 5,764 calls, about
410,000 rows each time) and "aggregate every mention" (1.19 billion rows). 5,764 calls means the whole corpus was
loaded about 5,764 times in 58 days.

**By cycle and by cause.** Supabase exposes no usage or billing figure through its API, so the cycle totals are
the dashboard readings recorded by the egress watchdog, and the split by cause is an estimate built on them.

| Cycle | Organisation total | Reddit Index's part, by cause |
|---|---|---|
| 5 Aug to 3 Sep | never read from the dashboard | The server's own counter implies roughly **500 GB** left this database before 3 September (1,333 GB since start-up when read on 22 Sep, less about 800 GB for September). The timed regeneration that caused the leak was in the very first build on 5 August, and 155 builds ran in August. Nobody was looking. |
| 3 Sep to 3 Oct | **873 GB** on 2 Oct (819 GB on 21 Sep) against 250 | Page regeneration, 3 to 17 Sep: about **800 GB** (the dashboard read 805 GB on 17 Sep with this project at 97%). Builds on 17 and 22 Sep: about 5 GB (13 builds at roughly 0.4 GB). Nightly collection: about 7 GB (30 nights at 0.24 GB). Idle: about 3 GB. Two weekly spikes: about 2 GB. Scripts and exports: megabytes. |

At the list price of $0.09 per GB the September overage is about **$56** (623 GB). The money was never the
problem. With the spend cap on, the consequence of an overage is that all sixteen projects are restricted; the
cap was switched off on 22 September to prevent that.

**What a normal day costs, measured:**

| State | GB a day | Source |
|---|---|---|
| Idle, nothing connected | 0.09 | two counter readings 303 s apart on 2 Oct; same as 1 Oct |
| A night with the old collector | 0.27 to 0.36 | watchdog, 8 readings |
| The two Thursdays (24 Sep, 1 Oct) | 1.19 and 1.28 | watchdog |

- **The collector's 0.24 GB a day is not data being read.** The collector's own queries return a few megabytes.
  What leaves the server is the write-ahead log: the database produces about 0.34 GB of it a day (19.7 GB in 58
  days), every segment is shipped to Supabase's backup storage, and the collector writes one row per statement
  (2.8 million single-row inserts into `mentions`). The server's counter cannot tell that traffic from data sent
  to a client. So **in the number the watchdog watches, writes cost as much as reads**, and any large rewrite of
  the tables will show up as egress.
- **The Thursday spikes are 0.9 GB above normal, seven days apart, and the 1 October one triggered the freeze.**
  Decision 0016 calls it unattributed. The pattern fits a weekly full backup of a 3 GB database. That is a
  hypothesis; it is tested on 8 October, when the collector is parked and nothing else can explain a spike.
- **Disk and compute:** Micro compute, about $10 a month; 8.4 GB disk, inside the plan.

## 5. Quality

[`quality_hand_check.csv`](investigation-2026-10/quality_hand_check.csv) (my verdict on each sampled mention; no
Reddit text), [`quality_domain_forms.csv`](investigation-2026-10/quality_domain_forms.csv),
[`quality_top_forms.csv`](investigation-2026-10/quality_top_forms.csv),
[`quality_rules.csv`](investigation-2026-10/quality_rules.csv),
[`quality_brands.csv`](investigation-2026-10/quality_brands.csv),
[`ranking_site_vs_methodology.csv`](investigation-2026-10/ranking_site_vs_methodology.csv),
[`ranking_per_brand.csv`](investigation-2026-10/ranking_per_brand.csv).

### Is a mention really about the brand?

I read 200 sampled mentions (191 distinct, 190 judgeable) and asked one question of each: is this text about the
product it is filed under? The sample is stratified by the matching rule that fired, so each line is its own
estimate.

| How the mention was matched | Share of the corpus | Checked | Not about the product |
|---|---|---|---|
| Brand name the gazetteer calls safe, any form | 81% | 29 | **8 (28%)** |
| of which short one-word names (extra sample) | | 59 | 4 (7%) |
| Brand's own web address | 12% | 20 | 0, but 16 of 20 are a bare link or an email address |
| Ambiguous name plus one supporting signal | 5% | 50 | **15 (30%)** |
| Hostile (dictionary-word) name plus two signals | 2% | 40 | **16 (40%)** |

Weighted by each rule's share, roughly **one stored mention in four is not about its brand** (small samples:
read it as 15% to 35%). Two causes account for nearly all of it.

**A parent company's web address filed under one product.** Counted exactly, not sampled:

| Every link to | is stored as a mention of | Mentions |
|---|---|---|
| github.com | GitHub Actions | 54,220 |
| google.com | Google Sheets | 38,952 |
| apple.com | Keynote | 14,024 |
| store.steampowered.com | Steam Game Recording | 12,332 |
| apps.apple.com | Snapseed | 11,550 |
| instagram.com | Edits | 11,414 |
| 32 more (microsoft.com, wordpress.org, mozilla.org, aws.amazon.com, linkedin.com ...) | one product each | 12,879 |
| **Total** | | **155,371 (10.8% of the corpus)** |

These are filed under the "safe" rule, which is why that rule's error is 28%.

**A dictionary word that is also a brand.** From the sample: "snow" as ServiceNow, "pieces" as Pieces for
Developers, "tabs" as Tabs3, "stat" as STAT Search Analytics, "chatbot" as the product ChatBot, "edits" as the
app Edits, "premiere" (of a film) as Premiere Pro, "numbers" as Apple Numbers, "maven" (the Java build tool) as
the course site Maven, "TPM" (the security chip) as Team Password Manager, "Sep 11" as Symantec Endpoint
Security, the Dutch word "als" as Across Language Server. The supporting-signal rule does not stop these,
because the surrounding thread is about software either way.

Two further things the numbers show:

- **The word "reddit" on Reddit** is 146,580 mentions, 10% of the corpus, filed under the brand Reddit. Correct,
  and useless as a signal.
- **The old classifier knew.** It marked mentions as "not this product" but the verdict was kept only in a file on
  a laptop that died in August. In the database a rejected mention is indistinguishable from one never looked
  at, and the site counts it as a neutral mention.

### Brands with no mentions

4,497 of 10,511 brands (43%) have none. 3,075 of those are among the 4,471 expansion brands the running
collector never knew about. The other 1,422 are original brands Reddit has not mentioned in the subreddits
watched.

### Does the ranking match the written methodology?

No, in three ways.

1. **Window and scope.** `docs/methodology.md` says a score uses the trailing 365 days in the category's scoring
   subreddits. The number on the page uses every opinionated mention ever collected, in every subreddit. Scored
   both ways with today's labels: the page's way scores 5,136 brands, the documented way 3,535. Across the 118
   categories with at least ten brands scored both ways, the two top-tens share 8.2 brands on average (as few as
   4), the number one is the same in 89, and one brand moves by 33 points.
2. **Two scores on one page.** The page body shows the all-time score. The page's description, the text search
   engines and link previews show, takes the windowed score stored on 25 August. Notion's page says 48 / 100 and
   its description says "scored 40/100". HubSpot 53 and 54, GitHub 68 and 62, Supabase 61 and 57.
3. **The display floor in the methodology is not applied.** The document says a brand needs its category's
   median opinionated count to be ranked. Decisions 0011 and 0012 removed that, and the code ranks every brand
   with a score.

The arithmetic itself is sound: recomputed independently, the positive and negative counts and the page scores
match the live site for all ten brands checked (HubSpot, Notion, GitHub, ChatGPT, Attio, Linear, Salesforce,
Supabase, Vercel, Cloudflare) (`worker/numerics.py`, checked against the site's own test
fixtures).

## 6. Where the documents said one thing and the system did another

Checked against the live systems on 2 October unless marked "from the code".

| The record says | What is true |
|---|---|
| The Railway cron was removed on 18 Aug and the service is offline (`decisions/0010:21`, `HANDOFF.md:23`, `SOP.md:274`, `docs/worker.md:5` and `:415`, `docs/how-the-index-updates.md:20`, `worker/update.sh:4`) | It ran 45 nights after that date. |
| The collector ran "from 2026-08-19 to 2026-10-01" and the index is frozen since 1 Oct (`README.md`, `decisions/0016`) | It ran on 2 Oct as well. `railway down` does not stop it. |
| To undo the freeze, `railway up` and set the schedule on the service (`decisions/0016`, "To undo") | `railway up` of that tree starts a full collection at once, and the service's schedule fields read empty while the cron fires. |
| `docs/worker.md:462` prints a `railway.json` with a cron and calls it the whole configuration | The file has had no cron since 18 Aug. The cron lives in the deployment. |
| Credentials are in `~/.claude/.reddit-index.json` | The file had not existed since the August laptop crash. Railway held the only copy of the database password. |
| Classification runs on DeepSeek (`decisions/0010`) | The DeepSeek key is gone and the provider is retired. Nothing could have classified since. |
| 527 core subreddits of 2,029 (`README.md:25`, `docs/worker.md:28`) | The lists hold 720 of 2,649. The running image used 2,029. |
| 10,510 brands (`README.md:77`); "roughly 8,500" (`decisions/0012`) | 10,511 in the database; 6,040 in the image that was collecting. |
| A score uses the trailing 365 days in scoring subreddits (`docs/methodology.md:38`) | The page score uses everything ever collected (`lib/data/boards.ts:13`, `decisions/0011`). |
| The display floor decides who is ranked (`docs/methodology.md:82`, `README.md:157`) | Dead code since decision 0011. |
| Methodology version 2.2.0 (`lib/format.ts:10`) | `worker/freeze_methodology.py:55` says 2.2.1. From the code. |
| A deleted comment disappears "on the next nightly sync" (`app/methodology/page.tsx:247`); nightly delete-sync is a mandatory condition (`decisions/0002:57`) | Last sync 25 Aug. It only ever ran when a person ran `update.sh`. |
| The non-affiliation notice is in the footer of every page (`decisions/0001:69`, `01-legal.md:115`) | It is rendered on `/methodology` only. From the code. |
| The collector uses credentials separate from every partner-facing system (`01-legal.md:70`, `:77`) | It uses the same Reddit app as every other Reddit tool on Vlad's machine (same client id). |
| `mentions.delete_checked_at` | Exists in the database, in no migration. |
| The extra 0.95 GB on 1 Oct is unattributed (`decisions/0016`) | Same size, same weekday as 24 Sep. Probably the weekly backup; tested on 8 Oct. |
| "Nightly collection alone measured about 0.33 GB a day" of egress | True as measured, but it is the write-ahead log being shipped to backup storage, not data read by anyone. |
| `HANDOFF.md` "tracks drift" (`README.md:82`) | It stops on 18 Aug. |
| Health assertions: 14 (`README.md:123`) or 15 (`SOP.md:20`) | 15 database checks plus 2 site checks. From the code. |

## What this means for the fixes

- The read path, not the collector, is where the cost was. The site must never be able to read the corpus.
- Writes are the second cost, through the write-ahead log. One row per statement, re-stamping wide rows and
  rewriting 2 GB tables all count.
- Brand matching needs two repairs before any score is worth publishing: parent web addresses must stop
  standing in for one product, and "not this product" must be recorded where it survives a laptop.
- The schedule has to be provable from the data, because Railway's own fields were wrong for seven weeks.

## Reproduce

```
python3 scripts/investigation_2026_10.py                 # every series, about four minutes
python3 scripts/investigation_2026_10.py --ranking       # score every brand both ways
python3 scripts/investigation_2026_10.py --egress 300    # idle rate from two counter readings
python3 scripts/investigation_2026_10.py --sample        # redraw the hand-check sample (random; text stays in worker/.cache/)
python3 worker/numerics.py --selftest                    # the score arithmetic against the site's fixtures
```

The watchdog series was copied from the watchdog's own log; the hand verdicts are mine and are in
`quality_hand_check.csv` with the document id of every mention judged.
