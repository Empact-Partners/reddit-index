# 0011 — A Reddit ❤️ Score on every company page

**Status:** Accepted · **Date:** 2026-08-19 · **Decided by:** Vlad Shvets

## Bottom line

Every company page shows a Reddit ❤️ Score. A brand that meets its category's ranking bar shows the board score, unchanged. A brand below the bar shows a score computed with the **same estimator and the same category prior over every opinionated mention collected for it** (the Positive and Negative tiles on its own page), and stays **unranked**: the rank tile still appears only for board members, and the boards do not change.

## Context

Before this ruling 546 of the 1,244 company pages in the outreach set showed a bare "—" because the brand's opinionated count inside the scoring window (trailing 365 days, scoring subreddits only) was below the category median. Of the 70 pages with no opinionated label at all, 59 simply had unclassified mentions. Vlad, 2026-08-19: "all the Reddit scores must be filled out anyway for all of these companies … compute based on the existing data." The company page is the outreach asset; a page with a number that matches its own tiles is the asset, a dash is not.

## The decision

1. `lib/data/page-score.ts` — a line-for-line TypeScript port of `worker/score.py`'s `fit_prior_pooled` (PRIOR_K 10, PRIOR_P0_SMOOTH 10, leave-one-out by mention mass within the brand's PRIMARY category) and `beta_quantile` at SCORE_QUANTILE 0.10. `tests/page-score.test.tsx` asserts integer parity against Python-produced fixtures.
2. `lib/data/snapshot.ts` computes `pageScore` per brand from the same aggregate that feeds the tiles. `components/pages/company-page.tsx` uses it only when the brand is below its bar; `lib/data/search-index.ts` agrees.
3. Nothing changes for boards, thresholds, eligibility, or the scoring run. No new constant, no new method. The methodology page states the rule in one paragraph.
4. A brand with zero opinionated labels shows no score. Classification, not collection, closes that gap (`worker/update.sh`).
