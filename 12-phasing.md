# Phasing and Scope

## Bottom line

- Four phases, each with a written entry gate and a kill test, so Reddit Index can be stopped for the price of the phase it dies in rather than the price of the whole build.
- **Only generalist subreddits score.** Any subreddit named for a vendor or product is excluded from every ranking. The reason is cross-brand comparability, not sentiment ([the scoring rule](#the-scoring-rule-generalist-subreddits-only)).
- **That rule is expensive and the cost is stated up front:** generalist subs carry **9%** of measured brand-bearing volume. The 56 vendor subs carry the other 76%, hostile subs the rest.
- **Phase 0 is one category: CRM.** 23 candidates, **16 scorable generalist subreddits**, **0.85 brand-bearing comments/hour** — the highest live yield of any floor-passing category, measured 2026-08-05. It publishes nothing.
- **Phase 1 is the first public spend.** Twenty categories are probed and **12 clear the five-scorable-subreddit floor**, up from 4 before the candidate lists were widened. The binding constraint was always the lists, never Reddit's opinion volume and never the exclusion rule.
- **Widening is proven work, not an open risk.** One widening pass added 24 candidate subreddits across the study, 18 of them usable; CRM alone went from 6 scorable subs to 16.
- Phase 2 is a 1,000+ category problem on Capterra's flat list, 2,237 on G2's ([taxonomy](03-taxonomy.md)). Audit labor scales linearly with it, and the per-brand publish gate stops being enforceable somewhere inside that multiple.
- **Phase 3 opens with a naming fork, not with ingest work.** The product is Reddit Index, so a non-Reddit source means a rename or a separately-branded second property ([0001](decisions/0001-name-reddit-index.md)).
- **Infrastructure is not the constraint.** Roughly **$74/month for Phase 1**, roughly **$301/month at full scale** ([architecture §8](08-architecture.md)). What binds is audit labor and a corrections desk staffed in perpetuity.

---

## The scoring rule: generalist subreddits only

A subreddit may score a brand only if it is **not named for, or dedicated to, a specific vendor or product**. r/salesforce, r/shopify, r/aws, r/Bitwarden and r/Notion are all excluded on the same footing. There is no intermediate "ecosystem" class.

Formally, a subreddit is scorable when its status is `ok`, its rule posture is not `hostile`, and `is_vendor_sub` is false. Of 156 measured subreddits, **56 are vendor subs**, **54 are hostile**, and **62 are scorable** ([measurements](data/subreddit-measurements.csv)).

**The reason is cross-brand comparability.** A brand with a large active home subreddit would gain a structural advantage over a competitor with a small one or none at all. Rank would then partly measure community size, which is the same confound the index already rejects for raw mention counts. A ranking table has to stand on neutral ground.

**The reason is not fan bias.** Sentiment was never measured in this study, so no directional claim about vendor subs is supportable in either direction. r/paypal is plausibly a support-seeking population; r/ObsidianMD is plausibly an enthusiast one. Neither was tested.

**The cost is real and is not to be softened.** Vendor subs carry **76%** of all measured brand-bearing volume; generalist subs retain **9%**. The excluded data is the densest measured, not the weakest. It is excluded because it is not comparable, not because it is poor.

Vendor subs stay usable as **evidence** on a brand's own page, and for tracking one brand against its own baseline over time. They never enter a ranking.

---

## The four phases at a glance

| Phase | Scope | Ships publicly | Hard entry gate |
|---|---|---|---|
| **0** | 1 category (CRM) | Nothing | None — this is the first spend |
| **1** | 50 categories, the 12 floor-passing ones first | Site, `/methodology`, corrections desk | Phase 0 passes G1–G5, the entry work lands, and the ship checklist is green |
| **2** | Full taxonomy (1,000+) | Same, wider | Phase 1 runs 2 clean audit cycles at cost |
| **3** | Non-Reddit sources | Multi-source indices | Phase 1 or 2 stable, a second source verified, naming fork resolved |

---

## Phase 0 — Proof of signal

**Nothing is published. No site is built. No domain is pointed anywhere.**

**The subject is CRM.** It clears the five-subreddit diversity floor with the widest margin in the study — 16 scorable generalist subs against a floor of 5 — and carries the highest measured live yield of any floor-passing category: **0.85 brand-bearing comments per hour**, a 3-year point estimate of **22,259** seed-brand-bearing comments, upper bound **116,689** ([category tests](data/category-tests-20.csv)).

### The CRM scoring set, measured 2026-08-04 / 2026-08-05

| Subreddit | Subscribers | Rule posture | Comments/h | Brand-bearing | bb/h |
|---|---:|---|---:|---:|---:|
| [r/sales](https://www.reddit.com/r/sales/) | 594,328 | permissive | 29.84 | 0% | 0.000 |
| [r/startups](https://www.reddit.com/r/startups/) | 2,107,067 | capped | 16.76 | 0% | 0.000 |
| [r/techsales](https://www.reddit.com/r/techsales/) | 61,630 | permissive | 10.63 | 0% | 0.000 |
| [r/EntrepreneurRideAlong](https://www.reddit.com/r/EntrepreneurRideAlong/) | 717,227 | permissive | 9.96 | 0% | 0.000 |
| [r/InsuranceAgent](https://www.reddit.com/r/InsuranceAgent/) | 46,157 | permissive | 7.76 | 1% | 0.078 |
| [r/PPC](https://www.reddit.com/r/PPC/) | 276,554 | permissive | 7.52 | 0% | 0.000 |
| [r/CRM](https://www.reddit.com/r/CRM/) | 55,275 | ⚠️ unknown | 5.56 | 12% | 0.667 |
| [r/consulting](https://www.reddit.com/r/consulting/) | 378,485 | permissive | 5.46 | 0% | 0.000 |
| [r/msp](https://www.reddit.com/r/msp/) | 245,261 | capped | 5.27 | 0% | 0.000 |
| [r/agency](https://www.reddit.com/r/agency/) | 96,594 | permissive | 4.38 | 0% | 0.000 |
| [r/smallbusinessuk](https://www.reddit.com/r/smallbusinessuk/) | 76,899 | permissive | 4.34 | 0% | 0.000 |
| [r/RealEstateTechnology](https://www.reddit.com/r/RealEstateTechnology/) | 55,112 | permissive | 3.54 | 0% | 0.000 |
| [r/salesdevelopment](https://www.reddit.com/r/salesdevelopment/) | 22,201 | permissive | 2.09 | 1% | 0.021 |
| [r/SalesOperations](https://www.reddit.com/r/SalesOperations/) | 18,487 | permissive | 1.05 | 6% | 0.063 |
| [r/B2BSaaS](https://www.reddit.com/r/B2BSaaS/) | 26,948 | permissive | 0.86 | 0% | 0.000 |
| [r/revops](https://www.reddit.com/r/revops/) | 6,593 | ⚠️ unknown | 0.36 | 5% | 0.018 |

<sup>Brand-bearing = share of one 100-comment page containing any of 5 seed brands. A `0%` reads as *not detected in a 100-comment sample*, never as *absent*. The 16 bb/h values sum to 0.847, the category's 0.85. Full rows in [subreddit-measurements.csv](data/subreddit-measurements.csv).</sup>

**Evidence corpus only, never scored:** r/salesforce (113,705), r/hubspot (22,278), r/gohighlevel (23,004) and r/Zoho (12,658) are vendor subs. r/SaaS, r/smallbusiness and r/Entrepreneur are hostile — their own rules delete the brand mentions we came for.

r/salesforce alone measured 1.35 bb/h, more than the 16 scorable subs combined at 0.847. That single exclusion costs CRM more yield than every generalist sub supplies, and it is exactly the trade the comparability rule makes.

### The widening pass, and what it proves

CRM's list was 13 measured candidates, of which 6 were scorable generalist subs — one above the floor. Ten more generalist practitioner subs were probed on 2026-08-05 and **all ten came back scorable**, lifting CRM to 16.

Across the whole study the same pass added 24 subreddits: 18 scorable, 6 hostile, **0 vendor**. Total scorable rose from 44 to 62, and floor-passing categories from 4 to 12.

**Small focused practitioner subs beat large ones.** Inside CRM, r/SalesOperations (18,487) measured 6% brand-bearing and r/revops (6,593) measured 5%, while r/startups (2.1M) and r/sales (594K) both measured 0%. The densest scorable subreddit in the entire study is r/PasswordManagers at 42% on 54,640 subscribers.

### CRM now has margin, and that matters for G3

Sixteen scorable subs against a floor of five means the category survives its two open classification calls rather than dying on either:

- **r/CRM's rule posture came back `unknown`** — the rules endpoint returned nothing parseable. Read those rules by hand before ingest. It is the densest scorable sub in the set at 12%, so losing it costs yield, not the floor.
- **r/revops is also `unknown`.** Seven of the 62 scorable subs carry an unknown posture and six more are `capped`; all thirteen need a manual read before ingest.

### Why CRM and not Password Managers

Password Managers / Security was the earlier candidate ([subreddit map](04-subreddit-mapping.md)). After widening it clears the floor at **7 scorable subs** and **0.57 bb/h**, so it is no longer disqualified — it is simply second.

CRM wins on both axes that Phase 0 tests: more than double the scorable subreddits (16 vs 7) and 1.5× the live yield (0.85 vs 0.57). Password Managers is the natural fallback subject if CRM fails on something category-specific rather than on method.

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

G2 is now the tighter risk on CRM, not G3. Sixteen subs leave the `distinct subreddits ≥5` clause easy to satisfy, but generalist-only retains 9% of the volume, so whether ten brands reach `n_eff ≥ 400` is genuinely open. **That is inference from the retention share, not a measured result** — nothing in this study counted mentions per brand.

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

### The first tranche: the twelve categories that pass the floor

Ship these first, because their generalist subreddit sets are measured and sufficient today ([category tests](data/category-tests-20.csv)):

| Category | Candidates | Vendor | Hostile | Scorable | Live bb/h | 3y point est. |
|---|---:|---:|---:|---:|---:|---:|
| CRM | 23 | 4 | 3 | 16 | 0.85 | 22,259 |
| Project Management | 18 | 5 | 6 | 10 | 0.29 | 7,726 |
| Applicant Tracking and Recruiting | 11 | 0 | 3 | 8 | 0.14 | 3,652 |
| Marketing Automation | 14 | 2 | 4 | 7 | 0.08 | 2,128 |
| Password Managers and Security | 15 | 4 | 4 | 7 | 0.57 | 15,111 |
| ERP | 13 | 4 | 4 | 7 | 0.10 | 2,733 |
| HR and HRIS | 10 | 0 | 4 | 6 | 0.21 | 5,439 |
| Email Marketing | 14 | 4 | 5 | 6 | 0.10 | 2,706 |
| Cloud Hosting and Infrastructure | 12 | 4 | 2 | 6 | 0.14 | 3,652 |
| Backup and Storage | 9 | 2 | 1 | 6 | 0.54 | 14,191 |
| Help Desk and Customer Support | 10 | 3 | 2 | 5 | 0.00 | 0 |
| Team Collaboration and Chat | 8 | 2 | 3 | 5 | 0.14 | 3,652 |

The other 38 ship behind them, as their entry gates clear.

**Two entries in that table carry a warning.** Help Desk clears the floor on count while measuring **0.00 bb/h** across its five scorable subs — it passes the structural gate and fails the yield question, and its 95% upper bound of 3.89 bb/h is the only reason it is not written off. Team Collaboration and Chat sits exactly on the floor at 5, with no margin for a single reclassification.

### Business Intelligence dropped out, and that is the rule working

Business Intelligence and Analytics was in the previous first tranche at 6 scorable subs. Under generalist-only it measures **4** and fails the floor. Four of its nine candidates are vendor subs: r/PowerBI, r/tableau, r/SQL and r/MicrosoftFabric.

Those four carried 1.36 of the category's measured bb/h. A ranking built on them would have scored Microsoft's products inside Microsoft's own communities and called the result a market view. **This is the exact error the exclusion rule exists to prevent**, and it was live in the plan until the rule was applied.

### Phase 1 entry work

Two items, each with its own gate, both before anything goes live.

**1. Widen the candidate lists for the 8 below-floor categories.** This is now costed work with a measured yield, not a hope: the 2026-08-05 pass probed 24 generalist practitioner subs and returned 18 scorable, 0 vendor, taking floor-passing categories from 4 to 12.

| Still failing | Candidates | Vendor | Hostile | Scorable |
|---|---:|---:|---:|---:|
| Note-taking and Knowledge Management | 17 | 6 | 11 | 4 |
| Design and Prototyping | 12 | 4 | 6 | 4 |
| Business Intelligence and Analytics | 9 | 4 | 1 | 4 |
| Payroll | 10 | 0 | 6 | 4 |
| Accounting | 11 | 2 | 6 | 3 |
| Video Editing | 14 | 5 | 7 | 3 |
| eCommerce Platforms | 13 | 5 | 7 | 3 |
| Payment Processing | 11 | 3 | 6 | 3 |

**Hostility now dominates the remaining failures, not vendor exclusion.** Note-taking has 11 hostile subs out of 17 candidates; Payroll has 6 of 10 with zero vendor subs at all. Widening works against short lists. It does not work against a category whose practitioner communities delete brand talk by rule.

> **Gate:** every one of the 50 either reaches ≥5 scorable generalist subreddits, or ships labeled *insufficient Reddit signal to rank* with the reason named — short candidate list, or rule hostility. The evidence supports a count failure, never a claim of absent discussion.

**2. Build the crosswalk, then map what is left.** 8 of the 50 Phase 1 rows are mapped; 42 are pending ([phase1-categories.csv](data/phase1-categories.csv)). Separately, 20 categories were probed, of which only 8 join the Phase 1 taxonomy by exact label. **These are different label sets and no crosswalk ships yet**, so the two counts cannot be added together and the 12 floor-passing labels do not map cleanly onto 12 of the 50 rows.

> **Gate:** all 50 carry a resolved candidate list with rule posture and vendor status read live, and the 15 `unknown` rule postures are resolved by hand.

**Dedupe before scheduling.** Ingest is per-subreddit, not per-category. The **254 candidate slots** across the 20 measured categories collapse to **156 unique subreddits**, and r/startups alone serves 9 categories — skip the dedupe and ~39% of calls re-fetch the same comment streams.

### Phase 1 ship checklist

Every box is green before the domain resolves publicly. These are build requirements, and the reasoning behind them — including the two risks the owner priced and accepted — is in [01-legal.md](01-legal.md).

- [ ] Phase 0 passed G1–G5, with intervals published rather than point estimates alone.
- [ ] Nightly delete-sync runs and is verified against a seeded set of deleted, removed, and edited items.
- [ ] Every mention renders permalink + username + "from Reddit."
- [ ] Removal route live: free, fast, no questions, no sales offer attached, reachable from every brand page.
- [ ] `/methodology` published, frozen, and version-controlled **before** the first scoring run — never adjusted after seeing where a company landed, in either direction.
- [ ] `/methodology` states the generalist-only rule, names the comparability reason, and publishes the 9% retention cost rather than burying it.
- [ ] Non-affiliation notice in the footer of every page.
- [ ] Zero ads anywhere on the domain, and no Reddit trade dress: no `#FF4500`, no Snoo, no Reddit Sans, no lookalike mark ([design](09-design.md)).
- [ ] Plain-text company names, no logos, and the measured variable printed beside every superlative ([0005](decisions/0005-superlative-labels.md)).
- [ ] Defensive `redditbrandindex.com` registered and redirecting to the primary.
- [ ] Canonical host in exactly one config value, every internal link relative, so a forced move costs a day rather than a quarter.
- [ ] Corrections desk staffed, with the SLA published on the site.

**The earlier ERP verdict is overturned.** ERP was written off at 3 scorable subs. The widened probe measures **7** and it clears the floor, at 0.10 bb/h and a 3-year point estimate of 2,733 — low, but rankable. Four of its 13 candidates are vendor subs (r/SAP, r/Netsuite, r/Odoo, r/Dynamics365) and they carried most of its density.

**What is not costed yet.** **42 of the 50 categories have no subreddit mapping.** Any Phase 1 estimate produced before that mapping lands is guesswork.

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

The generalist-only rule compounds here. Vendor subs are a larger share of the candidate pool in narrow long-tail categories than in broad ones, so retention below 9% should be expected as the taxonomy widens. **That is inference from the shape of the 20-category sample, not a measurement of the tail.**

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

A second source adds its own terms surface and its own ship checklist. It removes nothing from Phase 1's. The generalist-only rule travels with it: a vendor-run forum on any platform is excluded on the same reasoning.

---

## The cheaper alternative

Presented fairly, as the fallback if Phase 0 fails. The owner has chosen the full build.

**Shape:** one dated, positive-only study across the twelve floor-passing categories ([category tests](data/category-tests-20.csv)) as a PDF with a fixed collection window, plus a free private per-prospect diagnostic sent only to the company it describes.

| | Full build | Cheap version |
|---|---|---|
| What it gets | Public leaderboard, standing SEO/AEO surface, brand pages | The same outreach hook, the same PR and citation value |
| Cost | Phase 0 bandwidth, then ~$74/mo plus audit labor, forever | Days of work on existing report skills ([outreach play](11-outreach-play.md)) |
| Corpus | Required | None |
| Recompute obligation | Daily, forever ([algorithm §7](13-algorithm.md)) | None — the study is dated and frozen |
| Corrections desk | Staffed in perpetuity | None |
| What it gives up | — | The public leaderboard, the live property, the compounding search asset |

A dated study could legitimately use vendor subs, since it makes no cross-brand ranking claim. That is the one thing the cheap version can do which the index cannot.

The one thing it cannot deliver is the thing Phase 1 exists for: a standing public property that ranks brands and keeps ranking them.

---

## Effort and cost per phase

| Phase | Elapsed | Build effort | Infra | Recurring human cost |
|---|---|---|---|---|
| **0** | 3–5 weeks | ~35h annotation + pipeline | Bandwidth + **<$50** for the phase | None (nothing published) |
| **1** | Not estimable until 42 categories are mapped and 8 candidate lists are widened | Site + 42 mappings + 8 widenings + corrections process | **≈ $74/mo** ([architecture §8](08-architecture.md)) | 75K–150K adjudicated labels per audit cycle at 50 categories, plus a staffed corrections desk |
| **2** | Not planned | — | **≈ $301/mo** at full scale ([architecture §8](08-architecture.md)) | 1.5M–3M labels per audit cycle — the number that breaks it |
| **3** | Not planned | Second-source ingest, plus a rename or a second brand | Not estimated | Not estimated |

Both infra totals come from the line-item table in [08-architecture.md §8](08-architecture.md) and are the same figures the README carries. Inside them, only the ingest-worker line (Railway, or a Hetzner box) is secondary-sourced; verify it before committing. Every other line is a vendor-published price.

The label counts are per **audit** cycle, which is a human rhythm and not the publish rhythm. Daily publishing multiplies publish events, not adjudication volume: stages 5–8 classify only the delta since the last run, so total classified volume is unchanged ([algorithm §7](13-algorithm.md)).

Two one-time reviews sit outside every line above: an Estonian data-protection opinion and a US media-law read of the final page copy. **Neither is costed** — no figure for either appears anywhere in the research.

---

[← Back to README](README.md) · [00-concept.md](00-concept.md) · [08-architecture.md](08-architecture.md) · [14-category-tests.md](14-category-tests.md)
