# Phasing and Scope

## Bottom line

- Four phases, each with a written entry gate and a kill test, so Reddit Index can be stopped for the price of the phase it dies in rather than the price of the whole build.
- **Phase 0 is one category: CRM.** Five scorable subreddits, the highest measured live yield of any category that clears the diversity floor, measured live 2026-08-04 ([category tests](14-category-tests.md)). It publishes nothing. If its ranking does not match what a knowledgeable practitioner would say, the project stops there.
- **Phase 1 is the first public spend.** Fifty categories on redditindex.com. Twenty categories are now probed and **only 6 clear the five-scorable-subreddit floor**, so widening the 14 short candidate lists is entry work, not build work. Note the taxonomies differ: 8 of the 50 Phase 1 rows are mapped, and only 8 of the 20 probed labels join that taxonomy exactly. **No crosswalk ships yet.**
- Phase 2 is a 1,000+ category problem on Capterra's flat list, 2,237 on G2's ([taxonomy](03-taxonomy.md)). Audit labor scales linearly with it, and the per-brand publish gate stops being enforceable somewhere inside that multiple.
- **Phase 3 opens with a naming fork, not with ingest work.** The product is Reddit Index, so a non-Reddit source means a rename or a separately-branded second property ([0001](decisions/0001-name-reddit-index.md)).
- **Infrastructure is not the constraint.** Roughly **$74/month for Phase 1**, roughly **$301/month at full scale** ([architecture §8](08-architecture.md)), on continuous ingest and a daily publish ([algorithm §7](13-algorithm.md)). What binds is audit labor and a corrections desk staffed in perpetuity.

---

## The four phases at a glance

| Phase | Scope | Ships publicly | Hard entry gate |
|---|---|---|---|
| **0** | 1 category (CRM) | Nothing | None — this is the first spend |
| **1** | 50 categories, the 6 floor-passing ones first | Site, `/methodology`, corrections desk | Phase 0 passes G1–G5, the entry work lands, and the ship checklist is green |
| **2** | Full taxonomy (1,000+) | Same, wider | Phase 1 runs 2 clean audit cycles at cost |
| **3** | Non-Reddit sources | Multi-source indices | Phase 1 or 2 stable, a second source verified, naming fork resolved |

---

## Phase 0 — Proof of signal

**Nothing is published. No site is built. No domain is pointed anywhere.**

**The subject is CRM.** It clears the five-scorable-subreddit diversity floor and carries the highest measured live yield of any category that clears it: **2.02 brand-bearing comments per hour**, and a 3-year point estimate of **~53,000 seed-brand-bearing comments** ([14-category-tests.md](14-category-tests.md)).

### The CRM scoring set, measured 2026-08-04

| Subreddit | Subscribers | Rule posture | Type | Comments/h | Brand-bearing |
|---|---:|---|---|---:|---:|
| [r/EntrepreneurRideAlong](https://www.reddit.com/r/EntrepreneurRideAlong/) | 717,227 | permissive | independent | 10.0 | 0% |
| [r/sales](https://www.reddit.com/r/sales/) | 594,328 | permissive | independent | 29.8 | 0% |
| [r/salesforce](https://www.reddit.com/r/salesforce/) | 113,705 | permissive | ecosystem | 4.5 | 30% |
| [r/techsales](https://www.reddit.com/r/techsales/) | 61,630 | permissive | independent | 10.6 | 0% |
| [r/CRM](https://www.reddit.com/r/CRM/) | 55,275 | ⚠️ unknown | independent | 5.6 | 12% |

<sup>Brand-bearing = share of one 100-comment page containing any of 5 seed brands. A `0%` reads as *not detected in a 100-comment sample*, never as *absent* ([14 §4](14-category-tests.md)). Full rows in [subreddit-measurements.csv](data/subreddit-measurements.csv).</sup>

**Evidence corpus only, never scored:** r/hubspot (22,278), r/gohighlevel (23,004) and r/Zoho (12,658) are single-product communities. r/SaaS, r/smallbusiness and r/Entrepreneur are hostile — their own rules delete the brand mentions we came for.

### Why CRM and not Password Managers

Password Managers / Security was the earlier candidate, picked from a 12-category assessment that read it as the richest set ([subreddit map](04-subreddit-mapping.md)). The 20-category study measures it at **4 scorable subreddits, one short of the floor**: four candidates are single-product (r/Bitwarden, r/1Password, r/ProtonPass, r/KeePass) and three are hostile (r/privacy, r/cybersecurity, r/selfhosted).

A category that cannot satisfy [07](07-index-methodology.md)'s ≥5-subreddit diversity floor cannot produce a rankable board, which is the one thing Phase 0 exists to test.

**That is a subreddit-count failure, not a verdict on the discussion.** Password Managers still measured 0.57 brand-bearing comments/hour and a 3-year point estimate near 15,000, and at the 95% upper bound all 20 tested categories clear the mention threshold. A wider candidate list may well carry it back over the floor.

### CRM meets the floor exactly, with no margin

Five scorable subs against a floor of five means **every ranked brand must appear in all five**. Two classification calls carry the whole category:

- **r/CRM's rule posture came back `unknown`** — the rules endpoint returned nothing parseable. Read those rules by hand before ingest. A hostile posture there drops CRM to 4.
- **r/salesforce is scored as an ecosystem community**, not a single-product one. Blanket-excluding vendor-named subs drops CRM to 4 as well ([14 §3](14-category-tests.md)).

So the **first Phase 0 work item is widening the CRM candidate list past its current 11**, to buy margin before either call matters.

### Live evidence

- **Brand-titled threads:** "HubSpot" scoped to r/CRM returned 100 results plus a cursor, led by ["I hate Hubspot"](https://reddit.com/r/CRM/comments/1mcr4d4/i_hate_hubspot_its_like_blunt_force_trauma_to_the/) (37 points / 66 comments) and ["Zoho vs Hubspot vs Salesforce"](https://reddit.com/r/CRM/comments/1ne8y3d/zoho_vs_hubspot_vs_salesforce/) (63 comments) ([subreddit map](04-subreddit-mapping.md)).
- **Comment bodies Reddit's own search cannot reach:** the Lane C external probe returned *"HubSpot is atrocious"* and *"We switched from HubSpot to Attio this year"* ([algorithm §3](13-algorithm.md)).

### What gets built first

The gold sets, before the pipeline. Everything downstream is unmeasurable without them ([sentiment method](06-sentiment.md)).

| Artifact | Size | Effort |
|---|---|---|
| Entity gold set | 1,000 mentions, 2 annotators, 200-item overlap for kappa | ~15h |
| Sentiment gold set | 1,000–1,500 stratified, ≥150–200 per minority class | ~20h (estimate, not measured) |
| Held-out set | 500 items, unopened until the end | included above |

### The go/no-go test

All five must pass. Any single failure stops the project.

| # | Test | Threshold | Source |
|---|---|---|---|
| G1 | Mention-level entity precision on held-out | **≥0.97** point estimate, interval reported | [entity resolution](05-entity-resolution.md) |
| G2 | Brands clearing **`n_eff ≥ 400`**, where `n_eff = n / DEFF` and `DEFF = 1 + (m̄ − 1)·ICC` | **≥10 brands** | [index methodology](07-index-methodology.md) |
| G3 | All four diversity floors hold: distinct authors ≥50, distinct subreddits ≥5, distinct threads above the floor set in 07, max single-thread share ≤20% of `n` | all four, per ranked brand | [index methodology](07-index-methodology.md) |
| G4 | Leave-one-subreddit-out rank stability | top 10 does not reorder beyond ties | [index methodology](07-index-methodology.md) |
| G5 | Human concordance: 3 practitioners blind-rank the top 10 before seeing output, Spearman ρ vs the computed Love Index | **ρ ≥ 0.6** | threshold set here, not derived from the corpus |

G2 gates on the **design-effect-corrected** count, not the raw one. Reddit mentions cluster inside a few mega-threads and within threads by author, so raw `n` overstates independent information. Both `n` and `n_eff` publish on every brand page, with intervals from a cluster bootstrap resampled by thread and by author.

G1's threshold is a point estimate, not a tight one. On a 500-item held-out set an observed 0.97 carries a Wilson 95% interval of roughly [0.949, 0.980], so it cannot separate 0.97 from 0.95. Either the held-out set grows or the published claim states the interval rather than the point.

G5 is the question the whole phase exists to answer. The ≥0.97 precision / 0.80–0.88 recall figure carried through the research is **inference, never measured on this data**.

G3 is the tightest gate on CRM specifically. With exactly five scoring subreddits, its `distinct subreddits ≥5` clause admits only brands discussed in every one of them, so a brand strong in r/sales and r/CRM but absent from r/techsales does not publish. Widening the candidate list is the only thing that loosens this.

### Phase 0 kill criteria

Stop, permanently, on any of these:

- G1–G5 fails and a documented fix does not recover it inside one rebuild.
- The "most hated" column returns the category incumbents. That is the adoption-model confound: forced enterprise users complain, voluntary self-serve users praise, and no post-hoc correction exists because the confound sits in the exposure population ([index methodology](07-index-methodology.md)).
- Inter-annotator agreement lands where the research expects it (Krippendorff's α 0.60–0.75, below 0.35 on sarcasm) and the low-agreement band is large enough that ranks move when adjudication flips.

**Effort:** 3–5 weeks for one person, gold sets included.

**Cost:** bandwidth, essentially. The acquisition shape is Arctic Shift per-subreddit dumps for backfill plus the official free-tier API for the live edge ([data acquisition](02-data-acquisition.md)). One category runs **~180 calls a day** against a free-tier ceiling near 115,000 ([algorithm §8](13-algorithm.md)). Infrastructure runs under $50 for the whole phase.

**Cadence, from day one:** ingest runs continuously on each multireddit bucket's own 1–24h interval, and scoring runs once daily ([algorithm §7](13-algorithm.md)). Phase 0 publishes nothing, so "publish" here means writing a dated internal board — but the daily rhythm is exercised before Phase 1 depends on it.

A commercial vendor is a targeted gap-fill option, not the Phase 0 route. Bright Data's $250 minimum order is a cost only if a gap-fill is actually placed, and its per-record pricing makes it unusable as a census ([data acquisition](02-data-acquisition.md)).

---

## Phase 1 — Fifty categories

**What ships:** redditindex.com, 50 category pages (two columns plus the consolidated table), brand pages with mentions and thread links, a frozen version-controlled methodology page at `/methodology`, the delete-sync job, and a staffed corrections process with a published SLA. Scores refresh **daily**, from a continuously-ingested corpus ([algorithm §7](13-algorithm.md)).

### The first tranche: the six categories that already pass the floor

Ship these first, because their subreddit sets are measured and sufficient today ([14-category-tests.md](14-category-tests.md)):

| Category | Scorable subs | Live bb/h | 3y point est. |
|---|---:|---:|---:|
| CRM | 5 | 2.02 | 53,006 |
| Business Intelligence and Analytics | 6 | 1.11 | 29,144 |
| Backup and Storage | 6 | 0.54 | 14,191 |
| Help Desk and Customer Support | 6 | 0.30 | 7,831 |
| Cloud Hosting and Infrastructure | 7 | 0.24 | 6,254 |
| Team Collaboration and Chat | 5 | 0.14 | 3,652 |

The other 44 ship behind them, as their entry gates clear.

### Phase 1 entry work

Two items, each with its own gate, both before anything goes live.

**1. Widen the candidate lists for the 14 below-floor categories.** Target independent practitioner subreddits rather than product communities, which is precisely where the current lists are short: Note-taking has 10 candidates of which 7 are hostile and 6 single-product, leaving 1 scorable ([14 §5](14-category-tests.md)).

> **Gate:** every one of the 50 either reaches ≥5 scorable subreddits, or ships labeled *insufficient Reddit signal to rank* with the short candidate list named as the reason. The evidence supports a count failure, not a claim of absent discussion.

**2. Build the crosswalk, then map what is left.** 8 of the 50 Phase 1 rows are mapped; 42 are pending. Separately, 20 categories were probed, of which only 8 join the Phase 1 taxonomy exactly. Until a crosswalk ships, those two counts cannot be added together.

> **Gate:** all 50 carry a resolved candidate list with rule posture and community type read live, and the 13 `unknown` rule postures are resolved by hand ([14 §2](14-category-tests.md)).

**Dedupe before scheduling.** Ingest is per-subreddit, not per-category. The 187 candidate slots across the 20 measured categories collapse to 132 unique subreddits, and r/Entrepreneur alone serves 7 categories — skip the dedupe and ~29% of calls re-fetch the same comment streams.

### Phase 1 ship checklist

Every box is green before the domain resolves publicly. These are build requirements, and the reasoning behind them — including the two risks the owner priced and accepted — is in [01-legal.md](01-legal.md).

- [ ] Phase 0 passed G1–G5, with intervals published rather than point estimates alone.
- [ ] Nightly delete-sync runs and is verified against a seeded set of deleted, removed, and edited items.
- [ ] Every mention renders permalink + username + "from Reddit."
- [ ] Removal route live: free, fast, no questions, no sales offer attached, reachable from every brand page.
- [ ] `/methodology` published, frozen, and version-controlled **before** the first scoring run — never adjusted after seeing where a company landed, in either direction.
- [ ] Non-affiliation notice in the footer of every page.
- [ ] Zero ads anywhere on the domain, and no Reddit trade dress: no `#FF4500`, no Snoo, no Reddit Sans, no lookalike mark ([design](09-design.md)).
- [ ] Plain-text company names, no logos, and the measured variable printed beside every superlative ([0005](decisions/0005-superlative-labels.md)).
- [ ] Defensive `redditbrandindex.com` registered and redirecting to the primary.
- [ ] Canonical host in exactly one config value, every internal link relative, so a forced move costs a day rather than a quarter.
- [ ] Corrections desk staffed, with the SLA published on the site.

**What does not rank, on current evidence.** **ERP holds at 3 scorable subreddits** and so fails the diversity floor, consistent with the earlier probe returning 15 results with its top thread from 2023 ([subreddit map](04-subreddit-mapping.md)). Its point estimate is 2,733 and its upper bound 6,438 — low, though not the lowest of the 20 on either measure. It ships labeled *insufficient Reddit signal to rank* unless a wider candidate list clears the floor.

**The earlier Help Desk verdict is overturned.** The 20-category study measures it at 6 scorable subreddits. The r/CustomerService misroute still stands — it is a retail-horror-story sub — and dropping it on topical fit still leaves 5, so the category holds either way.

**What is not costed yet.** **Thirty of the 50 categories have no subreddit mapping.** Any Phase 1 estimate produced before that mapping lands is guesswork.

**What it costs to run.** Roughly **$74/month** of infrastructure across the ingest worker, Supabase Pro and Vercel Pro, at ~50 categories / ~500 brands / ~200 subs / ~1k pages ([architecture §8](08-architecture.md)). Daily publishing does not move that figure: only changed brand and category pages are revalidated, so a typical day rebuilds tens of pages ([algorithm §7](13-algorithm.md)). The audit labor is the expensive line.

### Phase 1 kill criteria

Any one of these means the artifact is no longer defensible while it is live:

- More than a handful of takedown demands in 90 days.
- An audit cycle that fails its publish gate (>3 errors in 60 on a stratum sample).
- The corrections desk falling behind its published SLA. Publishing is automated and daily, so the site keeps updating whether or not anyone is answering corrections — the failure is silent, and it has to be watched for rather than noticed.
- Daily publishes running on a corpus the audit has not caught up with. If adjudicated coverage stops keeping pace with what is being published, pin the public scores to the last audited run rather than shipping unaudited movement.

---

## Phase 2 — Full taxonomy

What changes at scale is arithmetic, not architecture. Capterra renders 1,000 leaf categories and truncates mid-W; G2 enumerates 2,237 ([taxonomy](03-taxonomy.md)).

What breaks first is the audit. At 50 categories × ~15 published brands × ≥150 adjudicated mentions, Phase 1's per-cycle label count is already 75K–150K, against a research budget of 400. The 20× category expansion puts Phase 2 at roughly 1.5M–3M labels a cycle, at which point the per-brand publish gate stops being enforceable at all.

What breaks second is delete-sync. A full sweep over 200–400M items at 100 ids per `/api/info` call is 2–4M requests and weeks of wall-clock ([data acquisition](02-data-acquisition.md)). A stale `[removed]` sitting behind a cited link is the failure this phase is most likely to ship.

The corpus itself is not the problem: ~240M items for 1,000 subreddits is ~53 GB compressed and fits one machine. Storage is budgeted from those compressed bytes, not from the 0.5–1.5 TB raw-JSON figure ([architecture](08-architecture.md)). The cost is human and recurring.

---

## Phase 3 — Beyond Reddit

**The name does not travel.** The product ships as Reddit Index on redditindex.com, so a Hacker News or Stack Overflow index cannot sit under it. This phase therefore opens with a naming fork rather than with ingest work, and the fork is the entry gate.

| Fork | What it means | What it costs |
|---|---|---|
| **Rename the property** | Move everything to a source-neutral name. `brandsonreddit.com`, the migration target recorded in [0001](decisions/0001-name-reddit-index.md), does not solve this one — it is Reddit-scoped too, so a genuinely multi-source name is a third choice still to be made. | Redirects, plus every citation and inbound link earned under the old name. |
| **Run a second property** | Reddit Index stays as it is and the non-Reddit index ships under its own brand. | Two sites, two frozen methodology pages, two corrections desks, no combined leaderboard. |

Neither is cheap, and the fork was priced when the name was chosen: legibility in a cold email was judged worth more than keeping the multi-source option open.

**Hacker News is the natural second source** — a genuinely permissive public API and a population overlapping the developer-tooling categories. **NOT VERIFIED: a direction to verify, not a fact.** No Hacker News terms, API limits, or signal density were assessed in the corpus.

| Source | Status | Note |
|---|---|---|
| Hacker News | 🟡 Direction to verify | Believed permissive; **NOT VERIFIED**, not assessed |
| Stack Overflow | 🟡 Direction to verify | **NOT VERIFIED**, not assessed |
| YouTube comments | 🔴 Not assessed | **NOT VERIFIED** |
| X | 🔴 Not assessed | **NOT VERIFIED** |

A second source adds its own terms surface and its own ship checklist. It removes nothing from Phase 1's.

---

## The cheaper alternative

Presented fairly, as the fallback if Phase 0 fails. The owner has chosen the full build.

**Shape:** one dated, positive-only study across the six floor-passing categories ([14-category-tests.md](14-category-tests.md)) as a PDF with a fixed collection window, plus a free private per-prospect diagnostic sent only to the company it describes.

| | Full build | Cheap version |
|---|---|---|
| What it gets | Public leaderboard, standing SEO/AEO surface, brand pages | The same outreach hook, the same PR and citation value |
| Cost | Phase 0 bandwidth, then ~$74/mo plus audit labor, forever | Days of work on existing report skills ([outreach play](11-outreach-play.md)) |
| Corpus | Required | None |
| Recompute obligation | Daily, forever ([algorithm §7](13-algorithm.md)) | None — the study is dated and frozen |
| Corrections desk | Staffed in perpetuity | None |
| What it gives up | — | The public leaderboard, the live property, the compounding search asset |

The one thing it cannot deliver is the thing Phase 1 exists for: a standing public property that ranks brands and keeps ranking them.

---

## Effort and cost per phase

| Phase | Elapsed | Build effort | Infra | Recurring human cost |
|---|---|---|---|---|
| **0** | 3–5 weeks | ~35h annotation + pipeline | Bandwidth + **<$50** for the phase | None (nothing published) |
| **1** | Not estimable until 30 categories are mapped and 14 candidate lists are widened | Site + 30 mappings + 14 widenings + corrections process | **≈ $74/mo** ([architecture §8](08-architecture.md)) | 75K–150K adjudicated labels per audit cycle at 50 categories, plus a staffed corrections desk |
| **2** | Not planned | — | **≈ $301/mo** at full scale ([architecture §8](08-architecture.md)) | 1.5M–3M labels per audit cycle — the number that breaks it |
| **3** | Not planned | Second-source ingest, plus a rename or a second brand | Not estimated | Not estimated |

Both infra totals come from the line-item table in [08-architecture.md §8](08-architecture.md) and are the same figures the README carries. Inside them, only the ingest-worker line (Railway, or a Hetzner box) is secondary-sourced; verify it before committing. Every other line is a vendor-published price.

The label counts are per **audit** cycle, which is a human rhythm and not the publish rhythm. Daily publishing multiplies publish events, not adjudication volume: stages 5–8 classify only the delta since the last run, so total classified volume is unchanged ([algorithm §7](13-algorithm.md)).

Two one-time reviews sit outside every line above: an Estonian data-protection opinion and a US media-law read of the final page copy. **Neither is costed** — no figure for either appears anywhere in the research.

---

[← Back to README](README.md) · [00-concept.md](00-concept.md) · [01-legal.md](01-legal.md) · [08-architecture.md](08-architecture.md)
