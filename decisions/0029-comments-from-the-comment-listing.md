# 0029 — Comments are read from each subreddit's comment listing

Date: 2026-10-12. Status: accepted; daytime passes on it since 12 Oct 23:38 UTC, the night's run from the night of
14 Oct (judged below).

## Context

The collector reads comments one thread at a time: it stores the posts that qualify, then asks Reddit for the comment
tree of each (`/comments/{id}`), up to 24 a subreddit a visit. `13-algorithm.md` names another way, measured in August
and never built into the daily collector: `/r/{sub}/comments` returns a subreddit's newest 100 comments in one call,
whatever thread they sit in, each with its thread's id and title.

Measured on 12 Oct:

| | Comment trees (the daytime pass `3cdf67d3`, 12 Oct) | Comment listing (130 subreddits sampled, one call each) |
|---|---|---|
| calls | 8,488 | 130 |
| comments read a call | 19.8 (median 8) | 93.8 |
| mention rows a call | **1.69** | **10.5** (core subreddits 15.5, the others 7.9) |
| rows for the brand "reddit" | 11% | 17% |

- The sample is 45 core and 85 other subreddits drawn at random from the 4,675 in the plan (`scripts/stream_probe.py`,
  seed 20261012, rows in `docs/go-live/stream-probe-2026-10-12.csv`), with the collector's own rules: deleted, removed
  and automated comments left out, the same resolver.
- **The trees miss about half.** Of 508 comments on those pages that name a brand and were written an hour or more
  before the subreddit's last visit, the database held 281 (55%). A tree is read only for a post that qualified; a
  brand named under any other post is never seen.
- **The rotation does not come round.** Of 4,863 subreddits ever listed, 1,148 were visited in the last day, 2,590 in
  the last three, and 1,209 not for more than a week. A visit costs a listing call and 11 tree calls, and a pass has
  about 9,500 calls.
- A subreddit of the sample writes 106 comments a day at the median when core and 34 otherwise; 80 of the 130 write
  under 100 a day. Reading every comment of every subreddit once a day is about 11,500 calls at one subreddit a call.
  The estimate for all 4,675 is 1.1 million comments and 52,000 mention rows a day, and it is rough: three of the
  sampled subreddits carry a third of the comments.

## Decision

A mode of the collect stage (`worker/collect.py`, `mode: "stream"`; `ops/schedule.json` `collect.mode_day` and
`collect.mode_night`, a pass's request, or `--collect-mode`):

1. **Comments come from the subreddit's comment listing**, newest first, back to the newest comment already read
   (a watermark a subreddit: `ingest_state`, stage `comment_stream`). The read stops on the comments' own times,
   never on a comment id (a listing anchored on a comment since deleted returns nothing). At most 10 calls a visit:
   the listing ends near 1,000 comments. A subreddit's first visit reads its newest 300.
2. **Posts are listed as before** (`/r/{sub}/new` to the post watermark) and a post that names a brand is a mention.
3. **A thread is stored when it holds a mention**: a post that names a brand, and the thread of every comment that
   does. Its row comes from the post listing just read when the thread is on those pages, else from `/api/info`, 100
   threads a call. No comment tree is read and no thread is stored to be read later.
4. **The stage ends when the run's room for new mentions is used**, a planned end like the Reddit calls: a set number
   by night (15,000, so the night keeps its hours for labelling, refresh and publish), and by day what the pass's own
   egress cap carries (cap x 0.9 / 13 KB: 12 Oct, a mention collected and labelled wrote 13 KB of log and classifier
   reads), never more than 0.9 of the new-mention cap.

Not changed: what qualifies a post, what counts as a mention, the resolver, the bot rule, the 400-day window, the
order of subreddits, the pace, the egress line and who guards it, takedowns.

## What is given up

- A subreddit that writes more than about 1,000 comments between two visits: the ones between are not reachable
  through the listing. The receipt counts and names them (`stream_gaps`, `stream_gap_subs`). Under trees those
  subreddits were sampled by their qualifying threads; under the listing by their newest 1,000 comments a visit.
- A comment whose thread Reddit no longer returns (`mentions_without_thread`): it could not be shown with a title.
- Comments older than a subreddit's first 300 that the trees never read.
- The comment score is the one at the read, minutes after the comment was written. Votes are not used
  (`docs/methodology.md`).

The public page already says the corpus is a sample and every count a floor; that stays true.

## What it costs

More mentions a day means more labelling: about 58 GLM credits and 2 cents of Jev a thousand mentions (12 Oct). At
70,000 mentions a day that is about 4,000 credits (the plan gives 28,000 every five hours) and $1.40, inside the
ceilings of `ops/schedule.json` `classify` (ruling of 6 Oct: the egress cap bounds labelling, not the model allowance).
The egress line bounds the day as before; a pass stops itself at it.

## Rehearsal

12 Oct 20:37 UTC, the stage in this mode against Reddit and the database inside one transaction, then rolled back
(the sweep's lock was held by a daytime pass, so nothing could be kept): five subreddits that pass had visited
between 20 minutes and 3 hours earlier (saasbuild, aiagents, audioengineering, Substack, Rag), each a first visit.
25 calls (5 post listings, 15 comment pages, 5 `/api/info`), 1,500 comments listed, **139 new mention rows**: 130
from 106 comments in 76 threads, 9 from 2 posts. Every row had its thread (33 rows offered: 2 posts, 11 from the post
listing, 20 from `/api/info`), all 139 were queued for labelling by the table's own trigger, both watermarks were
written, and nothing was left after the rollback. The oldest thread stored was from August 2023: a new comment under
an old post, which a comment tree never reached.

## Review

An independent read by GLM-5.3 (clean clone of `69d24fa`, read-only): the default mode is unchanged statement by
statement; no loss on the failure paths (a failed page, a failed `/api/info`, a cap reached inside a visit: both
watermarks and the rows sit in one transaction); the comment reads the same from either lane. Five minor findings,
all taken:

1. A comment written in the watermark's own second and listed after the read was dropped for ever: the read now
   includes that second (the mentions key refuses the one already stored).
2. The comment watermark could move back when the comment that set it was deleted: it only moves forward.
3. A run by hand that names its stages without `publish` was taken for a daytime pass (the day's mode, 36,000
   mentions of room): only a requested daytime pass is one; anything else keeps the night's mode and number.
4. The retired collector's health check counted rows, and a subreddit now has two: it counts the post listing's.
5. The receipt did not count the threads stored for posts that name a brand: `threads_from_posts`.

## Pilot and judgement

Recorded below as each happens: a pilot by hand between two runs (about 150 calls, kept), then the first daytime pass
on `mode_day: "stream"`, judged on mention rows a call against 3.05, subreddits visited a pass against 755, bytes
sent a new mention against 11 KB, the share of new mentions the classifier rejects as not the product against the
trees' share, and gaps.

## Pilot

12 Oct 23:10 UTC, by hand on Railway's code from the laptop, kept (run `5e93d998`, 300 calls): 810 mentions (527 from
comments, 283 from posts), every one with its thread and queued for labelling, no listing failed, no gap. It also
showed 205 of its 300 calls going to subreddits that never got a visit row: decision 0030.

## Judged, 13 Oct

The first three daytime passes on it, against the two daytime passes of 12 Oct on comment trees
(`scripts/run_yield.py`; the classifier's share read once their mentions were labelled):

| | trees, 12 Oct (`3cdf67d3`, `996856ee`) | comment listing, 13 Oct (`d5ec012d`, `d159a62c`, `1304e863`) |
|---|---|---|
| mentions a Reddit call | 3.05, 3.14 | **7.19**, 5.03, 6.22 |
| sent by the node a new mention | 9.5 KB, 7.6 KB | **6.2 KB**, 8.4 KB, 6.3 KB |
| subreddits a minute | 2.5, 1.9 | 5.7, 7.2, 6.5 |
| rejected by the classifier as not the product | 6.9%, 7.5% (7.2% together) | 5.8%, 9.4%, 7.7% (8.2% together) |
| the brand "reddit", share of mentions | 10%, 12% | 19%, 24%, 19% |
| gaps (the listing ended before the last comment read), comments without a thread | | 0, 0 |
| seconds matching | 2,196 of 14,256 (12 Oct evening) | 26 of 6,552 (decision 0031) |

`d5ec012d` collected 23,958 mentions in 109 minutes, about twice what a comment-tree pass found in five hours, and
ended when its room was used, as designed. Two things it showed, each now its own decision: it labelled nothing in
GLM's peak hours (decision 0032), and with the backup that followed the 24 hours read 2.20 GB at 11:30 UTC (decision
0033). The classifier rejects one point more of what the listing brings; the brand "reddit" is about twice the
share, the open question for Vlad in the README.

The night's run moves to it from the night of 14 Oct (`collect.mode_night: stream`): its room is `night_mentions`
(15,000) less the queue's share (decision 0032).
