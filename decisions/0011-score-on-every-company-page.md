# 0011 — A score AND a rank on every company page

**Status:** Accepted · **Date:** 2026-08-19 · **Decided by:** Vlad Shvets

## Bottom line

Every company with at least one opinionated mention is **scored and ranked in its category**. One number does all the work: it is computed over every opinionated mention collected for that company (the same corpus as the Positive and Negative tiles on its page), it is what the page shows, it is what search shows, and it is what its category board ranks it by. The per-category display threshold no longer decides who appears; a company with no opinionated mention at all is still unscored and unranked.

The pooled "All Categories" board keeps its bar of ten opinionated mentions. Placing a company inside its own category is a different claim from calling it the most loved brand on Reddit overall, and Vlad retracted a show-everyone experiment on the pooled board on 2026-08-16.

## Context

Before this ruling 546 of the 1,244 company pages in the outreach set showed a bare "—" because the brand's opinionated count inside the scoring window (trailing 365 days, scoring subreddits only) was below the category median. Of the 70 pages with no opinionated label at all, 59 simply had unclassified mentions. Vlad, 2026-08-19: "all the Reddit scores must be filled out anyway for all of these companies … compute based on the existing data." The company page is the outreach asset; a page with a number that matches its own tiles is the asset, a dash is not.

## The decision

1. `lib/data/page-score.ts` — a line-for-line TypeScript port of `worker/score.py`'s `fit_prior_pooled` (PRIOR_K 10, PRIOR_P0_SMOOTH 10, leave-one-out by mention mass within the brand's PRIMARY category) and `beta_quantile` at SCORE_QUANTILE 0.10. `tests/page-score.test.tsx` asserts integer parity against Python-produced fixtures.
2. `lib/data/snapshot.ts` computes `pageScore` per brand from the same aggregate that feeds the tiles. `components/pages/company-page.tsx` uses it only when the brand is below its bar; `lib/data/search-index.ts` agrees.
3. `lib/data/boards.ts` builds every category board from the companies themselves rather than from threshold-gated score rows, so a brand is ranked in its primary category whenever it has a score. `app/[slug]/page.tsx` already read the rank off that board, so the rank tile now appears for every scored company. Ranking everyone is only safe because the published score is the 0.10 posterior quantile under a leave-one-out prior: one positive comment buys a mid-table position near the category baseline, never the top (score.py, methodology 2.2.0).
4. Nothing changes in the scoring run, the eligibility flags or the collection lanes. No new constant, no new method.
5. A brand with zero opinionated labels shows no score and no rank. Classification, not collection, closes that gap: `worker/classify_brands.py --rejudge` re-decided all 1,671 mentions of the 70 such brands in the outreach set for $0.31 and moved 3 of them.
