# Handoff — open items

**State as of 2026-08-05, after the first build.** The repo is no longer
documentation only: the schema, the pipeline, the site and its build gates
exist, the method is frozen, and a sample corpus has been collected. What
follows is what a reader needs to know that the code does not say on its own.

The six defects in the previous handoff are still closed. Nine new ones were
found by building against the documents rather than reading them, and each is
recorded below with the resolution taken — per BUILD-PROMPT's rule that a
contradiction is fixed rather than picked silently.

## Bottom line

- **Nothing here is a published ranking.** The site ships `noindex` behind one
  constant in `lib/site-stage.ts`, with a banner saying so on every page. The
  corpus is a sample, not a census: Lane A (archive dumps) is not running, so
  every count is a floor.
- **Precision has not been measured.** No human-adjudicated audit exists. The
  ≥0.97 figure in `05-entity-resolution.md` is a design target and this build
  publishes no precision number, because none has been earned.
- **Four of the twenty categories cannot field five scoring subreddits** on the
  re-derived mapping. They render the insufficient-signal panel, which is a
  correct outcome and not a bug to fix by lowering a threshold.
- `www.redditindex.com` still has no CNAME. `redditbrandindex.com` is still
  unregistered, and `decisions/0001` wants it **before** launch.

---

## 1. 🔴 `category-candidates-20.json` is the pre-widening list

`data/README.md` describes it as producing "347 candidate slots" over "232
unique subreddits". The shipped file contains **254 slots over 156 subreddits**,
and **76 of the 232 measured subreddits have no category attribution anywhere in
the repo**. Recomputing the study's headline finding from shipped data only:

```
categories clearing the five-scorable-subreddit floor: 13 / 20
```

not 20/20. The seven extra categories were carried entirely by subreddits
nobody could attribute, and `analyze.py` cannot regenerate the mapping because
the raw probe output lives in an uncommitted scratch directory.

**Resolved** by re-deriving the mapping from Reddit in one pass:
`data/discover.py` → **`data/category-subreddits.csv`**, which is now the single
joinable source and supersedes both the JSON and `subreddit-map.csv`. Do not
read either as current.

Two measurement defects were fixed in the same pass, in `data/refine.py`:

- **Brand-bearing share is measured with word boundaries over low-ambiguity
  surface forms only** — `data/README.md`'s own correction rule, after the same
  instrument matched "Monday" the weekday and "SAP" the fluid. Run over a
  widened candidate set the substring version produced obvious nonsense:
  r/hardwareswap measured 1.96 brand-bearing comments/hour for Payment
  Processing because people say "PayPal" to arrange a sale.
- **A topicality term now weights the yield.** `13-algorithm.md`'s bootstrap
  score already has one — `T = 1.0 exact fit · 0.5 adjacent · 0 wrong` — marked
  human-coded. Coding 680 pairs by hand is not on, so it is coded locally from
  each subreddit's own description. `is_scoring` is the top 8 per category by
  `T × bb_per_hour`, never by subscriber count.

⚠️ **A trap worth recording.** The first discovery run ranked CANDIDATES by
subscriber count and truncated, which dropped r/CRM — the highest-yield CRM
community by a factor of four — behind r/technology and r/sanfrancisco.
`13-algorithm.md` says a scoring subreddit is "chosen by measured yield per
call, never by subscriber count"; sorting the candidate list that way
reintroduced the same mistake one step earlier, where nobody was looking.

## 2. 🔴 `mentions` cannot be partitioned and carry `UNIQUE(brand_id, doc_id)`

`08-architecture.md` §3 specifies both. Postgres rejects the combination
outright: a unique constraint on a partitioned table must include every
partition key column.

**Resolved:** the key is `PRIMARY KEY (brand_id, doc_id, created_utc)`.
`created_utc` is a fixed property of a Reddit fullname, so the same (brand,
document) pair cannot legitimately appear under two timestamps — and
`worker/gate_checks.sql` asserts nightly that it never does.

Same cause, one table over: `mention_sentiment` is keyed on
`(doc_id, brand_id, model_version)` rather than `mention_id`, because a foreign
key into a partitioned table has to carry the whole partition key. That is the
resolution unit `05-entity-resolution.md` §3 already defines.

## 3. 🔴 `n_eff` divides opinionated mentions, not all of them

The most consequential ambiguity in the specification, and it decides whether
anything publishes at all.

`07-index-methodology.md` §1 defines `n` as "all eligible mentions, opinionated
or not; reported everywhere, **never a denominator**". §5 then writes
`n_eff = n / DEFF` and gates on it. But `n_min = z²·0.25/h²` is the sample size
needed to estimate a **proportion** to half-width `h`, and that proportion's
denominator is `N_op`. Gating on `n` would let a brand publish a ±4pp claim on
roughly a third of the evidence the claim names.

**Resolved in favour of the stricter reading:** `n_eff = N_op / DEFF`. Recorded
in `methodology_params` as `n_eff_numerator = "n_op"`. This is a 2–3× difference
in the gate. `07` §5 should be amended to match.

## 4. 🟡 The design effect uses Kish's size-weighted mean

`07` §5 gives `DEFF = 1 + (m̄ − 1)·ICC` with `m̄` the plain mean cluster size.
For unequal clusters that understates the design effect, and ours are violently
unequal — one thread can carry seventy mentions while most carry one.

**Resolved:** `m̃ = Σn_j²/N`, the textbook Kish form. `m̃ ≥ m̄` always, so the
error is toward refusing to publish rather than toward publishing.

`ICC` is measured per brand by one-way random-effects decomposition, clustered
by thread and by author separately, carrying the larger design effect. The 0.08
in `07` §5 is explicitly illustrative and is never used; a floor of 0.10 applies
only where fewer than five clusters exist, and those rows carry
`icc_estimated = false`.

## 5. 🟡 The sentiment cascade is not built, deliberately

`06-sentiment.md` §3 specifies an eight-stage cascade whose economics are a
per-million API bill, and whose stage 1 is an encoder trained on a 1,000–1,500
item gold set. That gold set does not exist, is not scheduled, and §3 itself
says "build stage 6 and the gold set FIRST" — which is circular, because a gold
set is adjudicated *from* labels.

**Resolved:** classification runs 100% through `claude -p` on the Claude Max
subscription, locally, at zero marginal cost and with no metered API involved.
That removes the cascade's entire economic argument at this volume and breaks
the circularity: this pass produces the labels a gold set would be adjudicated
from. Recorded as `sentiment_engine` in `methodology_params`.

**Consequence for the architecture:** the classify stage cannot run in a Railway
container, because it needs the subscription and this machine. The pipeline is
local for now. `08-architecture.md` §7's `SENTIMENT_API_KEY` is unused.

## 6. 🟡 The label set is four-way

`07` §3 lists five values including `recommendation`; `06` §3 states the set is
four-way with `is_recommendation` as a **flag**, says so twice, and explains
why: only `pos` and `neg` enter a score, `neu` is a real judgment, `abstain` is
the classifier declining, and collapsing any of them changes the denominator and
therefore the rank.

**Resolved in favour of `06`,** which is the authority on sentiment. Frozen
encoding: `{neu: 0, pos: 1, neg: 2, abstain: 3}`. `07` §3 should be amended.

## 7. 🟡 Two rules in `13-algorithm.md` §4 are wrong, both measured

- **`num_comments` is an actively harmful ranking key.** §4 advises skipping
  short posts "unless comment count is high", which steers straight into
  general-chatter megathreads. Measured: a 1,232-comment r/sales thread returned
  **2** brand-bearing comments; a 34-comment r/CRM thread returned **12**. It is
  kept as a floor (≥3) and given a deliberately weak `log1p` weight in the
  ranking, nothing more.
- **"Not archived" as a qualification rule would delete the backfill.** Reddit's
  archiving blocks *writes*, not reads. Applied literally it discards every
  thread older than about six months, which is the entire historical corpus
  Lane D exists to reach. `archived` is recorded and never filtered on.

## 8. 🟡 `13-algorithm.md` §2 contradicts its own bottom line

Line 11 says "125 of 232 measured subs qualify" and "32% is retained"; §2's body
says "62 of 156", "56 of 156", and "9% of measured brand-bearing volume … across
the 156 measured subreddits". The shipped CSV agrees with the bottom line. §2's
body paragraphs are the superseded pre-re-run text and should be deleted rather
than reconciled.

## 9. 🟡 Small, but they will bite someone

- `BUILD-PROMPT.md` M1 names tables **`documents`** and **`scores`**. Neither
  exists in `08` §3. The real names are `threads` and `brand_category_scores`.
  §3 lists **13** tables, not 14.
- `08` §6 records "Deployments to date: 0 … Zero deployments is the correct
  state". There were **five**, all in state ERROR because the repo had no
  `package.json`. The sixth is a public launch on the apex.
- `08` §5's "direct connection on port 5432" is unreachable from a Railway
  container: `db.<ref>.supabase.co` resolves IPv6-only. Use Supavisor session
  mode.
- Five of twenty category colours failed their own C1–C7 constraints when
  recomputed from the stored hex — the optimiser satisfied them in continuous
  OKLCH and quantised afterwards. Repaired by `scripts/gen-palette.mjs`, each
  moved one 8-bit step. **The published minimum pairwise ΔE_OKLab is 0.0927, not
  0.0931**; `16-design-system.md` and `decisions/0008` both quote the old figure.
  `categories.csv` never carried a `dE_orange` column, so C5's third leg was
  unverifiable; it does now.
- `05` §6 applies a plain Wilson interval to a *stratified* sample. That is only
  valid under proportional allocation, and the doc's own advice (strata =
  ambiguity class) invites disproportionate allocation, where the raw sample
  proportion is biased. Use the stratified estimator and its effective sample
  size when the audit is eventually run.
- `data/probe.py` loads `cat20.json`, which is not a shipped filename. It will
  not run in a fresh clone.

---

## What the build changed about the milestone ladder

`BUILD-PROMPT.md` sequences the eligibility gate, the honest below-threshold and
insufficient-signal states, and `/methodology` **after** the milestone that
computes and renders a score. Three documents make that ordering unworkable:

- `decisions/0005` makes the methodology page and the measured-variable-beside-
  the-superlative rule **conditions** of using "Most Loved" and "Most Hated" at
  all, and requires the method frozen *before results are seen*.
- `decisions/0009`: "A flag is not a gate. Anything on a board is a claim."
- `07` §9: the method is tagged and its commit hash recorded **before the first
  production crawl runs**.

So the honesty layer shipped first, and the data made that the only sensible
order anyway: on a sample corpus almost every company sits below threshold, so
those states are the site's dominant surface rather than an edge case.

The eight pre-deploy gates in `16-design-system.md` §8, scheduled for the last
milestone, also run from the first build — they are cheap, and the domain is
live.

## Outstanding, outside the docs

- **`redditbrandindex.com` is not registered.** `decisions/0001` requires the
  defensive name before launch, and `01-legal.md` is blunt about why: "a
  defensive name bought after a complaint lands reads as bad faith, not
  protection." Roughly $12.
- **A correction inbox does not exist.** `/methodology` and every company page
  link `corrections@redditindex.com`, which must resolve before the site is
  public. It is a condition of two priced decisions, not a feature.
- **`www.redditindex.com` has no CNAME.** DNS is at NameBright. The apex
  resolves correctly without it.
- **The name breaches two Reddit clauses** — Data API Terms §4.1 and Developer
  Terms §5.3 — and enforcement is a UDRP filing Reddit runs *pro se* for about
  $1,500, having won every one on record. Recorded, not overlooked. A loss costs
  the domain, not the project, which is why the canonical host lives in exactly
  one config value (`lib/env.ts`) and every internal link is relative.
- **Legal review before launch**, per `01-legal.md`. Nothing here is legal
  advice.

## What is NOT open

Raised by reviewers and resolved as false positives — do not "fix" them:

| Claim | Status |
|---|---|
| Developer Terms §5.3 trademark text | ✅ Verified verbatim from the live page |
| *Suzuki Motor Corp. v. Consumers Union*, 330 F.3d 1110 (9th Cir. 2003) | ✅ Verified |
| G2 acquired Capterra, closed 2026-02-05 | ✅ Verified |
| "roughly 28 partner projects" | 🟡 Internal Empact figure, marked as such |
| `_global-error.html` renders without footer slot 4 | 🟡 It is Next's own last-resort 500 shell, not a route anyone navigates to. `app/global-error.tsx` — what actually renders on a runtime error — does carry slot 4, and `tests/footer.test.tsx` asserts it, because the HTML gate is structurally blind to error boundaries |

---

[← Back to README](README.md) · [BUILD-PROMPT.md](BUILD-PROMPT.md) · [Index methodology](07-index-methodology.md) · [Phasing](12-phasing.md)
