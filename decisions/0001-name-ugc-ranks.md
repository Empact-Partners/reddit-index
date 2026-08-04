# 0001 — The product is called UGC Ranks, not Reddit Ranks

**Status:** Accepted · **Date:** 2026-08-04 · **Decided by:** Vlad Shvets

## Bottom line

The product ships as **UGC Ranks** on **`ugcranks.com`**. Every "reddit\*" name we wanted is forbidden by Reddit's own trademark clauses and sits inside a live UDRP enforcement pattern. The neutral name also unlocks non-Reddit sources later. "Reddit" still appears in page copy as a nominative reference to the data source, which is a narrower right than it sounds.

## Context

The idea was sketched as "Reddit Rankings" with three candidate domains: `redditrankings.com`, `redditranks.com`, `redditbrands.com`.

All three are registered ([domain sweep](../data/domain-availability.csv), checked 2026-08-04). `redditbrands.com` (registered 2026-06-07) is **live** with a near-identical concept: "Reddit Brand Reputation. See what Reddit really thinks about your brand." `redditranks.com` (2025-09-10) sits on a Namecheap parking page; `redditrankings.com` (2026-06-23) resolves to an empty GoDaddy-hosted page.

`whatredditthinks.com` (registered 2026-05-25) is live as well, publishing per-question Reddit consensus pages. The reddit-named adjacent space is being actively claimed, not sitting open.

Two contractual clauses forbid the name outright:

- **Data API Terms §4.1** ([redditinc.com/policies/data-api-terms](https://www.redditinc.com/policies/data-api-terms)): "You are not permitted to use the Reddit Trademarks in, or as part of the name of your App, or any logos used to promote or identify your App, unless expressly authorized in writing by Reddit."
- **Developer Terms §5.3** ([redditinc.com/policies/developer-terms](https://www.redditinc.com/policies/developer-terms)): "you are not permitted to use the Reddit Trademarks in the name of your App or to promote or identify your App (including in any materials related to your App), without Reddit's prior written consent."

Data API Terms §4.2 licenses exactly one form: the wordmark "so long as you use 'for' preceding such use (e.g., '[insert name] for Reddit')."

Reddit's [Brand Guidelines](https://redditinc.com/hubfs/Reddit%20Inc/PDF/reddit_brand_guidelines_version_2022_2022-04-01-160548_akmi.pdf) reserve "all commercial use of Reddit's Brand Assets" for Reddit and its licensed partners, and define Brand Assets to include "any other word, name, phrase" identifying Reddit's products. The stated house rule is "Talk about, not as, Reddit."

Reddit enforces, and won every UDRP case found:

- [`reddit.win`](https://www.wipo.int/amc/en/domains/decisions/text/2020/d2020-1834.html) — *Reddit, Inc. v. Phil Carey*, D2020-1834, transferred; decision dated 2020-10-06.
- [`redditpromotion.com` / `redditshop.com`](https://www.wipo.int/amc/en/domains/decisions/text/2019/d2019-2964.html) — *Reddit, Inc. v. Sebastian Anderson*, D2019-2964, both transferred; decision dated 2020-01-29.
- [`reddit.co`](https://www.wipo.int/amc/en/domains/decisions/text/2018/dco2018-0008.html) — DCO2018-0008, transferred.

In the `reddit.win` decision the panel held that even noncommercial free-speech use of an identical mark "carries with it a high risk of implied affiliation." Reddit litigates these *pro se* — cheap for them, expensive for the respondent.

## Decision

The product is **UGC Ranks**, on **`ugcranks.com`**. `ugcrankings.com` is registered as a defensive redirect.

Both `.com` names were verified available on 2026-08-04. The `.io` and `.co` variants of each are in the sweep as **not checked** — verify them before treating them as reserved ([domain-availability.csv](../data/domain-availability.csv)).

## Consequences

**Removes** the trademark-in-name breach (§4.1 / §5.3) and the UDRP exposure. It removes nothing else. The commercial-use restriction bites on the product regardless of its name — see [../01-legal.md](../01-legal.md).

**"Reddit" still appears** in page copy, headings, title tags and URL paths, as a nominative reference to where the data came from: naming the source in order to describe it, rather than using the mark as the product's own name. That descriptive use is the standard basis for referring to someone else's mark, and it is the only ground claimed here.

It is a narrower right than "free and lawful." Reddit's own house rule ("Talk about, not as, Reddit") points the same way, and Reddit has not addressed third-party page copy by name — **NOT VERIFIED** either way. Nothing in this repo is legal advice; treat the naming rule as a risk-reduction call, not a clearance opinion.

**Costs** some click-through and topical clarity. The ranking signal for "[category] reddit" queries does not live in the domain, so the SEO loss is small. See [../10-seo-aeo.md](../10-seo-aeo.md).

**Gains** an unplanned strategic option. "UGC" is source-agnostic, so Hacker News, Stack Overflow, YouTube comments and X can be added later without a rename or a rebrand. This turned out to be the stronger reason. See [../12-phasing.md](../12-phasing.md).

**Note:** the GitHub repository is still named `reddit-rankings-app`, from the original sketch. Internal only, and trivial to rename.

## Alternatives rejected

| Option | Why not |
|---|---|
| Acquire `redditrankings.com` or `redditranks.com` | Unknown price, weeks of negotiation, and still carries the §4.1 and UDRP problem. |
| Register `redditbrandindex.com` (available 2026-08-04) | Same contractual breach, and invites confusion with the live `redditbrands.com`. |
| "UGC Ranks for Reddit" | The only §4.2-licensed form, but it is a clumsy product name and locks the brand to one source. |

---

[← Back to README](../README.md) · [Legal position](../01-legal.md) · [Domain sweep](../data/domain-availability.csv)
