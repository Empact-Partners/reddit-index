# 0006 — One published metric: the Reddit Love Score

**Status:** Accepted · **Date:** 2026-08-05 · **Decided by:** Vlad Shvets
**Supersedes:** [0004 — Love and hate are two axes, not one scale](0004-two-axis-index.md)

## Bottom line

Every brand carries **one** published number, the **Reddit Love Score**, 0–100. It is the empirical-Bayes shrunk positive rate over opinionated mentions, rescaled. Sorting it descending *is* the consolidated view: most loved at the top, most hated at the bottom. Most Hated is the same ordering read from the other end, never a second fit.

This is not a retreat from 0004's statistics. Every estimator in 0004 survives: the opinionated denominator, the shrinkage, the leave-one-out priors, the cluster-bootstrap intervals, the published `neutral_share`. What changes is that the site stops publishing a second number that 0004 itself showed was nearly determined by the first.

## Context

0004 established two independently shrunk scores, `love_score` and `hate_score`, on the grounds that positive and negative affect are separable constructs and a net score would make a contested brand look like an ignored one.

That reasoning is sound for *affect*. It is not sound for *this estimator*, and 0004 says so in its own Consequences section:

> **The two boards are near-complements.** Over the shared denominator `L + H = 1` before shrinkage, so the top of one column sits near the bottom of the other.

Both indices run over `N_op = pos + neg`. So `L = pos/N_op` and `H = neg/N_op` are algebraically complementary — `H = 1 − L` exactly, before shrinkage. The second index carries no information the first does not, because the denominator was already restricted to opinionated mentions in order to solve a different problem.

0004 then had to carry three separate provisions to manage a redundancy it had created: a warning that a brand in both top tens is an anomaly, a renormalised polarization formula because `L̃ + H̃ ≠ 1` after separate fits, and an open item requiring the consolidated table to declare a sort key that the two axes do not yield for free.

The product spec resolves it from the other direction. The requirement is a single ranked list with the loved end at the top and the hated end at the bottom, and two visible metrics per row. That is one ordering.

## Decision

**Reddit Love Score** is the single published index.

```
N_op  = pos + neg                        opinionated mentions only
L̃     = (x_pos + α₀) / (N_op + α₀ + β₀)   empirical-Bayes shrunk positive rate
Reddit Love Score = round(100 · L̃)
```

`α₀, β₀` are fitted per category, leave-one-out, exactly as in [../07-index-methodology.md §1](../07-index-methodology.md). No separate hate fit is performed, so no renormalisation is needed and no pair of scores can disagree.

| Surface | Meaning |
|---|---|
| **Most Loved** | The ordering, descending, truncated |
| **Most Hated** | The same ordering, ascending, truncated |
| **Consolidated** | The whole ordering, descending, every qualifying brand |
| Headline metrics per row | Reddit Love Score, and total mention count |

`neutral_share`, `abstain_share`, raw `n`, `n_eff`, the diversity floors and the 90% cluster-bootstrap interval all remain published. They move from the headline to the evidence row.

## Consequences

**"Most Hated" is a label on a position, not a measurement of hate.** The bottom of the loved ordering is where a brand's opinionated mentions skew negative. That is what the column means, and [0005](0005-superlative-labels.md) already requires the measured variable to ship beside every superlative.

**The polarizing-vs-ignored objection is answered by the gate, not by a second axis.** 0004's worry was that a contested brand and an ignored brand both land mid-scale. They do — but they never appear together, because an ignored brand does not clear `n_eff ≥ 400` and its category threshold, and publishes as **Not enough data**. Everything on a board has volume by construction. Among brands that clear the gate, a mid-scale score means genuine disagreement, and `neutral_share` distinguishes "people argue about it" (low neutral share) from "people mention it without caring" (high neutral share). Both are published on the brand page.

**Polarization stays a published field.** It no longer needs `2·min(L̃,H̃)/(L̃+H̃)`, because there is no second fit to reconcile. It is derived from `L̃` near 0.5 together with a low `neutral_share`, and it is stated on the brand page rather than inferred from the boards.

**The consolidated sort key is no longer an open question.** It is the Reddit Love Score, descending. 0004 left this undefined; the redundancy it created was the reason.

**A brand can no longer appear on both boards.** Under 0004 that was possible and had to be documented as an anomaly. Under one ordering it is arithmetically impossible.

**Cross-category pooling needs its own rule.** A single score does not make categories comparable — password managers run structurally positive and payment processors run structurally negative. The pooled homepage board sorts on the raw score with a per-category cap, decided separately in [0007](0007-flat-url-namespace.md)'s sibling record and specified in [../07-index-methodology.md §7](../07-index-methodology.md).

## What 0004 got right, and keeps

| 0004 provision | Status |
|---|---|
| Denominator is `N_op = pos + neg`, never all mentions | ✅ Unchanged |
| Empirical-Bayes shrinkage, leave-one-out category priors | ✅ Unchanged |
| `neutral_share` and `abstain_share` published beside every score | ✅ Unchanged |
| 90% cluster-bootstrap intervals over threads and authors | ✅ Unchanged |
| No upvote weighting in the headline index | ✅ Unchanged |
| Wilson rejected as the ranking objective | ✅ Unchanged |
| Exposure confound disclosed; trajectory against own baseline | ✅ Unchanged |
| Two separate published indices | ❌ Superseded by this record |
| Polarization as `2·min(L̃,H̃)/(L̃+H̃)` | ❌ No second fit exists to normalise |

## Alternatives rejected

| Option | Why not |
|---|---|
| Keep both indices, publish Love as the headline | Two numbers a reader can check against each other, one of which is ~`1 − ` the other. The first person to notice publishes a post about it |
| Net score over *all* mentions (`pos − neg` over `n`) | The failure 0004 correctly identified. Ubiquity dilutes the score and rank drifts toward adoption. The opinionated denominator is what makes a single axis safe |
| Rank Most Hated on a separately fitted negative rate | Reintroduces `L̃ + H̃ ≠ 1`, so the two boards can disagree about the same brand with no principled tie-break |
| Two axes internally, one exposed | The internal second fit still has to be reconciled and maintained, for a number nothing renders |

---

[← Back to README](../README.md) · [0004 (superseded)](0004-two-axis-index.md) · [0005](0005-superlative-labels.md) · [Index methodology](../07-index-methodology.md) · [Concept](../00-concept.md)
