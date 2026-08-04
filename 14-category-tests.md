# Category Tests — 20 categories, measured

What happened when the algorithm's subreddit-selection stage was run for real against 20 large, deliberately diverse software categories.

**Measured 2026-08-04** · 187 candidate slots · 132 unique subreddits · **656 base Reddit API calls** (the harness caches by subreddit, so duplicate slots are free)

## Bottom line

- **The binding constraint is not Reddit's opinion volume. It is the candidate lists.** Only **6 of 20** categories currently reach the five-scorable-subreddit floor, because hostile and single-product communities eat the candidates. That is a research gap we can close, not a property of the platform.
- **36.6% of *reachable* subreddits (48 of 131) actively delete brand talk.** (The single-product figure below uses all 132; the denominators differ deliberately.) This is the single most consequential number in the study, and it is read directly from each subreddit's own rules.
- **36% (48 of 132) are single-product communities** — r/Bitwarden, r/Notion, r/CapCut. Useful as evidence, never scoreable, because they self-select for invested users.
- **The live API edge alone cannot feed this product.** Point-estimate live yield across all 20 categories is a trickle. This confirms the archive census is mandatory rather than optional ([13-algorithm.md](13-algorithm.md) Lane A).
- **Ingest cost is ~29% lower than category counts imply.** 187 candidate slots collapse to 132 unique subreddits; r/Entrepreneur alone serves 7 categories.
- ⚠️ **This study cannot declare any category dead.** At the 95% upper bound, **all 20** could clear the mention threshold. Read §4 before quoting any "thin" verdict.

---

## 1. What was measured

For each of 187 candidate (category, subreddit) pairs:

| Measurement | Method |
|---|---|
| Subscribers, type, description | `/r/{sub}/about` |
| Rule posture | `/r/{sub}/about/rules`, classified by regex over the full rules text |
| Live comment rate | `/r/{sub}/comments?limit=100` — rate derived from the span of one page |
| Brand-bearing share | Share of that page (up to 100 comments) containing any of 5 seed brands |
| Search discoverability | `/r/{sub}/search` for 2 seed brands, exact-alias verified locally |

Raw per-subreddit JSON, the harness, and both CSVs ship with this repo. The harness is resumable: it skips any subreddit already on disk, so a re-run costs only the gap.

| File | Rows | What |
|---|---:|---|
| **[subreddit-measurements.csv](data/subreddit-measurements.csv)** | 132 | Every unique subreddit, measured |
| **[category-tests-20.csv](data/category-tests-20.csv)** | 20 | Category rollup with bounds |
| [category-candidates-20.json](data/category-candidates-20.json) | 20 | The candidate lists and seed brands used |
| [probe.py](data/probe.py) | — | The harness. Re-run to refresh |

---

## 2. The rules finding

**48 of 131 reachable subreddits (36.6%) are hostile to brand mentions.** Their own rules remove promotional or product-mention content.

| Posture | Count | Meaning |
|---|---:|---|
| `permissive` | 64 | Organic brand discussion allowed |
| `hostile` | 48 | Brand/product mentions actively removed |
| `unknown` | 13 | Rules endpoint returned nothing parseable |
| `capped` | 6 | Allowed behind a karma gate or weekly thread |

This is why subscriber count is not in the selection score. The largest communities are disproportionately the strictest — r/smallbusiness (2.5M) and r/Accounting (1.27M) both classify hostile.

## 3. Community type

**48 of 132 are single-product communities.** They carry dense brand talk — r/Bitwarden measured 37% brand-bearing, r/paypal 50%, r/SAP 49% — and every one of them is disqualified from scoring, because a product's own subreddit is a population of people who already chose it.

Six more are **ecosystem** communities: named after a vendor but populated by practitioners discussing the whole market (r/salesforce, r/shopify, r/aws, r/adobe, r/reactjs, r/node). These stay scoreable and carry a flag, because excluding them would throw away some of the best comparative discussion on Reddit.

That distinction was a correction made during analysis. Blanket-excluding every vendor-named subreddit dropped CRM from 5 scorable subs to 4 and would have failed the category on a classification error rather than on evidence.

---

## 4. ⚠️ What this study cannot tell you

**The instrument is a subreddit inventory, not a category verdict.** Three limits, each of which biases toward under-measuring:

**One page is a small sample, and not always a full one.** Pages return *up to* 100 comments. In practice **130 of 131 returned a full 100**; the single exception is r/talentacquisition at 24, and it is also the sub with the 3.3-year span. Against a subreddit with 0.5% brand density, 100 comments has an expected count of 0.5 hits. Measuring zero there is uninformative.

Where a category shows `0.0` live yield, the honest statement is *not detected in the sample*, never *absent*. Each subreddit's upper bound uses its own actual page size `n`, not an assumed 100.

**Five seed brands, not the real gazetteer.** Each category was probed with 5 brands. Real category gazetteers run 20-100 brands, so every yield figure here is a **floor**, understated by roughly the ratio of the lists.

**The measurement window varies by three orders of magnitude.** One page spans 0.58h in r/recruitinghell and 28,823h — 3.3 years — in r/talentacquisition, which is also the 24-comment page. The same instrument measures "this hour" in one sub and "this presidency" in another.

So the table below reports both a point estimate and a **95% upper bound** (rule-of-three where the count was zero). The upper bound is what the data cannot rule out.

| Category | Scorable subs | Hostile | Single-product | Live bb/h | 3y point est. | 3y upper bound | 5-sub floor |
|---|---:|---:|---:|---:|---:|---:|:--|
| CRM | 5 | 3 | 3 | 2.02 | 53,006 | 115,393 | ✅ |
| Business Intelligence and Analytics | 6 | 1 | 2 | 1.11 | 29,144 | 62,988 | ✅ |
| Help Desk and Customer Support | 6 | 2 | 2 | 0.30 | 7,831 | 118,844 | ✅ |
| Cloud Hosting and Infrastructure | 7 | 2 | 1 | 0.24 | 6,254 | 162,105 | ✅ |
| Backup and Storage | 6 | 1 | 2 | 0.54 | 14,191 | 179,474 | ✅ |
| Team Collaboration and Chat | 5 | 3 | 2 | 0.14 | 3,652 | 115,875 | ✅ |
| Design and Prototyping | 2 | 6 | 3 | 0.99 | 26,017 | 84,266 | ❌ |
| Password Managers and Security | 4 | 3 | 4 | 0.57 | 15,111 | 113,608 | ❌ |
| Email Marketing | 3 | 5 | 3 | 0.40 | 10,538 | 22,061 | ❌ |
| Payment Processing | 2 | 6 | 2 | 0.30 | 7,936 | 16,845 | ❌ |
| eCommerce Platforms | 2 | 6 | 4 | 0.30 | 7,831 | 20,057 | ❌ |
| Project Management | 3 | 6 | 5 | 0.29 | 7,726 | 28,736 | ❌ |
| Video Editing | 1 | 4 | 5 | 0.27 | 7,016 | 13,163 | ❌ |
| HR and HRIS | 4 | 4 | 0 | 0.21 | 5,439 | 166,956 | ❌ |
| ERP | 3 | 4 | 4 | 0.10 | 2,733 | 6,438 | ❌ |
| Payroll | 2 | 5 | 0 | 0.07 | 1,787 | 24,307 | ❌ |
| Note-taking and Knowledge Management | 1 | 7 | 6 | 0.03 | 735 | 1,135 | ❌ |
| Accounting | 2 | 6 | 2 | 0.01 | 367 | 21,751 | ❌ |
| Marketing Automation | 2 | 4 | 2 | 0.00 | 0 | 6,433 | ❌ |
| Applicant Tracking and Recruiting | 4 | 3 | 0 | 0.00 | 0 | 217,968 | ❌ |

<sup>`bb/h` = brand-bearing comments per hour across scorable subs, 5 seed brands. `3y` projects the live rate across a 3-year archive window. Upper bound is the 95% one-sided limit on brand density given each page's actual size, rule-of-three where the observed count was zero.</sup>

**17 of 20 clear 400 seed-brand mentions on the point estimate. All 20 clear it at the upper bound.** The mention threshold is not what fails here.

---

## 5. The finding that actually matters

**14 of 20 categories fail the five-scorable-subreddit floor**, and that floor exists for a real reason: [07-index-methodology.md](07-index-methodology.md) requires each ranked brand to appear across ≥5 subreddits, so a category with 4 scorable subs cannot satisfy its own diversity floor.

The failures are not caused by absent discussion. They are caused by candidate lists that were too short and too concentrated:

- **Note-taking**: 10 candidates → 7 hostile, 6 single-product → **1** scorable. The category's discussion lives almost entirely inside product communities.
- **Video Editing**: 5 of 9 candidates are single-product NLE communities.
- **Project Management**: 5 single-product plus 6 hostile out of 11.

Every one of these is fixable by widening the candidate list with independent practitioner subreddits before Phase 1 mapping. That is now a named piece of work, not a discovery waiting to happen mid-build.

---

## 6. Where the signal actually concentrates

The densest brand discussion per hour, across all 132 measured subreddits:

| Subreddit | Subscribers | Comments/h | Brand-bearing | bb/h | Type | Scoreable |
|---|---:|---:|---:|---:|---|:--|
| r/ObsidianMD | 350,730 | 63.0 | 21% | 13.24 | single-product | ❌ |
| r/paypal | 103,008 | 6.4 | 50% | 3.21 | single-product | ❌ |
| r/Notion | 466,690 | 8.2 | 33% | 2.70 | single-product | ❌ |
| r/FinancialCareers | 1,762,260 | 25.8 | 7% | 1.81 | independent | ❌ |
| r/SAP | 60,641 | 3.2 | 49% | 1.57 | single-product | ❌ |
| r/CapCut | 98,523 | 4.8 | 32% | 1.53 | single-product | ❌ |
| r/Bitwarden | 119,768 | 3.9 | 37% | 1.44 | single-product | ❌ |
| r/synology | 199,249 | 6.4 | 22% | 1.42 | single-product | ❌ |
| r/salesforce | 113,705 | 4.5 | 30% | 1.35 | ecosystem | ✅ |
| r/premiere | 184,980 | 5.8 | 21% | 1.22 | single-product | ❌ |

**The densest sources are systematically the ones we cannot score — only 1 of the top 10 is scoreable.** That is the structural tension of the whole product: the places people talk most about a product are the places that product's fans gather. Everything the index publishes has to come from the thinner, harder, independent middle.

r/salesforce is the exception worth studying — an ecosystem community with single-product density and genuinely comparative discussion.

---

## 7. Ingest overlap

**187 candidate slots collapse to 132 unique subreddits.** Twenty-eight subreddits serve more than one category:

| Subreddit | Categories served |
|---|---:|
| r/Entrepreneur | 7 |
| r/smallbusiness | 6 |
| r/SaaS | 5 |
| r/sysadmin | 5 |
| r/shopify | 4 |
| r/ITManagers | 4 |

Ingest is per-subreddit, not per-category, so **the ingest set must be deduplicated before scheduling** or ~29% of calls are wasted re-fetching the same comment streams. At full taxonomy scale the overlap grows, and so does the saving.

---

## 8. What to do before Phase 1

1. **Widen candidate lists** for the 14 categories below the floor, targeting independent practitioner subreddits rather than product communities.
2. **Re-run this probe with the full gazetteer**, not 5 seed brands, and over multiple pages per subreddit so the small-sample problem goes away.
3. **Resolve the 13 `unknown` rule postures** by reading those subreddits' rules manually.
4. **Ship the six floor-passing categories first** — CRM, Business Intelligence, Help Desk, Cloud Hosting, Backup and Storage, Team Collaboration. They are the natural Phase 1 set, and CRM is the natural Phase 0 subject on this evidence.
5. **Investigate the ecosystem-community pattern.** If r/salesforce generalises, it is a large recoverable source of scoreable density.

**Phase 0 recommendation changes on this evidence.** Password Managers was the pre-study candidate, chosen on an earlier and narrower measurement; [12-phasing.md](12-phasing.md) now specifies CRM. **CRM** is the better subject: it passes the floor with 5 scorable subs, carries the highest measured live yield of any floor-passing category, and its 3-year point estimate is comfortably above threshold.

---

[← Back to README](README.md) · [The algorithm](13-algorithm.md) · [Subreddit mapping](04-subreddit-mapping.md) · [Index methodology](07-index-methodology.md)
