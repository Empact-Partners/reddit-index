# 0019 — The organic mentions board and the index, linked

**Status:** Accepted 2026-10-06 · **Decided by:** Vlad Shvets ("they're all a super connected system ... establish a proper
relationship and proper links between the Reddit index and their organic mentions board"), executed by Claude

## The three systems

| | What it is | Where |
|---|---|---|
| The Reddit Index | uniform measurement of 10,689 brands across 159 categories, scored, public (noindex) | this repo; Supabase `nrsyqcttpijxhwtdtoct`; redditindex.com |
| The Reddit mentions tracker | real-time watch of the 15 partners Empact runs Reddit for, across a partner-chosen list of 3,520 subreddits; one Slack card per organic mention | `Empact-Partners/reddit-mentions` (Railway + Vlad's Mac) |
| The Organic Mentions board | one record per organic mention and the track record of what Empact did about it (replied, planned, passed to the partner, no reply, not about them) | `Empact-Partners/empact-ops` `reddit/partners/<p>/organic/`, the Reddit Boards page's third tab |

## The links

1. **Partner → brand.** Each partner's Empact Ops program carries `index_slug` (its brand here: `clementine-aba`, `lingo-app`,
   `framer` ...). All 15 are brands since decision 0018.
2. **Board → index.** Every board record is mirrored into `watch.organic_mentions` (migration 0024) with its brand, the
   Reddit document id, and `board_url` (the record on GitHub). `ops/watch_link.py` does it, called hourly by Empact Ops'
   organic job on Vlad's Mac, through the Management API, refusing the night window.
3. **Index → board.** The same call answers, per record, whether this index's own collection holds the document for that
   brand (`watch.organic_coverage.in_index`). The board shows it ("In Reddit Index") with a link to the partner's page
   (`https://redditindex.com/<slug>/`).
4. **Tracker → board.** The tracker's `GET /v1/organic` (its D15) feeds the board; a person's "not about them" goes back
   through its `/v1/override`.

## What is deliberately not linked

The tracker's mentions never enter `public.mentions` and never move a score (its D5; 0018). The index ranks every brand
on the same uniform collection; a partner watched closer than its competitors would rank higher for being watched, not for
being discussed. `watch.*` is outside the site's reads (the site role reads `site.*` only), carries no persona name
(`replied` is yes or no), and is the measure of how much of the partners' organic conversation the index's own collection
reaches: `python3 ops/watch_link.py --coverage`.

## Day one

On 6 Oct 2026 the board held 350 mentions (Framer 184, Contabo 144, Metaview 8, Expensify 8, DevRev 6), most of them the
tracker's first look back over the last month. The index's own collection held 104 of them (30%: Contabo 93 of 144, Framer 10 of 184, Expensify 1 of 8, Metaview 0 of 8, DevRev 0 of 6); the partners' 90-day Phase B
sweeps (0018) and the partner-priority collection order are what close that gap, uniformly, for their competitors too.
