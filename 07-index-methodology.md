# Ranking Index Specification

## Bottom line

- Rank on an **empirical-Bayes Beta-Binomial posterior mean**, shrunk toward the category base rate. IMDb's weighted rating is the same estimator wearing a friendlier name ([IMDb Ratings FAQ](https://help.imdb.com/article/imdb/track-movies-tv/faq-for-imdb-ratings/G67Y87TFYYP6TWAV)).
- **Fit the shrinkage constant from the data**, by method of moments or MLE on the observed spread of per-brand rates ([Robinson, Variance Explained](http://varianceexplained.org/r/empirical_bayes_baseball/)). A round number invites "your cutoff is arbitrary." A fitted one has an answer.
- **The denominator is opinionated mentions only**, `N_op = pos + neg`. Scoring over all mentions makes rank a function of ubiquity, because widely-used tools accrue incidental references that carry no opinion.
- **Two indexes, never one net score.** Love and hate are separable substrates, not poles of a single scale ([Cacioppo, Gardner & Berntson 1997](https://journals.sagepub.com/doi/10.1207/s15327957pspr0101_2)).
- **No upvote weighting in the headline index.** A single seeded upvote inflated final scores by 25% through herding ([Muchnik, Aral & Taylor, *Science*, 2013-08-09](https://www.science.org/doi/10.1126/science.1240466)).
- **Eligibility gates on the effective sample size, `n_eff ≥ 400`, not raw `n`.** Mentions cluster inside mega-threads and inside threads by author, so the simple-random-sample derivation of 400 is a floor on an assumption this data does not meet ([design effect](https://en.wikipedia.org/wiki/Design_effect)). Four independence floors apply on top.
- ⚠️ **The exposure confound cannot be fixed statistically.** Mention volume tracks company size and complaint rate tracks adoption model. The site must say so in plain language, on the page.

---

## 1. The estimator

Rank on the posterior mean of a Beta-Binomial model, shrunk toward the category's own base rate. The trial count is **opinionated mentions only**.

```
N_op = pos + neg
p̃    = (x + α₀) / (N_op + α₀ + β₀)
```

| Symbol | Meaning |
|---|---|
| `x` | opinionated mentions carrying the target label (positive for love, negative for hate) |
| `N_op` | `pos + neg` for this brand in this category — the denominator for both indexes |
| `n` | all eligible mentions, opinionated or not; reported everywhere, never a denominator |
| `α₀, β₀` | Beta prior fitted per category from the observed distribution of per-brand rates |
| `m` | prior strength, `m = α₀ + β₀` — the number of "virtual" mentions the prior is worth |
| `C` | category base rate, `C = α₀ / m` |

**Why neutrals are excluded from the denominator.** Widely-adopted tools accrue large incidental-mention volume ("export it to X", "the X API") that carries no opinion at all. Scoring over every mention dilutes both indexes in proportion to how often a brand is merely referenced, so rank drifts toward ubiquity and away from sentiment.

Neutral and abstained mentions are still counted and still published. Because the ratio runs over a subset of `n`, every score ships with `neutral_share` and `abstain_share`. A score computed over 40% of a brand's mentions is a different claim from one computed over 90%, and the reader has to see which one they are looking at.

Fit `α₀` and `β₀` by method of moments or MLE across every brand in the category, **leave-one-out** — a brand is excluded from the prior it is scored against, so the dominant brand is not pinned to its own mean ([Robinson, Variance Explained](http://varianceexplained.org/r/empirical_bayes_baseball/)). Laplace add-one is the degenerate `α₀ = β₀ = 1` case: far too weak a prior.

**Derivation (mine, algebraically checkable — not a cited claim).** IMDb publishes `WR = v/(v+m)·R + m/(v+m)·C` ([IMDb Ratings FAQ](https://help.imdb.com/article/imdb/track-movies-tv/faq-for-imdb-ratings/G67Y87TFYYP6TWAV)). Substituting `α₀ = mC` and `β₀ = m(1−C)` into `p̃` yields `(x + mC)/(N_op + m)`, which for `R = x/N_op` and `v = N_op` is exactly `WR`. Same maths, better PR.

**Worked check** (category prior C = 0.62, m = 400, so `α₀` = 248; arithmetic computed for this spec):

| Brand | Opinionated split | `N_op` | Raw `L` | Shrunk `L̃` |
|---|---|---|---|---|
| A | 5 positive, 1 negative | 6 | 0.833 | (248 + 5) / 406 = **0.623** |
| B | 3,200 positive, 800 negative | 4,000 | 0.800 | (248 + 3,200) / 4,400 = **0.784** |

B beats A by a wide margin, which is the correct behavior: a 5-of-6 split is not evidence of anything. A never reaches a board in any case — at `N_op` = 6 it fails the eligibility gate in §5 and publishes as **Not enough data**. Shrinkage does its real work on the brands that clear the gate and sit near it.

---

## 2. Why not Wilson's lower bound

Wilson's lower bound is a good interval and a bad ranking objective ([binomial proportion CI](https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval)):

```
w⁻ = [p̂ + z²/(2n) − z·√(p̂(1−p̂)/n + z²/(4n²))] / (1 + z²/n)
```

It answers "what is the worst-case true rate given this sample." The penalty term shrinks as the sample grows, so the bound **penalises small samples**: among brands with similar observed rates it favours the higher-volume one. Evan Miller's own framing is "which items are good enough to show," not "who is #1" ([evanmiller.org](https://www.evanmiller.org/how-not-to-sort-by-average-rating.html)).

**It does not simply rank volume, and overstating that is its own error.** The bound ranks observed rate and sample size jointly, and a high-rate small-sample brand can still beat a low-rate large-sample one. At z = 1.96, p̂ = 0.90 over n = 100 gives `w⁻` ≈ 0.826, ahead of p̂ = 0.80 over n = 400 at `w⁻` ≈ 0.758, on a quarter of the volume (arithmetic computed for this spec).

The reason not to rank on it stands. The size penalty is an artifact of the question the estimator answers, so a small brand can lose to a large one on identical observed behaviour — precisely the attack a large brand would run, inverted.

| Objective | Answers | Ranks | Role in Reddit Index |
|---|---|---|---|
| Raw rate `x/N_op` | "what did we observe" | noise at small `N_op` | never published as a rank |
| Wilson lower bound | "worst-case true rate" | rate and sample size jointly, penalising small `n` | neither ranked on nor used as the error bar |
| Cluster-bootstrap interval | "how far does this move on a resample" | — | 🟢 the published error bar (§5) |
| Beta posterior mean | "best estimate of true rate" | quality | 🟢 the headline rank |

**Inference, clearly marked:** rank on the posterior mean and never on a lower bound. The published error bar is not a Wilson or Beta interval either — mentions are clustered, so both understate the true spread. Ranks whose 90% intervals overlap are declared statistically tied and rendered as a tie.

---

## 3. Two axes, never one

Love and hate are separable substrates rather than opposite ends of one scale ([Cacioppo, Gardner & Berntson 1997](https://journals.sagepub.com/doi/10.1207/s15327957pspr0101_2)), and brand hate is a distinct construct with its own antecedents ([Zarantonello et al.](https://www.sciencedirect.com/science/article/abs/pii/S0148296319302590)).

A net score collapses that. A brand whose opinionated mentions split evenly across 4,000 observations scores the same `net` as one that splits evenly across 40. The first is contested at scale, the second is noise, and a single number cannot say which is which.

**Data model.** Every mention carries `label ∈ {positive, negative, neutral, recommendation, abstain}` plus intensity and model confidence — see [06-sentiment.md](06-sentiment.md). Per brand, per category:

| Field | Definition | Ranked? |
|---|---|---|
| `love_score` | shrunk `L = pos/N_op`, prior fitted on the category's positive rates | yes, descending — left column |
| `hate_score` | shrunk `H = neg/N_op`, prior fitted on the category's negative rates | yes, descending — right column |
| `polarization` | `2·min(L̃, H̃) / (L̃ + H̃)` — 1 when opinion splits evenly, 0 when it is one-sided | shown, not ranked |
| `net` | `L̃ − H̃` | reported, never ranked on |
| `n`, `n_eff` | raw and cluster-adjusted mention counts | shown side by side |
| `neutral_share`, `abstain_share` | share of `n` that carries no opinion, so sits outside the ratio | shown beside every score |
| `n_authors`, `n_subreddits` | independence evidence | shown |

**Polarization has to survive independent shrinkage.** Raw `L` and `H` sum to 1 by construction over `N_op`, but the two shrunk values are fitted against separate category priors and are **not** guaranteed to sum to 1, so a bare `2·min(L̃, H̃)` can leave the unit interval. Dividing by `L̃ + H̃` normalises it: the metric reads as the balance of opinion and stays in [0, 1] whatever the two fits do.

No rule in this spec may assume `L̃ + H̃ = 1`. Where a sum is needed, compute it; do not treat it as an invariant.

**What the two boards can and cannot show.** Because the denominator is shared, love and hate are near-complements: within a category the Most Hated board runs close to the inverse of the Most Loved board, and a brand cannot sit near the top of both. The two-axis model still earns its place — it refuses the net collapse, and each row carries its own `n_eff`, interval and neutral share.

**Polarization is where a contested brand actually shows up:** both shrunk rates near 0.5 while `neutral_share` is low, meaning a lot of people hold an opinion and they disagree. That is a different claim from "loved" or "hated", which is why it gets its own published column instead of being inferred from the two boards. Both facts belong on the methodology page.

---

## 4. No upvote weighting in the headline index

**The case for votes:** an upvote is a community endorsement of a specific claim, so a comment at +900 arguably carries more information than one at +2.

**The case against, which wins:** Reddit fuzzes displayed vote counts by design to defeat reverse-engineering (exact mechanism **NOT VERIFIED** from a first-party page). Scores are power-law, subreddit-size and time-of-day dependent, and causally inflated — one seeded upvote raised final scores 25% ([Muchnik, Aral & Taylor, *Science*, 2013-08-09](https://www.science.org/doi/10.1126/science.1240466)).

**Landing it:** votes are excluded from `love_score` and `hate_score` entirely. They are published as a separate, clearly labeled **salience** metric that never feeds the rank.

If salience is ever blended in (not in v1), the only defensible shape is `v* = percentile_rank(log1p(score))` within subreddit × month, capped as `w = 1 + λ·v*`, λ ≤ 0.5 and published. No comment may exceed roughly twice another's weight.

---

## 5. The eligibility gate, derived

Pick a published precision target and solve for the sample size. Do not pick a round number and back-fill a story.

```
n_min = z²·p(1−p) / h²
```

| Half-width `h` | z (95%) | p | `n_min` | Note |
|---|---|---|---|---|
| ±10 pp | 1.96 | 0.5 | 97 | too loose to defend |
| ±7 pp | 1.96 | 0.5 | 196 | — |
| **±5 pp** | **1.96** | **0.5** | **384 → 400** | the precision target, in **effective** observations |
| ±3 pp | 1.96 | 0.5 | 1,068 | starves Phase 2 categories |

`p = 0.5` is the variance-maximizing worst case, so 400 is conservative at every real rate — **for independent draws.** Reddit mentions are not independent draws. They cluster inside a handful of mega-recommendation threads, and inside a thread the same authors repeat. 400 correlated mentions carry less information than 400 independent ones.

That makes the derivation above the *start* of the argument. Taken alone it is the wrong model for this data, and shipping it as the gate would hand a critic the objection it was meant to close.

### The design-effect correction

```
DEFF  = 1 + (m̄ − 1)·ICC
n_eff = n / DEFF
```

`m̄` is the mean mentions per cluster for that brand and `ICC` the intra-cluster correlation, estimated from the data. This is Kish's design effect and the effective sample size it implies ([design effect](https://en.wikipedia.org/wiki/Design_effect)). `m̄` is a cluster size and has nothing to do with the prior strength `m` in §1.

**Decision, marked as ours rather than cited:** compute `DEFF` twice — clustering by thread and clustering by author — and carry the larger of the two, so the gate is set by whichever dependence structure is worse for that brand.

> **The gate is `n_eff ≥ 400`.** Raw `n` is never the gate. Both numbers are published on every brand page, and both appear in the downloadable counts.

**Worked check** (ICC = 0.08, illustrative — the real value is measured in Phase 0; arithmetic computed for this spec):

| Brand | `n` | Threads | `m̄` | `DEFF` | `n_eff` | Verdict |
|---|---|---|---|---|---|---|
| C | 1,400 | 210 | 6.7 | 1.45 | **963** | ranked |
| D | 900 | 45 | 20.0 | 2.52 | **357** | Not enough data |
| E | 2,600 | 130 | 20.0 | 2.52 | **1,032** | ranked |

D clears the naive 400 twice over and still fails, because its 900 mentions live in 45 threads and 45 threads is not 900 independent observations. E is clustered exactly as hard and passes on volume. That gap is the whole reason the correction exists.

The naive derivation is still worth publishing: it shows the precision target was chosen rather than invented. What answers "your cutoff is arbitrary" is the full chain — `n`, the measured `ICC`, `DEFF`, `n_eff`, and the code that turns one into the other. Comparable sites publish a round number and keep the internals secret: Metacritic fires at 4 reviews ([Metacritic](https://metacritichelp.zendesk.com/hc/en-us/articles/14478499933079-How-do-you-compute-METASCORES)), G2 at 10+ in-category reviews ([G2](https://documentation.g2.com/docs/research-scoring-methodologies)).

### Confidence intervals

Clustered observations break the independence assumption behind Wilson and Beta intervals, and both understate the spread as a result. Intervals come from a **cluster bootstrap: resample whole threads and whole authors rather than individual mentions** ([bootstrap, clustered-data resampling](https://en.wikipedia.org/wiki/Bootstrapping_(statistics))). Every published score carries a 90% interval from that procedure.

### Diversity floors

Shrinkage and `n_eff` still will not stop a coordinated push on their own, because a brigade can spread itself across threads. All four floors are mandatory, per brand, per category:

| Floor | Value | Defends against |
|---|---|---|
| Distinct authors | ≥ 50 | a small sockpuppet ring manufacturing a rank |
| Distinct subreddits | ≥ 5 | a single hostile or captured community defining a brand |
| Max share from one thread | ≤ 20% of `n` | one viral incident thread swamping years of ordinary sentiment |
| Max share from one author | ≤ 5% of `n` | one prolific voice carried across many threads |

A brand failing the `n_eff` gate or any floor is listed as **Not enough data**, with the failing test named. It is never silently omitted.

---

## 6. Time weighting

Exponential decay `w(t) = exp(−ln2·Δt/H)` is the standard reputation forgetting factor, and G2 publishes a concrete shape: full weight for roughly 90 days, strong to 18 months, about 3% of original weight by three years ([G2](https://documentation.g2.com/docs/research-scoring-methodologies)).

**Recommended default: a trailing 12-month window with uniform weight inside it**, plus published 24-month and all-time archives. A window is auditable and reproducible by a third party. A decay half-life is a hidden knob that silently rewrites history, and every rank change becomes an accusation.

**What breaks with a six-year-old scandal.** It leaves the trailing index, which is correct — and is exactly when Reddit Index gets accused of laundering a reputation. The fix is not a longer window. It is a permanent per-brand **event register** plus a trajectory chart beside the current rank, so history stays visible even when it no longer scores.

---

## 7. Cross-category normalization

Category base rates differ structurally. Airlines, ISPs, and banks live at low positive rates for reasons unrelated to any individual brand's quality.

| Method | Behavior | Verdict |
|---|---|---|
| Raw `p̃` across categories | ranks categories, not brands | 🔴 never |
| Z-score within category | assumes comparable variance; unstable when a category has few brands | 🟡 not for Phase 1 |
| Within-category percentile of `p̃` | comparable by construction | 🟢 use for the all-categories board |
| Category-demeaned `Δ = p̃ − C` | ranks "beats its own neighbors" | 🟢 use, label the claim precisely |

Publish every category's `C` alongside the board. State openly that a cross-category leaderboard answers a different question than a category page, and label it as such rather than as one universal ranking.

---

## 8. ⚠️ The confound that must be disclosed on the site

**Mention volume tracks company size. Complaint rate tracks adoption model.** Users who were assigned a tool by procurement complain; users who chose one voluntarily praise. The "most hated" column will therefore reliably surface category incumbents and enterprise-sold products.

There is no post-hoc statistical fix, because the confound sits in the exposure population, not in the estimator. Shrinkage, normalization, `n_eff` and the diversity floors all operate on a sample already selected on adoption model. **Marked as inference — no primary source in this repo's research corpus.**

The opinionated denominator in §1 closes a different hole and not this one. Dropping incidental mentions stops ubiquity from diluting a score; it says nothing about who ends up holding an opinion in the first place.

**How the site discloses it:**

| Surface | Requirement |
|---|---|
| Every category page | one persistent line stating that rank reflects what Reddit says, not product quality, and that enterprise-sold incumbents skew negative |
| Every brand page | a trajectory chart against **the brand's own baseline** shown alongside the cross-brand rank |
| Methodology page | the limitation in plain language, not buried in a footnote |
| Cold outreach | lead with the brand's own trajectory, never with the cross-brand rank alone |

The per-brand trajectory is the honest presentation. "Your negative share moved from 31% to 44% over twelve months" is a claim about one company against itself and survives the size objection entirely.

---

## 9. Freeze and version the methodology before any result is seen

*Suzuki Motor Corp. v. Consumers Union*, 330 F.3d 1110 (9th Cir. 2003) reversed summary judgment for the publisher because a jury could find the test course had been altered, not because the published verdict was wrong ([FindLaw](https://caselaw.findlaw.com/court/us-9th-circuit/1359248.html)). The lesson: method integrity, not conclusion accuracy, is the exposed surface.

| Rule | Implementation |
|---|---|
| Freeze before first result | this file is tagged and its commit hash recorded before the first production crawl runs |
| Version | semantic version + effective date in the file header and on the public page |
| Change control | every change ships with a changelog entry: what changed, why, effective date, back-recomputation policy |
| No post-hoc tuning | a parameter is never changed after seeing where a specific named brand landed |
| Audit trail | the git history is the evidence that the method predates the result |

The fitted quantities are covered by the same discipline. `α₀`, `β₀`, and the measured `ICC` are refit on a published schedule, never between one brand's complaint and the next publish. Anything that looks like a knob turned after a complaint is the fact pattern to avoid. See [01-legal.md](01-legal.md) for the surrounding exposure, including the deliberate decision to display full comment text.

---

## 10. What the public methodology page must disclose

| # | Item | Detail required |
|---|---|---|
| 1 | Data source and window | subreddit scope, API vs archive, collection dates, refresh cadence |
| 2 | Brand resolution | alias list, ambiguous-name disambiguation, false-positive rate from a labeled audit |
| 3 | Sentiment labeling | model class, human-validated agreement rate, confusion matrix, sarcasm and negation handling |
| 4 | Unit of analysis | comment vs thread vs author; deduplication and crosspost rules |
| 5 | The formulas in full | estimator, the `N_op = pos + neg` denominator, per-category α₀/β₀ and how fitted, any λ, window |
| 6 | Eligibility and derivation | the precision math, the design-effect correction, the `n_eff ≥ 400` gate, all four independence floors |
| 7 | Uncertainty | 90% cluster-bootstrap interval on every score; overlapping ranks declared tied |
| 8 | Category definitions | each category's `C`, assignment rules, appeal path for miscategorization |
| 9 | Manipulation controls | that countermeasures exist, without publishing the evasion recipe |
| 10 | What the index is NOT | not product quality, not a survey, not population-representative; Reddit skew stated; the two boards described as near-complements |
| 11 | Corrections and appeals | named contact, response SLA, public changelog with effective dates |
| 12 | Reproducibility artifact | downloadable per-brand counts — pos, neg, neutral, abstain, `n`, `n_eff` — behind every score |

Item 12 ends more disputes than the other eleven combined. A CMO who can download the counts argues with the counts, not with Reddit Index.

---

[← Back to README](README.md) · [01-legal.md](01-legal.md) · [06-sentiment.md](06-sentiment.md)
