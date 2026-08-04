# Category Taxonomy

## Bottom line

- **Capterra's public taxonomy is flat, not hierarchical.** [/categories/](https://www.capterra.com/categories/) renders one A-Z list of leaf categories; the 11 groupings are a nav mega-menu only, with no published per-grouping counts.
- **1,000 leaf URLs actually render and the list truncates mid-W at "Warranty Management,"** so the true count exceeds 1,000. The URL pattern is uniform: `capterra.com/{slug}-software/`.
- **G2 is the better spine: 2,237 category URLs enumerable from one page,** with the real two-level parent to child structure Capterra lacks ([g2.com/categories](https://www.g2.com/categories), scraped 2026-08-04).
- ⚠️ **Capterra's Terms of Use name category structure as a protected element.** §10 bans automated extraction and bans replicating their "information architecture, category structure, or user experience." Their robots.txt is permissive and the two documents directly conflict.
- **Therefore UGC Ranks does not ship a copy of anyone's catalog.** The spine is the intersection of G2 and Capterra vocabulary, renamed and reordered by us, anchored to Wikidata Q-IDs, with no product counts or ratings published.
- **Phase 1 is 50 categories** ([data/phase1-categories.csv](data/phase1-categories.csv)); Phase 2 opens the long tail once the pipeline holds.

---

## 1. What Capterra actually publishes

The A-Z list at [/categories/](https://www.capterra.com/categories/) is one flat set of leaf categories. Every entry resolves to `capterra.com/{slug}-software/`. Page copy claims "900+" and says the range runs "Accounting to Yoga Studio Management," but the rendered list stops at Warranty Management.

The 11 nav groupings (Human Resources, Marketing & Sales, IT & Security, Healthcare, and so on) are text labels, not linkable hub pages. Each shows 6 to 10 hand-picked featured children.

**INFERENCE:** the groupings are a UI layer only. The 1,000 A-Z categories carry no public grouping assignment, so a two-level tree cannot be rebuilt from Capterra alone. That limitation is the main reason we do not use Capterra as the spine.

## 2. ⚠️ The legal conflict, and why it decides the design

Capterra's [robots.txt](https://www.capterra.com/robots.txt) (fetched 2026-08-04) is permissive. It blocks only `/search`, `/ppc/clicks/`, `/ai-assistant/`, `/redirector/`, `/forms/` and sort parameters, and it explicitly allows GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, PerplexityBot, and Google-Extended at `/`.

Their [Terms of Use](https://www.capterra.com/legal/terms-of-use/) (updated 2026-05-04) say the opposite. §10 forbids accessing, collecting, copying, scraping, harvesting, caching, indexing, storing, or extracting content "through automated, programmatic, or mechanical means," and separately bans using extracted content to train or evaluate any machine-learning or generative AI system.

§10 also bans replicating "the look-and-feel, functionality, information architecture, **category structure**, or user experience." §3 claims "any analyses, transformations, aggregations, compilations, metadata, scores, ratings, rankings... Derived Data" as Capterra's sole and exclusive property.

That §10 clause is unusually specific and is aimed at exactly this use case. Taking only the category names is not a safer position than taking product data under their contract, because category structure is named directly.

**INFERENCE, not legal advice:** individual short names like "Project Management Software" are almost certainly uncopyrightable short phrases, and *Feist* holds an unoriginal compilation of facts is not protectable. A selection-and-arrangement claim over the specific 1,000-item set is still arguable, and contract breach is independent of copyright.

G2 now owns Capterra, so G2's terms are likely to be equally restrictive. **NOT VERIFIED** — nobody has read `g2.com/static/terms` yet. Treat G2 as legally identical to Capterra until someone does.

Note that this is a separate exposure from the Reddit comment text UGC Ranks displays on brand pages. That is a deliberate, priced risk taken by the owner and is documented in [01-legal.md](01-legal.md), not here.

## 3. Alternative taxonomies compared

| Source | Size | Access | Verdict |
|---|---|---|---|
| **[G2](https://www.g2.com/categories)** | 2,237 category URLs, verified in one scrape 2026-08-04; real two-level parent to child structure | robots.txt permissive on `/categories`; public sitemap index. ToS restrictiveness **NOT VERIFIED** | 🟢 **Best fit.** Deeper, hierarchical, fully enumerable, same industry vocabulary as Capterra |
| **[Capterra](https://www.capterra.com/categories/)** | 1,000 rendered, true count higher | robots.txt permissive, ToS explicitly hostile (§10, §3) | 🟡 Useful as a **cross-check vocabulary**, never as the published spine |
| **Product Hunt topics** | Count **NOT VERIFIED** — page lazy-loads, roughly 30 topics per fetch | Cloudflare-challenged to plain curl; GraphQL API needs a token | 🔴 Consumer and indie skew (`alexa-skills`, `adult-coloring-books`). Wrong universe for B2B software |
| **[NAICS 513210](https://www.census.gov/naics/?input=513210&year=2022&details=513210)** | 1 code, roughly 15 sub-descriptions | Public domain, US Government, zero restrictions | 🔴 Legally bulletproof, useless resolution. All of SaaS collapses into one code |
| **Wikidata subclasses of Q7397** | 16,397 classes (live SPARQL count, 2026-08-04) | CC0, free endpoint at `query.wikidata.org` | 🟡 Free and machine-queryable, but community-built and wildly inconsistent in granularity. Good as an **anchor**, bad as a spine |

## 4. The recommended spine

Derive the concept list from the **intersection** of G2 and Capterra category vocabulary. A concept that appears in both is industry-standard vocabulary rather than either company's proprietary arrangement, which is the strongest available position on both the contract and copyright axes.

Then do four things that break the link to either source:

| Step | Rule |
|---|---|
| Name | Write our own display name. Never reuse a competitor slug |
| Order | Rank by our own signal. Never inherit their sequence |
| Anchor | Attach a Wikidata Q-ID per concept as the neutral canonical identifier |
| Publish | Ship no product counts, ratings, review counts, rankings, or shortlist positions |

The publish rule exists because §3's "Derived Data" clause covers precisely counts, scores, ratings, and rankings. Our published numbers are Reddit-derived and ours; nothing sourced from a directory gets republished.

⚠️ **This repo deliberately does not contain a copy of Capterra's 1,000-item catalog.** Committing that file would be the single most quotable artifact in any dispute, and it buys nothing the intersection method does not already give us.

## 5. How the Phase 1 fifty were selected

The size signal was Capterra's own `schema.org/ItemList` JSON-LD `numberOfItems` value on each category page, measured across 184 candidate categories on 2026-08-04. The range ran from CRM at 1,670 down to Pest Control at 97.

That figure was validated as a real listing count by cross-checking prose on the same pages. Field Service showed JSON-LD 1,028 against prose "1,047 field service management products"; Accounting showed 997 against "over 977 products."

**The counts were a selection signal only and are not republished as a dataset.** [data/phase1-categories.csv](data/phase1-categories.csv) carries a `size_tier` column (XL / L / M) instead of raw numbers, which preserves the ordering decision without shipping anyone's derived data.

Because products are multi-listed across categories, these counts sum to far more than the real catalog. They rank categories against each other; they do not measure a market.

## 6. ⚠️ The slug trap

Never guess a Capterra slug. Twelve guessed slugs 404'd on 2026-08-04: `crm-software`, `erp-software`, `cad-software`, `database-software`, `retail-software`, `hotel-management-software`, `ehr-software`, `school-management-software`, `web-hosting-software`, `translation-software`, `password-manager-software`, `low-code-development-platforms-software`.

The real ones are irregular and must be read off the A-Z list: `enterprise-resource-planning-software`, `database-management-software`, `school-administration-software`, `grc-software`, `3d-cad-software`, `retail-pos-system-software`.

This matters for verification work even though we do not publish their slugs. A 404 from a guessed slug reads as "category does not exist" and silently drops a real category from consideration.

## 7. Phase 1 vs Phase 2 scope

| | Phase 1 | Phase 2 |
|---|---|---|
| Count | 50 categories | All viable categories |
| Selection | Largest by the JSON-LD size signal | Long tail, gated on Reddit signal density |
| Source list | [data/phase1-categories.csv](data/phase1-categories.csv) | Not built |
| Structure | Flat. 50 leaf category pages | Two-level, following the G2-shaped parent to child model |
| Gate to advance | Pipeline produces defensible loved/hated columns without manual repair | — |

Phase 1 stays flat deliberately. Fifty pages do not need a parent layer, and committing to a hierarchy before the Reddit signal is understood would lock in a shape we would then have to migrate.

Reddit signal per category is tracked in the same CSV via `reddit_signal_verdict`. Most rows read `not_assessed` as of 2026-08-04, so category ordering is currently a size ordering, not a coverage ordering.

---

[← Back to README](README.md) · [01-legal.md](01-legal.md) · [data/phase1-categories.csv](data/phase1-categories.csv)
