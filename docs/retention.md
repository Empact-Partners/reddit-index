# What the index keeps, for how long, and why

Written 2026-10-03. Numbers measured on the database that day. Code: `ops/retention.py`.

## The rule

Keep what a page shows, what a score counts, and what the next stage needs. Keep nothing twice. Before anything
is deleted, copy it into the `archive` schema of the same database, check the copy's row count, and keep the copy
14 days; the managed daily backup (about 11:15 UTC, seven kept) is the second copy.

Never touched by this policy: the takedown ledger (`public.removals`) and anything `01-legal.md` governs; text a
page shows (the no-truncation rule); the views the 15,000-company lookup reads (`published.*`), which keep their
names, columns and results.

## Where the space is (3,007 MB in all, 2 October)

| What | Size | Needed? |
|---|---|---|
| Mention text | 1,965 MB | One copy per comment is needed: 828 MB. The other 1,137 MB is the same comment stored again for every other brand it mentions |
| Rows already judged "not this product" | 225 MB of their text (174,384 rows) | Not shown, not counted. Kept 30 days so a wrong rule can be undone, then removed |
| Threads with no mention, older than seven days | 40 MB (168,637 rows) | No. A thread is kept to revisit its comments for 48 hours; one that never produced a mention is never read again |
| The old site's rail view (`mention_rail_mv`) | 231 MB | Only by the old site. Dropped one week after the new read path is live |
| Old text by age | about 60 MB before September 2025 | Kept: almost everything was collected May to October 2026, so trimming by age frees nothing worth the risk |

## The steps, in order

| Step | What | Saves | When | State (9 Oct) |
|---|---|---|---|---|
| 1 | Prune threads with no mention, older than 7 days (archive first) | 40 MB now, about 1 MB a day after | nightly, the sweep's `retention` stage | ran by hand 4 Oct (177,292 threads); nightly from 10 Oct |
| 2 | Remove mention rows judged "not this product" more than 30 days ago (archive first; the ledger row stays) | 225 MB from 2 November, then as it accrues | nightly, at most 20,000 rows a night | nothing qualifies before 2 Nov |
| 3 | One copy of each comment's text: keep it on one row per comment, clear it on the others; readers take the text from that row; a trigger stops new duplicates | about 1.1 GB, and halves daily growth | once, in chunks of one monthly partition, inside a declared egress budget | the trigger is live since 0019; the clearing runs from 9 Oct |
| 4 | Drop `mention_rail_mv` | 231 MB | after go-live | done 9 Oct (migration 0030): `published.mention_rail` reads `site.rail_card`; the database went from 3,774 to 3,554 MB |
| 5 | Vacuum the touched partitions so new rows reuse the space | | after 2 and 3 |

Why step 3 clears text in place rather than moving it to a new table: a new table would write 828 MB again (and
ship that through the write-ahead log, which the egress counter bills); clearing a column writes only the new,
small row version. The space is reused by new mentions rather than returned to the disk, which is what the index
needs: 4.7 GB of the 8.4 GB disk is free.

## Budget for step 3 (declared before it runs; revised 9 Oct on its first run)

First run, 9 Oct 15:46 UTC: 171,672 rows of the September partition cleared, every page's text and the lookup
job's counts identical before and after, for **0.763 GB** of egress on the node counter: 4.4 KB a cleared row, the
write-ahead log of the new row versions. The 1.0 GB estimate was low by half: the remaining 295,601 duplicates cost
about 1.3 GB. The run also overshot its 0.4 GB cap because it read the counter every five minutes; it took the day
to 2.10 GB, over the watchdog's 2 GB line, and the watchdog baseline was re-recorded at 16:00 UTC as planned heavy
work.

From 10 Oct: at most 0.9 GB a day and 2.5 GB in all, and never past the day's 1.9 GB line on the node counter (the
night's run included); the counter is read every 60 seconds. It runs in the morning after the night's run, one
monthly partition at a time. Before and after each partition: the text every page shows (`site.rail_card`) for a
sample of brands, compared word for word, and the counts the lookup job reads (`published.mentions` per brand),
compared exactly. Any difference stops the step and undoes that partition from the archive copy.

## Review and test before step 3 ran (2026-10-04)

An independent review (Codex `gpt-6-astra`, low effort, no web) of this file's code found what step 3 could do
wrong; fixed before it touched production text:

- a row pointing at a row step 3 clears would have lost its text (views follow one pointer). Each chunk now
  re-points such rows at the holder first, in the same transaction. Live data had 0 such rows (the insert trigger
  and step 3 pick the same holder, the lowest brand_id with the text), and 0 dangling pointers.
- the checksum summed the texts alone: a swap between rows or a NULL in place of text would not move it. It now
  hashes each row's key with its readable text; a dangling-pointer count is checked after every partition.
- a restore now puts back exactly the rows this run cleared (remembered in a temporary table), and a restore that
  does not verify fails the step loudly.
- `abs(hashtext(...))` overflowed on one value; every step's egress is measured on the node counter and recorded
  on its receipt; `archive.mentions.body` is nullable (migration 0022), or `rejected` would have rolled back.

Tested on a scratch sample inside the database (temporary tables write no write-ahead log, so no egress): 3,330
rows of the September partition, 1,125 of them (34%) word-for-word copies of another row's text. Run 1 cleared
1,125 and re-pointed a planted chain to the holder, readable text identical; run 2 changed nothing; a forced
restore put back 1,126 rows and verified.
