# Ranking Index Specification

## Bottom line

- Rank on an **empirical-Bayes Beta-Binomial posterior mean**, shrunk toward the category base rate. IMDb's weighted rating is the same estimator wearing a friendlier name ([IMDb Ratings FAQ](https://help.imdb.com/article/imdb/track-movies-tv/faq-for-imdb-ratings/G67Y87TFYYP6TWAV)).
- **Fit the shrinkage constant from the data**, by method of moments or MLE on the observed spread of per-brand rates ([Robinson, Variance Explained](http://varianceexplained.org/r/empirical_bayes_baseball/)). A round number invites "your cutoff is arbitrary." A fitted one has an answer.
- **Two indexes, never one net score.** Love and hate are separable substrates, not poles of a single scale ([Cacioppo, Gardner & Berntson 1997](https://journals.sagepub.com/doi/10.1207/s15327957pspr0101_2)).
- **No upvote weighting in the headline index.** A single seeded upvote inflated final scores by 25% through herding ([Muchnik, Aral & Taylor, *Science*, 2013-08-09](https://www.science.org/doi/10.1126/science.1240466)).
- **Eligibility is derived, not chosen:** n_min = z²p(1−p)/h² gives 384 at ±5pp, rounded up to 400, plus author, subreddit, and thread-concentration floors.
- ⚠️ **The exposure confound cannot be fixed statistically.** Mention volume tracks company size and complaint rate tracks adoption model. The site must say so in plain language, on the page.

---

## 1. The estimator

Rank on the posterior mean of a Beta-Binomial model, shrunk toward the category's own base rate.

```
p̃ = (x + α₀) / (n + α₀ + β₀)
```

| Symbol | Meaning |
|---|---|
| `x` | eligible mentions of this brand carrying the target label (positive for love, negative for hate) |
| `n` | eligible mentions of this brand in the category |
| `α₀, β₀` | Beta prior fitted per category from the observed distribution of per-brand rates |
| `m` | prior strength, `m = α₀ + β₀` — the number of "virtual" mentions the prior is worth |
| `C` | category base rate, `C = α₀ / m` |

Fit `α₀` and `β₀` by method of moments or MLE across every brand in the category ([Robinson, Variance Explained](http://varianceexplained.org/r/empirical_bayes_baseball/)). Laplace add-one is the degenerate `α₀ = β₀ = 1` case: far too weak a prior at n = 6.

**Derivation (mine, algebraically checkable — not a cited claim).** IMDb publishes `WR = v/(v+m)·R + m/(v+m)·C` ([IMDb Ratings FAQ](https://help.imdb.com/article/imdb/track-movies-tv/faq-for-imdb-ratings/G67Y87TFYYP6TWAV)). Substituting `α₀ = mC` and `β₀ = m(1−C)` into `p̃` yields `(x + mC)/(n + m)`, which for `R = x/n` and `v = n` is exactly `WR`. Same maths, better PR.

**Worked check** (category prior C = 0.62, m = 400; arithmetic computed for this spec):

| Brand | Raw | Raw rate | Shrunk `p̃` |
|---|---|---|---|
| A | 6 of 6 positive | 1.000 | (248 + 6) / 406 = **0.626** |
| B | 3,200 of 4,000 positive | 0.800 | (248 + 3,200) / 4,400 = **0.784** |

B beats A by a wide margin, which is the correct behavior. A perfect 6-for-6 is not evidence of anything.

---

## 2. Why not Wilson's lower bound

Wilson's lower bound is a good interval and a bad ranking objective ([binomial proportion CI](https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval)):

```
w⁻ = [p̂ + z²/(2n) − z·√(p̂(1−p̂)/n + z²/(4n²))] / (1 + z²/n)
```

It answers "what is the worst-case true rate given this sample." Because the penalty shrinks with `n`, sorting by `w⁻` systematically ranks volume rather than quality. Evan Miller's own framing is "which items are good enough to show," not "who is #1" ([evanmiller.org](https://www.evanmiller.org/how-not-to-sort-by-average-rating.html)).

That failure mode is precisely the attack a large brand would run, inverted: a small brand loses to a large one purely because it is small.

| Objective | Answers | Ranks | Role in UGC Ranks |
|---|---|---|---|
| Raw rate `x/n` | "what did we observe" | noise at small n | never published as a rank |
| Wilson lower bound | "worst-case true rate" | volume | eligibility gate + published error bar |
| Beta posterior mean | "best estimate of true rate" | quality | 🟢 the headline rank |

**Inference, clearly marked:** use a Wilson or Beta credible bound as an eligibility gate and as the published error bar on every score, and rank on the posterior mean. Ranks whose 90% intervals overlap are declared statistically tied and rendered as a tie.

---

## 3. Two axes, never one

Love and hate are separable substrates rather than opposite ends of one scale ([Cacioppo, Gardner & Berntson 1997](https://journals.sagepub.com/doi/10.1207/s15327957pspr0101_2)), and brand hate is a distinct construct with its own antecedents ([Zarantonello et al.](https://www.sciencedirect.com/science/article/abs/pii/S0148296319302590)).

A net score collapses that. A brand 45% loved and 45% hated lands at the same net value as a brand nobody has an opinion about, which is a factually wrong statement about the world.

**Data model.** Every mention carries `label ∈ {positive, negative, neutral}` plus intensity and model confidence — see [06-sentiment.md](06-sentiment.md). Per brand, per category:

| Field | Definition | Ranked? |
|---|---|---|
| `love_score` | shrunk `L = pos/N`, prior fitted on the category's positive rates | yes, descending — left column |
| `hate_score` | shrunk `H = neg/N`, prior fitted on the category's negative rates | yes, descending — right column |
| `polarization` | `2·min(L, H)` — high only when both are high | shown, not ranked |
| `net` | `L − H` | reported, never ranked on |
| `n_eligible`, `n_authors`, `n_subreddits` | eligibility evidence | shown |

The two columns read directly off `love_score` and `hate_score`. Both are shrunk independently against their own category prior — no normalization couples them.

**A brand can legitimately top both columns.** `L + H ≤ 1` because neutral mentions absorb the remainder, so when the neutral share is small both rates can be large at once. That is the correct outcome for polarizing brands and the most defensible choice in this spec.

---

## 4. No upvote weighting in the headline index

**The case for votes:** an upvote is a community endorsement of a specific claim, so a comment at +900 arguably carries more information than one at +2.

**The case against, which wins:** Reddit fuzzes displayed vote counts by design to defeat reverse-engineering (exact mechanism **NOT VERIFIED** from a first-party page). Scores are power-law, subreddit-size and time-of-day dependent, and causally inflated — one seeded upvote raised final scores 25% ([Muchnik, Aral & Taylor, *Science*, 2013-08-09](https://www.science.org/doi/10.1126/science.1240466)).

**Landing it:** votes are excluded from `love_score` and `hate_score` entirely. They are published as a separate, clearly labeled **salience** metric that never feeds the rank.

If salience is ever blended in (not in v1), the only defensible shape is `v* = percentile_rank(log1p(score))` within subreddit × month, capped as `w = 1 + λ·v*`, λ ≤ 0.5 and published. No comment may exceed roughly twice another's weight.

---

## 5. The minimum-mention threshold, derived

Pick a published precision target and solve for `n`. Do not pick a round number and back-fill a story.

```
n_min = z²·p(1−p) / h²
```

| Half-width `h` | z (95%) | p | `n_min` | Note |
|---|---|---|---|---|
| ±10 pp | 1.96 | 0.5 | 97 | too loose to defend |
| ±7 pp | 1.96 | 0.5 | 196 | — |
| **±5 pp** | **1.96** | **0.5** | **384 → 400** | 🟢 the published threshold |
| ±3 pp | 1.96 | 0.5 | 1,068 | starves Phase 2 categories |

`p = 0.5` is the variance-maximizing worst case, so 400 is conservative at every real rate. Publishing this derivation is what defeats "your cutoff is arbitrary."

Comparable sites use round numbers with secret internals — Metacritic fires at 4 reviews ([Metacritic](https://metacritichelp.zendesk.com/hc/en-us/articles/14478499933079-How-do-you-compute-METASCORES)), G2 at 10+ in-category reviews ([G2](https://documentation.g2.com/docs/research-scoring-methodologies)). Deriving ours is the differentiator.

**Diversity floors.** Shrinkage alone will not stop a coordinated push, because 400 mentions from one angry thread are still 400 mentions:

| Floor | Value | Defends against |
|---|---|---|
| Distinct authors | ≥ 50 | one prolific user or a small sockpuppet ring manufacturing a rank |
| Distinct subreddits | ≥ 5 | a single hostile or captured community defining a brand |
| Max share from one thread | ≤ 20% of `n` | one viral incident thread swamping years of ordinary sentiment |

A brand failing any floor is listed as **Not enough data**, with the failing floor named. It is never silently omitted.

---

## 6. Time weighting

Exponential decay `w(t) = exp(−ln2·Δt/H)` is the standard reputation forgetting factor, and G2 publishes a concrete shape: full weight for roughly 90 days, strong to 18 months, about 3% of original weight by three years ([G2](https://documentation.g2.com/docs/research-scoring-methodologies)).

**Recommended default: a trailing 12-month window with uniform weight inside it**, plus published 24-month and all-time archives. A window is auditable and reproducible by a third party. A decay half-life is a hidden knob that silently rewrites history, and every rank change becomes an accusation.

**What breaks with a six-year-old scandal.** It leaves the trailing index, which is correct — and is exactly when UGC Ranks gets accused of laundering a reputation. The fix is not a longer window. It is a permanent per-brand **event register** plus a trajectory chart beside the current rank, so history stays visible even when it no longer scores.

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

There is no post-hoc statistical fix, because the confound sits in the exposure population, not in the estimator. Shrinkage, normalization, and the diversity floors all operate on a sample already selected on adoption model. **Marked as inference — no primary source in this repo's research corpus.**

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

*Suzuki v. Consumers Union* survived summary judgment because a jury could have found the testing method was tampered with, not because the published verdict was wrong. **Case citation NOT VERIFIED — no primary source in this repo's corpus.** The lesson: method integrity, not conclusion accuracy, is the exposed surface.

| Rule | Implementation |
|---|---|
| Freeze before first result | this file is tagged and its commit hash recorded before the first production crawl runs |
| Version | semantic version + effective date in the file header and on the public page |
| Change control | every change ships with a changelog entry: what changed, why, effective date, back-recomputation policy |
| No post-hoc tuning | a parameter is never changed after seeing where a specific named brand landed |
| Audit trail | the git history is the evidence that the method predates the result |

Anything that looks like a knob turned after a complaint is the fact pattern to avoid. See [01-legal.md](01-legal.md) for the surrounding exposure, including the deliberate decision to display full comment text.

---

## 10. What the public methodology page must disclose

| # | Item | Detail required |
|---|---|---|
| 1 | Data source and window | subreddit scope, API vs archive, collection dates, refresh cadence |
| 2 | Brand resolution | alias list, ambiguous-name disambiguation, false-positive rate from a labeled audit |
| 3 | Sentiment labeling | model class, human-validated agreement rate, confusion matrix, sarcasm and negation handling |
| 4 | Unit of analysis | comment vs thread vs author; deduplication and crosspost rules |
| 5 | The formulas in full | estimator, per-category α₀/β₀ and how fitted, any λ, window |
| 6 | Eligibility and derivation | n_min with the precision math, author/subreddit/thread floors |
| 7 | Uncertainty | 90% credible interval on every score; overlapping ranks declared tied |
| 8 | Category definitions | each category's `C`, assignment rules, appeal path for miscategorization |
| 9 | Manipulation controls | that countermeasures exist, without publishing the evasion recipe |
| 10 | What the index is NOT | not product quality, not a survey, not population-representative; Reddit skew stated |
| 11 | Corrections and appeals | named contact, response SLA, public changelog with effective dates |
| 12 | Reproducibility artifact | downloadable per-brand counts (pos/neg/neutral/N) behind every score |

Item 12 ends more disputes than the other eleven combined. A CMO who can download the counts argues with the counts, not with UGC Ranks.

---

[← Back to README](README.md) · [01-legal.md](01-legal.md) · [06-sentiment.md](06-sentiment.md)
