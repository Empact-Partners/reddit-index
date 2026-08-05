# Category Tests — 20 categories, measured

What happened when the algorithm's subreddit-selection stage was run for real against 20 large, deliberately diverse software categories.

**Re-run 2026-08-05** · 254 candidate slots · 156 unique subreddits · **776 base Reddit API calls** (155 reachable subs × 5 endpoints + 1 that failed at the first call — the harness caches by subreddit, so duplicate slots are free)

## Bottom line

- **The binding constraint was always the candidate lists, and this re-run proves it.** Widening the lists with generalist practitioner subreddits took the study from 4 of 20 categories above the five-subreddit floor to **12 of 20** — under a *stricter* scoring rule, not a looser one.
- **Only generalist subreddits may score a brand.** Any subreddit named for, or dedicated to, one vendor or product is excluded outright. **56 of 156** measured subreddits are vendor subs.
- **54 of 155 reachable subreddits (34.8%) delete brand talk** by their own rules. Hostility, not the vendor rule, now dominates the categories that still fail.
- **62 of 156 subreddits are scorable** — generalist, reachable, and not hostile.
- **Generalist-only retains 9% of measured brand-bearing volume** (4.82 of 54.89 brand-bearing comments per hour). That is expensive and deliberate, bought for cross-brand comparability. It is not free, and the excluded data is the densest measured.
- **CRM is the Phase 0 subject.** 23 candidates, 4 vendor, 3 hostile, **16 scorable** generalist subs, 0.85 bb/h — the widest margin over the floor of any category.
- ⚠️ **This study cannot declare any category dead.** At the 95% upper bound, **all 20** clear the mention threshold. It is a floor instrument. Read §4 before quoting any "thin" verdict.

---

## 1. What was measured

For each of 254 candidate (category, subreddit) pairs:

| Measurement | Method |
|---|---|
| Subscribers, type, description | `/r/{sub}/about` |
| Rule posture | `/r/{sub}/about/rules`, classified by regex over the full rules text |
| Vendor sub | Whether the subreddit is named for or dedicated to one product or vendor |
| Live comment rate | `/r/{sub}/comments?limit=100` — rate derived from the span of one page |
| Brand-bearing share | Share of that page (up to 100 comments) containing any of 5 seed brands |
| Search discoverability | `/r/{sub}/search` for 2 seed brands, exact-alias verified locally |

Raw per-subreddit JSON, the harness, and both CSVs ship with this repo. The harness is resumable: it skips any subreddit already on disk, so a re-run costs only the gap.

| File | Rows | What |
|---|---:|---|
| **[subreddit-measurements.csv](data/subreddit-measurements.csv)** | 156 | Every unique subreddit, measured |
| **[category-tests-20.csv](data/category-tests-20.csv)** | 20 | Category rollup with bounds |
| [category-candidates-20.json](data/category-candidates-20.json) | 20 | The widened candidate lists and seed brands used |
| [probe.py](data/probe.py) | — | The harness. Re-run to refresh |

Collection and reuse constraints on this data: [01-legal.md](01-legal.md).

---

## 2. The rules finding

**54 of 155 reachable subreddits (34.8%) are hostile to brand mentions.** Their own rules remove promotional or product-mention content.

| Posture | Count | Meaning |
|---|---:|---|
| `permissive` | 79 | Organic brand discussion allowed |
| `hostile` | 54 | Brand/product mentions actively removed |
| `unknown` | 15 | Rules endpoint returned nothing parseable |
| `capped` | 7 | Allowed behind a karma gate or weekly thread |
| unreachable | 1 | r/B2BForSales returned no subreddit object |

This is why subscriber count is not in the selection score. The largest communities are disproportionately the strictest: r/Entrepreneur (5,249,043) and r/productivity (4,231,867), the two biggest subreddits in the study, both classify hostile.

`capped` and `unknown` still score — 49 permissive, 6 capped and 7 unknown subs make up the 62. `unknown` is a parsing failure, not a permission, and §8 keeps it on the list to resolve by hand.

---

## 3. Vendor subs vs generalist subs

This is the only community distinction that survives, and it is binary.

**56 of 156 measured subreddits (35.9%) are vendor subs** — named for or dedicated to a single product or vendor. Every one is disqualified from scoring. `scorable` = reachable AND not hostile AND not a vendor sub.

**The old `ecosystem` class is abolished.** It was a third bucket for vendor-named subs held to be full-market practitioner communities, and it was kept scorable. The line could not be drawn defensibly: r/salesforce was called ecosystem while r/SAP, r/Netsuite and r/Zoho were called single-product. They are the same kind of community. All four are now vendor subs.

**The old reasoning is retracted.** Earlier drafts justified exclusion by claiming product subs "self-select for invested users." That was never measured. Sentiment is not in this dataset at all, so no directional claim about vendor-sub bias is supportable in either direction — r/paypal is plausibly a support-seeking population, r/ObsidianMD an enthusiast one.

**The real reason is cross-brand comparability.** A brand with a large active home subreddit would gain a structural advantage over a competitor with a small one or none. Rank would then partly measure community size — the same confound the index already rejects for raw mention counts. A ranking table has to stand on neutral ground.

**The cost is large and we state it plainly.** Vendor subs carry **76.5%** of all measured brand-bearing volume (41.98 of 54.89 bb/h). Generalist-only keeps **8.8%**. The excluded data is the densest measured, not the weakest.

Vendor subs stay usable as **evidence** on a brand's own page, and for that brand's trajectory against its own baseline, where cross-brand comparability does not apply. They never enter a ranking.

---

## 4. ⚠️ What this study cannot tell you

**The instrument is a subreddit inventory, not a category verdict.** Three limits, each of which biases toward under-measuring:

**One page is a small sample, and not always a full one.** Pages return *up to* 100 comments. **154 of 155 returned a full 100**; the exception is r/talentacquisition at 24. Against a subreddit with 0.5% brand density, 100 comments has an expected count of 0.5 hits. Measuring zero there is uninformative.

Where a category shows `0.0` live yield, the honest statement is *not detected in the sample*, never *absent*. Each subreddit's upper bound uses its own actual page size `n`.

**Five seed brands, not the real gazetteer.** Each category was probed with 5 brands. Real gazetteers run 20-100, so every yield figure here is a **floor**, understated by roughly the ratio of the lists.

**The measurement window varies by four orders of magnitude.** One page spans 0.58h in r/recruitinghell and 28,823.44h — 3.3 years — in r/talentacquisition, which is also the 24-comment page. The same instrument measures "this hour" in one sub and "this presidency" in another.

So the table reports both a point estimate and a **95% upper bound** (rule-of-three where the count was zero). The upper bound is what the data cannot rule out.

| Category | Candidates | Vendor | Hostile | Scorable | Live bb/h | 3y point est. | 3y upper bound | 5-sub floor |
|---|---:|---:|---:|---:|---:|---:|---:|:--|
| CRM | 23 | 4 | 3 | **16** | 0.85 | 22,259 | 116,689 | ✅ |
| Project Management | 18 | 5 | 6 | **10** | 0.29 | 7,726 | 198,037 | ✅ |
| Applicant Tracking and Recruiting | 11 | 0 | 3 | **8** | 0.14 | 3,652 | 249,729 | ✅ |
| Password Managers and Security | 15 | 4 | 4 | **7** | 0.57 | 15,111 | 166,360 | ✅ |
| ERP | 13 | 4 | 4 | **7** | 0.10 | 2,733 | 108,299 | ✅ |
| Marketing Automation | 14 | 2 | 4 | **7** | 0.08 | 2,128 | 27,645 | ✅ |
| Backup and Storage | 9 | 2 | 1 | **6** | 0.54 | 14,191 | 179,474 | ✅ |
| HR and HRIS | 10 | 0 | 4 | **6** | 0.21 | 5,439 | 184,474 | ✅ |
| Cloud Hosting and Infrastructure | 12 | 4 | 2 | **6** | 0.14 | 3,652 | 169,573 | ✅ |
| Email Marketing | 14 | 4 | 5 | **6** | 0.10 | 2,706 | 28,659 | ✅ |
| Team Collaboration and Chat | 8 | 2 | 3 | **5** | 0.14 | 3,652 | 115,875 | ✅ |
| Help Desk and Customer Support | 10 | 3 | 2 | **5** | 0.00 | 0 | 102,168 | ✅ |
| Design and Prototyping | 12 | 4 | 6 | **4** | 1.08 | 28,356 | 114,903 | ❌ |
| Business Intelligence and Analytics | 9 | 4 | 1 | **4** | 0.84 | 22,075 | 48,777 | ❌ |
| Payroll | 10 | 0 | 6 | **4** | 0.07 | 1,787 | 60,210 | ❌ |
| Note-taking and Knowledge Management | 17 | 6 | 11 | **4** | 0.03 | 735 | 58,058 | ❌ |
| Video Editing | 14 | 5 | 7 | **3** | 0.34 | 8,882 | 44,026 | ❌ |
| Accounting | 11 | 2 | 6 | **3** | 0.01 | 367 | 26,056 | ❌ |
| eCommerce Platforms | 13 | 5 | 7 | **3** | 0.00 | 0 | 20,049 | ❌ |
| Payment Processing | 11 | 3 | 6 | **3** | 0.00 | 105 | 16,837 | ❌ |

<sup>`bb/h` = brand-bearing comments per hour summed across that category's scorable subs, 5 seed brands. `3y` projects the live rate across a 3-year archive window — a projection, not a count. Upper bound is the 95% one-sided limit on brand density given each page's actual size, rule-of-three where the observed count was zero. Vendor and hostile columns count candidate slots and can overlap.</sup>

**16 of 20 clear 400 seed-brand mentions on the point estimate. All 20 clear it at the upper bound.** The mention threshold is not what fails here — the subreddit floor is.

---

## 5. The finding that actually matters

**Widening the candidate lists moved the study from 4 of 20 categories above the floor to 12 of 20 — while the scoring rule got stricter.** Nothing about Reddit changed between the two runs. Only our lists did.

That settles the question the first run left open. The floor failures were never evidence about Reddit's opinion volume, and they were never caused by the exclusion rule. They were caused by candidate lists that were too short and too concentrated on product communities.

<sup>The 4-of-20 figure comes from the pre-widening run and is not in the shipped CSVs. Replaying the old 187-slot lists against today's measurements gives 3 of 20 — the direction and magnitude hold either way.</sup>

The floor exists for a real reason: [07-index-methodology.md](07-index-methodology.md) requires each ranked brand to appear across ≥5 subreddits, so a category with 4 scorable subs cannot satisfy its own diversity floor.

**CRM is the demonstration.** Its list grew from 11 candidates to 23. All 12 added subreddits are generalist and scorable, taking CRM from 4 scorable subs to **16** — from failing the floor to clearing it three times over.

The additions are ordinary practitioner subs: r/revops, r/SalesOperations, r/salesdevelopment, r/B2BSaaS, r/msp, r/consulting, r/agency, r/PPC, r/RealEstateTechnology, r/InsuranceAgent, r/smallbusinessuk, r/startups.

**Small focused subs beat large ones.** Among scorable subs, r/PasswordManagers (54,640 subscribers) measured **42%** brand-bearing, the highest generalist figure in the study. r/startups (2,107,067) and r/recruitinghell (1,437,876) both measured **0%**. Size predicts nothing; specificity does.

---

## 6. Where the signal actually concentrates

The densest brand discussion per hour, across all 156 measured subreddits:

| Subreddit | Subscribers | Comments/h | Brand-bearing | bb/h | Vendor sub | Scorable |
|---|---:|---:|---:|---:|:--|:--|
| r/ObsidianMD | 350,730 | 63.03 | 21% | 13.236 | yes | ❌ |
| r/paypal | 103,008 | 6.43 | 50% | 3.215 | yes | ❌ |
| r/Notion | 466,690 | 8.19 | 33% | 2.703 | yes | ❌ |
| r/FinancialCareers | 1,762,260 | 25.82 | 7% | 1.807 | no | ❌ hostile |
| r/SAP | 60,641 | 3.21 | 49% | 1.573 | yes | ❌ |
| r/CapCut | 98,523 | 4.78 | 32% | 1.53 | yes | ❌ |
| r/Bitwarden | 119,768 | 3.89 | 37% | 1.439 | yes | ❌ |
| r/synology | 199,249 | 6.43 | 22% | 1.415 | yes | ❌ |
| r/salesforce | 113,705 | 4.5 | 30% | 1.35 | yes | ❌ |
| r/premiere | 184,980 | 5.79 | 21% | 1.216 | yes | ❌ |

**None of the top 10 is scorable.** Nine are vendor subs; the tenth is generalist and hostile. That is the structural tension of the whole product, and the generalist-only rule makes it total rather than near-total. Everything the index publishes comes from the thinner, harder middle.

The thinner middle, ranked on its own terms — the densest **scorable** subs:

| Subreddit | Subscribers | Comments/h | Brand-bearing | bb/h | Posture |
|---|---:|---:|---:|---:|---|
| r/UXDesign | 245,287 | 8.25 | 12% | 0.99 | permissive |
| r/analytics | 277,313 | 12.76 | 6% | 0.766 | permissive |
| r/CRM | 55,275 | 5.56 | 12% | 0.667 | unknown |
| r/PasswordManagers | 54,640 | 1.37 | 42% | 0.575 | unknown |
| r/DataHoarder | 986,173 | 26.99 | 2% | 0.54 | permissive |
| r/editors | 193,221 | 5.34 | 5% | 0.267 | permissive |
| r/agile | 86,947 | 7.77 | 2% | 0.155 | permissive |
| r/ExperiencedDevs | 408,386 | 13.87 | 1% | 0.139 | permissive |
| r/Emailmarketing | 121,660 | 1.03 | 10% | 0.103 | permissive |
| r/Frontend | 347,264 | 0.99 | 9% | 0.089 | permissive |

These 10 subs carry 4.29 of the 4.82 total scorable bb/h — **89% of all scorable signal sits in 10 of the 62 scorable subreddits.** Losing any one of them measurably thins a category, which is an argument for widening lists further, not for relaxing the rule.

---

## 7. Ingest overlap

**254 candidate slots collapse to 156 unique subreddits — 38.6% fewer fetches.** Thirty-six subreddits serve more than one category:

| Subreddit | Categories served |
|---|---:|
| r/startups | 9 |
| r/smallbusiness | 7 |
| r/Entrepreneur | 7 |
| r/msp | 7 |
| r/consulting | 7 |
| r/agency | 7 |
| r/sysadmin | 7 |
| r/ITManagers | 6 |

Ingest is per-subreddit, not per-category, so **the ingest set must be deduplicated before scheduling** or a third of the calls re-fetch the same comment streams. Widening the lists increased the overlap rather than reducing it, so the saving grows with the taxonomy.

Note that r/smallbusiness and r/Entrepreneur are hostile and score nothing, yet both are still worth ingesting as context. Ingest membership and scoring eligibility are separate decisions.

---

## 8. What to do before Phase 1

**Eight categories still sit below the floor**, and hostility now dominates the failures rather than the vendor rule. Across the 12 passing categories, 26.1% of candidate slots are hostile. Across the 8 failing ones, **51.5%** are.

| Still failing | Scorable | Hostile / candidates | The shape of the problem |
|---|---:|---|---|
| Design and Prototyping | 4 | 6 / 12 | Hostile and vendor split evenly |
| Business Intelligence and Analytics | 4 | 1 / 9 | Was carried entirely by vendor subs |
| Payroll | 4 | 6 / 10 | Zero vendor subs — pure hostility |
| Note-taking and Knowledge Management | 4 | 11 / 17 | Worst hostility rate in the study |
| Video Editing | 3 | 7 / 14 | Hostile NLE and craft communities |
| Accounting | 3 | 6 / 11 | Large hostile professional subs |
| eCommerce Platforms | 3 | 7 / 13 | Hostile plus 5 vendor subs |
| Payment Processing | 3 | 6 / 11 | Hostile plus 3 vendor subs |

**Business Intelligence dropped from passing to failing** under the generalist-only rule. It was held up by r/PowerBI, r/tableau, r/SQL and r/MicrosoftFabric, all now vendor subs. Its four remaining scorable subs are r/analytics, r/dataengineering, r/datascience and r/dataanalysis.

Then the work, in order:

1. **Widen the eight failing lists using the method CRM demonstrated.** One focused pass of generalist practitioner subreddits per category, probed and measured, not guessed. That single technique is what produced the 4 → 12 result.
2. **Note-taking is the hard case.** 11 of 17 candidates are hostile and its 4 scorable subs (r/Zettelkasten, r/students, r/GradSchool, r/writing) are adjacent communities rather than tool-comparison venues. It may need a different candidate strategy entirely, not a longer list.
3. **Re-run the probe with the full gazetteer**, not 5 seed brands, and over multiple pages per subreddit so the small-sample problem goes away.
4. **Resolve the 15 `unknown` rule postures** by reading those subreddits' rules manually. Seven of them currently score, including r/CRM and r/PasswordManagers — two of the four densest scorable subs in the study.
5. **Ship CRM first.** It clears the floor by the widest margin (16 scorable subs against a floor of 5), carries the highest live yield of any passing category at 0.85 bb/h, and its 3-year point estimate of 22,259 is far above threshold. [12-phasing.md](12-phasing.md) already specifies CRM; this evidence strengthens rather than changes that.

---

[← Back to README](README.md) · [The algorithm](13-algorithm.md) · [Subreddit mapping](04-subreddit-mapping.md) · [Index methodology](07-index-methodology.md)
