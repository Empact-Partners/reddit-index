# 0001 — The product is Reddit Index, on redditindex.com

**Status:** Accepted, with known trademark exposure · **Date:** 2026-08-04 · **Decided by:** Vlad Shvets

⚠️ This name breaches Reddit's trademark clauses. It was chosen with the exposure understood and priced. This record exists so nobody later claims it was an oversight.

## Bottom line

- The product ships as **Reddit Index** on **`redditindex.com`**, verified available 2026-08-04 with no DNS and effectively no archive history.
- It breaches [Data API Terms §4.1](https://www.redditinc.com/policies/data-api-terms) and [Developer Terms §5.3](https://www.redditinc.com/policies/developer-terms), both of which forbid Reddit trademarks in a product name.
- The realistic enforcement path is **not a lawsuit**. It is a UDRP filing, which Reddit runs *pro se* for roughly $1,500 and has won every time it filed.
- **What that costs is the domain, not the project.** The pipeline, the index, the methodology and the content all survive a transfer. That asymmetry is why the risk is acceptable.
- A meaningfully lower-risk option existed and was not taken. It is recorded below rather than omitted.

## Context

The idea was sketched as "Reddit Rankings". All three original candidates are registered ([domain sweep](../data/domain-availability.csv)): `redditbrands.com` (2026-06-07) is **live** with a near-identical concept, `redditranks.com` (2025-09-10) is parked, `redditrankings.com` (2026-06-23) resolves to an empty page.

An earlier revision of this decision chose a Reddit-free name. The owner reversed it: the site will not be promoted loudly, and a name that says what it is beats a name that has to be explained in a cold email.

## What the name breaches

| Clause | Text |
|---|---|
| [Data API Terms §4.1](https://www.redditinc.com/policies/data-api-terms) | "You are not permitted to use the Reddit Trademarks in, or as part of the name of your App, or any logos used to promote or identify your App, unless expressly authorized in writing by Reddit." |
| [Developer Terms §5.3](https://www.redditinc.com/policies/developer-terms) | "you are not permitted to use the Reddit Trademarks in the name of your App or to promote or identify your App (including in any materials related to your App), without Reddit's prior written consent." |
| [Brand Guidelines](https://redditinc.com/hubfs/Reddit%20Inc/PDF/reddit_brand_guidelines_version_2022_2022-04-01-160548_akmi.pdf) | "All commercial use of Reddit's Brand Assets is reserved for Reddit and its licensed partners." Brand Assets include "any other word, name, phrase" identifying Reddit's products. House rule: "Talk about, not as, Reddit." |

Data API Terms §4.2 licenses exactly one form — the wordmark preceded by "for", as in "[name] for Reddit". We do not use it.

## The enforcement record

Reddit files UDRP complaints and wins them:

- [`reddit.win`](https://www.wipo.int/amc/en/domains/decisions/text/2020/d2020-1834.html) — *Reddit, Inc. v. Phil Carey*, D2020-1834, transferred, decision 2020-10-06.
- [`redditpromotion.com` / `redditshop.com`](https://www.wipo.int/amc/en/domains/decisions/text/2019/d2019-2964.html) — D2019-2964, both transferred, decision 2020-01-29.
- [`reddit.co`](https://www.wipo.int/amc/en/domains/decisions/text/2018/dco2018-0008.html) — DCO2018-0008, transferred.

In `reddit.win` the panel held that even noncommercial free-speech use of an identical mark "carries with it a high risk of implied affiliation."

⚠️ **Low traffic is not a defence.** A UDRP is a registrar-level administrative proceeding, not litigation. It needs no damages, no discovery, and no proof that anyone visited the site. It needs only that Reddit notices.

## Decision

**`redditindex.com`.** `redditbrandindex.com` is registered as a defensive second name and redirects.

The hyphenated `reddit-index.com` was available and was **rejected**. UDRP panels treat hyphens as irrelevant to confusing similarity, so it buys no protection at all, while costing typability and reading as SEO-era spam.

## What we chose against

Honesty requires recording this. **`brandsonreddit.com`** was available and carries a materially better posture.

The difference is what the mark is doing inside the name. "Reddit Index" puts REDDIT first, which reads as a Reddit sub-brand — exactly the implied-affiliation problem the `reddit.win` panel described. "Brands on Reddit" is a descriptive phrase in which Reddit is the *subject being covered*, which supports a real legitimate-interest argument.

It was not taken because legibility in a cold email was judged worth more than the reduced risk. It stays on the shelf as the migration target.

## Consequences

**The trademark breach is now live and permanent.** [01-legal.md](../01-legal.md) previously scored §4.1 as satisfied. It no longer is, and the risk register reflects that.

**Nothing else changes.** The commercial-use restriction in Developer Terms §4.1 bites on the product regardless of its name, and the comment-display exposure in [0002](0002-display-full-mentions.md) is untouched by naming. This decision adds one risk and removes none.

**The blast radius is unchanged, but the trigger got cheaper.** A reddit-named domain is a standing, searchable signal. The [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) permits suspending "associated accounts, bots, **domains**, or subreddits", which reaches Empact's live Reddit operation. The name makes us easier to find.

**The name is now Reddit-locked.** Phase 3 in [12-phasing.md](../12-phasing.md) contemplates Hacker News and other sources. "Reddit Index" cannot carry those without a rename. That option was sold for clarity, knowingly.

## Mandatory conditions

1. **Non-affiliation notice in the footer of every page:** "Not affiliated with, endorsed by, or sponsored by Reddit, Inc. 'Reddit' is a trademark of Reddit, Inc., used here descriptively."
2. **No Reddit visual identity, ever** — no orange `#FF4500`, no Snoo, no Reddit Sans, no lookalike mark. Trade dress stacked on top of the name is what turns a survivable UDRP into an easy one. See [09-design.md](../09-design.md).
3. **Register the defensive names before launch**, not after. `redditbrandindex.com` at minimum.
4. **Keep a migration plan warm.** All internal links relative, the canonical host in exactly one config value, and `brandsonreddit.com` named as the destination. A forced move should cost a day, not a quarter.
5. **Never claim or imply partnership** with Reddit in any copy, deck, or outreach email.

## Revisit when

- Any communication arrives from Reddit or its counsel. Revisit immediately and expect to move.
- The site starts ranking for high-volume queries, which is when a brand team notices it.
- Reddit publishes a commercial data tier a consultancy can buy, which would change the whole posture rather than just this decision.

## Alternatives rejected

| Option | Why not |
|---|---|
| `reddit-index.com` | The hyphen gives zero UDRP protection, costs typability, and reads as spam. |
| `brandsonreddit.com` | Genuinely lower risk. Rejected for being less legible in a cold email. Kept as the migration target. |
| `redditbrandindex.com` as primary | Four characters longer for no gain once "Index" already implies the subject. Taken as the defensive name. |
| A Reddit-free name (the previous revision of this decision) | Removes the exposure entirely, but has to be explained every time it lands in an inbox. |
| "Reddit Index for Reddit" (the §4.2-compliant form) | The only licensed construction. Absurd as a product name. |

---

*Nothing in this repo is legal advice. This is a priced business risk, not a clearance opinion.*

[← Back to README](../README.md) · [Legal position](../01-legal.md) · [Display decision](0002-display-full-mentions.md) · [Domain sweep](../data/domain-availability.csv)
