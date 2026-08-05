# 0009 — Category-scaled eligibility thresholds

**Status:** Accepted · **Date:** 2026-08-05 · **Decided by:** Vlad Shvets

## Bottom line

The eligibility threshold is **per category**, not a single global number. Each category is assigned a published **precision target** `h`, and its threshold follows from it:

```
n_min = z²·p(1−p) / h²      z = 1.96,  p = 0.5
```

| Tier | Precision target | `n_min` (effective observations) |
|---|---|---|
| **Deep** | ±4 pp | 601 → **600** |
| **Standard** | ±5 pp | 384 → **400** |
| **Thin** | ±7 pp | 196 → **200** |

The threshold runs on `n_eff`, never on raw `n`. **The diversity floors do not scale** — they are absolute at every tier. Because the error bar is published on every score, a lower threshold is disclosed on the page rather than hidden in the method.

## Context

[../07-index-methodology.md §5](../07-index-methodology.md) derives a single gate, `n_eff ≥ 400`, from a ±5 pp precision target. That is defensible as a single number and it is what a critic can attack least.

It is also the wrong shape for the measured data. The 20-category study in [../14-category-tests.md](../14-category-tests.md) found brand-bearing volume differing by more than an order of magnitude across categories under the generalist-only rule. A flat 400 does two bad things at once: it lets large categories publish scores looser than they could afford, and it silently deletes small categories that carry real, usable signal.

The owner's instruction was direct: smaller categories get a lower threshold, larger ones a higher threshold.

The danger in that instruction is obvious and has to be closed. A threshold tuned per category is exactly the knob a hostile reader would expect to have been turned until the answer looked good. Anything discretionary here forfeits [../07-index-methodology.md §9](../07-index-methodology.md), the freeze-before-you-look rule that *Suzuki v. Consumers Union* turned on.

## Decision

**Scale the precision target, not the threshold.** The threshold is never picked; it is computed from a stated `h` through the formula already published in §5. Three tiers exist so the mapping is enumerable, and every tier's `h` is printed on the methodology page and on each category page.

### Tier assignment is mechanical

A category's tier is a function of its **measured** brand-bearing volume from the subreddit study, computed by the pipeline and recorded in [../data/categories.csv](../data/categories.csv). It is not a judgment call, and it is not revisited because a result was disappointing.

### What does not scale

| Floor | Value | At every tier |
|---|---|---|
| Distinct authors | ≥ 50 | ✅ absolute |
| Distinct subreddits | ≥ 5 | ✅ absolute |
| Max share from one thread | ≤ 20% of `n` | ✅ absolute |
| Max share from one author | ≤ 5% of `n` | ✅ absolute |

The floors defend against manufactured rank, and a small category is **more** vulnerable to a brigade, not less. Scaling them would make the thin tier both smaller and easier to game.

### Disclosure is the price of the lower tier

A Thin-tier score ships with a wider interval, and the interval is already mandatory on every score chip under [0005](0005-superlative-labels.md). The category page states its tier and its `h` in words. A reader who wants to discount a ±7 pp category can see that it is one.

## Consequences

**A category can rank that a flat 400 would have deleted.** That is the point. It ranks with a visibly wider error bar.

**Cross-category comparison gets harder, and the pooled board must say so.** Brands from different tiers appear on the same homepage list with different underlying precision. The board already carries a per-category cap and a disclosure line; the tier is part of what that line discloses.

**Tiers are frozen with the methodology version.** A category's tier is set from the measured study and versioned with it. Moving a category between tiers is a methodology change, which means a version bump and a dated changelog entry, not a config edit.

**The thin tier has a floor below it.** A category that cannot reach 200 effective observations with 5 subreddits and 50 authors does not get a fourth, looser tier. It renders the insufficient-signal state and says which floor it missed. There is no threshold at which a ranking becomes honest through relaxation alone.

## Alternatives rejected

| Option | Why not |
|---|---|
| Single global `n_eff ≥ 400` | Deletes categories carrying real signal, and lets large ones publish looser than they could afford |
| Continuous threshold, e.g. a percentile of the category's own distribution | Every category gets a bespoke number, which is unauditable and reads as tuned |
| Pick thresholds per category by hand | The exact discretionary knob §9 exists to remove |
| Scale the diversity floors too | Makes small categories easier to brigade at the moment they become rankable |
| Keep 400 and widen the subreddit lists until every category clears it | Already done — the generalist widening took the floor from 4/20 to 12/20. It is complementary, not a substitute: some categories are genuinely smaller than others |
| Publish thin categories without an eligibility gate, flagged | A flag is not a gate. Anything on a board is a claim |

---

[← Back to README](../README.md) · [Index methodology](../07-index-methodology.md) · [Category tests](../14-category-tests.md) · [0005](0005-superlative-labels.md) · [data/categories.csv](../data/categories.csv)
