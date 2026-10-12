# 0027 — The collector does no work that cannot yield a mention

Date: 2026-10-11. Status: accepted (the commission: full speed under the egress line and the shared Reddit app).

## Context

Two things bound collection: the Reddit app the index shares (28 calls a minute by day against a declared 45: the
waits for the app's window were 35% of a five-hour pass) and the egress line (a stored row is shipped in the log and
again in the daily backup). Measured on the daytime pass of 11 Oct (541 subreddits, 8,519 calls, 12,806 mentions):

| | |
|---|---|
| mentions per listing call (621 calls) | 12.9 |
| mentions per comment-tree call (7,898 calls) | 0.61 |
| tree calls for a thread with no comment at all | 1,311 |
| repeat reads of a thread already read, and how many found anything | 1,710, of which 272 |
| threads stored | 10,786 |
| of those, never holding a mention (each: a row written, stamped, a week later archived and deleted) | 7,420 |
| of those, with no comment and older than 48 hours when first seen | 2,049 |
| threads stored whose post was more than 400 days old (a first visit lists a quiet subreddit's last 100 posts) | 1,609, with 1,014 tree calls |
| mentions stored that were more than 400 days old | 1,374 of 12,806 |

The score counts the trailing 365 days and the methodology says the collector pages back to that cutoff
(docs/methodology.md). The nightly retention removed 28,000 threads without a mention on 11 Oct.

## Decision

In the collect stage (`worker/collect.py`):

1. **A post more than 400 days old when listed is not stored and its comments are not read** (`HARVEST_DAYS`; the
   labels cover 400 days). The watermark still passes it.
2. **A qualifying post is stored as a thread only if it names a brand, has a comment, or is under 48 hours old**
   (`worth_storing`). A post with none of the three is a row nobody reads.
3. **A comment tree is read when it can hold something new** (`choose_trees`): a thread never read, when it has a
   comment; a thread already read, when Reddit shows more comments than it had at that read
   (`threads.tree_comments`, migration 0036). The count now comes from the listing just read, for every post on its
   pages; for threads not on them, one `/api/info` call covers up to 100.

Not changed: what qualifies a post, what counts as a mention, the 72-hour window in which a thread is revisited,
24 trees a subreddit a visit, the pace.

## What is given up

Comments on a post with no comment after 48 hours that arrive later still; comments that replace deleted ones
without the count moving; mentions older than 400 days from a subreddit's first visit (they never scored, and
counted only in a page's all-time total).

## Pilot

By hand from the laptop on 11 Oct 20:30 UTC, 60 calls (run `97432c73`): 24 trees read, 10 skipped with no comment,
12 skipped as unchanged, two `/api/info` calls, 22 dead posts not stored, every thread read carries its count, no
error.

## Review

An independent read by GLM-5.3 (clean clone, read-only) found no fault in the collector's new rules and one in their
migration: `threads.tree_comments` had been applied to the database for the pilot, and the night's retention stage
archived threads by position (`insert into archive.threads select moved.*, now()`), so that night's run would have
failed with one value too many. The archive copies now name their columns (PR #60, on the night service since
11 Oct 20:48 UTC, before any night ran on the new schema).

## How it is judged

The first daytime pass on the new code (12 Oct, the day service; the night's run keeps the code before this until
that pass has been read): mentions per call against 1.50, tree calls per subreddit against 14.6, threads stored per
mention against 0.84.

## Judged, 12 Oct

The first daytime pass on it (run `3cdf67d3`, 12:34 to 17:59 UTC, the day service's first, by itself), against the
first pass of 11 Oct on the code before it. Both five hours of collection on the shared Reddit app, one comment tree
at a time:

| | 11 Oct | 12 Oct |
|---|---|---|
| subreddits visited | 541 | 755 |
| Reddit calls | 8,519 | 9,483 |
| new mentions | 12,806 | **28,948** |
| mentions a call | 1.50 | **3.05** |
| comment trees read a subreddit | 14.6 | 11.3 |
| threads stored a new mention | 0.84 | 0.50 |
| posts more than 400 days old, not stored | | 8,996 |
| trees not read: no comment / not grown | | 3,127 / 286 |
| dead posts not stored | | 1,293 |
| `/api/info` calls for comment counts | | 97 |
| sent by the node during the pass (counter) | | 0.321 GB, 11 KB a new mention |

The rate-limit waits on the shared app were 2,377 s of the 300 minutes, and calls ran at 32 a minute: the app, not
the collector, still sets the pace. The night service runs this code from the night of 13 Oct.

Labelling did not keep up inside the pass: 18,177 of 28,948 were settled in its 25 minutes, 10,771 wait (no try is
counted when time runs out). Daytime collection now ends 45 minutes before a pass's end instead of 30
(`reserve_minutes_after_collect_day`).
