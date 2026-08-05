# Ranking Index Specification

## Bottom line

- Rank on an **empirical-Bayes Beta-Binomial posterior mean**, shrunk toward the category base rate. IMDb's weighted rating is the same estimator wearing a friendlier name ([IMDb Ratings FAQ](https://help.imdb.com/article/imdb/track-movies-tv/faq-for-imdb-ratings/G67Y87TFYYP6TWAV)).
- **Fit the shrinkage constant from the data**, by method of moments or MLE on the observed spread of per-brand rates ([Robinson, Variance Explained](http://varianceexplained.org/r/empirical_bayes_baseball/)). A round number invites "your cutoff is arbitrary." A fitted one has an answer.
- **The denominator is opinionated mentions only**, `N_op = pos + neg`. Scoring over all mentions makes rank a function of ubiquity, because widely-used tools accrue incidental references that carry no opinion.
- **One published metric: the Reddit Love Score.** It is `round(100·p̃)`, an integer from 0 to 100, using the empirical-Bayes estimator below. Sort it descending for the consolidated view: most loved is at the top and most hated is at the bottom.
- **No upvote weighting in the headline index.** A single seeded upvote inflated final scores by 25% through herding ([Muchnik, Aral & Taylor, *Science*, 2013-08-09](https://www.science.org/doi/10.1126/science.1240466)).
- **The eligibility gate is category-scaled and runs on effective sample size, never raw `n`.** Deep, Standard, and Thin categories require `n_eff` of 600, 400, and 200 respectively; four diversity floors apply separately on top ([design effect](https://en.wikipedia.org/wiki/Design_effect)).
- ⚠️ **The exposure confound cannot be fixed statistically.** Mention volume tracks company size and complaint rate tracks adoption model. The site must say so in plain language, on the page.

---

## 1. The estimator

Rank on the posterior mean of a Beta-Binomial model, shrunk toward the category's own base rate. The trial count is **opinionated mentions only**.

```
N_op = pos + neg
p̃    = (x_pos + α₀) / (N_op + α₀ + β₀)
Reddit Love Score = round(100·p̃)
```

| Symbol | Meaning |
|---|---|
| `x_pos` | positive opinionated mentions for this brand in this category |
| `N_op` | `pos + neg` for this brand in this category — the denominator for the estimator |
| `n` | all eligible mentions, opinionated or not; reported everywhere, never a denominator |
| `α₀, β₀` | Beta prior fitted per category from the observed distribution of per-brand rates |
| `m` | prior strength, `m = α₀ + β₀` — the number of "virtual" mentions the prior is worth |
| `C` | category base rate, `C = α₀ / m` |

**Why neutrals are excluded from the denominator.** Widely-adopted tools accrue large incidental-mention volume ("export it to X", "the X API") that carries no opinion at all. Scoring over every mention dilutes the estimator in proportion to how often a brand is merely referenced, so rank drifts toward ubiquity and away from sentiment.

Neutral and abstained mentions are still counted and still published. Because the ratio runs over a subset of `n`, the published Reddit Love Score ships with `neutral_share` and `abstain_share`. A score computed over 40% of a brand's mentions is a different claim from one computed over 90%, and the reader has to see which one they are looking at.

Fit `α₀` and `β₀` by method of moments or MLE across every brand in the category, **leave-one-out** — a brand is excluded from the prior it is scored against, so the dominant brand is not pinned to its own mean ([Robinson, Variance Explained](http://varianceexplained.org/r/empirical_bayes_baseball/)). Laplace add-one is the degenerate `α₀ = β₀ = 1` case: far too weak a prior.

**Derivation (mine, algebraically checkable — not a cited claim).** IMDb publishes `WR = v/(v+m)·R + m/(v+m)·C` ([IMDb Ratings FAQ](https://help.imdb.com/article/imdb/track-movies-tv/faq-for-imdb-ratings/G67Y87TFYYP6TWAV)). Substituting `α₀ = mC` and `β₀ = m(1−C)` into `p̃` yields `(x_pos + mC)/(N_op + m)`, which for `R = x_pos/N_op` and `v = N_op` is exactly `WR`. Same maths, better PR.

**Worked check** (category prior C = 0.62, m = 400, so `α₀` = 248; arithmetic computed for this spec):

| Brand | Opinionated split | `N_op` | Observed positive share | `p̃` |
|---|---|---|---|---|
| A | 5 positive, 1 negative | 6 | 0.833 | (248 + 5) / 406 = **0.623** |
| B | 3,200 positive, 800 negative | 4,000 | 0.800 | (248 + 3,200) / 4,400 = **0.784** |

B beats A by a wide margin, which is the correct behavior: a 5-of-6 split is not evidence of anything. A never reaches a board in any case — at `N_op` = 6 it fails the eligibility gate in §5 and publishes as **Below threshold**. Shrinkage does its real work on the brands that clear the gate and sit near it.

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

## 3. One estimator, published once

Love and hate are separable substrates rather than simply the absence of the other ([Cacioppo, Gardner & Berntson 1997](https://journals.sagepub.com/doi/10.1207/s15327957pspr0101_2)), and brand hate has distinct antecedents ([Zarantonello et al.](https://www.sciencedirect.com/science/article/abs/pii/S0148296319302590)). That psychology is why the denominator remains opinionated mentions only: neutral references must not erase a positive or negative opinion merely because a brand is widely named.

The former Love and Hate indexes used the shared denominator `N_op = pos + neg`. Before separate shrinkage, `H = neg/N_op = 1 − pos/N_op = 1 − L` exactly. The two indexes were therefore algebraically complementary; the redundancy was already recorded in the consequences of decisions/0004. The site publishes that estimator once, as the Reddit Love Score, rather than fitting the same split twice.

This is not a net score over all mentions — the failure that a single-score warning would correctly identify. It remains the positive share of **opinionated** mentions, empirically shrunk toward the leave-one-out category prior as in §1. Sorting the published Reddit Love Score descending is the consolidated ordering. “Most Hated” names the lower position in that ordering; it is not a second fit.

**Data model.** Every mention carries `label ∈ {positive, negative, neutral, recommendation, abstain}` plus intensity and model confidence — see [06-sentiment.md](06-sentiment.md). A mention in a post body and a mention in a comment are counted and scored identically. They remain distinct `doc_type` objects so the evidence card labels the object and links to its own permalink; neither type receives different size, order, prominence, or scoring weight. Per brand, per category:

| Field | Definition | Role |
|---|---|---|
| `reddit_love_score` | `round(100·p̃)`, the published Reddit Love Score | ranked, descending |
| `polarization` | `2·min(pos, neg) / N_op` — 1 when observed opinion splits evenly, 0 when it is one-sided | published evidence, not ranked |
| `n`, `n_eff` | all eligible mentions and cluster-adjusted effective mentions | published evidence |
| `neutral_share`, `abstain_share` | shares of `n` carrying no opinion, outside the estimator denominator | published evidence |
| `n_authors`, `n_subreddits`, thread and author concentration | diversity evidence | published evidence |

**How disagreement differs from being ignored.** An ignored brand fails the separate eligibility gate in §5 and never reaches a board. Among brands that clear it, a mid-scale Reddit Love Score together with a low `neutral_share` indicates genuine disagreement: many mentions contain opinions, split on both sides. `polarization` remains published to make that evidence explicit, but it no longer needs `2·min(L̃, H̃) / (L̃ + H̃)` because there is no second fit.

---

## 4. No upvote weighting in the headline index

**The case for votes:** an upvote is a community endorsement of a specific claim, so a comment at +900 arguably carries more information than one at +2.

**The case against, which wins:** Reddit fuzzes displayed vote counts by design to defeat reverse-engineering (exact mechanism **NOT VERIFIED** from a first-party page). Scores are power-law, subreddit-size and time-of-day dependent, and causally inflated — one seeded upvote raised final scores 25% ([Muchnik, Aral & Taylor, *Science*, 2013-08-09](https://www.science.org/doi/10.1126/science.1240466)).

**Landing it:** votes are excluded from the Reddit Love Score entirely. They are published as a separate, clearly labeled **salience** metric that never feeds the rank.

If salience is ever blended in (not in v1), the only defensible shape is `v* = percentile_rank(log1p(score))` within subreddit × month, capped as `w = 1 + λ·v*`, λ ≤ 0.5 and published. No comment may exceed roughly twice another's weight.

---

## 5. The eligibility gate, derived

Pick a published precision target and solve for the sample size. Do not pick a round number and back-fill a story.

```
n_min = z²·0.25 / h²
```

| Tier | Half-width `h` | z (95%) | p | `n_min` | Precision target |
|---|---|---|---|---|---|
| Deep | ±4 pp | 1.96 | 0.5 | 600 | highest precision target, in **effective** observations |
| Standard | ±5 pp | 1.96 | 0.5 | 400 | standard precision target, in **effective** observations |
| Thin | ±7 pp | 1.96 | 0.5 | 200 | lower-volume category precision target, in **effective** observations |

`p = 0.5` is the variance-maximizing worst case, so each tier's threshold is conservative at every real rate — **for independent draws.** Tier assignment is mechanical from measured category volume and is frozen with the methodology version; it is never hand-picked per category or brand. Reddit mentions are not independent draws. They cluster inside a handful of mega-recommendation threads, and inside a thread the same authors repeat. Correlated mentions carry less information than independent ones.

That makes the derivation above the *start* of the argument. Taken alone it is the wrong model for this data, and shipping it as the gate would hand a critic the objection it was meant to close.

### The design-effect correction

```
DEFF  = 1 + (m̄ − 1)·ICC
n_eff = n / DEFF
```

`m̄` is the mean mentions per cluster for that brand and `ICC` the intra-cluster correlation, estimated from the data. This is Kish's design effect and the effective sample size it implies ([design effect](https://en.wikipedia.org/wiki/Design_effect)). `m̄` is a cluster size and has nothing to do with the prior strength `m` in §1.

**Decision, marked as ours rather than cited:** compute `DEFF` twice — clustering by thread and clustering by author — and carry the larger of the two, so the gate is set by whichever dependence structure is worse for that brand.

> **The separate eligibility gate is `n_eff ≥ n_min` for the category's frozen tier:** Deep `≥ 600`, Standard `≥ 400`, Thin `≥ 200`. Raw `n` is never the gate. Both numbers are published on every brand page, and both appear in the downloadable counts.

**Worked check** (Standard tier; ICC = 0.08, illustrative — the real value is measured in Phase 0; arithmetic computed for this spec):

| Brand | `n` | Threads | `m̄` | `DEFF` | `n_eff` | Verdict |
|---|---|---|---|---|---|---|
| C | 1,400 | 210 | 6.7 | 1.45 | **963** | ranked |
| D | 900 | 45 | 20.0 | 2.52 | **357** | Below threshold |
| E | 2,600 | 130 | 20.0 | 2.52 | **1,032** | ranked |

D clears the naive 400 twice over and still fails, because its 900 mentions live in 45 threads and 45 threads is not 900 independent observations. E is clustered exactly as hard and passes on volume. That gap is the whole reason the correction exists.

The naive derivation is still worth publishing: it shows the precision target was chosen rather than invented. What answers "your cutoff is arbitrary" is the full chain — `n`, the measured `ICC`, `DEFF`, `n_eff`, and the code that turns one into the other. Comparable sites publish a round number and keep the internals secret: Metacritic fires at 4 reviews ([Metacritic](https://metacritichelp.zendesk.com/hc/en-us/articles/14478499933079-How-do-you-compute-METASCORES)), G2 at 10+ in-category reviews ([G2](https://documentation.g2.com/docs/research-scoring-methodologies)).

### Confidence intervals

Clustered observations break the independence assumption behind Wilson and Beta intervals, and both understate the spread as a result. Intervals come from a **cluster bootstrap: resample whole threads and whole authors rather than individual mentions** ([bootstrap, clustered-data resampling](https://en.wikipedia.org/wiki/Bootstrapping_(statistics))). Every published score carries a 90% interval from that procedure.

### Diversity floors

Shrinkage and the separate `n_eff` eligibility gate still will not stop a coordinated push on their own, because a brigade can spread itself across threads. All four diversity floors are mandatory, per brand, per category, and do not scale with the category tier:

| Floor | Value | Defends against |
|---|---|---|
| Distinct authors | ≥ 50 | a small sockpuppet ring manufacturing a rank |
| Distinct subreddits | ≥ 5 | a single hostile or captured community defining a brand |
| Max share from one thread | ≤ 20% of `n` | one viral incident thread swamping years of ordinary sentiment |
| Max share from one author | ≤ 5% of `n` | one prolific voice carried across many threads |

A brand failing the `n_eff` gate or any diversity floor is listed as **Below threshold**, with the failing test named. It is never silently omitted. This is distinct from **Category cannot be ranked**: a category can fail its five-subreddit viability test even when an individual brand within it passes every brand-level test; that brand is not below threshold.

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
| Published Reddit Love Score across categories, with a per-category cap | pooled discovery board; a maximum of five brands from any category appear in each list | 🟢 use for the pooled board, with an explicit on-page disclosure |
| Z-score within category | assumes comparable variance; unstable when a category has few brands | 🟡 not for Phase 1 |
| Within-category percentile of `p̃` | comparable by construction, but answers a category-standing question | ⚪ not used for the pooled board |
| Category-demeaned `Δ = p̃ − C` | ranks "beats its own neighbors" | ⚪ not a published score or pooled-board rank |

The homepage pooled board takes the top 100 most loved and top 100 most hated from opposite ends of the one published-score ordering, subject to the maximum of five brands per category in each list. The lists are disjoint. If fewer than 200 brands qualify, each list contains at most `floor(N/2)` brands, and the page states the actual count rather than implying 100.

Publish every category's `C` alongside the board. State openly that the pooled board answers a different question from a category page: it is a capped, cross-category discovery view, not a claim that categories have identical baselines. The per-category cap and that explicit disclosure are the mitigation for using the published Reddit Love Score across categories.

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
| 6 | Eligibility and derivation | the category's frozen tier and precision target; the precision math; the design-effect correction; the corresponding `n_eff ≥ n_min` gate; all four diversity floors |
| 7 | Uncertainty | 90% cluster-bootstrap interval on every score; overlapping ranks declared tied |
| 8 | Category definitions and pooled board | each category's `C`, assignment rules, appeal path for miscategorization, and the pooled board's maximum of five brands per category in each list |
| 9 | Manipulation controls | that countermeasures exist, without publishing the evasion recipe |
| 10 | What the index is NOT | not product quality, not a survey, not population-representative; Reddit skew stated; Most Loved and Most Hated are opposite ends of one ordering |
| 11 | Corrections and appeals | named contact, response SLA, public changelog with effective dates |
| 12 | Reproducibility artifact | downloadable per-brand counts — pos, neg, neutral, abstain, `n`, `n_eff` — behind every score |

Item 12 ends more disputes than the other eleven combined. A CMO who can download the counts argues with the counts, not with Reddit Index.

---

[← Back to README](README.md) · [01-legal.md](01-legal.md) · [06-sentiment.md](06-sentiment.md)
