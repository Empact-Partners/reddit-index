# 0042 — A faster backfill for the batch: 50 trees a subreddit, brand-named threads first, three at once

Date: 2026-10-29. Status: accepted. Decided by Vlad Shvets (the partner-development follow-up batch, 29 Oct 2026
~09:00 Chile), executed by Claude. Amends decision 0018's backfill (`ops/schedule.json` `backfill`); 0039's queue and
0041's line stand.

## What Vlad decided

> "the backfill finishes around 2-3 Nov => not acceptable. figure out how to go faster."
> "Index speed: cut the comment depth per subreddit from 150 threads to 50 ... => yep do smaller pages"
> "i want this done asap"

## Where things stood (29 Oct, 12:00 UTC)

- 0039's backfill: 16 of 295 subreddits done; 279 left. 32 of the batch's 90 brands live (4 new today).
- The pass of 07:02 UTC (`d9e448a9`) used its 150 minutes for 3,604 Reddit calls (2,194 trees, 14,120 mentions):
  **24 calls a minute, one subreddit and one tree at a time**, each call about 2.5 s from start to stored. The client's
  pace (`reddit_pace_seconds`, 1.2 s) would allow 50.
- The app is shared (the index's sweep and day service, empact-reddit-mentions at 30 a minute, reddit-agent-reactive-v2
  at 50 a minute). Its window, read live at 12:00 UTC: 1,000 calls in 10 minutes, about 140 a minute asked for.
- At that rate the queue ends around 2 or 3 November.

## The change

1. **`backfill.tree_cap` 150 → 50.** A subreddit's qualifying threads are still listed in full; at most 50 comment
   trees are fetched. Raising the cap later makes a subreddit unfinished again (`sweep.sub_complete` is judged at the
   cap), so the depth can be filled in after the batch without redoing what is stored.
2. **Brand-named threads first** (`worker/sweep.py` tree order): under a cap, threads whose title names a brand (the
   resolver's alias automaton) go first, then the busiest. The same rule for every brand, so no brand is favoured; a
   small cap never drops the threads a standing rests on. Without a cap the order is the old one.
3. **Three subreddits at once** (`backfill.workers`, at most 4): each worker has its own database connection; the
   gazetteer, resolver and mapping are shared read-only; the stop switch, caps and receipt are read and written under one
   lock. `reddit_client` still starts one request per pace for every thread, so the width raises the pass's share of
   the shared app, not the pace, and the client spreads its calls when the window runs low.
   `resolve._dom_claims` is now built whole before it is published (a half-built map read from a second thread could
   take a shared domain for one brand's own).

## What it costs

- Smaller standings in these categories until the depth is filled in: about a third of the trees per subreddit, the
  most informative ones (brand-named, then busiest) kept.
- The shared app's other users (mentions, reactive agent) are slowed by the window when all three ask at once; neither
  is changed.
- Egress per pass is unchanged in kind and still capped by 0041's line.

## Expected

About 140 calls a subreddit instead of about 225, at 35 to 50 calls a minute instead of 24: the 279 subreddits in about
one more day of passes instead of four or five.
