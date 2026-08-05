# Category Tests — 20 categories, measured

What happened when the algorithm's subreddit-selection stage was run for real against 20 large, deliberately diverse software categories.

**Re-run 2026-08-05** · 347 candidate slots · 232 unique subreddits · discovery-widened and signal-verified

## Bottom line

- **The binding constraint was always the candidate lists.** Discovery widened them rather than hand-picking additions: eight topical `/subreddits/search` seed queries per category produced 3,526 new candidates, and a one-call live screen of the 562 best-ranked candidates promoted only subreddits with at least one brand-bearing comment.
- **All 20 categories now clear the five-subreddit floor.** That is a statement about the widened, measured lists, not a triumphant claim about Reddit or about any category's eventual rankability.
- **Only generalist subreddits may score a brand.** Any subreddit named for, or dedicated to, one vendor or product is excluded outright. **50 of 232** measured subreddits are vendor subs.
- **56 of 231 reachable subreddits delete brand talk** by their own rules. Hostility is a separate reason a generalist sub cannot score.
- **125 of 232 subreddits are scorable** — generalist, reachable, and not hostile.
- **The five-subreddit floor does not make a category rankable.** Every brand still has to clear its assigned per-brand `n_eff` threshold and all four diversity floors. This study has no brand-level data yet.
- ⚠️ **This study cannot declare a category deep, thin, or dead in the publishing sense.** Its new category tiers are provisional estimates from category-level comment flow. Read §4 before treating them as per-brand evidence.

---

## 1. What was measured

For each candidate (category, subreddit) pair, discovery started with eight topical `/subreddits/search` queries per category. The search produced 3,526 new candidates; the 562 best-ranked received a cheap one-call screen, and only a live brand-bearing signal promoted a candidate into the measured lists.

| Measurement | Method |
|---|---|
| Subscribers, type, description | `/r/{sub}/about` |
| Rule posture | `/r/{sub}/about/rules`, classified by regex over the full rules text |
| Vendor sub | Derived from the brand gazetteer plus per-category seed brands, token-matched against the subreddit name |
| Live comment rate | `/r/{sub}/comments?limit=100` — rate derived from the span of one page |
| Brand-bearing share | Share of that page containing the gazetteer's low-ambiguity probe terms |
| Search discoverability | `/r/{sub}/search` for probe terms, exact-alias verified locally |

Raw per-subreddit JSON, the harness, and both CSVs ship with this repo. The harness is resumable: it skips any subreddit already on disk, so a re-run costs only the gap.

| File | Rows | What |
|---|---:|---|
| **[subreddit-measurements.csv](data/subreddit-measurements.csv)** | 232 | Every unique subreddit, measured |
| **[category-tests-20.csv](data/category-tests-20.csv)** | 20 | Category rollup, bounds, and provisional tiers |
| [category-candidates-20.json](data/category-candidates-20.json) | 20 | Candidate-list and seed-brand input |
| [analyze.py](data/analyze.py) | — | Regenerates the CSV outputs from raw probe output |
| [probe.py](data/probe.py) | — | The harness. Re-run to refresh |

Collection and reuse constraints on this data: [01-legal.md](01-legal.md).

---

## 2. The rules finding

**56 reachable, non-vendor subreddits are hostile to brand mentions.** Their own rules remove promotional or product-mention content, so they never score.

| Posture | Count | Meaning |
|---|---:|---|
| `permissive` | 120 | Organic brand discussion allowed |
| `hostile` | 72 | Brand/product mentions actively removed; 56 are non-vendor and therefore a distinct scoring exclusion |
| `unknown` | 28 | Rules endpoint returned nothing parseable |
| `capped` | 11 | Allowed behind a karma gate or weekly thread |
| unreachable | 1 | Returned no subreddit object |

This is why subscriber count is not in the selection score. The largest communities can still be the strictest, so size is not evidence that a community can carry an unbiased brand sample.

`capped` and `unknown` still score — 93 permissive, 10 capped, and 22 unknown subs make up the 125. `unknown` is a parsing failure, not a permission, and §8 keeps it on the list to resolve by hand.

---

## 3. Vendor subs vs generalist subs

This is the only community distinction that survives, and it is binary.

**50 of 232 measured subreddits are vendor subs** — named for or dedicated to a single product or vendor. Every one is disqualified from scoring. `scorable` = reachable AND not hostile AND not a vendor sub.

**The old `ecosystem` class is abolished.** It was a third bucket for vendor-named subs held to be full-market practitioner communities, and it was kept scorable. The line could not be drawn defensibly: product communities are product communities.

**The old reasoning is retracted.** Earlier drafts justified exclusion by claiming product subs "self-select for invested users." That was never measured. Sentiment is not in this dataset at all, so no directional claim about vendor-sub bias is supportable in either direction.

**The real reason is cross-brand comparability.** A brand with a large active home subreddit would gain a structural advantage over a competitor with a small one or none. Rank would then partly measure community size — the same confound the index already rejects for raw mention counts. A ranking table has to stand on neutral ground.

**The cost is large and we state it plainly.** Vendor subs carry 41.28 of 81.93 measured brand-bearing comments per hour. Generalist, scorable subs retain 26.45 comments per hour. The excluded data is not necessarily weak; it is simply ineligible for a cross-brand ranking.

Vendor subs stay usable as **evidence** on a brand's own page, and for that brand's trajectory against its own baseline, where cross-brand comparability does not apply. They never enter a ranking.

---

## 4. ⚠️ What this study cannot tell you

**The instrument is a subreddit inventory, not a category verdict.** Three limits, each of which biases toward under-measuring:

**One page is a small sample, and not always a full one.** Pages return *up to* 100 comments. **230 of 231 reachable subreddits returned a full 100**; the exception is r/talentacquisition at 24. Against a subreddit with 0.5% brand density, 100 comments has an expected count of 0.5 hits. Measuring zero there is uninformative.

Where a category shows `0.0` live yield, the honest statement is *not detected in the sample*, never *absent*. Each subreddit's upper bound uses its own actual page size `n`.

**The probe is not the real per-brand gazetteer.** It uses low-ambiguity probe terms to screen live pages. The eventual gazetteer will be broader, so every yield figure here is a **floor**, not a publication count.

**The measurement window varies enormously.** One page spans 0.58h in r/recruitinghell and 72,797.87h in r/academia. The same instrument can measure "this hour" in one sub and years of history in another.

So the table reports both a point estimate and a **95% upper bound** (rule-of-three where the count was zero). The upper bound is what the data cannot rule out. It is still a category-level estimate, not a count of eligible evidence for any individual brand.

The table is sorted by scorable subreddits, descending; ties use the 3-year point estimate, descending.

| Category | Candidates | Vendor | Hostile | Scorable | Live bb/h | 3y point est. | 3y upper bound | Tier | Precision | `n_min` | 5-sub floor |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|:--|
| CRM | 26 | 4 | 5 | **17** | 0.96 | 25,224 | 102,928 | deep | ±4 pp | 600 | ✅ |
| Design and Prototyping | 26 | 3 | 7 | **16** | 2.05 | 53,948 | 124,241 | deep | ±4 pp | 600 | ✅ |
| Cloud Hosting and Infrastructure | 18 | 0 | 3 | **15** | 0.57 | 14,964 | 274,213 | standard | ±5 pp | 400 | ✅ |
| Business Intelligence and Analytics | 18 | 3 | 1 | **14** | 2.37 | 62,412 | 71,850 | deep | ±4 pp | 600 | ✅ |
| Marketing Automation | 22 | 2 | 6 | **13** | 0.89 | 23,360 | 47,138 | deep | ±4 pp | 600 | ✅ |
| Team Collaboration and Chat | 18 | 2 | 4 | **12** | 12.25 | 321,854 | 477,713 | deep | ±4 pp | 600 | ✅ |
| Project Management | 20 | 5 | 4 | **11** | 0.36 | 9,332 | 186,840 | standard | ±5 pp | 400 | ✅ |
| Video Editing | 23 | 4 | 9 | **10** | 2.19 | 57,514 | 86,968 | deep | ±4 pp | 600 | ✅ |
| Password Managers and Security | 19 | 4 | 5 | **10** | 1.13 | 29,657 | 187,495 | deep | ±4 pp | 600 | ✅ |
| Backup and Storage | 12 | 3 | 1 | **8** | 0.71 | 18,627 | 175,440 | standard | ±5 pp | 400 | ✅ |
| Applicant Tracking and Recruiting | 11 | 0 | 3 | **8** | 0.14 | 3,645 | 242,585 | thin | ±7 pp | 200 | ✅ |
| Email Marketing | 17 | 3 | 6 | **8** | 0.11 | 2,875 | 30,548 | thin | ±7 pp | 200 | ✅ |
| Note-taking and Knowledge Management | 21 | 6 | 8 | **7** | 0.66 | 17,395 | 74,317 | standard | ±5 pp | 400 | ✅ |
| Accounting | 16 | 2 | 7 | **7** | 0.34 | 8,870 | 34,153 | standard | ±5 pp | 400 | ✅ |
| ERP | 13 | 4 | 2 | **7** | 0.10 | 2,738 | 104,600 | thin | ±7 pp | 200 | ✅ |
| Payment Processing | 16 | 4 | 6 | **6** | 4.71 | 123,697 | 140,364 | deep | ±4 pp | 600 | ✅ |
| HR and HRIS | 10 | 0 | 4 | **6** | 0.21 | 5,419 | 175,776 | standard | ±5 pp | 400 | ✅ |
| eCommerce Platforms | 19 | 5 | 8 | **6** | 0.18 | 4,720 | 24,769 | thin | ±7 pp | 200 | ✅ |
| Help Desk and Customer Support | 11 | 3 | 2 | **6** | 0.17 | 4,468 | 106,636 | thin | ±7 pp | 200 | ✅ |
| Payroll | 11 | 0 | 6 | **5** | 0.13 | 3,416 | 60,299 | thin | ±7 pp | 200 | ✅ |

<sup>`bb/h` = brand-bearing comments per hour summed across that category's scorable subs. `3y` projects the live rate across a 3-year archive window — a projection, not a count. Upper bound is the 95% one-sided limit on brand density given each page's actual size, rule-of-three where the observed count was zero. Vendor and hostile columns count candidate slots.</sup>

### Provisional category-scaled tiers

The tier assignment is mechanical from the estimated 3-year brand-bearing volume across a category's scorable generalist subs: **deep** at or above 20,000 (`±4 pp`, `n_min` 600), **standard** at or above 5,000 (`±5 pp`, `n_min` 400), and **thin** below 5,000 (`±7 pp`, `n_min` 200). The re-run assigns eight categories deep, six standard, and six thin.

These cut points are round, stated, and **provisional**. This study measures category-level comment flow, not per-brand `n_eff`; Phase 0 must confirm every tier against real per-brand `n_eff` before anything publishes. [Decision 0009](decisions/0009-category-scaled-thresholds.md) records the threshold rule and the diversity floors that do not scale.

**A category clearing five scorable subreddits is not thereby rankable.** Every individual brand still needs eligible evidence at its tier's `n_min` and must pass all four diversity floors. No brand-level eligibility data exists in this study.

---

## 5. The finding that actually matters

### Method correction: substring matching made false positives

The first screen matched brand names as substrings. It therefore surfaced r/nfl and r/rugbyunion for Project Management (`Monday` the weekday), r/worldbuilding for ERP (`SAP` the fluid), and r/baseball for HR (`Rippling`, `Workday`). Word-boundary matching plus a restriction to the gazetteer's low-ambiguity brands fixed it. This is a live confirmation of the ambiguity classes [05-entity-resolution.md](05-entity-resolution.md) defines.

### Method correction: hand-written vendor regex missed product communities

Hand-written vendor detection silently scored r/ObsidianMD, r/logseq, and r/Anytype as generalist. Note-taking's estimated 3-year brand-bearing volume was 369,652 with those communities and 17,395 without them: the category was being carried almost entirely by its own product communities.

Vendor detection is now derived from the brand gazetteer plus per-category seed brands and token-matched against the subreddit name, rather than hand-maintained. An intermediate prefix test called r/Frontend a vendor sub because `Front` is its prefix; token splitting fixed that too.

### The binding constraint remains the lists

**Widening the candidate lists is what brought every category above the floor.** Nothing in a five-subreddit result demonstrates that Reddit contains enough per-brand evidence to rank; it demonstrates only that the discovery-and-screening process found at least five scorable generalist communities for each category.

That distinction matters. The earlier failures were never evidence about Reddit's opinion volume, and they were not evidence that the exclusion rule was wrong. They were evidence that candidate lists were too short and too concentrated on product communities.

The inventory floor remains one part of the [index methodology](07-index-methodology.md), not a substitute for its per-brand evidence and diversity gates.

**CRM is the clearest inventory example.** Its current list has 26 candidate slots and 17 scorable generalist subreddits. That makes it a useful Phase 0 test case, not proof that every CRM brand is eligible.

**Small focused subs can beat large ones.** Among scorable subs, r/PasswordManagers (54,640 subscribers) measured 42% brand-bearing, while r/startups (2,107,067) and r/recruitinghell (1,437,876) measured 0%. Size predicts nothing; specificity does.

---

## 6. Where the signal actually concentrates

The densest brand discussion per hour, across all 232 measured subreddits, sorted by `bb/h` descending:

| Subreddit | Subscribers | Comments/h | Brand-bearing | bb/h | Vendor sub | Scorable |
|---|---:|---:|---:|---:|:--|:--|
| r/ObsidianMD | 350,730 | 63.03 | 21% | 13.236 | yes | ❌ |
| r/UkrainianConflict | 486,840 | 50.43 | 12% | 6.052 | no | ✅ |
| r/Superstonk | 1,199,123 | 168.83 | 2% | 3.377 | no | ✅ |
| r/paypal | 103,008 | 6.43 | 50% | 3.215 | yes | ❌ |
| r/PersonalFinanceCanada | 1,870,254 | 68.12 | 4% | 2.725 | no | ✅ |
| r/Notion | 466,690 | 8.19 | 33% | 2.703 | yes | ❌ |
| r/IndianWorkplace | 132,737 | 9.52 | 20% | 1.904 | no | ❌ hostile |
| r/buhaydigital | 491,386 | 26.57 | 7% | 1.860 | no | ✅ |
| r/FinancialCareers | 1,762,260 | 25.82 | 7% | 1.807 | no | ❌ hostile |
| r/SAP | 60,641 | 3.21 | 49% | 1.573 | yes | ❌ |

**Four of the top 10 are scorable.** The rest are vendor communities or hostile generalist communities. Eligibility still trades coverage for comparability; the study does not hide that cost.

The scorable middle, sorted by `bb/h` descending:

| Subreddit | Subscribers | Comments/h | Brand-bearing | bb/h | Posture |
|---|---:|---:|---:|---:|---|
| r/UkrainianConflict | 486,840 | 50.43 | 12% | 6.052 | permissive |
| r/Superstonk | 1,199,123 | 168.83 | 2% | 3.377 | capped |
| r/PersonalFinanceCanada | 1,870,254 | 68.12 | 4% | 2.725 | permissive |
| r/buhaydigital | 491,386 | 26.57 | 7% | 1.860 | permissive |
| r/UXDesign | 245,287 | 8.25 | 12% | 0.990 | permissive |
| r/developersIndia | 1,579,180 | 89.12 | 1% | 0.891 | permissive |
| r/analytics | 277,313 | 12.76 | 6% | 0.766 | permissive |
| r/AfterEffects | 344,708 | 14.18 | 5% | 0.709 | permissive |
| r/VideoEditor_forhire | 75,216 | 7.57 | 9% | 0.681 | permissive |
| r/CRM | 55,275 | 5.56 | 12% | 0.667 | unknown |

These 10 subs carry 18.72 of the 26.45 total scorable bb/h — **70.8% of scorable signal sits in 10 of 125 scorable subreddits.** Losing any one of them can measurably thin a category, which remains an argument for discovery-led list maintenance, not for relaxing the rule.

---

## 7. Ingest overlap

**347 candidate slots collapse to 232 unique subreddits — 33.1% fewer fetches.** Ingest is per-subreddit, not per-category, so **the ingest set must be deduplicated before scheduling**. The wider discovery lists make that deduplication more valuable, not less.

Ingest membership and scoring eligibility are separate decisions. A hostile or vendor sub can still be retained as context or as evidence on its own brand page, but it cannot contribute to a cross-brand ranking.

---

## 8. What to do before Phase 1

All categories now clear the inventory floor. The work before Phase 1 is therefore not to declare them ready; it is to establish brand-level eligibility and verify the rules that the inventory cannot test.

1. **Run Phase 0 on real per-brand evidence.** Confirm every provisional tier from actual per-brand `n_eff` before publishing anything.
2. **Apply the per-brand gate in full.** A brand needs its category's `n_min` and all four diversity floors. Five scorable subreddits in a category is necessary inventory, not a ranking result.
3. **Re-run with the real gazetteer and multiple pages per subreddit.** The one-page, low-ambiguity probe is deliberately a screen; it cannot settle per-brand volume or absence.
4. **Resolve the 28 `unknown` rule postures by reading the rules manually.** Twenty-two of those subreddits currently score, so the parsing gap is material.
5. **Audit the gazetteer-derived vendor classifier as it grows.** The r/ObsidianMD, r/logseq, r/Anytype, and r/Frontend corrections show why this is a continuing data-quality check rather than a one-time regex.
6. **Use CRM as a controlled first inventory test.** Its 17 scorable generalist subreddits give Phase 0 room to test per-brand eligibility, while remaining subject to exactly the same evidence and diversity gates. [12-phasing.md](12-phasing.md) already identifies CRM as the first category.

---

[← Back to README](README.md) · [The algorithm](13-algorithm.md) · [Subreddit mapping](04-subreddit-mapping.md) · [Index methodology](07-index-methodology.md)
