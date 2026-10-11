# 0024 — Every changed page is published every night

Date: 2026-10-11. Status: accepted (the commission: the index refreshes itself daily).

## Context

The publisher expired and proved at most 1,000 company pages a night (decision 0017). The cap rested on one number:
0.2 MB of database egress for each page the site re-renders, measured on the pilot's fifty largest pages. About
5,700 pages change every night, most of them because a rank, a score or a board size moved when another brand's did.

Read on 11 Oct, 06:50 UTC:

| | |
|---|---|
| company pages | 6,098 |
| waiting to be published (the page served is not the page the database holds) | 4,723 |
| of those, with a mention newer than the page shows | 507 |
| of those, whose own numbers or cards were recomputed since the page was last seen | 3,467 |
| median time since a page was last published | 3.1 days (longest: 4.7, the whole time since the relaunch) |
| pages changed and deferred, every night since 5 Oct | 5,363 to 6,040 changed, 4,363 to 5,040 deferred |

The order was waiting time alone, so a page with new mentions queued behind pages whose rank had moved one place.

## What a page costs, measured

| Measurement, 11 Oct | Result |
|---|---|
| 800 waiting pages published from the laptop between two four-minute baselines, on the node counter | 18.9 MB while publishing, 2.5 MB of it the background rate: **20.5 KB a page** |
| the same 800 pages, HTML as fetched (compressed) | 14.6 KB a page: the database sends about 1.4 bytes per byte of compressed HTML |
| card text a render reads, 250 waiting pages picked at random | 26.5 KB on average, median 6.6 KB, largest 339 KB |
| the night of 11 Oct, whole run, on the node counter | 0.49 GB (the receipt estimated 0.62), with 1,000 pages of 72 KB of HTML each |
| 600 pages at 8 fetches at once instead of 4 | 67 seconds, 9 pages a second, every page proven, none fetched twice |

A typical page costs about a tenth of the number the cap was built on. The night's 1,000 are the heavy ones (takedown
pages come first and belong to the brands with the most cards): about 0.1 GB. Every changed page is about 0.2 GB.

## Decision

- The publisher expires, fetches and proves every changed page every night. `max_expire_pages` and `verify_pages` go
  from 1,000 to 7,000, above the number of pages that exist: a bound, not a quota.
- 8 fetches at once instead of 4. Collection ends 105 minutes before the run's end and classification 45 (each 10
  minutes earlier), so publishing about 5,700 pages (about 11 minutes) ends inside the window.
- If a night ever has fewer slots than pages (a smaller cap, or the run's end): takedown pages first, as before; then
  pages whose own data changed, longest-waiting first; a fifth of the slots stays with the longest-waiting pages
  whatever changed on them (`worker/site_publish.py pick`).
- The receipt's render estimate is 1.5 bytes per byte of HTML fetched, in place of 0.2 MB a page.

## Not changed

Takedown pages are published first and always, and a takedown's receipt is stamped only when its page has been seen
without the card (decisions 0002 and 0017). A page counts as published only when it was fetched and carried the
fingerprint the database holds. Pages change only when the sweep names them.

## How it is judged

The night of 12 Oct: `pages_deferred` 0 and nothing failed; the publish stage's minutes; the night on the node
counter against 0.49 and 0.61 GB for the two nights before. If the night's egress rises by more than 0.3 GB, the cap
comes back down to what the counter supports and this record says so.
