# Methodology — the Reddit ❤️ Score, as built

*The definitive plain statement of what the published number is. The
critical audit of it lives in [methodology-review.md](methodology-review.md);
the original long-form design record is `07-index-methodology.md` and
`13-algorithm.md` at the repo root.*

## The score (methodology 2.0.0)

```
N_op  = pos + neg                      (opinionated mentions only)
p₀    = (pooled_pos + 5) / (pooled_op + 10)   over every OTHER brand
α₀    = 10·p₀        β₀ = 10·(1−p₀)
p̃     = (pos + α₀) / (N_op + α₀ + β₀)
score = round(100 · p̃)
```

The prior is the category's **pooled** positive rate over every *other*
brand's opinionated mentions (leave-one-out by mention mass), at a **fixed
strength of 10 pseudo-observations**, lightly smoothed toward 0.5 so a tiny
pool degrades gracefully. A brand with 40 real opinions is ~80% its own
data; a brand with 3 is mostly the category's base rate until it earns more.
A 6-mention darling still cannot outrank a 4,000-mention incumbent by luck.

### Why 2.0.0 exists (2026-08-12)

v1 fitted the prior by method-of-moments over per-brand rates, only counting
brands with n_op ≥ 30, and fell back to a **200-pseudo-observation** prior
whenever fewer than 4 brands qualified — which at this corpus depth was
nearly every category. In domain-registrars exactly two brands qualified, so
each was scored against *the other's* rate at ~5× its own evidence:
**Porkbun (41 pos / 1 neg) published 20/100 while GoDaddy (4 pos / 111 neg)
published 63/100.** Every fitted strength in the shipped table was ~200, so
every published score was 80-95% prior. v2 replaces the fit with the fixed
pooled prior above, and `worker/gate_calibration.py` now refuses to load any
scoring run where, within a category (brands with n_op ≥ 10), the rank
correlation between raw rate and published score falls below 0.8 or an
extreme raw rate lands on the opposite end of the board. The gate is
self-tested against the real v1 output: it raises three violations on it.

## What counts

- Comments and post bodies from the category's **scoring subreddits**
  (measured density × topicality, top 8, never vendor-run — see
  [taxonomy.md](taxonomy.md)), trailing **365 days**, uniform weight.
- Only brands whose **category membership** includes the scored category —
  a mention of Google Drive in r/CRM stays on Google Drive's page and out
  of the CRM leaderboard.
- Neutral and abstain mentions are counted and published, never scored.
- **Votes are ignored** — an upvote measures visibility agreement inside a
  feedback loop, not sentiment.
- One mention = one (document, brand) pair; a comment naming three products
  produces three verdicts.

## Display floors vs statistical gates

Two different bars, deliberately:

- **Display floor** (what it takes to appear on a board): `n_op ≥ 3` on a
  category board, `n_op ≥ 10` on the pooled all-categories boards.
- **Statistical gates** (what it would take to call a score settled):
  `n_eff ≥ n_min` where `n_eff = N_op / DEFF` (Kish design effect, clustered
  by thread AND author, the worse of the two), plus absolute diversity
  floors — ≥50 authors, ≥5 subreddits, ≤20% from one thread, ≤5% from one
  author. Tier targets: deep ±4pp → 600 · standard ±5pp → 400 · thin
  ±7pp → 200. These stay in the database on every score row; today's boards
  are directional, and nothing yet clears the formal gates. Deeper daily
  data is the cure, not a lower bar.

## The ordering

Most Loved and Most Hated are the two ends of ONE ordering (score
descending). No second fit, no separate "hate score", and a brand can never
appear on both boards. The pooled boards rank each brand once, through its
highest-volume category row.

## Freezing

Method constants are frozen in an append-only `methodology_params` table
(rejects UPDATE/DELETE at the trigger level) with the git commit recorded.
Changing one is a version bump with a dated entry, never an edit. Adding the
expansion categories was such a bump.
