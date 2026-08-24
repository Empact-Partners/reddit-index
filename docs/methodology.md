# Methodology — the Reddit ❤️ Score, as built

*The definitive plain statement of what the published number is. The
critical audit of it lives in [methodology-review.md](methodology-review.md);
the original long-form design record is `07-index-methodology.md` and
`13-algorithm.md` at the repo root. Live corpus and score-row counts live in
[qa-audit.md](qa-audit.md) — they move daily and are deliberately not
restated here.*

## The score (methodology 2.2.0)

```
N_op = pos + neg
p0   = (pooled_pos + 5) / (pooled_op + 10)     over every OTHER company (LOO)
a0   = 10*p0        b0 = 10*(1-p0)
posterior = Beta(x_pos + a0,  x_neg + b0)
Reddit Love Score = round(100 * Q_0.10(posterior))
```

The published number is the **10th-percentile posterior quantile** — the
lower bound, not the mean. 2.0.0 fixed the mis-specified v1 prior; 2.2.0
replaced the published mean with the lower bound after the mean rewarded
thin evidence (shift4, 0 positives out of 4 opinions, published above PayPal
at 25% positive over 72). The lower bound is monotone in the positive rate
AND in the amount of evidence, so sparse data costs a company position
instead of buying it one. Implemented as a deterministic dependency-free
Beta inverse-CDF (`worker/score.py::beta_quantile`), verified against closed
forms. `p_tilde` (the mean) is still computed and published as evidence.


## What counts

- Comments and posts from the category's **scoring subreddits** —
  every community that passes all qualification bars: exists & open, alive
  (~2+ posts/week), not vendor-run, rules do not forbid product discussion,
  topicality ≥ 0.5, and observed brand talk. No top-N cap and never ranked
  by subscriber count (frozen as `scoring_subreddit_selection`, 2.0.1 — see
  [taxonomy.md](taxonomy.md)). Trailing **365 days**, uniform weight. The
  window is applied at scoring time, not at harvest, so widening it is a
  methodology change and a recompute — never a re-crawl.
- **A post's document is its TITLE plus its selftext.** It was the selftext
  alone until 2026-08-17, and that one omission is most of why the index
  read as comments-only: a brand named in a headline — "Anyone moved off
  HubSpot?", the single most common place a brand appears on Reddit —
  resolved to nothing, because the title was passed to the resolver as
  context and never scanned; and a link or image post has an EMPTY selftext,
  so it produced no document at all and its title was read by nothing.
  `worker/harvest.py::post_doc` is now the one builder every collector
  imports, so the stored body is byte-identical whichever lane minted it,
  and `worker/backfill_posts.py` re-read every stored thread through
  `/api/info` to recover the historical posts.
- **Coverage is complete for normal subreddits and approximate for the
  busiest ones, and this is a floor rather than a census.** The collector
  pages `/new` back to the window's cutoff, which fully covers any
  subreddit under ~11 posts/day. Where Reddit's ~1,000-post listing cap is
  younger than the cutoff, the subreddit is marked `coverage="approximate"`
  and supplemented with `/top` (month and year, client-filtered) plus
  per-noun scoped search. Separately, the sweep fetches the **150
  highest-comment qualifying threads per subreddit** (`decisions/0014`),
  ordered richest-first on a measured yield curve — a 100+-comment thread
  returns 9.2 mentions against 1.2 for a 2-comment thread — so a capped
  subreddit contributes its most opinion-dense threads, not an arbitrary
  slice. Raising the cap and re-running is additive: already-swept threads
  are recorded, so a deeper pass continues rather than repeating.
  **Every count this produces is therefore a floor.** This paragraph was
  promised by `docs/depth-execution-plan.md:216` in August 2026 and was
  missing until 2026-08-24; the number that was never written down anywhere
  is what made a later sweep run ~50x the intended work.
- Only brands whose **category membership** includes the scored category —
  a mention of Google Drive in r/CRM stays on Google Drive's page and out
  of the CRM leaderboard.
- Neutral and abstain mentions are counted and published, never scored.
- **Votes are ignored** — an upvote measures visibility agreement inside a
  feedback loop, not sentiment.
- One mention = one (document, brand) pair; a comment naming three products
  produces three verdicts, and so does a post whose title names three.

## Display floors vs statistical gates

Two different bars, deliberately, and neither one is the other.

**Display floor** — what it takes to appear on a board. Each category
publishes at its OWN **median `n_op`, clamped to [3, 30]**: a brand must
carry at least as much opinionated evidence as the typical brand it is being
ranked against. Computed in `lib/data/snapshot.ts`, applied in
`lib/data/boards.ts`, frozen as `ranking_threshold` in 2.2.0. A category
whose typical brand has forty opinions therefore demands more than one whose
typical brand has four, and the floor of 3 keeps thin categories publishable
instead of empty. The pooled all-categories boards require that AND
`n_op ≥ 10`, because most-loved-in-the-whole-index is a bigger claim than
most-loved-in-CRM. A brand under its bar appears on NO board; it stays
reachable through search and through its own page.

The median replaced two broken things. What the code actually did was a flat
`n_op ≥ 3`, which ranked one-mention brands beside eight-hundred-mention
brands; Vlad retracted that on 2026-08-16 in his own words ("I shouldn't have
told it to display all the companies — that is wrong"). What this page
*claimed* it did was the `n_eff` gate below, which no component ever
consulted and which admitted 10 of 2,056 score rows — and the category tiers
behind that gate were a hardcoded default derived from three-year CATEGORY
comment flow, never from per-brand evidence. A median is self-calibrating,
derived per category from the brands actually being compared, and cannot be
tuned by hand without changing the data it is a median of.

**Statistical gates** — what it would take to call a score *settled*.
`n_eff ≥ n_min` where `n_eff = N_op / DEFF` (Kish design effect, clustered by
thread AND author, the worse of the two), plus absolute diversity floors —
≥50 authors, ≥5 subreddits, ≤20% from one thread, ≤5% from one author. Tier
targets: deep ±4pp → 600 · standard ±5pp → 400 · thin ±7pp → 200. These are
computed for every brand and stored on every score row, and they are what a
company page discloses about precision. They no longer decide visibility:
`n_eff_role` is frozen as `precision_claim_not_visibility` in 2.2.0, because
an index whose own bar is 600 renders empty and shows nothing to anyone.

Almost nothing clears them. On the 2026-08-16 scoring run, **53 of 4,000**
brand×category rows were eligible. Today's boards are directional and say
so on the page. Deeper daily data is the cure, not a lower bar.

## What a company page shows

A board ranks; a company page displays, and the two count different things.
The mention list on a company page is **the 80 newest comments and the 40
newest posts** for that brand — two rails, one per document type, not a
single newest-N by recency. One rail was tried and left brands holding
thousands of posts showing seventeen of them, which makes a Posts filter a
filter over noise. The stat tiles, the Posts/Comments filter counts and the
subreddit ledger are computed over the WHOLE corpus rather than over the
rail, and the page prints "Showing the N most recent of M mentions" so the
window is never mistaken for the total.

## The ordering

Most Loved and Most Hated are the two ends of ONE ordering (score
descending). No second fit, no separate "hate score", and a brand can never
appear on both boards — the two-table view is derived from the single
consolidated list by `splitScope`, which is disjoint by construction. The
home boards show the top 100 of each end; the full view is that same list,
same thresholding, uncapped. The pooled boards rank each brand once, through
its highest-volume category row — its home turf, not its best look.

## Freezing

Method constants are frozen in an append-only `methodology_params` table
(rejects UPDATE/DELETE at the trigger level) with the git commit recorded.
Changing one is a version bump with a dated entry, never an edit. Adding the
expansion categories was such a bump; so were the 2.2.0 entries that moved
`n_eff` off visibility and wrote down `ranking_threshold`.
