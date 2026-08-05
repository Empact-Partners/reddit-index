# SEO and AI-Citation Specification

## Bottom line

- **Build for citation and the outreach hook, not for sessions.** G2 lost 84.5% of organic traffic (2.56M → 397K visits, Jan 2024 → Dec 2025) yet still holds 23.1% of review-platform links in AI Overviews; Capterra fell 89% and holds 17.8% ([SE Ranking, 30K keywords / 22,729 AIOs, 2025-12-01](https://seranking.com/blog/review-platforms-in-ai-overviews/)).
- Nothing in Google's spam policy bans programmatic pages. It bans *unoriginal* ones, "no matter how it's created" ([Google spam policies](https://developers.google.com/search/docs/essentials/spam-policies)). Our live exposure is the **Scraping** clause, not the AI clause.
- **The whole ranking question reduces to one sentence.** redditindex.com is a Reddit-derived property on its own domain, so "some type of unique benefit to the user" is a test every page takes. Section 2 names the four things that pass it and the one layout that fails it.
- URL structure uses one shared flat segment for category and company pages — `/{category}/`, `/{company}/`, `/methodology/` — and a company page is **global**, so its breadcrumb names a primary category it does not nest under (section 4).
- `AggregateRating` and `Review` markup are off the table: Google requires ratings "sourced directly from users" and forbids aggregating them from other websites ([review snippet guidelines](https://developers.google.com/search/docs/appearance/structured-data/review-snippet)). Use `Dataset`, `ItemList`, `BreadcrumbList`.
- Schema does not buy AI citations. Ahrefs tracked 1,885 pages that added JSON-LD Aug 2025 → Mar 2026 against 4,000 matched controls: AI Overviews **−4.6%**, AI Mode +2.4%, ChatGPT +2.2% ([Ahrefs](https://ahrefs.com/blog/schema-ai-citations/)).
- Skip `llms.txt`. Across 137,210 domains, 28% published a valid file and **97% of those were never fetched by anything** ([Ahrefs, May 2026](https://ahrefs.com/blog/llmstxt-study/)).
- The hardest gate here: a company page is indexable only with **≥3 computed datapoints** existing nowhere else in that combination. Pages that are thin for indexation ship `noindex`.

---

## 1. The reframe

Directory traffic economics are broken. Directory citation economics are not. Modeling revenue on sessions from this category is modeling 2023.

Reddit Index earns its keep three ways, in this order: it gets **cited** by AI engines answering "best X", it produces a **per-brand outreach artifact** Empact can email a CMO, and only third does it earn clicks. See [00-concept.md](00-concept.md) and [11-outreach-play.md](11-outreach-play.md).

| Asset | Metric that matters | Metric that does not |
|---|---|---|
| Category page | Cited in ChatGPT / AI Mode / Perplexity answers | Sessions |
| Company page | Replies when pasted into a cold email | Ranking position |
| `/methodology/` | Cited as the provenance for a number | Traffic |

---

## 2. The Google policy that actually bites

The scaled-content-abuse policy targets "creating large amounts of unoriginal content that provides little to no value to users, no matter how it's created" ([spam policies](https://developers.google.com/search/docs/essentials/spam-policies)). Generation method is explicitly irrelevant.

Our real exposure is the **Scraping** clause in the same document: "Reproducing content feeds from other sites without providing some type of unique benefit to the user." That sentence is the whole risk model for this project.

**Site reputation abuse does not apply.** It governs third-party content on a *host* site trading on that host's ranking signals, and its not-a-violation list names "Sites designed to allow user-generated content, such as a forum website or comment sections" ([Google, Nov 2024](https://developers.google.com/search/blog/2024/11/site-reputation-abuse)). 🟡 INFERENCE: a standalone domain is out of scope.

### The unique-benefit test, answered

Reddit publishes none of the four things below. Each one is a computation that exists because we ran it, which is what makes redditindex.com a property rather than a mirror.

| What we add | Why it is a unique benefit |
|---|---|
| **The published Reddit Love Score** — the shrunk empirical-Bayes integer 0–100 value, `round(100 * p̃)`, where `p̃ = (x_pos + a0) / (N_op + a0 + b0)`, with a leave-one-out category prior over opinionated mentions only | No score of any kind exists on the source. The published 0–100 score is a computation that does not exist on Reddit ([decisions/0006](decisions/0006-single-reddit-love-score.md)) |
| **Cross-company comparison inside a category** | Reddit has no category leaderboard. Ranking every qualifying company in a category against one window, with ties shown as ties, is the product |
| **The published methodology** — sample, window, both denominators, entity-matching failure modes, tie rule | Provenance is the citation lever. It is why an engine can attribute a number to us instead of to a thread ([00-concept.md](00-concept.md)) |
| **The effective-sample correction** — `n_eff = n / DEFF`, category-scaled gate at `n_eff ≥ n_min` (600 Deep, 400 Standard, 200 Thin) from published ±4/±5/±7pp precision targets, plus four diversity floors: ≥50 authors, ≥5 subreddits, ≤20% from one thread, ≤5% from one author | Raw `n` (all eligible mentions) is visible to anyone who scrolls. `n_eff` exists only because we measured the clustering ([07-index-methodology.md](07-index-methodology.md)) |

**What forfeits it, in one line: a page whose value collapses to a list of somebody else's comments.** The published Reddit Love Score is the page; quoted mentions are evidence sitting beneath it. Any layout that inverts that order fails the Scraping clause on its own wording, without Google needing a new policy.

That order is load-bearing here because company pages render full mention text by owner decision, so the unique-benefit defense cannot rest on the mentions. Post-body and comment mentions are counted and displayed identically; each card labels its document type and links to the corresponding permalink. The reasoning and the risk register are in [01-legal.md](01-legal.md).

Two build requirements follow, and they are requirements, not preferences. Every mention card carries permalink, username, and "from Reddit". A nightly delete-sync purges removed or edited content and triggers the static rebuild, because a quote behind a dead link is a method-integrity failure before it is anything else ([08-architecture.md](08-architecture.md)).

Removal requests are honored free, on request, with no commercial step attached — and honored ahead of any index consideration. A page pulled for a removal request returns 410, not `noindex` on a live page.

---

## 3. Structured data, honestly

`AggregateRating` on Reddit-derived sentiment is a violation, not a gray area ([review snippet](https://developers.google.com/search/docs/appearance/structured-data/review-snippet)). Publish the single, shrunk **Reddit Love Score** as plain HTML plus `Dataset` schema; never use a rating type that implies a third-party company published it.

| Type | Use | Where |
|---|---|---|
| `BreadcrumbList` | 🟢 Yes | Every page |
| `ItemList` | 🟢 Yes | Category pages ([carousel docs](https://developers.google.com/search/docs/appearance/structured-data/carousel)) |
| `Dataset` | 🟢 Yes | Category, company, `/methodology`, `/data/*.csv` |
| `Organization`, `WebSite` | 🟢 Yes | Root |
| `FAQPage` | 🟡 Optional | Rich-result eligibility is now narrow |
| `AggregateRating`, `Review` | 🔴 Never | Explicit violation on third-party-derived sentiment |

Do not expect schema to move AI citations. Google's own AI-features doc (updated 2025-12-10) states "There's also no special schema.org structured data that you need to add" ([Google](https://developers.google.com/search/docs/appearance/ai-features)). Schema here buys breadcrumb display and machine-readable provenance. That is all it buys.

**`llms.txt`: skip it.** 97% of valid published files were never fetched by any agent ([Ahrefs](https://ahrefs.com/blog/llmstxt-study/)), and Google confirmed non-support in July 2025. Building one is time spent on a file nothing reads.

---

## 4. URL structure

One shared flat URL segment for categories and companies, plus data surfaces. All lowercase, hyphenated, and self-canonical. Every category and company page is one segment deep; nothing outside this table is indexable.

| Route | Example | What it is |
|---|---|---|
| `/` | `redditindex.com/` | Pooled top-100 Most Loved and top-100 Most Hated boards, plus category grid. Both lists use opposite ends of the published Reddit Love Score ordering, are disjoint, cap each category at five companies in each list, show each company's category, and disclose the cap and actual counts; if the qualifying population is under 200, each list takes at most `floor(N/2)`. |
| `/{category}/` | `/project-management/` | One category: Most Loved / Most Hated boards by default, with its consolidated list at `?view=list`, ordered descending by the published Reddit Love Score |
| `/{company}/` | `/notion/` | One company, global across all qualifying categories: per-category rank rows, mentions, correction path |
| `/methodology/` | `/methodology/` | One URL, everywhere. Badge destination, `Dataset` provenance target, footer link |
| `/changelog/` | `/changelog/` | Dated recompute history. The freshness evidence an engine can actually read |
| `/data/{name}.csv` | `/data/love-index-2026-09.csv` | Flat per-recompute export, one `Dataset` node each |

The pooled board answers which companies are most loved or hated across the measured site; a category page answers the different question of how qualifying companies compare within that category. The per-category cap and explicit on-page disclosure are the mitigation for that pooled comparison, not a substitute for the category page.

Slugs are ours and are written by hand. Category and company slugs are frozen once published: moving a company slug after it is indexed loses the ranking that made its page worth sending in outreach. Framework paths take precedence over site routes, then category slugs, then company slugs; the build fails on every duplicate. Never reuse a competitor's category slug, and never guess one: twelve plausible Capterra slugs 404'd during research ([03-taxonomy.md](03-taxonomy.md)).

**A company page is global, not category-nested.** `/{category}/{company}/` does not exist and must never be linked or emailed. A company appearing in three categories has one frozen, stable URL carrying three rank rows ([11-outreach-play.md](11-outreach-play.md)).

### Breadcrumbs

| Page | Visible crumb | `BreadcrumbList` items |
|---|---|---|
| Category | `Home › {Category}` | `/` → `/{category}/` |
| Company | `Home › {Primary category} › {Company}` | `/` → `/{primary-category}/` → `/{company}/` |
| Methodology | `Home › Methodology` | `/` → `/methodology/` |
| Changelog | `Home › Methodology › Changelog` | `/` → `/methodology/` → `/changelog/` |

The company crumb's middle item is that company's **primary category**, defined as the one with the highest `n_eff`, resolved at recompute and stored with the page so a near tie cannot flip the crumb month to month.

The crumb is a path through the site, not a path in the URL. Its middle item links to `/{primary-category}/`; the company's own URL stays flat. Visible breadcrumb and markup must agree item for item, or the markup is invalid.

---

## 5. Indexation architecture at 5,000 pages

We do not have a crawl-budget problem. Google's threshold is "1 million+ unique pages" changing weekly or "10,000+ unique pages" changing daily ([docs](https://developers.google.com/search/docs/crawling-indexing/large-site-managing-crawl-budget)). At 5K pages the problem is value per page.

| Concern | Rule |
|---|---|
| Internal linking | Hub-and-spoke: the 20 measured category hubs → company spokes; every company links up to its category and laterally to 5-10 peers |
| Breadcrumbs | Visible breadcrumb plus `BreadcrumbList` on every page, no exceptions — routes and crumb mapping in section 4 |
| Sitemaps | Index at root, one child sitemap per measured category, plus a company sitemap; all listed category and company URLs are one segment deep, so Search Console coverage is diagnosable per segment |
| `<lastmod>` | Rewritten on every daily recompute, accurate or omitted |
| Canonical | Self-canonical everywhere. No cross-canonical between category and company; `?view=list`, filter, and cursor variants canonicalize to the bare URL |
| Pagination | No `rel=prev/next` (Google dropped support). Plain links, self-canonical each page |
| Parameter variants | `?view=list`, filter, and cursor variants stay crawlable and send `noindex,follow` plus a canonical to the bare URL. Do not `Disallow` them: Google must crawl a URL to see its `noindex`. Reserve `Disallow` for genuinely infinite or private spaces, such as `/api/`, which were never meant to be indexed. |
| Launch cadence | v1 ships the 20 measured categories in [14-category-tests.md](14-category-tests.md), not the 50-row Phase 1 taxonomy; no unmeasured category is presented as ranked. Categories ship in waves, not 5,000 pages on one day |

### The indexation gate

There is no published Google word count for a thin page. 🟡 INFERENCE: the operative test is whether the page contains something unobtainable from the source. The gate below is our version of that test.

**A company page is indexable only if it carries ≥1 category membership and ≥3 of:** the published Reddit Love Score (computed, not a star rating), total mention count, subreddit distribution, first and last mention date, trend versus prior recompute, competitor co-mention rate.

**Thin for indexation → `<meta name="robots" content="noindex,follow">`.** The page still exists, still links out, still serves outreach, and stays out of the index. This is separate from measurement eligibility: a company that passes its company-level tests is not “Below threshold” when its category cannot be ranked because that category fails the five-subreddit viability test. Thin company pages are the largest index-bloat risk here, and the gate is enforced in code at render time, not editorially.

⚠️ Never pad a thin page with generated prose to clear the gate. Padding is the tell. A 120-word page of real numbers is safer than a 900-word page of filler ([spam policies](https://developers.google.com/search/docs/essentials/spam-policies)).

---

## 6. The "[category] reddit" query class

This is the target query class because Google keeps rewarding it. Reddit's share of Google top-3 positions rose to **10.24%** after the May 2026 core update, up from 8.56% post-March, gaining across all 20 tracked niches ([SE Ranking](https://seranking.com/blog/google-may-2026-core-update-analysis/)).

Demand is growing on Reddit's side too: weekly search users grew roughly 30% year over year, 60M → 80M ([eMarketer](https://www.emarketer.com/content/reddit-weekly-search-activity-jumps-30-yoy-boosting-ad-intent-user-reach)).

**NOT VERIFIED:** no primary keyword-level dataset for "[category] reddit" volume was obtained, and the repeated "32% of US Gen Z appends reddit weekly" figure is survey-derived secondary. Pull real volumes from Ahrefs before any post-v1 category expansion; v1 is the 20 measured categories in [14-category-tests.md](14-category-tests.md).

Title and H1 pattern: `Best [Category] According to Reddit ([Month Year])`, with a real month that changes on recompute.

---

## 7. AEO and GEO: what gets a data property cited

Four levers, in descending order of evidence strength.

| Lever | Evidence | Implementation |
|---|---|---|
| **Freshness** | Median days since publication of cited URLs: ChatGPT 958, Copilot 1,056, Gemini 1,118, Perplexity 1,166, versus Google organic 1,416 ([Ahrefs, 16.975M URLs](https://ahrefs.com/blog/do-ai-assistants-prefer-to-cite-fresh-content/)) | Daily recompute, visible "Data as of" line, accurate `dateModified`, public `/changelog/` |
| **Stated methodology** | 🟡 INFERENCE from source-provenance behavior | `/methodology/`: sample size, date range, collection method, scoring formula, limitations, changelog. Linked from every page |
| **Front-loaded answer** | 🟡 SECONDARY: 44.2% of LLM citations come from the first 30% of page content; listicles 21.9%, articles 16.7%, product pages 13.7% ([Ahrefs data summary](https://www.quattr.com/blog/takeaway-from-ahrefs-ai-search-study)) | Ranked table above the fold. One extractable verdict per company. No preamble |
| **Source type** | Semrush, 230K prompts / 13 weeks: UGC dominates but is volatile — Reddit's ChatGPT citation share fell ~60% → ~10% after a Sept 11 parameter change ([Semrush](https://www.semrush.com/blog/most-cited-domains-ai/)) | Do not build on being *inside* Reddit's citation share. Be the structured summary *of* it |

Authority still gates entry: sites with 32,000+ referring domains were 3.5× likelier to be cited by ChatGPT than sites with ≤200 (🟡 SECONDARY, [Leapd](https://www.leapd.ai/blog/ai-visibility/how-chatgpt-google-ai-overviews-and-perplexity-source-information-in-2026)). 🟡 INFERENCE: a new domain gets cited by being the only source of a specific number, not on authority.

Category-page order: H1 with month → one-sentence verdict → default Most Loved / Most Hated boards → shadcn/ui Tabs switcher to the consolidated list at `?view=list` → "total mentions analyzed, data as of [date]" → per-company rows with links → category-specific interpretation → methodology link. Rows lead with the published Reddit Love Score and total mention count; `n`, `n_eff`, authors, subreddits, threads, concentration shares, interval, and window are evidence in a disclosure. The variant is `noindex,follow` and canonical to the bare category URL.

---

## 8. AI crawler access policy

Blocking a retrieval agent forfeits citation eligibility, which is the entire business case.

| Agent | Policy | Reason |
|---|---|---|
| `Googlebot`, `Bingbot` | 🟢 Allow | Baseline |
| `Google-Extended` | 🟢 Allow | Governs Gemini grounding; blocking it is a self-inflicted wound |
| `OAI-SearchBot`, `ChatGPT-User`, `PerplexityBot`, `Claude-SearchBot`, `Claude-User` | 🟢 Allow | Retrieval and answer agents |
| `GPTBot`, `CCBot`, `anthropic-ai` | 🟡 Block | Training-only; standard 2026 posture, costs nothing in citations ([Anagram](https://www.anagram.ai/blog/ai-crawlers-explained-gptbot-claudebot-perplexitybot-and-how-to-let-them-in-2026)) |
| `?view=list`, filter, cursor params | 🟢 Crawlable; `noindex,follow` and canonical to the bare URL | Prevent duplicate indexation while letting crawlers receive the directive |
| `/api/` and genuinely infinite or private spaces | 🔴 Disallow | Never intended for indexation |

Allowing an agent means serving it the page a person gets. No cloaking, no agent-specific rendering, no interstitial, and no ads anywhere on the site — an ad layer would be the first thing a citing engine renders around our own numbers.

Reddit trade dress stays off every surface: no Reddit logo, no Snoo, no orange, no `r/` styling on our own chrome. Subreddit names appear as plain text inside attribution rows.

---

## 9. Deindexation risks, ranked by likelihood

| # | Risk | Likelihood | Mechanism |
|---|---|---|---|
| 1 | Reproduced mention text becomes the page | 🔴 High | Scraping clause, verbatim. Mitigate by making the published Reddit Love Score the page and the quotes the evidence |
| 2 | Thin company pages shipped past the gate | 🔴 High | Scaled content abuse |
| 3 | Parameter variants allowed into the index, or blocked before their `noindex` can be read | 🟡 Medium | Duplicate pages accumulate or the directive is stranded |
| 4 | `AggregateRating` on the published Reddit Love Score | 🟡 Medium | Structured-data violation → manual action, rich results removed |
| 5 | Generated prose padding thin pages | 🟡 Medium | Padding is the detection signal, not the fix |
| 6 | Static, never-recomputed data | 🟡 Medium | Decays out of AI answers; reads as abandoned |
| 7 | No stated methodology | 🟡 Medium | Uncitable by engines that need provenance, and the largest unique-benefit claim disappears with it |
| 8 | Category-nested company URLs shipped by mistake | 🟡 Medium | Two URLs for one company, split signals, breadcrumb markup that contradicts the visible crumb |
| 9 | Subdomain rented to a third party | 🟢 Low | Site reputation abuse; relocating it "may be viewed as an attempt to circumvent spam policy" |
| 10 | Forecast built on G2-era traffic assumptions | 🟢 Low (planning) | Directory organic traffic fell 76-92% across the category 2024 → 2025 |

Claims that a "March 2026 core update explicitly named scaled content abuse" circulate on SEO blogs. **NOT VERIFIED** against any Google primary source. Do not plan against it.

---

[← Back to README](README.md) · [00-concept.md](00-concept.md) · [03-taxonomy.md](03-taxonomy.md) · [07-index-methodology.md](07-index-methodology.md) · [11-outreach-play.md](11-outreach-play.md)
