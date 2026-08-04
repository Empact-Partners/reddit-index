# SEO and AI-Citation Specification

## Bottom line

- **Build for citation and the outreach hook, not for sessions.** G2 lost 84.5% of organic traffic (2.56M → 397K visits, Jan 2024 → Dec 2025) yet still holds 23.1% of review-platform links in AI Overviews; Capterra fell 89% and holds 17.8% ([SE Ranking, 30K keywords / 22,729 AIOs, 2025-12-01](https://seranking.com/blog/review-platforms-in-ai-overviews/)).
- Nothing in Google's spam policy bans programmatic pages. It bans *unoriginal* ones, "no matter how it's created" ([Google spam policies](https://developers.google.com/search/docs/essentials/spam-policies)). Our live exposure is the **Scraping** clause, not the AI clause.
- `AggregateRating` and `Review` markup are off the table: Google requires ratings "sourced directly from users" and forbids aggregating them from other websites ([review snippet guidelines](https://developers.google.com/search/docs/appearance/structured-data/review-snippet)). Use `Dataset`, `ItemList`, `BreadcrumbList`.
- Schema does not buy AI citations. Ahrefs tracked 1,885 pages that added JSON-LD Aug 2025 → Mar 2026 against 4,000 matched controls: AI Overviews **−4.6%**, AI Mode +2.4%, ChatGPT +2.2% ([Ahrefs](https://ahrefs.com/blog/schema-ai-citations/)).
- Skip `llms.txt`. Across 137,210 domains, 28% published a valid file and **97% of those were never fetched by anything** ([Ahrefs, May 2026](https://ahrefs.com/blog/llmstxt-study/)).
- The hardest gate here: a brand page is indexable only with **≥3 computed datapoints** existing nowhere else in that combination. Below threshold ships `noindex`.

---

## 1. The reframe

Directory traffic economics are broken. Directory citation economics are not. Modeling revenue on sessions from this category is modeling 2023.

Reddit Index earns its keep three ways, in this order: it gets **cited** by AI engines answering "best X", it produces a **per-brand outreach artifact** Empact can email a CMO, and only third does it earn clicks. See [00-concept.md](00-concept.md) and [11-outreach-play.md](11-outreach-play.md).

| Asset | Metric that matters | Metric that does not |
|---|---|---|
| Category page | Cited in ChatGPT / AI Mode / Perplexity answers | Sessions |
| Brand page | Replies when pasted into a cold email | Ranking position |
| `/methodology/` | Cited as the provenance for a number | Traffic |

---

## 2. What actually gets a site killed

The scaled-content-abuse policy targets "creating large amounts of unoriginal content that provides little to no value to users, no matter how it's created" ([spam policies](https://developers.google.com/search/docs/essentials/spam-policies)). Generation method is explicitly irrelevant.

Our real exposure is the **Scraping** clause in the same document: "Reproducing content feeds from other sites without providing some type of unique benefit to the user." That sentence is the whole risk model for this project.

**Site reputation abuse does not apply.** It governs third-party content on a *host* site trading on that host's ranking signals, and its not-a-violation list names "Sites designed to allow user-generated content, such as a forum website or comment sections" ([Google, Nov 2024](https://developers.google.com/search/blog/2024/11/site-reputation-abuse)). 🟡 INFERENCE: a standalone domain is out of scope.

### What our unique benefit is

| Layer | Counts as unique benefit? | Why |
|---|---|---|
| Computed loved/hated index per brand | 🟢 Yes | Exists nowhere else |
| Cross-brand ranking inside a category | 🟢 Yes | Reddit has no category leaderboard |
| Subreddit distribution, thread counts, mention dates | 🟢 Yes | Derived aggregates, not source expression |
| Stated methodology and scoring formula | 🟢 Yes | Provenance is the citation lever |
| Reproduced comment text | 🔴 No | This is the feed, not a benefit on top of it |

⚠️ **Displaying full comment text is a decided, priced risk.** The owner reviewed the contractual and copyright exposure and chose to display comment bodies with links back to the thread. This is not a compliant posture and is not defended here. Its consequence for SEO is single and specific: **the unique-benefit defense cannot rest on the comments.** See [01-legal.md](01-legal.md).

Any page whose value collapses to "a list of somebody else's comments" forfeits the Scraping-clause defense. The computed index must be the page; quotes are evidence beneath it, never the reverse.

---

## 3. Structured data, honestly

`AggregateRating` on Reddit-derived sentiment is a violation, not a gray area ([review snippet](https://developers.google.com/search/docs/appearance/structured-data/review-snippet)). Publish the score as plain HTML plus `Dataset` schema, and name it a **sentiment index**, never a rating.

| Type | Use | Where |
|---|---|---|
| `BreadcrumbList` | 🟢 Yes | Every page |
| `ItemList` | 🟢 Yes | Category pages ([carousel docs](https://developers.google.com/search/docs/appearance/structured-data/carousel)) |
| `Dataset` | 🟢 Yes | Category, brand, `/methodology/`, `/data/*.csv` |
| `Organization`, `WebSite` | 🟢 Yes | Root |
| `FAQPage` | 🟡 Optional | Rich-result eligibility is now narrow |
| `AggregateRating`, `Review` | 🔴 Never | Explicit violation on third-party-derived sentiment |

Do not expect schema to move AI citations. Google's own AI-features doc (updated 2025-12-10) states "There's also no special schema.org structured data that you need to add" ([Google](https://developers.google.com/search/docs/appearance/ai-features)). Schema here buys breadcrumb display and machine-readable provenance. That is all it buys.

**`llms.txt`: skip it.** 97% of valid published files were never fetched by any agent ([Ahrefs](https://ahrefs.com/blog/llmstxt-study/)), and Google confirmed non-support in July 2025. Building one is time spent on a file nothing reads.

---

## 4. Indexation architecture at 5,000 pages

We do not have a crawl-budget problem. Google's threshold is "1 million+ unique pages" changing weekly or "10,000+ unique pages" changing daily ([docs](https://developers.google.com/search/docs/crawling-indexing/large-site-managing-crawl-budget)). At 5K pages the problem is value per page.

| Concern | Rule |
|---|---|
| Internal linking | Hub-and-spoke: 50 category hubs → brand spokes; every brand links up to its category and laterally to 5-10 peers |
| Breadcrumbs | Visible breadcrumb plus `BreadcrumbList` on every page, no exceptions |
| Sitemaps | Index at root, one child sitemap per category, so Search Console coverage is diagnosable per segment |
| `<lastmod>` | Rewritten on every monthly recompute, accurate or omitted |
| Canonical | Self-canonical everywhere. No cross-canonical between category and brand |
| Pagination | No `rel=prev/next` (Google dropped support). Plain links, self-canonical each page |
| Faceted / filter URLs | `Disallow` in robots.txt, never `noindex` — with `noindex` "Google will still request, but then drop the page… wasting crawling time" ([docs](https://developers.google.com/search/docs/crawling-indexing/large-site-managing-crawl-budget)) |
| Launch cadence | Categories ship in waves, not 5,000 pages on one day |

### The indexation gate

There is no published Google word count for a thin page. 🟡 INFERENCE: the operative test is whether the page contains something unobtainable from the source. The gate below is our version of that test.

**A brand page is indexable only if it carries ≥1 category membership and ≥3 of:** sentiment index (computed, not a star rating), total mention count, subreddit distribution, first and last mention date, trend versus prior recompute, competitor co-mention rate.

**Below threshold → `<meta name="robots" content="noindex,follow">`.** The page still exists, still links out, still serves outreach, and stays out of the index. Thin brand pages are the largest index-bloat risk here, and the gate is enforced in code at render time, not editorially.

⚠️ Never pad a thin page with generated prose to clear the gate. Padding is the tell. A 120-word page of real numbers is safer than a 900-word page of filler ([spam policies](https://developers.google.com/search/docs/essentials/spam-policies)).

---

## 5. The "[category] reddit" query class

This is the target query class because Google keeps rewarding it. Reddit's share of Google top-3 positions rose to **10.24%** after the May 2026 core update, up from 8.56% post-March, gaining across all 20 tracked niches ([SE Ranking](https://seranking.com/blog/google-may-2026-core-update-analysis/)).

Demand is growing on Reddit's side too: weekly search users grew roughly 30% year over year, 60M → 80M ([eMarketer](https://www.emarketer.com/content/reddit-weekly-search-activity-jumps-30-yoy-boosting-ad-intent-user-reach)).

**NOT VERIFIED:** no primary keyword-level dataset for "[category] reddit" volume was obtained, and the repeated "32% of US Gen Z appends reddit weekly" figure is survey-derived secondary. Pull real volumes from Ahrefs before finalizing the category list in [03-taxonomy.md](03-taxonomy.md).

Title and H1 pattern: `Best [Category] According to Reddit ([Month Year])`, with a real month that changes on recompute.

---

## 6. AEO and GEO: what gets a data property cited

Four levers, in descending order of evidence strength.

| Lever | Evidence | Implementation |
|---|---|---|
| **Freshness** | Median days since publication of cited URLs: ChatGPT 958, Copilot 1,056, Gemini 1,118, Perplexity 1,166, versus Google organic 1,416 ([Ahrefs, 16.975M URLs](https://ahrefs.com/blog/do-ai-assistants-prefer-to-cite-fresh-content/)) | Monthly recompute, visible "Data as of" line, accurate `dateModified`, public `/changelog/` |
| **Stated methodology** | 🟡 INFERENCE from source-provenance behavior | `/methodology/`: sample size, date range, collection method, scoring formula, limitations, changelog. Linked from every page |
| **Front-loaded answer** | 🟡 SECONDARY: 44.2% of LLM citations come from the first 30% of page content; listicles 21.9%, articles 16.7%, product pages 13.7% ([Ahrefs data summary](https://www.quattr.com/blog/takeaway-from-ahrefs-ai-search-study)) | Ranked table above the fold. One extractable verdict per brand. No preamble |
| **Source type** | Semrush, 230K prompts / 13 weeks: UGC dominates but is volatile — Reddit's ChatGPT citation share fell ~60% → ~10% after a Sept 11 parameter change ([Semrush](https://www.semrush.com/blog/most-cited-domains-ai/)) | Do not build on being *inside* Reddit's citation share. Be the structured summary *of* it |

Authority still gates entry: sites with 32,000+ referring domains were 3.5× likelier to be cited by ChatGPT than sites with ≤200 (🟡 SECONDARY, [Leapd](https://www.leapd.ai/blog/ai-visibility/how-chatgpt-google-ai-overviews-and-perplexity-source-information-in-2026)). 🟡 INFERENCE: a new domain gets cited by being the only source of a specific number, not on authority.

Category-page order: H1 with month → one-sentence verdict → ranked table → "n threads / n comments analyzed, data as of [date]" → per-brand rows with links → category-specific interpretation → methodology link.

---

## 7. AI crawler access policy

Blocking a retrieval agent forfeits citation eligibility, which is the entire business case.

| Agent | Policy | Reason |
|---|---|---|
| `Googlebot`, `Bingbot` | 🟢 Allow | Baseline |
| `Google-Extended` | 🟢 Allow | Governs Gemini grounding; blocking it is a self-inflicted wound |
| `OAI-SearchBot`, `ChatGPT-User`, `PerplexityBot`, `Claude-SearchBot`, `Claude-User` | 🟢 Allow | Retrieval and answer agents |
| `GPTBot`, `CCBot`, `anthropic-ai` | 🟡 Block | Training-only; standard 2026 posture, costs nothing in citations ([Anagram](https://www.anagram.ai/blog/ai-crawlers-explained-gptbot-claudebot-perplexitybot-and-how-to-let-them-in-2026)) |
| `/search`, `/filter`, faceted params | 🔴 Disallow | Index bloat |

⚠️ The tension is unresolved: we want AI engines ingesting a derived dataset while Reddit litigates over derived and circumvented data ([Reddit v. SerpApi, Reddit v. Perplexity](https://www.coronium.io/blog/is-web-scraping-legal-2026)). Opening the door widens the audience for whatever exposure the display decision carries. Documented, not mitigated.

---

## 8. Deindexation risks, ranked by likelihood

| # | Risk | Likelihood | Mechanism |
|---|---|---|---|
| 1 | Reproduced comment text at scale | 🔴 High | Scraping clause verbatim, plus copyright exposure. Mitigate by making the computed index the page |
| 2 | Thin brand pages shipped past the gate | 🔴 High | Scaled content abuse |
| 3 | Faceted or filter URLs left crawlable | 🟡 Medium | 5K pages become 500K; manufactures a doorway problem |
| 4 | `AggregateRating` on the sentiment index | 🟡 Medium | Structured-data violation → manual action, rich results removed |
| 5 | Generated prose padding thin pages | 🟡 Medium | Padding is the detection signal, not the fix |
| 6 | Static, never-recomputed data | 🟡 Medium | Decays out of AI answers; reads as abandoned |
| 7 | No stated methodology | 🟡 Medium | Uncitable by engines needing provenance; a defamation surface on named companies |
| 8 | Subdomain rented to a third party | 🟢 Low | Site reputation abuse; relocating it "may be viewed as an attempt to circumvent spam policy" |
| 9 | Forecast built on G2-era traffic assumptions | 🟢 Low (planning) | Directory organic traffic fell 76-92% across the category 2024 → 2025 |

Claims that a "March 2026 core update explicitly named scaled content abuse" circulate on SEO blogs. **NOT VERIFIED** against any Google primary source. Do not plan against it.

---

[← Back to README](README.md) · [00-concept.md](00-concept.md) · [11-outreach-play.md](11-outreach-play.md)
