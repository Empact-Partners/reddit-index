# UGC Ranks — Product Concept

## Bottom line

- UGC Ranks is a public, indexable leaderboard that ranks software brands per category by what people say about them on Reddit, split into a "most loved" and a "most hated" column, operated openly by Empact Partners.
- 🟢 The core position is empty. No live property ranks B2B software by Reddit sentiment as a public leaderboard; the Reddit-native category leader GummySearch closed 2025-11-30 ([gummysearch.com](https://gummysearch.com/)).
- 🟢 The format is proven, just not for software. ApeWisdom has run a public Reddit-derived ticker leaderboard for years on a short, mechanical methodology page ([apewisdom.io/methodology](https://apewisdom.io/methodology/)), and Profound runs the identical playbook for AI answers ([Profound Index](https://www.tryprofound.com/profound-index)).
- 🟡 Two numbers carry every page: **Sentiment Score** and **Mention Count**, plus a visible qualification threshold that decides whether a brand is ranked at all.
- ⚠️ Brand pages will display full Reddit comment text. That is a deliberate, priced risk taken by the owner against known contract and copyright exposure, not a compliant design. See [01-legal.md](01-legal.md).

---

## What it is

UGC Ranks turns Reddit's opinion layer into a browsable ranking of software brands, one page per category, one page per brand. Every score traces back to individual comments, each linked to its original thread.

Phase 1 covers the 50 largest software categories. Phase 2 extends to all categories. Nothing is built yet; this repository is documentation only.

It exists because Empact Partners needs a reason to email a stranger. The opening line is "here is what people say about you on Reddit," and the ranking is the artifact that makes that line land.

### Who it is for

| Audience | What they come for | What they do next |
|---|---|---|
| Software buyers | Unpaid opinion on a category they are shopping | Read the category page, click through to threads |
| Marketing and product leads at ranked companies | Their own score, their own comments | Recognize the problem, reply to Empact's email |
| AI answer engines | A structured, citable per-category ranking | Cite the category page in generated answers |
| Empact Partners (operator) | A named, warm reason to open a cold conversation | Send the outreach, book the call |

---

## The competitive gap

The neighboring seats are occupied. The seat itself is not.

| Occupant | What it owns | Why it is not this |
|---|---|---|
| Brand24, Brandwatch, Sprout, Syften, F5Bot | Reddit monitoring | All gated behind a login. None publishes a public brand ranking |
| [ApeWisdom](https://apewisdom.io/api/), SwaggyStocks | Public Reddit leaderboards | Stock tickers, not software. Proves the format survives |
| [Profound Index](https://www.tryprofound.com/profound-index) | Free public brand leaderboard, weekly, 50+ industries | Ranks AI-answer visibility, not Reddit sentiment |
| [YouGov BrandIndex Lite](https://yougov.com/business/products/brandindex-lite) | Free public brand scores | Survey panel, consumer brands, not software |
| G2 / Capterra | Software review authority | Vendor-paid. Structurally cannot publish unpaid opinion |

Two 2025-2026 events opened the gap. GummySearch, the one true Reddit-native player, shut down on 2025-11-30. G2 then acquired Capterra, Software Advice, and GetApp from Gartner for roughly $110M, closing 2026-02-05 ([PRNewswire](https://www.prnewswire.com/news-releases/g2-to-acquire-capterra-software-advice-and-getapp-from-gartner-302673901.html)).

That consolidation left one vendor-paid incumbent controlling most software-review influence. An unpaid, unsolicited-opinion ranking is now the only structurally independent alternative, and G2 can never build one, because Reddit contradicts its own paying customers.

Reddit's own surface keeps growing. It reached 10.24% of Google top-3 results after the May 2026 core update ([SE Ranking](https://seranking.com/blog/google-may-2026-core-update-analysis/)), which is the same corpus AI engines answer software questions from.

**Inference, not measured:** the reason no monitoring tool publishes a public ranking is that their revenue is the dashboard, so a free leaderboard would cannibalize it. The pattern is uniform across all seven vendors surveyed, but no vendor has stated this.

---

## The two metrics

Every surface shows the same two numbers, in the same order, with the same definitions.

| Metric | What it is | Where it appears |
|---|---|---|
| **Sentiment Score** | The published index for the brand in that category, on a fixed scale, with its confidence interval | Homepage, category page, brand page |
| **Mention Count** | Qualifying brand mentions in the window, with the effective (cluster-adjusted) count shown next to the raw count | Homepage, category page, brand page |
| **Qualification status** | Ranked · Statistically tied · Below threshold | Category table, brand page |

Entry to the ranking is gated by a minimum-mention threshold plus independence floors on distinct authors, distinct subreddits, and single-thread and single-author concentration. **The threshold and the brand's position against it must be visible on the page, not buried in the methodology.** Formulas live in [07-index-methodology.md](07-index-methodology.md).

Brands below the threshold are suppressed, never ranked low. Ranks whose intervals overlap are displayed as tied, following the same "publish your own failure modes" posture ApeWisdom takes on its methodology page.

---

## Page-by-page UX specification

### Homepage — `/`

| Element | Spec |
|---|---|
| Hero | One sentence stating what is measured and over what window. No marketing copy |
| Two columns | **Most Loved** and **Most Hated**, all categories pooled, top 10 each. Brand name, category, Sentiment Score, Mention Count |
| Consolidated table | Every qualifying brand across all categories, sortable by Sentiment Score, Mention Count, and category. Paginated |
| Category grid | All Phase 1 categories, linked, each showing brand count and last-updated date |
| Footer | "Created by Empact Partners." Link to `/about`. Explicit no-affiliation-with-Reddit disclaimer |

### Category page — `/category/{slug}`

The same two columns as the homepage, scoped to one category, above a full ranked table of every brand in the category.

| Column | Notes |
|---|---|
| Rank | Ties displayed as ties, sharing one rank number |
| Brand | Plain text name, links to the brand page. No logos, no brand colors |
| Sentiment Score | With confidence interval |
| Mention Count | Raw and effective |
| Qualification status | Ranked · Tied · Below threshold |
| Trend | Rank delta versus prior period |

Below-threshold brands appear in a separate collapsed block labeled with the threshold they missed. The window and the last-updated date sit at the top of the table, not the footer.

### Brand page — `/brand/{slug}`

| Section | Contents |
|---|---|
| Header | Brand name, Sentiment Score, Mention Count, window |
| Category ranks | One row per category the brand appears in, with rank, score, and status |
| Trend | Score and rank over the trailing window, month by month |
| Mentions | The individual Reddit comments: text, username, subreddit, date, permalink to the thread |
| Correction path | Free, unconditional, never bundled with a commercial offer |

⚠️ The mentions section is where the risk sits. Every live analogue — ApeWisdom, SwaggyStocks, Quiver — publishes counts and links but never verbatim user text, and that restraint is the shared survival trait. UGC Ranks departs from it by owner decision. Read [01-legal.md](01-legal.md) before changing a word of that section.

### Methodology page — `/about`

**This page is load-bearing legally, not decoratively.** Comparative ratings survive as opinion when the methodology is fully disclosed and applied consistently ([ZL Technologies v. Gartner](https://www.courtlistener.com/opinion/2540667/zl-technologies-inc-v-gartner-inc/)). An undisclosed or altered method is the fact pattern that loses.

It must contain, at minimum: the data source and collection window; the exact scoring definitions; the minimum-mention threshold and every independence floor; the entity-matching rules and their known failure modes; the tie rule; the correction and removal process; the operator's identity and commercial interest; and a version history with dates.

Write it like ApeWisdom's, not like a vendor's: short, mechanical, and openly self-incriminating about what the method gets wrong.

### Breadcrumbs

`Home > Category > Brand` on every page, marked up as structured data. Category pages carry `Home > Category`. No page is a dead end.

---

## What UGC Ranks is explicitly NOT

| Not this | Because |
|---|---|
| A review site | No one submits a review. Nothing is solicited, verified, or vendor-supplied |
| A G2 competitor | No vendor pays, no profiles are claimed, no badges are sold |
| A monitoring tool | No login, no alerts, no dashboard, nothing per-customer |
| An independent publication | Empact Partners operates it openly as a side project and uses it for outreach. The footer says so |
| A live API or data product | Reddit's Data API Terms forbid deriving revenue from the data without express written approval ([data-api-terms](https://redditinc.com/policies/data-api-terms)) |

---

## Name rationale

The product is **UGC Ranks**, at ugcranks.com. "Reddit" appears nowhere in the name, domain, subdomain, or logo.

Two reasons, both binding. Reddit's Data API Terms §4.1 forbid using Reddit trademarks in or as part of an app's name, and §4.2 permits only the "[X] for Reddit" form ([data-api-terms](https://redditinc.com/policies/data-api-terms)).

Reddit also litigates domain names *pro se* and wins. `reddit.win` was transferred in [WIPO D2020-1834](https://www.wipo.int/amc/en/domains/decisions/text/2020/d2020-1834.html), where the panel held that even noncommercial use of an identical mark "carries with it a high risk of implied affiliation."

The second reason is product scope. "UGC" lets the property extend to Hacker News, Stack Overflow, YouTube comments, and X without a rename, a redirect, or a rebuild of the brand.

**NOT VERIFIED:** the owner also cites Developer Terms §5.3 as a basis for the naming decision. The research corpus verifies Data API Terms §4.1 and §4.2 directly; the §5.3 reference has not been checked against the live text.

---

## Related

[← Back to README](README.md) · [01-legal.md](01-legal.md) · [07-index-methodology.md](07-index-methodology.md) · [08-architecture.md](08-architecture.md)
