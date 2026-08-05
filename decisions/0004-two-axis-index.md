# 0004 — Love and hate are two axes, not one scale

**Status:** ⚠️ **Superseded** by [0006 — One published metric: the Reddit Love Score](0006-single-reddit-love-score.md) · **Date:** 2026-08-04 · **Superseded:** 2026-08-05 · **Decided by:** Vlad Shvets, on the research

> **This record is retained for its reasoning, not as the current design.** The site publishes
> **one** index. Because both scores here run over the shared denominator `N_op = pos + neg`,
> they are algebraically complementary (`H = 1 − L` before shrinkage) — a redundancy this record
> documents in its own Consequences section. Everything else below is still in force: the
> opinionated denominator, the shrinkage, the leave-one-out priors, the cluster-bootstrap
> intervals, the published `neutral_share`, and the exposure confound. See [0006](0006-single-reddit-love-score.md).

## Bottom line

Every brand carries two independently shrunk scores, `love_score` and `hate_score`, each computed over opinionated mentions only (`N_opinionated = pos + neg`). One net score would make a contested brand look identical to an ignored one. Because the denominator is shared, the two boards run close to inverses, so polarization ships as its own published field rather than as "a brand tops both columns."

## Context

The obvious design is one sentiment score per brand: rank descending for "most loved", ascending for "most hated". Two columns, one number.

That design has a defect that shows up immediately in real data. A brand that half the community loves and half despises produces a middling net score — identical to a brand nobody has an opinion about. The single most interesting brands in any category become invisible.

The psychology literature says this is not a modelling convenience but a real property of the underlying attitudes. Positive and negative affect are separable substrates rather than poles of one scale ([Cacioppo, Gardner & Berntson, 1997](https://journals.sagepub.com/doi/10.1207/s15327957pspr0101_2)), and brand hate is studied as a distinct construct with its own antecedents rather than as the absence of brand love ([Zarantonello et al.](https://www.sciencedirect.com/science/article/abs/pii/S0148296319302590)).

## Decision

Every brand carries **two independent scores** — `love_score` and `hate_score` — each an empirical-Bayes shrunk rate over that brand's **opinionated mentions**, `N_opinionated = pos + neg`. Love is shrunk against the category's positive base rate, hate against its negative base rate.

Neutral and abstained mentions are counted and published, never used as a denominator. Scoring over every mention makes rank a function of ubiquity: widely adopted tools accrue incidental references ("export it to X", "the X API") that carry no opinion and dilute both indexes.

The two-column board reads directly off the two scores. They are ranked on two separate indices rather than being one ordering displayed twice.

Formulas, the shrinkage estimator and the fitted priors are specified in [../07-index-methodology.md](../07-index-methodology.md).

## Consequences

**The two boards are near-complements.** Over the shared denominator `L + H = 1` before shrinkage, so the top of one column sits near the bottom of the other. A brand appearing in both top tens is an anomaly to investigate, not a feature to design for. See [../09-design.md](../09-design.md).

**No rule may assume `L̃ + H̃ = 1`.** The two rates are shrunk against separate category priors, so the shrunk pair does not sum to exactly 1. Polarization is therefore normalised as `2·min(L̃, H̃) / (L̃ + H̃)`, which keeps it inside [0, 1] whatever the two fits do.

**Polarization is published, not inferred.** A contested brand shows up as a low `neutral_share` with both shrunk rates near 0.5: plenty of people hold an opinion and they disagree. That is a different claim from "loved" or "hated", so it gets its own field instead of being read off the boards.

**The excluded share travels with the score.** A score computed over 40% of a brand's mentions is a different claim from one computed over 90%, so `neutral_share` and `abstain_share` are published beside every score.

**Two scores need two error bars.** Both are 90% intervals from a cluster bootstrap over threads and authors — mentions are not independent draws, and Wilson or Beta intervals understate the spread ([bootstrap](https://en.wikipedia.org/wiki/Bootstrapping_(statistics))). A score without its interval is the thing a hostile CMO attacks first.

**The consolidated ranking table needs a defined sort key.** The two axes do not collapse into one ordering for free. The methodology doc must state which key the default table sorts on and why.

**Upvotes stay out of both scores.** Reddit fuzzes displayed vote counts by design, and a single seeded upvote was shown to inflate final scores by 25% through herding ([Muchnik, Aral & Taylor, *Science*, 2013-08-09](https://www.science.org/doi/10.1126/science.1240466)). Votes become a separate, clearly labelled salience metric.

## The confound this does not fix

⚠️ Mention volume tracks **company size**, and complaint rate tracks **adoption model**. Users forced onto enterprise software complain; users who chose a self-serve tool praise it. The "most hated" column will reliably surface category incumbents.

Two axes do not fix this, because the confound sits in the exposure population rather than in the estimator. No post-hoc statistical correction exists.

The opinionated denominator closes a different hole. Dropping incidental mentions stops ubiquity from diluting a score; it says nothing about who ends up holding an opinion in the first place.

The honest response is disclosure plus a second view: each brand also gets a **trajectory against its own baseline** over time, which is immune to the confound because the comparison is the brand against itself. The methodology page states the limitation in plain language.

## Alternatives rejected

| Option | Why not |
|---|---|
| Single net sentiment score | Makes a polarizing brand indistinguishable from an ignored one. |
| Scoring over all mentions rather than `N_opinionated` | Rank becomes a function of how often a brand is merely referenced, so ubiquitous tools drift toward the category mean on both boards. |
| Wilson lower bound as the ranking objective | Answers "what is the worst-case true rate". Its penalty term shrinks with `n`, so it penalises small samples and, at equal observed rates, favours the larger one ([evanmiller.org](https://www.evanmiller.org/how-not-to-sort-by-average-rating.html)). |
| Raw positive percentage | A brand with six opinionated mentions, all positive, outranks one with four thousand at 80%. Shrinkage exists precisely to stop this. |
| Upvote-weighted scoring | Vote counts are fuzzed, power-law distributed, subreddit-size dependent, and demonstrably herd. |

Wilson is rejected as an ordering, and the reason has to be stated precisely. It ranks observed rate and sample size jointly, not volume alone: at z = 1.96, p̂ = 0.90 over n = 100 gives `w⁻` ≈ 0.826, ahead of p̂ = 0.80 over n = 400 at ≈ 0.758 (arithmetic computed for this record).

The objection stands anyway, because the size penalty is an artifact of the question the bound answers: a small brand can lose to a large one on identical observed behaviour. Wilson is neither the rank, the eligibility gate, nor the error bar here — eligibility runs on `n_eff ≥ 400` and the interval comes from the cluster bootstrap ([../07-index-methodology.md](../07-index-methodology.md)).

---

[← Back to README](../README.md) · [Index methodology](../07-index-methodology.md) · [Design](../09-design.md)
