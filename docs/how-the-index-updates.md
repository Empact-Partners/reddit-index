# How the index updates

**Cadence: manual, on demand.** The index has no scheduled jobs — no launchd
lanes, no Railway cron. A human runs **`worker/update.sh`** (collect → classify
→ score → delete-sync → publish → verify) and that IS the update. That is a
ruling ([decisions/0010](../decisions/0010-manual-on-demand.md), 2026-08-18,
superseding the daily-cadence ruling of 2026-08-17), made after the project's
automation burned an entire 5-hour Claude quota in a day. The old ruling's data
still governs the *guidance*: run at least weekly, because waiting costs
collection data that cannot be recovered — Reddit's `/new` only reaches about
1,000 posts back, and a thread leaves the 72-hour revisit window with whatever
comments it had when it was found. Everything downstream of collection loses
nothing to waiting. The full operating procedure is [SOP.md](../SOP.md).

Collection (`worker/daily.py`, stage 1 of the chain) walks the scoring
subreddits core-first, reads `/r/{sub}/new`, resolves brands out of the posts
and out of the comment trees of recently-seen threads, and writes mentions to
Supabase. It can carry a time budget (`--max-minutes`) and stops cleanly
when it expires, which is exactly why the walk is core-first: a truncated pass
loses the tail, not the 527 subreddits that carry the categories. (It ran on a
Railway cron until 2026-08-18; the service is Offline and the pass now runs
Mac-side inside `update.sh`, on the same credential fallbacks.)

One pass has to cover a full day of every subreddit, so the listing budget is
eight pages — 800 posts, past anything in this set (the busiest, r/pcmasterrace,
runs about 512 a day). Pages are only fetched while the listing is still ahead
of the watermark, so a quiet subreddit still costs one call.

The rest of the chain follows in the same `update.sh` run: classify → score →
delete-sync → publish → verify. Classification runs on the **DeepSeek API**
(`deepseek-v4-flash`, ~1,100 items/min, ~$0.18 per 1,000 items — decisions/0010;
the old "free" Haiku lane drew the shared Claude Max-plan quota and remains only
as an explicit fallback). The chain is deliberately **not** `set -e`. It used to
be, and a stalled classifier therefore aborted the script before scoring and
publishing — one slow lane, and the site stopped updating with data it already
had.

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

**What the numbers describe.** The *scores* describe the trailing 365 days as of
the last rebuild. The *mention counts* — the Mentions column on the boards, the
totals on a company page — describe everything ever collected, all the way back.
Those are two different windows on purpose, and the pages that show them say
which one they are showing.

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

**Publish = rebuild.** The site is fully static: every route is prerendered from
one database read at build time, and there is deliberately no runtime data path
— no anon key ships, no client fetches, and the snapshot module is `server-only`.
`worker/publish.py` asks Vercel to rebuild the current production commit with
the fresh data; if that call fails the chain falls back to pushing an empty
commit, because Vercel builds every push. A git push does the
same for code changes. Company routes set `dynamicParams = false`, so a brand
that was not in the build has no page until the next one.

There is one narrow runtime endpoint, `POST /api/revalidate`, and it carries no
data: it is bearer-gated and only invalidates cache tags. Delete-sync uses it.

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
3. **Counted** into its category's next scoring pass if its brand is actually
   tracked in that category (primary or `also_in`) and its timestamp is inside
   the 365-day window.
4. **Ages out** of the score window after a year. It stays in the database and it
   stays on the company page.
5. **Purged** if its author deletes it on Reddit. No tombstone.

**Delete-sync runs before the publish, in the same chain.**
`worker/delete_sync.py` takes a batch of stored documents, probes them through
Reddit's `/api/info` a hundred at a time, and treats anything Reddit no longer
returns — or returns with the body blanked to `[deleted]`/`[removed]`, or the
author blanked — as gone. Gone documents are written to a `removals` ledger
first, then their `mentions` and `mention_sentiment` rows are deleted, then the
affected pages are invalidated, then `revalidated_at` is stamped as the receipt.
That order is the whole design: a crash anywhere leaves a row that
`gate_checks.sql` flags, rather than a live page still serving a comment its
author deleted with nothing recording it.

Purging Postgres is only half the job — a cached page keeps serving a removed
comment until its tag is invalidated, which is why delete-sync owns the
revalidate call instead of leaving it to the publish. Running it inside the
chain, immediately before the rebuild, is what makes the purge and the pages
that reflect it land together: the `--publish-follows` flag stamps the receipt
on the rebuild, which invalidates more thoroughly than any tag set. This is not
a nice-to-have. Reddit's Developer Terms require deletions to propagate as soon
as possible, and `decisions/0002` makes it a *condition* of displaying full
comment text at all.

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
