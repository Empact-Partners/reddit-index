# Platform QA — 2026-08-16

A full sweep of the shipped site: every built page read mechanically, the
data invariants re-run, the design gates self-tested, the desktop rendering
reviewed by eye, and the SEO surface built out. Zero model spend.

## What was checked

| Layer | How |
|---|---|
| Every built page (3,839) | `scripts/qa-sweep.mjs` — links, metas, stray values, sentiment sums, score ranges, noindex, cross-surface rank agreement |
| Corpus | `worker/qa_audit.py --only invariants` — 6 SQL invariants |
| Design law | `pnpm gates:selftest` — all 7 gates re-proved to fail on injected violations |
| Behaviour | `pnpm test` — 30 vitest + 8 node:test resolver tests |
| Rendering | Headless screenshots at 1440px, read directly |

## Defects found and fixed

**1. The methodology page described the wrong estimator.** It still rendered
the posterior-MEAN formula while the site had been publishing the
10th-percentile posterior lower bound since 2.2.0. The page now states the
quantile, why it replaced the mean (the shift4/PayPal inversion), the
100-per-side board cap and the pooled ten-mention bar — both previously
unmentioned — and that the Mentions column is total collected.

**2. Version drift, three ways.** `worker/score.py` stamped 2.2.0,
`lib/format.ts` and the freeze script said 2.1.0, `docs/methodology.md` said
2.0.0. Unified on 2.2.0 and re-frozen (33 parameters, including the new
`score_quantile`). This mattered: `/methodology` queries parameters BY
version and renders an empty table on a mismatch — it would have silently
shown zero parameters.

**3. Mention bodies lost their line breaks.** 86,771 stored bodies (23%)
contain single newlines, which the card collapsed — every bulleted list
rendered as one mashed paragraph. Also 1,071 bodies carry HTML entities
(`&amp;`, `&gt;`) that displayed literally. Both fixed at render.

**4. Category meta descriptions overcounted.** They were built from every
scored row rather than the thresholded board, describing /web-hosting as 67
brands against the 32 it shows. Now computed from the board itself, and the
description names the most loved and most hated brand.

**5. Titles were too long for search results.** The layout template appended
" · Reddit Brand Index" to every page, pushing 3,805 pages past 80
characters when Google truncates near 60 — the differentiating words were the
ones being cut. Titles are absolute now, and shrink progressively for long
brand names rather than truncating the name itself.

**6. A screen-reader duplication in the rank tile.** The sr-only text read
"Ranked number 18 in" and the visible label "of 24 in CRM", so the tile
announced "Ranked number 18 in of 24 in CRM".

**7. The site advertised a sitemap that did not exist.** `robots.ts` has
always pointed at `/sitemap.xml`; nothing emitted one. Going public would
have shipped a robots file pointing at a 404. Added, generated from the same
route registry that mints the pages, so it cannot list a 404 or miss a page.

**8. The resolver's tests never ran.** `tests/resolve.test.mjs` is node:test
and `pnpm test` ran vitest only — 8 tests covering the documented false
matches ("Monday" the weekday, "SAP" the fluid, "Sage" the herb) were
silently skipped. Wired in; all 8 pass.

**9. A stale reference** in `app/not-found.tsx` cited a gate file that does
not exist.

## Added

- **`/llms.txt`** (llmstxt.org convention) — what the index is, what the
  score means, the category list with counts, and notes for agents. Generated
  from the live registry and snapshot, so it cannot drift from the site.
- **Open Graph + Twitter metadata** on every route, with per-page titles and
  descriptions and a canonical URL.
- **`scripts/qa-sweep.mjs`** — the sweep is now a repeatable script, not a
  one-off. 1,260 rank cross-checks per run.
- Two regression tests pinning search behaviour (hits keep their TRUE board
  position; clearing the query restores the board).

## Findings that were NOT defects

- **`NaN`, `undefined`, `24000/100`** appearing on company pages: all inside
  quoted Reddit comments — a video thread quoting "23.976 (24000/1001) FPS",
  an Attio thread saying "an undefined sales process". The sweep now excludes
  quoted bodies; only our own chrome is scanned.
- **Two rank "mismatches"** (SharePoint, Sophos Firewall): the checker had
  matched them against the wrong category by row-count coincidence. Both
  ranks were correct. The check resolves the category by name now.
- **A rank/DOM-order trap** worth recording: the two-card view renders the
  loved half then the hated half REVERSED, so DOM order is not board order.
  A naive cross-check calls every hated-side brand a mismatch. HubSpot sits
  at DOM index 18 of 24 and is genuinely rank 18.

## Responsive QA — done properly, second pass

The first pass could not verify mobile and said so. The cause was the
harness: `chrome --headless --window-size=390,844` does **not** give a 390px
viewport. A probe page printing `window.innerWidth` reported **500** for a
requested 390, in both old and new headless — Chrome clamps the window to a
500px minimum and merely crops the PNG. Every "mobile defect" found that way
was an artifact.

`scripts/device-shot.mjs` now drives the DevTools Protocol directly (Node 25
has a native WebSocket, so no dependency) and calls
`Emulation.setDeviceMetricsOverride`, which actually resizes the layout
viewport. It reports `innerWidth`, `scrollWidth` and the elements wider than
the viewport — so a failure names its culprit instead of leaving it to be
guessed from a picture. Verified against the probe: requested 390, reported
390.

Measured on the real thing:

| Device | Viewport | Page overflow | Widest element |
|---|---|---|---|
| iPhone SE | 375 | 0 | all fits |
| iPhone 14 | 390 | 0 | all fits |
| iPhone Pro Max | 430 | 0 | all fits |
| iPad mini portrait | 744 | 0 | all fits |
| iPad landscape | 1133 | 0 | all fits |
| iPad Pro | 1024 | 0 | all fits |

**Two genuine responsive defects, found and fixed:**

1. **The score was off-screen on phones.** The board table rendered 813px
   wide inside a 358px card, so `#` and `Brand` were visible and the Reddit
   Love Score — the reason the page exists — sat behind a horizontal scroll.
   Mentions now hides below 900px (it is one tap away on the company page),
   the category chip hides below 430px, and brand names wrap instead of
   forcing the table wide.
2. **The Category `<th>` carried no column class**, so hiding the column hid
   its cells while the header kept the column alive at full width. Every
   header now carries its column class.

Both were masked by a CSS **source-order** trap worth recording: a
`@media (max-width: 700px)` block placed ABOVE the rules it overrides loses
every same-specificity tie, so `width: min(280px, 100%)` and
`white-space: nowrap` kept winning and the mobile rules appeared to do
nothing. The phone block now sits at the END of the stylesheet.

## Known limitations, stated rather than hidden

- **The build fails intermittently** with `TypeError: Iterator value
  undefined is not an entry object` during "Collecting page data", roughly
  one run in four, and passes on retry with no code change. Not diagnosed;
  it does not affect the artifact a successful build produces.
- The `n_eff` precision gate remains computed and published but does not gate
  visibility — documented as such on /methodology.

## Result

`qa-sweep.mjs`: **3,839 pages, 1,260 rank cross-checks, ALL CHECKS PASS.**
Invariants 6/6. Gates 7/7. Tests 38/38.
