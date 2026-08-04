# 0004 — Love and hate are two axes, not one scale

**Status:** Accepted · **Date:** 2026-08-04 · **Decided by:** Vlad Shvets, on the research

## Context

The obvious design is one sentiment score per brand: rank descending for "most loved", ascending for "most hated". Two columns, one number.

That design has a defect that shows up immediately in real data. A brand that half the community loves and half despises produces a middling net score — identical to a brand nobody has an opinion about. The single most interesting brands in any category become invisible.

The psychology literature says this is not a modelling convenience but a real property of the underlying attitudes. Positive and negative affect are separable substrates rather than poles of one scale ([Cacioppo, Gardner & Berntson, 1997](https://journals.sagepub.com/doi/10.1207/s15327957pspr0101_2)), and brand hate is studied as a distinct construct with its own antecedents rather than as the absence of brand love ([Zarantonello et al.](https://www.sciencedirect.com/science/article/abs/pii/S0148296319302590)).

## Decision

Every brand carries **two independent scores** — `love_score` and `hate_score` — each an empirical-Bayes shrunk rate over its own qualifying mention set.

The two-column board reads directly off them. A brand can rank high on both, and when it does the site says so rather than averaging the fact away.

Formulas and the shrinkage estimator are specified in [../07-index-methodology.md](../07-index-methodology.md).

## Consequences

**A brand can appear in both columns.** This is correct behaviour, not a bug, and the UI needs a first-class "polarizing" treatment for it. See [../09-design.md](../09-design.md).

**Two scores need two error bars.** Both get published. A score without its interval is the thing a hostile CMO attacks first.

**The consolidated ranking table needs a defined sort key.** The two axes do not collapse into one ordering for free. The methodology doc must state which key the default table sorts on and why.

**Upvotes stay out of both scores.** Reddit fuzzes displayed vote counts by design, and a single seeded upvote was shown to inflate final scores by 25% through herding ([Muchnik, Aral & Taylor, *Science*, 2013-08-09](https://www.science.org/doi/10.1126/science.1240466)). Votes become a separate, clearly labelled salience metric.

## The confound this does not fix

⚠️ Mention volume tracks **company size**, and complaint rate tracks **adoption model**. Users forced onto enterprise software complain; users who chose a self-serve tool praise it. The "most hated" column will reliably surface category incumbents.

Two axes do not fix this, because the confound sits in the exposure population rather than in the estimator. No post-hoc statistical correction exists.

The honest response is disclosure plus a second view: each brand also gets a **trajectory against its own baseline** over time, which is immune to the confound because the comparison is the brand against itself. The methodology page states the limitation in plain language.

## Alternatives rejected

| Option | Why not |
|---|---|
| Single net sentiment score | Makes a polarizing brand indistinguishable from an ignored one. |
| Wilson lower bound as the ranking objective | Answers "what is the worst-case true rate", so it ranks volume rather than quality. Kept as an eligibility gate and a published error bar instead. |
| Raw positive percentage | A brand with six mentions, all positive, outranks one with four thousand at 80%. Shrinkage exists precisely to stop this. |
| Upvote-weighted scoring | Vote counts are fuzzed, power-law distributed, subreddit-size dependent, and demonstrably herd. |

---

[← Back to README](../README.md) · [Index methodology](../07-index-methodology.md) · [Design](../09-design.md)
