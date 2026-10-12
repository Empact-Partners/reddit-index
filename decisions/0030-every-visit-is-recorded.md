# 0030 — Every visit to a subreddit is recorded

Date: 2026-10-12. Status: accepted (the commission: full speed under the shared Reddit app).

## Context

The collector visits subreddits most overdue first, and "overdue" is read from the last visit recorded in
`ingest_state` (stage `new_listing`). Three kinds of visit left no record, so those subreddits stayed "never visited"
and were visited first on every pass:

| Kind | On 12 Oct | Calls a pass |
|---|---|---|
| The post listing ran out of pages (8 of 100 posts) before reaching the watermark (`capped`) | 23 subreddits, up from 8 on 10 Oct | 184 |
| Reddit no longer serves the subreddit: 404 (banned or deleted) for 20, 403 (private) for 1 | 21 | 21 |
| The first listing was empty, so there was no post to set a watermark from | 9 | 9 |

Measured: the same counts appear on every run since 10 Oct (capped 8 to 23, failed 15 to 21), and a probe of the
first 70 subreddits of the order at 23:50 UTC on 12 Oct returned 20 answers of 404, one of 403 and nine empty
listings. The pilot of decision 0029 (run `5e93d998`, 300 calls) spent 205 of its 300 calls on these before it reached
anything else.

The capped rule held the watermark so that "the next pass starts from the same floor and the pages are re-walked
rather than skipped" (`worker/daily.py`). The listing is read newest first, so a held watermark never brought the
posts below the last page within reach: each visit read the same newest 800 posts again (their mentions already
stored) and the posts beyond them stayed out of reach exactly as if the watermark had moved.

## Decision

In the collect stage (`worker/collect.py`), every visit writes its row:

1. **A capped listing moves the watermark to the newest post listed**, with status `capped`. The receipt names the
   subreddits (`capped_subs`). The posts between the last page and the old watermark were not reachable by re-reading.
2. **An empty first listing is a visit** that found nothing: a row with no watermark and nothing found, so the
   subreddit is quiet for three days like any other that found nothing.
3. **A subreddit Reddit answers 403, 404 or 451 for is a visit** that found nothing, status `gone`, its watermark
   kept, so it comes round like a quiet subreddit (every third day) instead of first on every pass. At most 40 a
   run (`GONE_STAMPS`): an app-wide refusal must not mark the whole map visited. They still count as failed listings,
   so the stage's alarm (more than half of the subreddits failing) still reads them.

A listing that failed for any other reason (a 5xx, the network) still leaves no record and is tried first again.

## What is given up

Nothing that was being collected: the posts beyond a capped listing's last page were already out of reach. A
subreddit that comes back from private or banned is seen up to three days later.

## How it is judged

The next passes' receipts: `capped_listings` and `listings_failed` fall to the subreddits that are new to the state
that day, and the calls before the first subreddit that yields anything fall from about 200 to about 30.
