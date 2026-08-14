# The Reddit ❤️ Score, interrogated

*2026-08-09. Written against the live corpus (8,924 in-window scored mentions,
412 brand × category rows). This is the honest audit of what the number is,
what it is not, and what should change.*

> **Addendum 2026-08-14.** This review predates methodology 2.0.x on two
> counts: the prior it describes (brand-rate method of moments) was replaced
> by the pooled-LOO prior (K=10) in 2.0.0, and the "top 8" scoring-subreddit
> selection it references was replaced in 2.0.1 by all-qualifying selection
> (no cap; six qualification bars). The audit's findings stand as the record
> that motivated both changes. Current doctrine: [methodology.md](methodology.md).

## How the score actually works, in plain words

1. **Collect.** For each category, we harvest threads from its scoring
   subreddits (top 8 communities by measured brand-discussion density ×
   topicality), pull full comment trees, and keep every comment or post body
   that names a tracked brand. Names are matched by strict rules — word
   boundaries, qualified forms for ambiguous names ("Close CRM" counts, bare
   "close" never does) — and nothing is guessed.
2. **Judge.** Every mention gets a four-way verdict about THAT brand:
   positive, negative, neutral, or abstain (can't tell). "We moved off HubSpot
   to Pipedrive" is one negative for HubSpot and one positive for Pipedrive
   in the same sentence. Neutral and abstain are counted and published but
   never enter the score — being named a lot without opinion is not love.
3. **Score.** The score is the brand's positive share among opinionated
   mentions (pos ÷ (pos + neg)), shrunk toward the category's own base rate:

   `score = 100 × (pos + α₀) / (pos + neg + α₀ + β₀)`

   α₀/β₀ come from fitting the distribution of every OTHER brand's rate in
   the category (leave-one-out), so the biggest brand isn't pinned to its own
   average and a brand with 4 opinionated mentions gets pulled strongly
   toward "typical for this category" instead of sitting at 100 or 0.
4. **Window.** Only the trailing 12 months count. Votes never count — an
   upvote measures agreement with visibility, not sentiment, and it feeds
   back on itself.

## What's defensible

- **The estimator.** Empirical-Bayes shrinkage is the correct tool for
  ranking small samples; a 6-mention darling cannot outrank a 4,000-mention
  incumbent by luck. The leave-one-out prior avoids self-referential
  shrinkage.
- **Neutral exclusion.** Counting "we use X" as approval would launder
  install-base into love.
- **Whole-thread selection.** A thread is either wholly in the corpus or
  wholly out, so the published mention count and the score always describe
  the same corpus.
- **Vote-ignoring, rules-only entity matching, verbatim bodies with
  permalinks.** Every number on the site can be checked by clicking through.

## What's wrong, in order of how much it distorts the boards today

### 1. Categories rank the wrong brands (the big one)
A category's board currently ranks EVERY brand mentioned in that category's
subreddits. That is why **Google Workspace tops the CRM board (83, 51
mentions)** — r/CRM talks about Workspace constantly (as email
infrastructure, favourably) without Workspace being a CRM. Same for Google
Drive (#12 in CRM) and QuickBooks (#5). The corpus is right; the assignment
is wrong.

**Fix (decided):** a category ranks only brands whose category membership
(primary or secondary) includes it. "What r/CRM says about Google Drive"
stays in the data and on Google Drive's own page; it stops occupying a CRM
leaderboard slot. Ships with the 100-category expansion.

### 2. The Most Hated pooled board is built on scraps
Display floor is `n_op ≥ 3` opinionated mentions. Fine for a category page;
on the pooled all-categories board it lets **monday.com be #2 most hated on
3 mentions**. Three annoyed comments should not brand a company most-hated
across the whole index.

**Fix (decided):** pooled boards require `n_op ≥ 10`; category boards keep 3.
The formal statistical gates (n_eff ≥ 200-600, author/subreddit diversity
floors) still exist in the database and stay the bar for calling anything
"statistically settled" — nothing currently clears them, which is honest:
today's boards are directional, not settled, and deeper daily data is the
cure.

### 3. Exposure bias, undisguised
Enterprise software is discussed by people who had it chosen FOR them;
self-serve tools by the person who picked them. That pushes Salesforce/SAP
down and indie tools up regardless of quality. No statistical correction
exists that doesn't smuggle in editorial judgment; we disclose instead of
adjusting. Read every "big vendor scores low" with this in mind.

### 4. Sample, not census
Reddit search reaches roughly the recent past of each community; older
threads surface only when qualification queries find them. Every count is a
floor. The daily worker narrows this going forward (it sees everything new);
history stays a sample.

### 5. Known smaller items
- **Deliberate recall loss:** brands named like English words (Close, Make,
  Front, Square…) only count via qualified forms — their mention counts run
  low by design, never their scores.
- **Mixed judge engines:** labels come from two models (Claude Haiku early
  corpus, GPT luna since), measured at 81% exact 4-way agreement, 96% on
  polarity. Acceptable for a directional index; a settled index would
  re-judge everything with one engine and a human-audited gold set.
- **Precision is a design target, not a measurement.** No human audit of the
  entity matcher has run yet. The rules are conservative by construction, but
  ≥0.97 precision is asserted nowhere on the site because it hasn't been
  earned.
- **A brand's pooled row is its highest-volume category** — Notion appears
  once (its noisiest category), not once per category. Defensible, but it
  means the pooled board hides a brand's second life (Notion the note-taking
  darling vs Notion the project-management punching bag).

## The scale of what a score means today

| n_op | What the score is | Example |
|---|---|---|
| 3-9 | A hint. Shrinkage dominates; the prior speaks more than the data. | monday.com "19" |
| 10-50 | Directional. Real signal, wide error. | Trello 19 on 20 mentions |
| 50-300 | Solid for a provisional index. | Salesforce, 794 opinionated |
| 600+ (n_eff) | The formal bar. Nothing clears it yet. | — |

The daily worker exists to move everything down this table.
