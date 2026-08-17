# Methodology — the Reddit ❤️ Score, as built

*The definitive plain statement of what the published number is. The
critical audit of it lives in [methodology-review.md](methodology-review.md);
the original long-form design record is `07-index-methodology.md` and
`13-algorithm.md` at the repo root.*

## The score (methodology 2.2.0)

```
N_op = pos + neg
p0   = (pooled_pos + 5) / (pooled_op + 10)     over every OTHER company (LOO)
a0   = 10*p0        b0 = 10*(1-p0)
posterior = Beta(x_pos + a0,  x_neg + b0)
Reddit Love Score = round(100 * Q_0.10(posterior))
```

The published number is the **10th-percentile posterior quantile** — the
lower bound, not the mean. 2.0.0 fixed the mis-specified v1 prior; 2.2.0
replaced the published mean with the lower bound after the mean rewarded
thin evidence (shift4, 0 positives out of 4 opinions, published above PayPal
at 25% positive over 72). The lower bound is monotone in the positive rate
AND in the amount of evidence, so sparse data costs a company position
instead of buying it one. Implemented as a deterministic dependency-free
Beta inverse-CDF (`worker/score.py::beta_quantile`), verified against closed
forms. `p_tilde` (the mean) is still computed and published as evidence.


## What counts

- Comments and post bodies from the category's **scoring subreddits** —
  every community that passes all qualification bars: exists & open, alive
  (~2+ posts/week), not vendor-run, rules do not forbid product discussion,
  topicality ≥ 0.5, and observed brand talk. No top-N cap and never ranked
  by subscriber count (frozen as `scoring_subreddit_selection`, 2.0.1 — see
  [taxonomy.md](taxonomy.md)). Trailing **365 days**, uniform weight.
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
