# 0007 — Categories and companies share one flat URL namespace

**Status:** Accepted · **Date:** 2026-08-05 · **Decided by:** Vlad Shvets

## Bottom line

Three route shapes and nothing else:

```
redditindex.com/                 the pooled board
redditindex.com/{category}/      one category
redditindex.com/{company}/       one company, across every category it appears in
```

Both dynamic routes occupy the **same** path segment. Collisions are therefore possible, so they are resolved at build time by a fixed precedence order and a gate that **fails the build** on any duplicate. Published slugs are frozen and never regenerated.

## Context

The earlier spec used `/category/{slug}` and `/brand/{slug}`. Prefixed routes cannot collide, which is their entire appeal.

The flat form was specified directly by the owner. It is shorter, it reads better in a cold-outreach email, and it puts the company name immediately after the domain — `redditindex.com/hubspot` — which is the whole point of the asset.

The cost is real. One namespace means a company named the same as a category is an ambiguity, and the failure mode is silent: whichever route wins, the other page simply stops existing. Nobody notices until a brand searches for itself.

## Decision

### Precedence, highest first

| # | Class | Examples |
|---|---|---|
| 1 | **Framework and file paths** | `/api/*`, `/_next/*`, `/sitemap.xml`, `/robots.txt`, `/favicon.ico` |
| 2 | **Site routes** | `/methodology`, `/search` |
| 3 | **Category slugs** | the fixed, curated set of 20 |
| 4 | **Company slugs** | everything else |

A company whose natural slug is taken at a higher tier is assigned a disambiguated slug instead. The disambiguator is deterministic and derived from the company's primary category, so it is reproducible from the data rather than hand-assigned.

### The build gate

The union of all four tiers is asserted unique at build time. **A duplicate fails the build.** It is never resolved at request time and never resolved by whichever route the router happens to match first.

### Slugs are frozen

A published slug is persisted and never regenerated from the display name. Renames, casing changes, and gazetteer edits do not move a live URL; they update the display name only. If a slug must change, the old path emits a permanent redirect and both are recorded.

This is the rule that matters most for the outreach use case. A company page that moves after Google has indexed it loses the ranking that made it worth sending.

### One company, one page

A company belongs to more than one category — HubSpot to CRM and Marketing Automation, Deel to HR and Payroll, NetSuite to Accounting and ERP. There is exactly one `/{company}/` page, and it lists that company's score and rank **in every category it qualifies in**, each row naming its category.

The breadcrumb shows the company's **primary category** — the one where its opinionated mention volume is highest. The breadcrumb is navigation, not a claim of exclusivity, and the page body carries the full list.

## Consequences

**Category slugs are effectively permanent.** Adding a category in Phase 2 that collides with a published company slug is now a breaking change, not a content edit. The taxonomy work in [../03-taxonomy.md](../03-taxonomy.md) has to check the company gazetteer before minting a slug.

**The reserved list is data, not code.** It is generated from the categories table and the framework's own routes, so a new site route cannot silently shadow a company that already ships.

**Generic company names are the live risk.** Monday, Notion, Framer, Linear, Square, Slack and Stacks are all real products with common-word names. None currently collides with a category slug, but the gate is what guarantees that, not the observation.

**Sitemaps and canonicals are flat too.** Every page is one segment deep, self-canonical, and listed once.

## Alternatives rejected

| Option | Why not |
|---|---|
| Keep `/category/{slug}` and `/brand/{slug}` | Cannot collide, and was rejected by the owner. The flat form is the product decision |
| Suffix companies, e.g. `/hubspot-reviews/` | Reintroduces a prefix by another name and reads like SEO filler |
| Resolve collisions at request time | The ambiguity becomes a runtime behaviour nobody can see. A build failure is visible exactly once, to the person who caused it |
| Let the router's match order decide | Same defect, plus it depends on file naming rather than on a stated rule |
| Regenerate slugs from display names each build | A gazetteer edit silently moves a live, indexed URL |

---

[← Back to README](../README.md) · [Concept](../00-concept.md) · [Architecture](../08-architecture.md) · [Taxonomy](../03-taxonomy.md) · [SEO](../10-seo-aeo.md)
