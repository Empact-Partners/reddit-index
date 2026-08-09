# How the index updates

**Cadence: daily.** Railway fetches every scoring subreddit's new threads at
04:00 UTC and stores resolved mentions in Supabase; the Mac classifies,
re-scores, and triggers a Vercel rebuild around 07:30 UTC. The numbers on
the site describe the trailing 365 days as of the last rebuild.

**There is no history and no deltas — by design.** The scores table holds
exactly one truthful set: each daily run upserts the fresh scores and
deletes everything older. The site never shows "up 3 since last week"
because a moving 12-month window plus a growing corpus makes day-over-day
deltas mostly measurement noise wearing a trend costume. Supabase keeps
every MENTION ever collected (verbatim, permanently, minus Reddit-deleted
ones) — history of the evidence, not of the rankings.

**Publish = rebuild.** The site is fully static: every route is prerendered
from one database read at build time, and there is deliberately no runtime
data path (no anon key ships, no client fetches). A Vercel Deploy Hook
triggers the daily rebuild; a git push does the same for code changes. New
brands get their pages at the next build.

**A mention's lifecycle:**
1. Fetched by the daily worker (or the backfill), body stored verbatim with
   its author, permalink and timestamp.
2. Classified within a day (pos / neg / neu / abstain, about THAT brand).
3. Counted into its category's next scoring pass if its brand belongs to
   that category and it is inside the 365-day window.
4. Ages out of the score window after a year (stays in the database).
5. If deleted on Reddit: removed from the site at the next delete-sync, no
   tombstone.
