# How the index updates

**Cadence: once a day, by itself** ([decisions/0017](../decisions/0017-daily-sweep.md), 2026-10). One job,
`worker/run_daily.py`, runs at 00:00 UTC on its own Railway service and does everything in order: takedowns,
collection, classification, refresh, scoring, publishing, receipt. It is bounded (Reddit calls, rows, time,
egress), resumes from what the database says, and messages Vlad only when something went wrong. How to look at
it, stop it or change it: [SOP.md](../SOP.md).

Before that: from 2026-08-18 the index was meant to update only when a person ran `worker/update.sh`
(decision 0010), while a forgotten Railway cron ran the old collector every night until 2026-10-02 (decision
0016 and its addendum; `docs/investigation-2026-10.md`).

Collection (`worker/collect.py`, using `worker/daily.py`'s helpers) walks the scoring subreddits core-first,
reads `/r/{sub}/new`, resolves brands out of the posts and out of the comment trees of recently-seen threads,
and writes mentions to Supabase. It stops cleanly at its caps, which is exactly why the walk is core-first: a
truncated pass loses the tail, not the core subreddits that carry the categories. A subreddit that produced
nothing on its last pass is visited every third day.

One pass has to cover a full day of every subreddit, so the listing budget is
eight pages — 800 posts, past anything in this set (the busiest, r/pcmasterrace,
runs about 512 a day). Pages are only fetched while the listing is still ahead
of the watermark, so a quiet subreddit still costs one call.

Classification follows in the same run: a rule first (a link to a parent company's web address is not a
mention of one of its products), then Jev for the mentions it is sure of, then GLM-5.3 for the rest, with
"not this product" recorded where it survives any machine (`docs/classify-backlog.md`). Each stage records
what it did and the next one runs whatever the last one managed, so one slow lane never stops the site
from updating with data it already has.

The chain ends with `worker/healthcheck.py` — the same fourteen-assertion
battery that used to run as a standalone 3-hourly job (retired 2026-08-18 with
the other lanes; its freshness thresholds assume a recent run, which is exactly
what "end of the chain" guarantees). It exists because of a specific failure: from 2026-08-16 to 2026-08-17 the daily fetch collected
nothing at all and every signal a human would check stayed green. The cron ran,
the container exited 0, `ingest_state` gained a fresh row with `status='ok'`,
and the site kept serving. The only trace was `rows=0`, and nobody reads a row
for a zero. So the check is not "did it run" but "did it MOVE": fourteen
assertions comparing clocks and counts against what a healthy pass produces,
including that posts are still being read as posts and that the
`published.mentions` view is not pinned to a single sentiment model. It posts to
Slack only on a change of state — into failure, and again on recovery — and only
if `slack_channel` is set in `~/.claude/.reddit-index.json`.

**What the numbers describe.** The score on a page and its board rank use every opinionated mention collected
(decision 0011; methodology 2.3.0 says so since 2026-10-03, after 2.2.0 still described a 365-day window). The
mention counts use every mention collected. One window, everywhere on the site. The weekly table
`brand_category_scores` (trailing 365 days, scoring subreddits only) is still computed for the tools that read
it and is not what the site shows.

**There is no history and no deltas — by design.** The scores table holds
exactly one truthful set: each run upserts the fresh scores, deletes every older
`week_start`, and additionally drops any row at the current `week_start` that
this run did not just compute. That last sweep is not tidiness. Because the
loader upserts, a (brand, category) that scored yesterday and has no evidence
today would otherwise keep its stale row at today's date forever — purging
30,858 false-positive mentions once left 44 such rows live, publishing scores on
evidence that no longer existed. A score must not outlive its evidence.

The site never shows "up 3 since last week" because a moving 12-month window
plus a growing corpus makes day-over-day deltas mostly measurement noise wearing
a trend costume. Supabase keeps every MENTION ever collected (verbatim,
permanently, minus the ones deleted on Reddit) — history of the evidence, not of
the rankings.

**Publish = expire the pages that changed.** The site reads small precomputed rows (schema `site`, one row per
page plus its cards) through a role that can read nothing else. A page is rendered on its first visit and
cached until the sweep names it: after refreshing and scoring, `worker/site_publish.py` posts the paths whose
fingerprint changed to `POST /api/revalidate/` (bearer-gated, paths only, no data), then fetches every page
that held a takedown, a sample of the rest, and the boards, and records which fingerprint it saw. A code
change still rebuilds the site; data never does.

**A mention's lifecycle:**

1. **Collected.** Both posts and comments become mentions. A post's document is
   its TITLE plus its selftext, stored as `doc_type 2`. It used to be selftext
   alone, and that one omission is why the index read as comments-only: a brand
   named in the headline ("Anyone moved off HubSpot?") resolved to nothing, and
   a link post with an empty body produced no document at all. Posts are now
   resolved straight off the `/new` listing the pass already holds, at zero extra
   API calls. Comments (`doc_type 1`) come from the comment trees of threads
   first seen in the last 72 hours, unread threads first. Either way the body is
   stored verbatim with its author, permalink, score and timestamp.
2. **Classified**, usually within a day, but the classifier trails collection.
   It is an anti-join against `mention_sentiment` that drains the backlog and
   exits, and it runs once, at 08:30 UTC. So the 02:00 batch is labelled the same
   morning, the 14:00 batch waits for the next one, and a deep backlog takes
   longer still. This matters because scoring reads only labelled rows: a
   collected but unclassified mention exists in the database, is visible on the
   company page, and is not yet in any score.
3. **Counted** into its brand's score at the next run once it carries a positive or negative label.
4. **Set aside** if it turns out not to be about the brand: recorded in `mention_rejections`, no longer counted.
5. **Purged** if it is deleted, removed or edited on Reddit. Only the ledger row remains.

**Takedowns run first, every day.** `worker/takedown.py` re-checks every comment shown on any page through
Reddit's `/api/info` (about 140,000 documents, 1,400 calls), then the documents checked longest ago. Reddit no
longer returning one, a body of `[deleted]`/`[removed]`, a deleted author, `removed_by_category`, or an edit
after we stored it: all purge. The ledger row, the purge and the stamp happen in one transaction; a batch
Reddit did not answer is "not checked", never "deleted" (the old delete-sync read it as deleted). If more than
15% of what was checked looks gone at once, nothing is purged and Vlad is told. The receipt
(`removals.revalidated_at`) is stamped only after the publish stage FETCHED every page that held the document and
saw it without the card. Reddit's Developer Terms require deletions to propagate as soon as possible, and
`decisions/0002` makes it a *condition* of displaying full comment text at all.

**A company page shows a window, and says so.** Each page renders the 80 newest
comments and the 40 newest posts for that brand — two separate rails, not one
list of 120 by recency. Every mention in that rail is serialised into the page,
because the dashboard filters and paginates without a fetch, so the rail is
sized by page weight and not by appetite. Posts are about a quarter of the corpus and are clustered
differently in time, so a single newest-N window left brands with thousands of
posts showing seventeen of them, and a Posts filter over that is a filter over
noise. Every *count* on the page is computed from the whole corpus rather than
from the cards shown: the stat tiles, the Posts/Comments filter counts, and the
subreddit ledger all come from a full-table aggregate. The page states the gap
itself, above the list ("Showing the N most recent of M mentions"), and labels
the oldest-first sort "Oldest shown" — because the oldest mention held can be
years older than the oldest card rendered, and calling that button "Oldest"
would be a lie.
