# Methodology — the Reddit ❤️ Score, as built

*The definitive plain statement of what the published number is. The
critical audit of it lives in [methodology-review.md](methodology-review.md);
the original long-form design record is `07-index-methodology.md` and
`13-algorithm.md` at the repo root.*

## The score

```
N_op  = pos + neg                      (opinionated mentions only)
p̃     = (pos + α₀) / (N_op + α₀ + β₀)
score = round(100 · p̃)
```

α₀/β₀ are an empirical-Bayes Beta prior fitted by method-of-moments over
every **other** brand's positive rate in the same category (leave-one-out,
so the dominant brand is not shrunk toward its own average). The practical
meaning: a brand with a handful of mentions is pulled strongly toward its
category's base rate, and a 6-mention darling cannot outrank a 4,000-mention
incumbent by luck.

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
