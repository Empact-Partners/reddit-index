# UGC Ranks

A public site ranking the **most loved and most hated software brands** in every category, computed from what people actually say on Reddit. Built and operated by Empact Partners as a cold-outreach asset.

**Last verified: 2026-08-04** · 12 research lanes, primary sources, live measurement

> ⚠️ **Nothing is built.** This repo is the specification. No site, no pipeline, no data. Read [01-legal.md](01-legal.md) before writing a line of code.

---

## ⚡ Bottom line

The concept is **viable and the space is open** — no live property ranks software brands by Reddit sentiment as a public leaderboard, and the one Reddit-native competitor shut down in November 2025.

It is also **not compliant with Reddit's terms**, and the owner has chosen to proceed anyway with the exposure understood. The asset genuinely at risk is not this website — it is Empact's live Reddit operation across roughly 28 partner projects.

The single number that reframes the build: **Reddit's API reaches about 8 days of history.** Everything else follows from that.

---

## In 30 seconds

1. **The API cannot backfill.** Every Reddit listing hard-caps at ~1,000 items. Measured live: `/r/SaaS/new` exhausted at 995 items, then `after=None`. History has to come from archive dumps.
2. **Reddit search indexes posts, not comment bodies.** Brand opinion lives in comments, so per-brand search is a discovery tool, never a census. You must ingest whole subreddits and match locally.
3. **Signal does not track subscriber count.** r/PasswordManagers (54,639) beats r/marketing (1,958,653), because r/marketing's rules delete exactly that content — 2 surviving posts a day against r/SaaS's 350.
4. **31% of software brands share a name with a common English word.** Notion, Slack, Monday, Linear, Stripe, Craft, Front, Ramp, Make, Segment, Loom. This is the hardest engineering problem in the project.
5. **The corpus is smaller than intuition.** ~1,000 subreddits is 200-400M items, roughly 0.5-1.5 TB. One machine, about $85/month. The build is tractable.

---

## The numbers

| Fact | Value | Confidence |
|---|---|---|
| Reddit listing cap | **~1,000 items** (995 measured) | 🟢 Measured live |
| History reachable via API | **~8 days** for r/SaaS | 🟢 Measured live |
| Corpus, ~1,000 subreddits | 200-400M items · 0.5-1.5 TB | 🟡 Extrapolated |
| Infrastructure, Phase 1 | **~$85/month** | 🟡 Vendor list prices |
| Sentiment classification | ~$45-85 per 1M comments | 🟡 Calculated |
| Minimum mentions to rank | **400** (from n = z²p(1−p)/h²) | 🟢 Derived |
| High-ambiguity brand names | **35 of 113 (31%)** | 🟢 Classified |
| Capterra categories | 1,000 rendered, truncated mid-W | 🟢 Scraped |
| G2 categories | 2,237 enumerable | 🟢 Scraped |
| Categories that cannot be ranked | **ERP, Help Desk** | 🟢 Signal-tested |

---

## Common beliefs, checked

| Belief | Verdict |
|---|---|
| "We'll pull the history from the Reddit API" | ❌ **Wrong.** ~1,000 items per listing, about 8 days. The API is a maintenance tool, not an acquisition tool. See [02-data-acquisition.md](02-data-acquisition.md). |
| "Search Reddit for each brand name" | ❌ **Wrong.** Search does not index comment bodies, and results cap out. Ingest subreddits, match locally. |
| "Big subreddits have the most brand talk" | ❌ **Wrong.** The biggest ones ban it. Map to rule-permissive subs. See [04-subreddit-mapping.md](04-subreddit-mapping.md). |
| "Free and ad-free keeps us outside the commercial rules" | ❌ **Wrong.** Reddit lists "free product features available for upsell" as commercial use. |
| "Aggregate scores only would be legally safer" | 🟡 **Half right.** Safer on copyright, not on contract — and contract is the theory Reddit wins on. |
| "Use Capterra's categories" | 🟡 **Half right.** Their ToS §10 names "category structure" as protected. Derive the spine instead. See [decisions/0003](decisions/0003-g2-taxonomy-spine.md). |
| "One sentiment score, sorted both ways" | ❌ **Wrong.** Love and hate are separable. A net score makes a polarizing brand look identical to an ignored one. |
| "Upvoted comments should count more" | ❌ **Wrong.** Reddit fuzzes vote counts, and one seeded upvote inflated scores 25% via herding. |
| "This space is crowded" | ✅ **Correct that tools exist, wrong that the gap is filled.** Monitoring is crowded and private. No public Reddit-derived software leaderboard exists. |

---

## Decisions already taken

| # | Decision | Record |
|---|---|---|
| 1 | Product is **UGC Ranks** on `ugcranks.com`. "Reddit" removed from the name — Data API Terms §4.1 forbids it, and Reddit wins UDRP cases. | [0001](decisions/0001-name-ugc-ranks.md) |
| 2 | Brand pages **display full comment text** with links back. Knowingly non-compliant, priced as a risk. | [0002](decisions/0002-display-full-mentions.md) |
| 3 | **Derive the category spine**, do not copy Capterra's. | [0003](decisions/0003-g2-taxonomy-spine.md) |
| 4 | **Two axes**, love and hate scored independently. | [0004](decisions/0004-two-axis-index.md) |

Empact Partners operates it openly. The footer reads "Created by Empact Partners." It is a side project, not an independent publication, and does not pretend to be one.

---

## Navigate

| Doc | What's in it |
|---|---|
| **[00-concept.md](00-concept.md)** | The product, page by page. Start here. |
| **[01-legal.md](01-legal.md)** | ⚠️ Clause-level risk register. The most important file in the repo. |
| [02-data-acquisition.md](02-data-acquisition.md) | The 1,000-item cap, archive backfill, volumes, cost |
| [03-taxonomy.md](03-taxonomy.md) | G2 vs Capterra, and why we derive our own spine |
| [04-subreddit-mapping.md](04-subreddit-mapping.md) | Category → subreddit, and the rules that kill brand signal |
| [05-entity-resolution.md](05-entity-resolution.md) | The "is this *monday* the vendor" problem |
| [06-sentiment.md](06-sentiment.md) | Targeted ABSA, the cascade, validation protocol |
| **[07-index-methodology.md](07-index-methodology.md)** | The formulas. What a hostile CMO attacks first. |
| [08-architecture.md](08-architecture.md) | Stack, schema, refresh, cost table |
| [09-design.md](09-design.md) | Empact brand applied — Syne, Public Sans, the palette |
| [10-seo-aeo.md](10-seo-aeo.md) | Indexation, schema, AI citation, what gets it killed |
| [11-outreach-play.md](11-outreach-play.md) | The GTM motion and the email angles, ranked |
| [12-phasing.md](12-phasing.md) | Phase 0 → 3, with kill criteria |
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
| [domain-availability.csv](data/domain-availability.csv) | 87 | The sweep behind the name |

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
- **"The rankings measure sentiment."** They partly measure **adoption model**. Forced enterprise users complain; voluntary self-serve users praise. The "most hated" column will reliably surface category incumbents, and no post-hoc statistical fix exists — the confound is in the exposure population. This must be disclosed on the site.
- **"Naming the most hated brands drives outreach."** Guilt-framed cold email raises reply rate but **cuts meetings booked 14%**. Every verified precedent monetizes winners or third-party buyers.
- **"Badges build backlinks."** Google requires badge links to be nofollow or sponsored, and a third-party rating widget makes the page ineligible for star rich results.

---

## Limits

**38 of the 50 Phase 1 categories have no subreddit mapping.** Twelve were mapped and signal-tested. The rest is real work.

**No gold set exists and no pipeline has been run.** Every accuracy figure — precision ≥0.97, recall 0.80-0.88, the sentiment cascade cost — is a target derived from published benchmarks, not a measurement of our own system.

**Reddit's commercial pricing is unknown.** No public rate card exists. The often-quoted $0.24 per 1,000 calls is the June 2023 announced developer rate, not a verified 2026 enterprise price.

**G2's terms of use were not read**, only assumed similar to Capterra's post-acquisition. Marked NOT VERIFIED throughout.

**This repo is not legal advice.** It was written from primary sources by non-lawyers. Get an Estonian data-protection opinion and a US media-law read on the final page copy before launch.

---

*Created by Empact Partners. Not affiliated with, endorsed by, or sponsored by Reddit, Inc. "Reddit" and subreddit names are trademarks of their respective owners and are used here descriptively.*
