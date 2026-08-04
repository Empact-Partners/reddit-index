# Reddit Index — Product Concept

## Bottom line

- **Reddit Index** (`redditindex.com`) is a public, indexable leaderboard that ranks software brands per category by what people say about them on Reddit, split into a **Most Loved** and a **Most Hated** column, operated openly by Empact Partners.
- Four page types carry the entire product: the homepage `/`, one category page per category, one brand page per brand, and a single methodology page at `/methodology`. Nothing else ships in Phase 1.
- Three numbers appear on every surface, in the same order: a **Love Index**, a **Hate Index**, and the mention count published as both raw `n` and effective `n_eff`. Two independent scores, never one net score ([decisions/0004](decisions/0004-two-axis-index.md)).
- Ranking is gated at `n_eff ≥ 400` plus four diversity floors. Everything under the gate is **Profiled**: mentions shown, no position published. That tier is where the outreach comes from ([11-outreach-play.md §6](11-outreach-play.md)).
- Every mention on a brand page carries the comment text, the author's username, a "from Reddit" label, and a permalink to the thread. Deleted comments disappear within a day, no page runs ads, and removal is free and unconditional.
- 🟡 The **public cross-brand leaderboard** seat is unoccupied. The **adjacent per-brand audit** seat is not: [redditbrands.com](https://redditbrands.com/) and [whatredditthinks.com](https://whatredditthinks.com/) are both live, both registered within the last three months ([domain sweep](data/domain-availability.csv), verified 2026-08-04).
- 🟢 The format is proven, just not for software. ApeWisdom has run a public Reddit-derived ticker leaderboard for years on a short, mechanical methodology page ([apewisdom.io/methodology](https://apewisdom.io/methodology/)), and Profound runs the identical playbook for AI answers ([Profound Index](https://www.tryprofound.com/profound-index)).
- Two things here are priced risks rather than solved problems: the Reddit-containing name, and the display of full comment text. The reasoning and the clause citations live in [01-legal.md](01-legal.md).

---

## What it is

Reddit Index turns Reddit's opinion layer into a browsable ranking of software brands at `redditindex.com`: one page per category, one page per brand. Every score traces back to individual comments, each linked to the thread it came from.

Phase 1 covers the 50 largest software categories. Phase 2 extends to all categories. Nothing is built yet; this repository is documentation only.

It exists because Empact Partners needs a reason to email a stranger. The opening line is "here is what people say about you on Reddit," and the ranking is the artifact that makes that line land.

### Who it is for

| Audience | What they come for | What they do next |
|---|---|---|
| Software buyers | Unpaid opinion on a category they are shopping | Read the category page, click through to threads |
| Marketing leads at **profiled** brands, below the ranking threshold | Their own mentions and their own trajectory, with no published position | Recognize the problem, reply to Empact's email |
| Marketing leads at **ranked** head brands | Their position, their badge, their comments | Embed the badge, or dispute the score. They are the credibility layer, not the pipeline |
| AI answer engines | A structured, citable per-category ranking | Cite the category page in generated answers |
| Empact Partners (operator) | A named, warm reason to open a cold conversation | Send the outreach, book the call |

The ranked tier and the buying tier are different companies by design. Anything that clears `n_eff ≥ 400` plus the diversity floors is a category incumbent, and category incumbents do not buy boutique retainers. The two-tier resolution is specified in [11-outreach-play.md §6](11-outreach-play.md).

---

## The competitive gap

The neighboring seats are occupied, and two of them were taken this year. The cross-brand leaderboard seat itself is still open.

| Occupant | What it owns | Why it is not this |
|---|---|---|
| [redditbrands.com](https://redditbrands.com/) | Live per-brand "Reddit Brand Reputation" audit: free A-to-F grade, four-engine AI probe, PDF export | On-demand, one brand at a time. No cross-brand board, no per-category ranking, no published eligibility threshold |
| [whatredditthinks.com](https://whatredditthinks.com/) | Live per-question Reddit consensus pages, with a methodology page and a paraphrase-not-quote policy | Indexes questions, not brands. Ranks nothing, so there is no position to defend or dispute |
| Brand24, Brandwatch, Sprout, Syften, F5Bot | Reddit monitoring | All gated behind a login. None publishes a public brand ranking |
| [ApeWisdom](https://apewisdom.io/api/), SwaggyStocks | Public Reddit leaderboards | Stock tickers, not software. Proves the format survives |
| [Profound Index](https://www.tryprofound.com/profound-index) | Free public brand leaderboard, weekly, 50+ industries | Ranks AI-answer visibility, not Reddit sentiment |
| [YouGov BrandIndex Lite](https://yougov.com/business/products/brandindex-lite) | Free public brand scores | Survey panel, consumer brands, not software |
| G2 / Capterra | Software review authority | Vendor-paid. Structurally cannot publish unpaid opinion |

`redditbrands.com` was registered 2026-06-07 and `whatredditthinks.com` on 2026-05-25; both were fetched live on 2026-08-04 ([domain sweep](data/domain-availability.csv), [method.md](method.md)). They validate the demand and they take the audit lane. The leaderboard seat is open, but it is not open indefinitely.

One product difference is worth naming plainly: `whatredditthinks.com` paraphrases, it does not quote. Reddit Index quotes, and that single choice is what separates the two properties on every brand page.

Two 2025-2026 events widened the seat. GummySearch, the one true Reddit-native player, shut down on 2025-11-30 ([gummysearch.com](https://gummysearch.com/)). G2 then acquired Capterra, Software Advice, and GetApp from Gartner for roughly $110M, closing 2026-02-05 ([PRNewswire](https://www.prnewswire.com/news-releases/g2-to-acquire-capterra-software-advice-and-getapp-from-gartner-302673901.html)).

That consolidation left one vendor-paid incumbent controlling most software-review influence. An unpaid, unsolicited-opinion ranking is now the only structurally independent alternative, and G2 can never build one, because Reddit contradicts its own paying customers.

Reddit's own surface keeps growing. It reached 10.24% of Google top-3 results after the May 2026 core update ([SE Ranking](https://seranking.com/blog/google-may-2026-core-update-analysis/)), which is the same corpus AI engines answer software questions from.

**Inference, not measured:** the reason no monitoring tool publishes a public ranking is that their revenue is the dashboard, so a free leaderboard would cannibalize it. The pattern is uniform across all seven vendors surveyed, but no vendor has stated this.

---

## The three numbers

Every surface shows the same numbers, in the same order, with the same definitions.

| Metric | What it is | Where it appears |
|---|---|---|
| **Love Index** | Shrunk share of *opinionated* mentions labeled positive, with its confidence interval | Homepage, category page, brand page |
| **Hate Index** | Shrunk share of *opinionated* mentions labeled negative, with its confidence interval | Homepage, category page, brand page |
| **Mention count** | Qualifying brand mentions in the window, published as raw `n` **and** effective `n_eff` | Homepage, category page, brand page |
| **Qualification status** | Ranked · Statistically tied · Below threshold | Category table, brand page |

Two independent scores, never one net score. A net figure makes a brand half the category loves and half despises look identical to one nobody has an opinion about. Formulas live in [07-index-methodology.md](07-index-methodology.md); the call is recorded in [decisions/0004](decisions/0004-two-axis-index.md).

### The denominator is opinionated mentions only

`N_opinionated = pos + neg`. Both indexes are computed against that, never against all mentions. Ubiquitous tools accrue large incidental volume ("export it to X", "the X API"), and scoring on it would rank ubiquity rather than sentiment.

`neutral_share` and `abstain_share` are therefore published beside every score. A reader who cannot see how much of the conversation was excluded cannot check the number.

Before shrinkage, `L + H = 1` by construction. The two are then shrunk **independently** against their own category priors, so the published pair does not sum to exactly 1. The page says so rather than implying an invariant that does not hold.

Polarization is not "a brand tops both columns." It is a low `neutral_share` with both shrunk rates sitting near 0.5, and it is published as its own field rather than inferred from the two columns.

### Entry to the ranking is gated on the effective sample

The naive derivation — `n_min = z²p(1−p)/h² = 384`, rounded to 400 at ±5pp — assumes independent draws. Reddit mentions cluster inside a handful of mega-recommendation threads and again by author, so that assumption fails and 400 raw mentions can carry far less information than 400.

The gate is therefore `n_eff ≥ 400`, where `n_eff = n / DEFF` and `DEFF = 1 + (m̄ − 1)·ICC`. Both counts are published on every brand page. Confidence intervals come from a cluster bootstrap resampling by thread and by author, not from a plain Wilson interval.

Four diversity floors sit on top: distinct authors, distinct subreddits, distinct threads, and a cap on the share of mentions coming from any single thread. **The threshold and the brand's position against it must be visible on the page, not buried in the methodology.**

Brands below the threshold are suppressed, never ranked low. Ranks whose intervals overlap are displayed as tied, following the same "publish your own failure modes" posture ApeWisdom takes on its methodology page.

### The threshold squeeze

At `n_eff ≥ 400` plus the floors, only category head brands qualify. Head brands are Salesforce-class incumbents that do not buy consultancy retainers, so the statistically sound half of the product and the commercially useful half point at different companies.

The resolution is a two-tier site, not a lower bar: Tier 1 **Ranked** carries position, badges and press; Tier 2 **Profiled** carries mentions and a labeled "not enough data to rank" state, with no position published at all. Outreach comes from Tier 2. See [11-outreach-play.md §6](11-outreach-play.md).

### The column labels

The columns are labeled **Most Loved** and **Most Hated**, and they do not change ([decisions/0005](decisions/0005-superlative-labels.md)).

Every surface carries the measured variable beside the label, in the form `Hate Index 21/100 · 412 opinionated mentions · Jan–Jun 2026`. The superlative is the headline; the measured variable is what the reader checks it against. A label standing alone is a defect, not a style choice.

The scope travels with the label everywhere it appears: this index, this source, this window. No page title, meta description, or badge says "worst software" or "companies people hate."

---

## Page-by-page UX specification

### Homepage — `/`

| Element | Spec |
|---|---|
| Hero | One sentence stating what is measured and over what window. No marketing copy |
| Exposure-confound line | Persistent, above the boards: rank reflects what Reddit says, not product quality, and enterprise-sold incumbents skew negative. Required on every ranked surface by [07-index-methodology.md §8](07-index-methodology.md) |
| Two columns | **Most Loved** and **Most Hated**, all categories pooled, top 10 each. Brand name, category, the governing index with its interval, raw and effective mention count |
| Consolidated table | Every qualifying brand across all categories, sortable by Love Index, Hate Index, mention count, and category. The default sort key is named on the page. Paginated |
| Category grid | All Phase 1 categories, linked, each showing brand count and last-updated date |
| Footer | "Created by Empact Partners," the non-affiliation notice, and the link to `/methodology`. Present on every page of the site, not just this one |

### Category page — `/category/{slug}`

The same two columns as the homepage, scoped to one category, above a full ranked table of every brand in the category.

| Column | Notes |
|---|---|
| Rank | Ties displayed as ties, sharing one rank number |
| Brand | Plain text name, links to the brand page. No logos, no brand colors |
| Love Index | With confidence interval |
| Hate Index | With confidence interval |
| Mentions | Raw `n` and effective `n_eff` |
| Qualification status | Ranked · Tied · Below threshold |
| Trend | Rank delta versus prior period |

The exposure-confound line is a distinct component from the methodology callout and both appear. The callout states method, version and window; the confound line states what the rank does not mean. A page carrying only the callout has not met the requirement.

Below-threshold brands appear in a separate collapsed block labeled with the threshold they missed. The window and the last-updated date sit at the top of the table, not the footer.

### Brand page — `/brand/{slug}`

| Section | Contents |
|---|---|
| Header | Brand name, Love Index and Hate Index with intervals, raw and effective mention count, window |
| Confound disclosure | The persistent line, plus `neutral_share` and `abstain_share` for the window |
| Trajectory | The brand against its own baseline over time, shown alongside the cross-brand rank. This is the presentation that survives the size objection |
| Category ranks | One row per category the brand appears in, with rank, both indexes, and status |
| Mentions | The individual Reddit comments: full text, the author's username, a "from Reddit" label, subreddit, date, and a permalink to the thread |
| Correction path | Free, unconditional, one click from the page, never bundled with a commercial offer |

Four requirements ship with the mentions section or the mentions section does not ship. They are build items, not policy language.

- A permalink to the source thread on every single mention
- The author's username, displayed as written
- A visible "from Reddit" label on the block, so no reader mistakes the text for ours
- A nightly delete-sync: a comment deleted, edited, or removed on Reddit is gone here within a day

Two more hold across the whole property. No page runs advertising of any kind, on any surface, ever. Removal requests from a commenter or a brand are free, unconditional, and never routed through a sales conversation.

### Methodology page — `/methodology`

One URL, everywhere, and one click from every ranking. It is the badge destination, the `Dataset` schema provenance target, and the footer link. No second `/about` route carries any of that.

It must contain, at minimum: the data source and collection window; the exact scoring definitions and both denominators; the `n_eff ≥ 400` gate with its derivation and every diversity floor; the entity-matching rules and their known failure modes; and the tie rule.

It must also carry the exposure confound in plain language, the correction and removal process, the operator's identity and commercial interest, and a version history with dates.

The method is frozen and version-controlled before the first scoring run, and every subsequent change is logged with a timestamp. Nothing is adjusted after seeing where a brand landed, in either direction.

Write it like ApeWisdom's, not like a vendor's: short, mechanical, and openly self-incriminating about what the method gets wrong.

### Breadcrumbs

`Home > Category > Brand` on every page, marked up as structured data. Category pages carry `Home > Category`. No page is a dead end, and no page is reachable only from search.

---

## What Reddit Index is explicitly NOT

| Not this | Because |
|---|---|
| A review site | No one submits a review. Nothing is solicited, verified, or vendor-supplied |
| A G2 competitor | No vendor pays, no profiles are claimed, no badges are sold |
| A monitoring tool | No login, no alerts, no dashboard, nothing per-customer |
| A per-brand audit tool | `redditbrands.com` occupies that lane. Reddit Index publishes a standing cross-brand board, not an on-demand grade |
| An independent publication | Empact Partners operates it openly as a side project and uses it for outreach. The footer says so |
| A live API or data product | No public API, no bulk export, nothing licensed or sold. That constraint is permanent, not a roadmap item |

---

## Name rationale

The product is **Reddit Index**, at `redditindex.com`, verified available 2026-08-04 with no DNS and effectively no archive history. `redditbrandindex.com` is registered as a defensive second name and redirects to it.

The name is deliberately Reddit-specific. It says what the product is with zero explanation, and the surface where that matters most is a cold email, where the first line is the only attention this property ever gets. A name that has to be unpacked spends that line on itself.

Two costs came with that legibility. Both were priced rather than avoided, and the full record, with the alternatives rejected and the conditions attached, is in [decisions/0001](decisions/0001-name-reddit-index.md).

**The build absorbs the first cost as design rules.** No Reddit visual identity, ever: no orange `#FF4500`, no Snoo, no Reddit Sans, no lookalike mark ([09-design.md](09-design.md)). Plain-text company names only, no logos. A non-affiliation notice in the footer of every page, exact wording in [decisions/0001](decisions/0001-name-reddit-index.md).

**The second cost is that the name is Reddit-locked.** Phase 3 in [12-phasing.md](12-phasing.md) contemplates Hacker News, Stack Overflow and other sources. "Reddit Index" cannot carry them without a rename, a redirect, and a rebuild of the brand. That option was sold for legibility, knowingly.

`brandsonreddit.com` was available and is the documented migration target. So everything stays cheap to move: all internal links relative, the canonical host in exactly one config value, and a rename should cost a day rather than a quarter.

---

## Related

[← Back to README](README.md) · [01-legal.md](01-legal.md) · [07-index-methodology.md](07-index-methodology.md) · [08-architecture.md](08-architecture.md) · [09-design.md](09-design.md) · [11-outreach-play.md](11-outreach-play.md) · [12-phasing.md](12-phasing.md)
