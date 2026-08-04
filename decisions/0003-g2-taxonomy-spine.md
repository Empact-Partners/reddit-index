# 0003 — Derive the category spine, do not copy Capterra's

**Status:** Accepted · **Date:** 2026-08-04 · **Decided by:** Vlad Shvets, on the research

## Bottom line

The category spine is **derived**, not copied. Capterra's [Terms of Use](https://www.capterra.com/legal/terms-of-use/) name "category structure" as a protected element, its public list is flat and truncates at 1,000 leaf URLs, and G2 — which now owns Capterra — sits in the same legal position with a deeper list.

We take only the concept vocabulary appearing in **both** directories, anchor each concept to a neutral Wikidata Q-ID, and name and order the tree ourselves. No product counts, ratings, rankings or Shortlist positions are republished.

## Context

The original sketch was "use Capterra categories" — pick the 50 largest, then extend to all of them in Phase 2.

Measuring Capterra on 2026-08-04 turned up three problems.

**The taxonomy is flat.** [capterra.com/categories/](https://www.capterra.com/categories/) renders one A-Z list of leaf categories. The 11 top-level groupings exist only as a navigation mega-menu with roughly 9-10 hand-picked children each, and Capterra publishes no per-grouping counts. You cannot rebuild a two-level tree from Capterra alone.

**The list is truncated.** Exactly 1,000 leaf URLs render, and the list stops mid-W at "Warranty Management" while the page copy promises "Accounting to Yoga Studio Management." The true count exceeds what the page will give you.

**The terms name this use case specifically.** Capterra's [Terms of Use](https://www.capterra.com/legal/terms-of-use/) (updated 2026-05-04) §10 bans automated extraction, and separately bans replicating "the look-and-feel, functionality, information architecture, **category structure**, or user experience."

§3 goes further, claiming "any analyses, transformations, aggregations, compilations, metadata, scores, ratings, rankings… Derived Data" as their sole and exclusive property.

Their [robots.txt](https://www.capterra.com/robots.txt) is permissive and explicitly allows GPTBot, ClaudeBot and PerplexityBot at `/`. The two documents conflict. The terms are the binding one. The full legality position is in [../01-legal.md](../01-legal.md); this record only decides where the spine comes from.

## Decision

Derive the spine from the **intersection of G2 and Capterra category vocabulary**, then name and order it ourselves.

A concept appearing in both directories is industry-standard vocabulary rather than either company's property. Each concept is anchored to a neutral Wikidata Q-ID as its canonical identifier.

The intersection is a *vocabulary* test, not an *independence* test, and the difference matters more than it did a year ago. See the ownership note below.

**No product counts, ratings, rankings or Shortlist positions are republished.** Capterra's schema.org `numberOfItems` was used as a selection signal to pick the 50 and is cited as evidence in [../03-taxonomy.md](../03-taxonomy.md). It does not ship as a dataset. See [../data/README.md](../data/README.md).

G2 is the better structural reference: **2,237 category URLs enumerable from one page** ([g2.com/categories](https://www.g2.com/categories), measured 2026-08-04), with the real two-level parent→child hierarchy Capterra lacks.

### The two directories now share an owner

G2 acquired Capterra, Software Advice and GetApp from Gartner for roughly $110M: announced 2026-01-29, closed 2026-02-05 ([PRNewswire](https://www.prnewswire.com/news-releases/g2-to-acquire-capterra-software-advice-and-getapp-from-gartner-302673901.html)). Two consequences, and they pull in opposite directions.

**Legal.** Assume G2's terms are at least as restrictive as Capterra's until somebody reads them. G2's own terms are **NOT VERIFIED** — check `g2.com/static/terms` before relying on any G2 structure, slug, ordering or count.

**Methodological (inference).** Common ownership weakens "it appears in both" as evidence of independent industry usage going forward, since the two catalogs can now be aligned by a single editor. It does not weaken it retroactively: both vocabularies were built independently over years before February 2026, and the Phase 1 spine was measured on 2026-08-04 against catalogs that still diverge.

Practical rule: treat agreement between G2 and Capterra as **necessary but not sufficient**. Every concept in the spine must also survive a third, unaffiliated check — Wikidata, NAICS or plain trade usage — before it earns a page.

## Consequences

Phase 2's "all categories" is now our own taxonomy at whatever depth we choose, not a mirror of somebody's catalog. That is more work up front and a better asset afterwards.

It also removes an awkward dependency: a directory that just reproduces Capterra's structure has a weak answer to Google's Scraping policy, which asks what unique benefit we add. See [../10-seo-aeo.md](../10-seo-aeo.md).

⚠️ **Never guess a Capterra slug.** Twelve plausible guesses returned 404 during research, including `crm-software`, `erp-software` and `cad-software`. The real ones are irregular: `enterprise-resource-planning-software`, `database-management-software`, `school-administration-software`.

## Alternatives rejected

| Option | Why not |
|---|---|
| Mirror Capterra's 1,000 categories verbatim | Directly hits §10's "category structure" clause. |
| Use G2's 2,237 as the spine verbatim | Same problem, same owner, deeper list. |
| NAICS 513210 "Software Publishers" | Public domain and legally bulletproof, but one code for all of SaaS. Useless resolution. |
| Wikidata subclasses of Q7397 alone | 16,397 classes, CC0 and queryable, but community-built and wildly inconsistent in granularity. Used as an anchor, not a spine. |

---

[← Back to README](../README.md) · [Taxonomy](../03-taxonomy.md) · [Legal position](../01-legal.md) · [Phase 1 categories](../data/phase1-categories.csv)
