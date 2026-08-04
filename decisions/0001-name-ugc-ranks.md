# 0001 — The product is called UGC Ranks, not Reddit Ranks

**Status:** Accepted · **Date:** 2026-08-04 · **Decided by:** Vlad Shvets

## Context

The idea was sketched as "Reddit Rankings" with three candidate domains: `redditrankings.com`, `redditranks.com`, `redditbrands.com`.

All three are registered. `redditbrands.com` is **live** with a near-identical concept — "Reddit Brand Reputation. See what Reddit really thinks about your brand." `redditranks.com` sits on a Namecheap parking page; `redditrankings.com` resolves to an empty GoDaddy-hosted page.

Two contractual clauses forbid the name outright:

- **Data API Terms §4.1:** "You are not permitted to use the Reddit Trademarks in, or as part of the name of your App, or any logos used to promote or identify your App, unless expressly authorized in writing by Reddit."
- **Developer Terms §5.3:** "you are not permitted to use the Reddit Trademarks in the name of your App or to promote or identify your App (including in any materials related to your App), without Reddit's prior written consent."

Data API Terms §4.2 licenses exactly one form: the wordmark "so long as you use 'for' preceding such use (e.g., '[insert name] for Reddit')."

Reddit enforces. It has won every UDRP case found: [`reddit.win`](https://www.wipo.int/amc/en/domains/decisions/text/2020/d2020-1834.html) (transferred 2020-09-30), [`reddit.co`](https://www.wipo.int/amc/en/domains/decisions/text/2018/dco2018-0008.html), and `redditshop.com` / `redditpromotion.com`. In the `reddit.win` decision the panel held that even noncommercial free-speech use of an identical mark "carries with it a high risk of implied affiliation."

## Decision

The product is **UGC Ranks**, on **`ugcranks.com`**. `ugcrankings.com` is registered as a defensive redirect.

Both were verified available on 2026-08-04, along with `.io` and `.co` for each.

## Consequences

**Removes** the §4.1 / §5.3 breach and the UDRP exposure. "Reddit" is still used freely and lawfully in page copy, headings, title tags and URLs as nominative reference to where the data came from — that is descriptive use, not use as a product name.

**Costs** some click-through and topical clarity. The ranking signal for "[category] reddit" queries does not live in the domain, so the SEO loss is small. See [../10-seo-aeo.md](../10-seo-aeo.md).

**Gains** an unplanned strategic option. "UGC" is source-agnostic, so Hacker News, Stack Overflow, YouTube comments and X can be added later without a rename or a rebrand. This turned out to be the stronger reason. See [../12-phasing.md](../12-phasing.md).

**Note:** the GitHub repository is still named `reddit-rankings-app`, from the original sketch. Internal only, and trivial to rename.

## Alternatives rejected

| Option | Why not |
|---|---|
| Acquire `redditrankings.com` or `redditranks.com` | Unknown price, weeks of negotiation, and still carries the §4.1 and UDRP problem. |
| Register `redditbrandindex.com` (available) | Same contractual breach, and invites confusion with the live `redditbrands.com`. |
| "UGC Ranks for Reddit" | The only §4.2-licensed form, but it is a clumsy product name and locks the brand to one source. |

---

[← Back to README](../README.md) · [Legal position](../01-legal.md) · [Domain sweep](../data/domain-availability.csv)
