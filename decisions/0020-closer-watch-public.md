# 0020 — The closer watch's mentions, public and counted in nothing

**Status:** Accepted 2026-10-06 · **Decided by:** Vlad Shvets ("nothing private, all public", on keeping the Reddit
mentions tracker's mentions off the public pages), executed by Claude

## What changes

Every organic mention on the Empact Ops board (decision 0019's mirror, `watch.organic_mentions`) is shown on its
company's page, in its own section under the counted one: **"More mentions, from a closer watch"**. All of them, in full,
newest first, at most 60 a page, with the same card and the same attribution as every other mention (username, permalink,
"from Reddit"). A watched company the index has not collected yet still gets a page for them.

| | |
|---|---|
| Counted | nothing: not the score, the totals, the subreddit table, the rank or any board. A document the index's own collection holds for the company is in the counted section and never repeated here |
| Sentiment | the watch's own reading (Claude, on the tracker), shown as the card's nearest word; the index's labels are untouched |
| Disclosed | on the page ("Empact Partners, which runs this index, also runs Reddit marketing for X") and on `/methodology` (the watched companies, by name, 01-legal.md §4.1) |
| Never shown | "not about them" on the board; Empact's own accounts (never on the board); a document in the takedown ledger |

## Why it does not move a number

The index ranks every company on the same uniform collection. The watch reads 3,520 subreddits in real time for 15
companies; counting it would rank them higher for being watched, not for what Reddit says (tracker D5; 0018; 0019). Shown
and labelled, it is information; counted, it would be a thumb on the scale.

## The legal rules, unchanged and applied

01-legal.md and decision 0002 govern these cards exactly as the others: attribution on each; the nightly takedown checks
every watch card against Reddit with the counted ones (`worker/takedown.py`); a document deleted, removed or edited there is
ledgered in `public.removals`, its text dropped from the mirror and its card deleted in one transaction
(`site.purge_watch`), its page rebuilt and re-proven; a ledgered document is never mirrored as showable again.

## How

Migration 0026: `site.watch_card` (the cards), `site.watch_shown` (what the site reads; never a ledgered document),
`site.watched_brand` (the disclosure list), `site.refresh_watch` (rebuilt on every refresh of a company and on every board
link), `site.purge_watch`, and the page fingerprint extended so a page without watch cards hashes exactly as before (all
5,965 fingerprints proven unchanged when it was applied). `ops/watch_link.py` carries the card fields from the board
hourly. The nightly sweep's publisher re-renders and re-proves each changed page.

## Day one

132 public cards: Framer 60 (of 174 not already counted), Contabo 51, Metaview 8, Expensify 7, DevRev 6. DevRev and
Metaview get pages before the index's own collection reaches them.
