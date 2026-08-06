# Reddit Index

### 🔗 redditindex.com

**The most loved and most hated software brands in every category, according to Reddit.**

Pick a category. See the two columns. Click a brand and read the actual comments people wrote about it, linked back to the thread they came from.

Built and operated by **Empact Partners**. Next.js on Vercel, Supabase for data.

**Last verified: 2026-08-05** · 12 research lanes, primary sources, live measurement

> **It is built, and it is live at [redditindex.com](https://redditindex.com) — behind `noindex`.**
> The site, the schema, the pipeline and eight blocking build gates all exist. What is
> published so far is a SAMPLE, not a census, and no company clears its category's
> eligibility gate on it: every one renders "below threshold" with the test it missed and
> both numbers. That is the correct outcome, not a missing feature.
>
> Start at [HANDOFF.md](HANDOFF.md) — it records the nine defects building against these
> documents exposed, and what changed in them as a result.

## How to run it

```bash
pnpm install && pnpm build          # 8 gates run pre- and post-build; any one fails the build
pnpm test                           # component + footer-slot-4 contracts
node scripts/gates/__selftest__.mjs # proves each gate fails when violated
node --test tests/resolve.test.mjs  # the documented false matches, pinned

python3 data/discover.py            # category -> subreddit mapping, all 20, resumable
python3 data/refine.py              # yield re-measure + topicality, so junk subs cannot score
python3 worker/freeze_methodology.py  # before any ingest. 07 section 9
python3 worker/harvest.py --all --depth thin --deep-category crm
python3 worker/pipeline.py --max-mentions 200   # resolve -> classify -> score
python3 worker/load.py --seed --mentions --scores
python3 worker/verify.py            # the gate evidence, as checkable artefacts
python3 worker/delete_sync.py       # purge what its author deleted, then revalidate
```

No metered API is touched anywhere. Classification runs through `claude -p` on a Claude
Max subscription, locally.

---

## Bottom line

**Nobody owns this.** No live property ranks software brands by Reddit sentiment as a public leaderboard. GummySearch, the Reddit-native category leader, shut down 2025-11-30. The adjacent per-brand-audit seat is taken — [redditbrands.com](https://redditbrands.com/) and [whatredditthinks.com](https://whatredditthinks.com/) are both live — but the cross-brand board is open.

**It is buildable, and it is cheap.** The corpus for ~1,000 subreddits is 200-400M items, roughly 0.5-1.5 TB. One machine. **About $74/month** at Phase 1 scale, updating **daily**. See [08-architecture.md](08-architecture.md).

**The one number that reshapes the build: Reddit's API reaches roughly 3 to 8 days of history**, not years. So the API is a maintenance tool, and history comes from archive dumps. Everything downstream follows from that.

**Only generalist subreddits score a brand.** Any subreddit named for a vendor or a product is out, r/salesforce and r/shopify included. That is **50 of the 232** subreddits measured, carrying **50%** of the brand-bearing volume, given up so that two brands in a category are ranked on the same ground. Another 56 are hostile to vendor talk by rule. **125 are scorable**, and widening the candidate lists by discovery rather than by hand took the categories clearing the five-subreddit floor from 12 of 20 to **20 of 20**. ⚠️ **That figure does not reproduce from what shipped.** `category-candidates-20.json` is the pre-widening list — 254 slots over 156 subreddits against the 347/232 quoted — and 76 measured subreddits have no category attribution at all, which puts the reproducible figure at **13 of 20**. The mapping was re-derived from Reddit into [data/category-subreddits.csv](data/category-subreddits.csv); once a topicality term is applied so that a jiu-jitsu subreddit cannot be a payments community, **16 of 20** field five scoring subreddits. The other four render the insufficient-signal panel. See [HANDOFF.md](HANDOFF.md) item 1.

**What is unproven is trust, not feasibility.** Whether the ranking matches what a knowledgeable person would say is exactly what [Phase 0](12-phasing.md) tests, on **CRM**: 17 scorable generalist subreddits out of 26 candidates, the widest margin of any category measured.

Two risks are priced and accepted rather than avoided — the Reddit-containing name and displaying full comment text. Both are recorded with their clause citations in [01-legal.md](01-legal.md) and [decisions/](decisions/). If a UDRP ever lands it costs the domain, not the pipeline or the index.

---

## In 30 seconds

1. **The API cannot backfill.** Every Reddit listing hard-caps at ~1,000 items. Measured live: `/r/SaaS/new` exhausted at 995 items, then `after=None`. Against r/SaaS's measured posting rate that is 3 to 8 days. History has to come from archive dumps.
2. **Reddit search indexes posts, not comment bodies.** Brand opinion lives in comments, so per-brand search is a discovery tool, never a census. You must ingest whole subreddits and match locally.
3. **Signal does not track subscriber count.** r/PasswordManagers (54,640 subscribers) runs **42%** brand-bearing comments. r/marketing (1,958,693) runs **0%**, because its rules delete exactly that content. Same story in CRM: r/CRM (55,275) at 12%, r/startups (2,107,067) at 0%. All four re-measured on 2026-08-05.
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
| Minimum mentions to rank | **`n_eff ≥ n_min`** after the design-effect correction — 600, 400 or 200 by category tier | 🟢 Derived |
| High-ambiguity brand names | **35 of 113 (31%)** | 🟢 Classified |
| Capterra categories | 1,000 rendered, truncated mid-W | 🟢 Scraped |
| G2 categories | 2,237 enumerable | 🟢 Scraped |
| Unique subreddits measured | **156** | 🟢 Measured live |
| Vendor subreddits, excluded from scoring | **56 of 156 (36%)** | 🟢 Classified |
| Subreddits hostile to brand talk | **54 of 156 (35%)** | 🟢 Read from their own rules |
| Scorable: generalist and non-hostile | **62 of 156 (40%)** | 🟢 Derived |
| Brand-bearing volume left on scorable subs | **9%** | 🟢 Measured live |
| Categories reaching the 5-subreddit floor | **20 of 20** (5 to 17 scorable subs each) | 🟢 Measured live |
| Candidate slots → unique subreddits | **254 → 156** (~39% ingest saving) | 🟢 Measured |
| Live adjacent competitors | **2**, both per-brand audits | 🟢 Fetched live |

**On the generalist-only rule.** Vendor subreddits are the densest data measured, and they are excluded anyway. A brand with a large home subreddit would otherwise out-rank a competitor with a small one or none, so the table would partly measure community size. The price is 91% of the brand-bearing volume, and it is not free ([14-category-tests.md](14-category-tests.md)).

**On reachable history.** r/SaaS was measured twice on 2026-08-04 by two methods: **122 posts/day** from the span of the last 100 posts in `/new`, and **~350/day** extrapolated from the 10 newest. The second runs high because the newest posts have not yet cleared moderation removal. Quote the range, never "8 days" as a fact ([02-data-acquisition.md](02-data-acquisition.md)).

**On the eligibility gate.** The naive derivation `n = z²p(1−p)/h² = 384 → 400` assumes independent draws. Reddit mentions cluster inside a handful of mega-threads and within threads by author, so that assumption fails and the raw count overstates the information you have.

The gate is therefore `n_eff = n / DEFF ≥ n_min`, where `DEFF = 1 + (m̄ − 1)·ICC` and `n_min` is set by the category's published precision target — 600, 400 or 200 for the Deep, Standard and Thin tiers ([decisions/0009](decisions/0009-category-scaled-thresholds.md)). Both `n` and `n_eff` are published on every brand page, intervals come from a cluster bootstrap, and **four diversity floors — authors ≥ 50, subreddits ≥ 5, max share from one thread ≤ 20%, max share from one author ≤ 5% — apply on top and never scale** ([07-index-methodology.md](07-index-methodology.md)).

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
| "Reddit doesn't have enough discussion for most categories" | ❌ **Wrong.** The candidate lists were short, not Reddit. Widening them with generalist practitioner subs, then again by subreddit discovery, moved the categories clearing the 5-subreddit floor from 4 of 20 to **12 of 20**, under the same rule. The 8 that still fail are killed by hostility: Note-taking has **11 hostile of 17 candidates**. See [14-category-tests.md](14-category-tests.md). |
| "A product's own subreddit is the best source" | ❌ **Wrong for a ranking.** Only generalist subs score. Vendor subs hold **50%** of measured brand-bearing volume and are excluded anyway, because a big home subreddit would buy rank against a competitor that has none — community size, not sentiment. They stay usable as evidence on a brand's own page. |
| "The one Reddit-native player is gone, so the field is clear" | 🟡 **Half right.** GummySearch did shut down on 2025-11-30 ([gummysearch.com](https://gummysearch.com/)), but two adjacent properties launched inside the following seven months. The seat is open, not open indefinitely. |

---

## Decisions already taken

| # | Decision | Record |
|---|---|---|
| 1 | Product is **Reddit Index** on `redditindex.com`. "Reddit" kept in the name deliberately, breaching [Data API Terms §4.1](https://www.redditinc.com/policies/data-api-terms) and [Developer Terms §5.3](https://www.redditinc.com/policies/developer-terms). The realistic enforcement is a UDRP filing, not a lawsuit, and losing one costs the domain rather than the project. | [0001](decisions/0001-name-reddit-index.md) |
| 2 | Brand pages **display full comment text** with links back. Knowingly non-compliant, priced as a risk. | [0002](decisions/0002-display-full-mentions.md) |
| 3 | **Derive the category spine**, do not copy Capterra's. | [0003](decisions/0003-g2-taxonomy-spine.md) |
| 4 | ~~Two axes, love and hate scored independently.~~ **Superseded by 6.** | [0004](decisions/0004-two-axis-index.md) |
| 5 | Columns stay labelled **"Most Loved" and "Most Hated."** Owner-specified superlatives, priced as exposure, with the measured variable shown beside them. | [0005](decisions/0005-superlative-labels.md) |
| 6 | **One published metric, the Reddit Love Score** (0-100). Sorting it descending *is* the consolidated view. Supersedes 4, whose two indices ran over a shared denominator and were therefore complementary by construction. | [0006](decisions/0006-single-reddit-love-score.md) |
| 7 | **Flat URLs** — `/{category}/` and `/{company}/` share one namespace, with a build-time collision gate and frozen slugs. | [0007](decisions/0007-flat-url-namespace.md) |
| 8 | **A unique colour and lucide icon per category**, generated under constraint so none can read as the loved or hated accent, and none is orange. | [0008](decisions/0008-category-identity-system.md) |
| 9 | **Category-scaled thresholds** — the eligibility gate follows a published precision target per category. The diversity floors never scale. | [0009](decisions/0009-category-scaled-thresholds.md) |

⚠️ **Decisions 1 and 2 are priced risks, not solved problems.** The name breaches Reddit's trademark clauses and the brand pages display full comment text. Both were taken with the exposure in front of the owner, and neither is mitigated by anything built later.

The name is also **Reddit-locked**: Phase 3 in [12-phasing.md](12-phasing.md) contemplates Hacker News and other sources, which "Reddit Index" cannot carry without a rename. `redditbrandindex.com` is the defensive registration. `brandsonreddit.com` was available, carries a materially better UDRP posture, and is the documented migration target ([0001](decisions/0001-name-reddit-index.md)).

Empact Partners operates it openly. The footer reads "Created by Empact Partners," beside the non-affiliation notice that decision 1 makes mandatory on every page. It is a side project, not an independent publication, and does not pretend to be one.

---

## Navigate

| Doc | What's in it |
|---|---|
| **[BUILD-PROMPT.md](BUILD-PROMPT.md)** | **The build prompt.** Paste it into a fresh session to start building. Four milestones, each with an acceptance gate. |
| **[00-concept.md](00-concept.md)** | The product, page by page, and the live competitive field. Start here. |
| **[13-algorithm.md](13-algorithm.md)** | **How it actually works.** Subreddit selection, the comment-stream discovery lane, mention detection, the continuous-ingest daily-publish loop. |
| [01-legal.md](01-legal.md) | The clause-level risk register and the two priced decisions |
| [02-data-acquisition.md](02-data-acquisition.md) | The 1,000-item cap, archive backfill, volumes, cost |
| [03-taxonomy.md](03-taxonomy.md) | G2 vs Capterra, and why we derive our own spine |
| [04-subreddit-mapping.md](04-subreddit-mapping.md) | Category → subreddit, and the rules that kill brand signal |
| [05-entity-resolution.md](05-entity-resolution.md) | The "is this *monday* the vendor" problem |
| [06-sentiment.md](06-sentiment.md) | Targeted ABSA, the cascade, validation protocol |
| **[07-index-methodology.md](07-index-methodology.md)** | The formulas. What a hostile CMO attacks first. |
| [08-architecture.md](08-architecture.md) | Next.js on Vercel, Supabase, schema, daily refresh, cost table |
| **[14-category-tests.md](14-category-tests.md)** | **20 categories measured live.** 232 subreddits, the generalist-only rule, what the data says and what it cannot say |
| [09-design.md](09-design.md) | Visual spec: trade dress, component inventory, accessibility |
| [15-empact-brand.md](15-empact-brand.md) | The Empact brand system, transcribed from the style guide — and what this site refuses |
| [16-design-system.md](16-design-system.md) | The implementation layer: tokens, shadcn/lucide map, the 20 category colours, build gates |
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
| **[subreddit-measurements.csv](data/subreddit-measurements.csv)** | 232 | **Every subreddit measured**, with `is_vendor_sub` and `scorable`. Start here. |
| **[category-tests-20.csv](data/category-tests-20.csv)** | 20 | Per category: candidates, hostile, vendor, scorable, floor verdict, threshold tier |
| **[categories.csv](data/categories.csv)** | 20 | The shipping categories: slug, colour, lucide icon, threshold tier, `n_min` |
| [phase1-categories.csv](data/phase1-categories.csv) | 50 | The Phase 1 spine |
| [subreddit-map.csv](data/subreddit-map.csv) | 131 | The earlier category → subreddit map, superseded for scoring |
| [brand-gazetteer-seed.csv](data/brand-gazetteer-seed.csv) | 113 | Seed brands with ambiguity classification |
| [domain-availability.csv](data/domain-availability.csv) | 120 | The sweep behind the name, plus the live competitors |
| [analyze.py](data/analyze.py) | — | Regenerates the three measurement CSVs from raw probe output |

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

**42 of the 50 Phase 1 categories have no subreddit mapping.** Eight Phase 1 rows are mapped. Separately, 20 categories were probed live ([14-category-tests.md](14-category-tests.md)) — only 8 of those labels join the Phase 1 taxonomy exactly, and **no crosswalk ships yet**. The rest is real work.

**A failed floor is not a dead category.** Eight of the 20 fall short of five scorable generalist subreddits. That is a statement about the candidate list, not about Reddit — widening the lists once already flipped categories that had failed. This is a floor instrument. It cannot declare a category empty.

**No gold set exists and no pipeline has been run.** Every accuracy figure — precision ≥0.97, recall 0.80-0.88, the sentiment cascade cost — is a target derived from published benchmarks, not a measurement of our own system.

**The audit is sized to the claim.** At p̂ = 0.97 on 400 items the Wilson 95% interval runs roughly ±1.7pp, which cannot separate 0.97 from 0.95. The audit is therefore **1,000 items per cycle**, and precision publishes as a Wilson lower bound rather than a point estimate ([05-entity-resolution.md](05-entity-resolution.md)).

**Reddit's commercial pricing is unknown.** No public rate card exists. The often-quoted $0.24 per 1,000 calls is the June 2023 announced developer rate, not a verified 2026 enterprise price.

**G2's terms of use were not read**, only assumed similar to Capterra's post-acquisition. Marked NOT VERIFIED throughout.

**This repo is not legal advice.** It was written from primary sources by non-lawyers. Get an Estonian data-protection opinion and a US media-law read on the final page copy before launch.

---

Start here: [00-concept.md](00-concept.md) · Read before coding: [01-legal.md](01-legal.md) · The gate that decides it: [12-phasing.md](12-phasing.md) · The formulas: [07-index-methodology.md](07-index-methodology.md) · Every source: [sources.md](sources.md)

*Created by Empact Partners. Not affiliated with, endorsed by, or sponsored by Reddit, Inc. "Reddit" and subreddit names are trademarks of their respective owners and are used here descriptively.*
