# Reddit Index

### 🔗 redditindex.com

**The most loved and most hated software brands in every category, according to Reddit.**

Pick a category. See the two columns. Click a brand and read the actual comments people wrote about it, linked back to the thread they came from.

Built and operated by **Empact Partners**. Next.js on Vercel, Supabase for data.

**Last verified: 2026-08-04** · 12 research lanes, primary sources, live measurement

> ⚠️ **Nothing is built yet.** This repo is the specification: how it works, how it is scored, and what it costs.

---

## ⚡ Bottom line

**Nobody owns this.** No live property ranks software brands by Reddit sentiment as a public leaderboard. GummySearch, the Reddit-native category leader, shut down 2025-11-30. The adjacent per-brand-audit seat is taken — [redditbrands.com](https://redditbrands.com/) and [whatredditthinks.com](https://whatredditthinks.com/) are both live — but the cross-brand board is open.

**It is buildable, and it is cheap.** The corpus for ~1,000 subreddits is 200-400M items, roughly 0.5-1.5 TB. One machine. **About $74/month** at Phase 1 scale, updating **daily**. See [08-architecture.md](08-architecture.md).

**The one number that reshapes the build: Reddit's API reaches roughly 3 to 8 days of history**, not years. So the API is a maintenance tool, and history comes from archive dumps. Everything downstream follows from that.

**What is unproven is trust, not feasibility.** Whether the ranking matches what a knowledgeable person would say about a category is exactly what [Phase 0](12-phasing.md) tests, on one category, before anything ships.

Two risks are priced and accepted rather than avoided — the Reddit-containing name and displaying full comment text. Both are recorded with their clause citations in [01-legal.md](01-legal.md) and [decisions/](decisions/). If a UDRP ever lands it costs the domain, not the pipeline or the index.

---

## In 30 seconds

1. **The API cannot backfill.** Every Reddit listing hard-caps at ~1,000 items. Measured live: `/r/SaaS/new` exhausted at 995 items, then `after=None`. Against r/SaaS's measured posting rate that is 3 to 8 days. History has to come from archive dumps.
2. **Reddit search indexes posts, not comment bodies.** Brand opinion lives in comments, so per-brand search is a discovery tool, never a census. You must ingest whole subreddits and match locally.
3. **Signal does not track subscriber count.** r/PasswordManagers (54,639) beats r/marketing (1,958,653), because r/marketing's rules delete exactly that content — ~2 surviving posts a day against r/SaaS's 122-350.
4. **31% of software brands share a name with a common English word.** Notion, Slack, Monday, Linear, Stripe, Craft, Front, Ramp, Make, Segment, Loom. This is the hardest engineering problem in the project.
5. **The corpus is smaller than intuition.** ~1,000 subreddits is 200-400M items: 0.5-1.5 TB as raw JSON, **50-150 GB** once stored as zstd-compressed Parquet. One machine, about $74/month.

---

## The numbers

| Fact | Value | Confidence |
|---|---|---|
| Reddit listing cap | **~1,000 items** (995 measured) | 🟢 Measured live |
| History reachable via API | **~3 to 8 days** for r/SaaS | 🟢 Two live methods |
| Corpus, ~1,000 subreddits | 200-400M items · **50-150 GB** compressed (0.5-1.5 TB raw JSON) | 🟡 Extrapolated |
| Infrastructure, Phase 1 | **~$74/month** (~$301/month at full scale) | 🟡 Vendor list prices |
| Sentiment cascade | ~$31-53 per 1M comments with a Haiku stage 2 · ~$3-6 with a nano-class stage 2 | 🟡 Calculated |
| Minimum mentions to rank | **n_eff ≥ 400**, after the design-effect correction | 🟢 Derived |
| High-ambiguity brand names | **35 of 113 (31%)** | 🟢 Classified |
| Capterra categories | 1,000 rendered, truncated mid-W | 🟢 Scraped |
| G2 categories | 2,237 enumerable | 🟢 Scraped |
| Subreddits hostile to brand talk | **48 of 131 (37%)** | 🟢 Read from their own rules |
| Single-product communities (unscoreable) | **48 of 132 (36%)** | 🟢 Classified |
| Categories reaching the 5-subreddit floor | **6 of 20** | 🟢 Measured live |
| Candidate slots → unique subreddits | **187 → 132** (~29% ingest saving) | 🟢 Measured |
| Live adjacent competitors | **2**, both per-brand audits | 🟢 Fetched live |

**On reachable history.** r/SaaS was measured twice on 2026-08-04 by two methods: **122 posts/day** from the span of the last 100 posts in `/new`, and **~350/day** extrapolated from the 10 newest. The second runs high because the newest posts have not yet cleared moderation removal. Quote the range, never "8 days" as a fact ([02-data-acquisition.md](02-data-acquisition.md)).

**On the eligibility gate.** The naive derivation `n = z²p(1−p)/h² = 384 → 400` assumes independent draws. Reddit mentions cluster inside a handful of mega-threads and within threads by author, so that assumption fails and the raw count overstates the information you have.

The gate is therefore `n_eff = n / DEFF ≥ 400`, where `DEFF = 1 + (m̄ − 1)·ICC`. Both `n` and `n_eff` are published on every brand page, intervals come from a cluster bootstrap, and four diversity floors — authors, subreddits, threads, and max share from any one thread — apply on top ([07-index-methodology.md](07-index-methodology.md)).

---

## Common beliefs, checked

| Belief | Verdict |
|---|---|
| "We'll pull the history from the Reddit API" | ❌ **Wrong.** ~1,000 items per listing, 3 to 8 days. The API is a maintenance tool, not an acquisition tool. See [02-data-acquisition.md](02-data-acquisition.md). |
| "Search Reddit for each brand name" | ❌ **Wrong.** Search does not index comment bodies, and results cap out. Ingest subreddits, match locally. |
| "Big subreddits have the most brand talk" | ❌ **Wrong.** The biggest ones ban it. Map to rule-permissive subs. See [04-subreddit-mapping.md](04-subreddit-mapping.md). |
| "Free and ad-free keeps us outside the commercial rules" | ❌ **Wrong.** Reddit lists "free product features available for upsell" as commercial use. |
| "Aggregate scores only would be legally safer" | 🟡 **Half right.** Safer on copyright, not on contract. Reddit has not won that case — but its contract theory survived a preemption challenge and was remanded to state court on 2026-03-30. See [01-legal.md](01-legal.md). |
| "A low-profile site won't attract Reddit's attention" | ❌ **Wrong.** A [UDRP](https://www.wipo.int/amc/en/domains/decisions/text/2020/d2020-1834.html) is a registrar-level administrative proceeding. It needs no damages, no discovery, and no proof anyone visited. Reddit files them *pro se* for roughly $1,500 and has won every one found. See [decisions/0001](decisions/0001-name-reddit-index.md). |
| "Use Capterra's categories" | 🟡 **Half right.** Their ToS §10 names "category structure" as protected. Derive the spine instead. See [decisions/0003](decisions/0003-g2-taxonomy-spine.md). |
| "One sentiment score, sorted both ways" | ❌ **Wrong.** Love and hate are separable. A net score makes a polarizing brand look identical to an ignored one. |
| "Upvoted comments should count more" | ❌ **Wrong.** Reddit fuzzes vote counts, and one seeded upvote inflated scores 25% via herding. |
| "This space is crowded" | 🟡 **Half right.** Monitoring is crowded and private. The per-brand audit lane now has live entrants. No public cross-brand Reddit-derived software leaderboard exists. |
| "Nobody else is building anything like this" | ❌ **Wrong.** [redditbrands.com](https://redditbrands.com/) (registered 2026-06-07) grades one brand at a time A-to-F with a four-engine AI probe and PDF export. [whatredditthinks.com](https://whatredditthinks.com/) (2026-05-25) publishes per-question consensus pages. Both live 2026-08-04. See [00-concept.md](00-concept.md). |
| "We just need enough Reddit discussion" | 🟡 **Half right.** Volume is not the binding constraint — subreddit COUNT is. Only 6 of 20 categories reach the 5-scorable-subreddit floor, because hostile and single-product communities eat the candidate lists. See [14-category-tests.md](14-category-tests.md). |
| "A product's own subreddit is the best source" | ❌ **Wrong.** It is the densest and the least usable. r/Bitwarden measured 37% brand-bearing, r/paypal 50% — and every one is disqualified, because a product's subreddit is people who already chose it. |
| "The one Reddit-native player is gone, so the field is clear" | 🟡 **Half right.** GummySearch did shut down on 2025-11-30 ([gummysearch.com](https://gummysearch.com/)), but two adjacent properties launched inside the following seven months. The seat is open, not open indefinitely. |

---

## Decisions already taken

| # | Decision | Record |
|---|---|---|
| 1 | Product is **Reddit Index** on `redditindex.com`. "Reddit" kept in the name deliberately, breaching [Data API Terms §4.1](https://www.redditinc.com/policies/data-api-terms) and [Developer Terms §5.3](https://www.redditinc.com/policies/developer-terms). The realistic enforcement is a UDRP filing, not a lawsuit, and losing one costs the domain rather than the project. | [0001](decisions/0001-name-reddit-index.md) |
| 2 | Brand pages **display full comment text** with links back. Knowingly non-compliant, priced as a risk. | [0002](decisions/0002-display-full-mentions.md) |
| 3 | **Derive the category spine**, do not copy Capterra's. | [0003](decisions/0003-g2-taxonomy-spine.md) |
| 4 | **Two axes**, love and hate scored independently. | [0004](decisions/0004-two-axis-index.md) |
| 5 | Columns stay labelled **"Most Loved" and "Most Hated."** Owner-specified superlatives, priced as exposure, with the measured variable shown beside them. | [0005](decisions/0005-superlative-labels.md) |

⚠️ **Decisions 1 and 2 are priced risks, not solved problems.** The name breaches Reddit's trademark clauses and the brand pages display full comment text. Both were taken with the exposure in front of the owner, and neither is mitigated by anything built later.

The name is also **Reddit-locked**: Phase 3 in [12-phasing.md](12-phasing.md) contemplates Hacker News and other sources, which "Reddit Index" cannot carry without a rename. `redditbrandindex.com` is the defensive registration. `brandsonreddit.com` was available, carries a materially better UDRP posture, and is the documented migration target ([0001](decisions/0001-name-reddit-index.md)).

Empact Partners operates it openly. The footer reads "Created by Empact Partners," beside the non-affiliation notice that decision 1 makes mandatory on every page. It is a side project, not an independent publication, and does not pretend to be one.

---

## Navigate

| Doc | What's in it |
|---|---|
| **[00-concept.md](00-concept.md)** | The product, page by page, and the live competitive field. Start here. |
| **[13-algorithm.md](13-algorithm.md)** | **How it actually works.** Subreddit selection, the comment-stream discovery lane, mention detection, the weekly loop. |
| [01-legal.md](01-legal.md) | The clause-level risk register and the two priced decisions |
| [02-data-acquisition.md](02-data-acquisition.md) | The 1,000-item cap, archive backfill, volumes, cost |
| [03-taxonomy.md](03-taxonomy.md) | G2 vs Capterra, and why we derive our own spine |
| [04-subreddit-mapping.md](04-subreddit-mapping.md) | Category → subreddit, and the rules that kill brand signal |
| [05-entity-resolution.md](05-entity-resolution.md) | The "is this *monday* the vendor" problem |
| [06-sentiment.md](06-sentiment.md) | Targeted ABSA, the cascade, validation protocol |
| **[07-index-methodology.md](07-index-methodology.md)** | The formulas. What a hostile CMO attacks first. |
| [08-architecture.md](08-architecture.md) | Next.js on Vercel, Supabase, schema, daily refresh, cost table |
| **[14-category-tests.md](14-category-tests.md)** | **20 categories measured live.** 132 subreddits, what the data says and what it cannot say |
| [09-design.md](09-design.md) | Empact brand applied — Syne, Public Sans, the palette |
| [10-seo-aeo.md](10-seo-aeo.md) | Indexation, schema, AI citation, what gets it killed |
| [11-outreach-play.md](11-outreach-play.md) | The GTM motion and the email angles, ranked |
| [12-phasing.md](12-phasing.md) | Phase 0 → 3, with kill criteria |
| **[HANDOFF.md](HANDOFF.md)** | Open items. 6 known defects, listed not hidden. Read before editing. |
| [method.md](method.md) | How this research was done, how to re-run it |
| [sources.md](sources.md) | Every primary source, dated |

---

## The data

All CSV, one click each. Click the file, then **Download raw file**.

| File | Rows | What's in it |
|---|---:|---|
| **[phase1-categories.csv](data/phase1-categories.csv)** | 50 | **The Phase 1 spine.** Start here. |
| **[subreddit-map.csv](data/subreddit-map.csv)** | 131 | Category → subreddit, with rule posture |
| [brand-gazetteer-seed.csv](data/brand-gazetteer-seed.csv) | 113 | Seed brands with ambiguity classification |
| [domain-availability.csv](data/domain-availability.csv) | 87 | The sweep behind the name, plus the live competitors |

Column reference and regeneration: **[data/README.md](data/README.md)**

---

## How this was verified

| Pass | Method | Result |
|---|---|---|
| 1 | 12 parallel research lanes against primary sources | Reddit's own terms, court records, published benchmarks |
| 2 | Live measurement | API caps, subscriber counts, corpus volumes, registry lookups |
| 3 | 3 adversarial critics instructed to kill the project | Surviving objections written into the docs, not dropped |
| 4 | 3-lens review of the written docs | Fabrication, self-flattery, mechanical consistency |

---

## What the evidence does NOT support

- **"Free and ad-free makes this defensible."** It does not. The commercial-use definition reaches upsell features and derived data.
- **"Aggregate-only would solve the legal problem."** It solves copyright, not contract.
- **"The rankings measure sentiment."** They partly measure **adoption model**. Forced enterprise users complain; voluntary self-serve users praise. The "most hated" column will reliably surface category incumbents, and no post-hoc statistical fix exists — the confound is in the exposure population. This must be disclosed on the site's `/methodology` page.
- **"Naming the most hated brands drives outreach."** Guilt-framed cold email raises reply rate but **cuts meetings booked 14%**. Every verified precedent monetizes winners or third-party buyers.
- **"Badges build backlinks."** Google requires badge links to be nofollow or sponsored, and a third-party rating widget makes the page ineligible for star rich results.

---

## Limits

**38 of the 50 Phase 1 categories have no subreddit mapping.** Twelve were mapped and signal-tested. The rest is real work.

**No gold set exists and no pipeline has been run.** Every accuracy figure — precision ≥0.97, recall 0.80-0.88, the sentiment cascade cost — is a target derived from published benchmarks, not a measurement of our own system.

**The planned audit cannot prove the precision target tightly.** At p̂ = 0.97 on 400 items the Wilson 95% interval is roughly ±1.7pp, which cannot separate 0.97 from 0.95. Either the audit n rises or the published claim softens to what the sample supports ([06-sentiment.md](06-sentiment.md)).

**Reddit's commercial pricing is unknown.** No public rate card exists. The often-quoted $0.24 per 1,000 calls is the June 2023 announced developer rate, not a verified 2026 enterprise price.

**G2's terms of use were not read**, only assumed similar to Capterra's post-acquisition. Marked NOT VERIFIED throughout.

**This repo is not legal advice.** It was written from primary sources by non-lawyers. Get an Estonian data-protection opinion and a US media-law read on the final page copy before launch.

---

Start here: [00-concept.md](00-concept.md) · Read before coding: [01-legal.md](01-legal.md) · The gate that decides it: [12-phasing.md](12-phasing.md) · The formulas: [07-index-methodology.md](07-index-methodology.md) · Every source: [sources.md](sources.md)

*Created by Empact Partners. Not affiliated with, endorsed by, or sponsored by Reddit, Inc. "Reddit" and subreddit names are trademarks of their respective owners and are used here descriptively.*
