# Category → Subreddit Mapping

How a category becomes a list of subreddits worth scoring — the one binding exclusion rule, the widening step that decides whether a category lives or dies, and the traps a name-based guess walks straight into.

**Method doc.** Measured numbers live in [14-category-tests.md](14-category-tests.md) and [data/subreddit-measurements.csv](data/subreddit-measurements.csv). This file does not restate them as a second source of truth.

## Bottom line

- **Only generalist subreddits score a brand.** Any subreddit named for, or dedicated to, a specific vendor or product is excluded from scoring outright. `scorable` = status ok **and** posture not hostile **and** not a vendor sub. That rule reproduces all 156 rows of the measurements CSV with zero exceptions.
- **The reason is cross-brand comparability, not bias.** A brand with a large active home subreddit would outscore a competitor with a small one or none. Rank would then partly measure community size — the same confound the index already rejects for raw mention counts.
- **254 candidate slots resolve to 156 unique subreddits.** 56 are vendor subs, 54 are hostile to brand talk, and **62 are scorable generalist subs**.
- **12 of 20 tested categories clear the 5-subreddit floor.** Before the candidate lists were widened, only 4 did. The binding constraint was always the lists — never Reddit's opinion volume, never the exclusion rule.
- **Generalist-only retains 9% of measured brand-bearing volume.** That is a deliberate and expensive choice. The excluded data is the densest measured, not the weakest.
- ⚠️ **No category may be declared dead from this evidence.** This is a floor instrument. At the 95% upper bound all 20 clear the mention threshold ([14-category-tests.md](14-category-tests.md) §4).

## Where the numbers live

| Source | Rows | Authoritative for |
|---|---:|---|
| [data/subreddit-measurements.csv](data/subreddit-measurements.csv) | 156 | Per-subreddit posture, `is_vendor_sub`, live rate, brand-bearing share, scorability |
| [data/category-tests-20.csv](data/category-tests-20.csv) | 20 | Per-category rollup and the 5-sub floor verdict |
| [data/category-candidates-20.json](data/category-candidates-20.json) | 20 | The widened candidate lists, per category, with seed brands |
| [14-category-tests.md](14-category-tests.md) | — | The 20-category study, its bounds, and its limits |
| [13-algorithm.md](13-algorithm.md) §2 | — | The selection score that ranks survivors and caps each category at 8 |
| [data/phase1-categories.csv](data/phase1-categories.csv) | 50 | Which Phase 1 categories are mapped (8) versus pending (42) |

[data/subreddit-map.csv](data/subreddit-map.csv) is the earlier 12-category map, superseded as a measurement source. It survives only as the per-category row form.

## The binding rule — vendor subs never score

A subreddit named for or dedicated to one vendor or product is excluded from scoring. No sub-classes, no exceptions. **56 of 156** measured subreddits are vendor subs, carrying the `is_vendor_sub` flag in the CSV.

**Why: cross-brand comparability.** Scoring a brand inside its own community lets community size leak into rank. A brand with a busy home sub would beat a competitor with a small one or none at all, on structure rather than on opinion. A ranking table has to sit on neutral ground, so the whole class comes out.

**What this is not.** Earlier drafts justified the exclusion as product subs self-selecting for invested users. **That was never measured and is retracted.** Sentiment was never measured in this study, so no directional claim is supportable. r/paypal is plausibly a support-seeking population skewing negative; r/ObsidianMD an enthusiast one skewing positive. Neither was tested.

**Vendor subs stay in the corpus as evidence.** They are usable on a brand's own page and for that brand's trajectory against its own baseline, where cross-brand comparability does not apply. They never enter a ranking. Label them visibly as the product's own subreddit ([01-legal.md](01-legal.md) covers attribution and takedown).

### The cost, stated honestly

Vendor subs hold **76%** of all brand-bearing comments-per-hour measured across the 156 subreddits. Generalist-only keeps **9%**. The densest rows in the file are the excluded ones: r/Odoo 51% brand-bearing, r/paypal 50%, r/SAP 49%, r/Wix 49%, r/hubspot 48%, r/Slack 48%. r/ObsidianMD alone produces 13.2 brand-bearing comments per hour.

Never present the exclusion as free, and never call the excluded data low quality. It is high quality and structurally unusable for ranking.

## Exclusion — rule posture

A sub that deletes product mentions is a dead source at any size. Posture is classified by regex over the full rules text from `/r/{sub}/about/rules`.

| Posture | Count | Meaning | Map action |
|---|---:|---|---|
| `permissive` | 79 | Organic brand discussion allowed | Scoreable if generalist |
| `hostile` | 54 | Brand or product mentions actively removed | Drop, any size |
| `unknown` | 15 | Rules endpoint returned nothing parseable | Resolve by hand before shipping |
| `capped` | 7 | Karma gate or weekly-promo-thread confinement | Scoreable, organic threads only |

One row, r/B2BForSales, returned `unavailable` and carries no posture.

The two exclusions overlap less than expected: 17 subs are both vendor and hostile, 39 are vendor but not hostile, and 37 are hostile but not vendor. Neither rule is redundant.

**The largest communities are disproportionately the strictest.** The biggest hostile subs are r/Entrepreneur (5,249,043), r/productivity (4,231,867), r/webdev (3,291,935), r/smallbusiness (2,515,817), r/marketing (1,958,693), r/FinancialCareers (1,762,260) and r/SaaS (771,500) — every one of them a generalist sub that would otherwise score.

**r/smallbusiness changed in June 2026** — Rule 2 now removes product mentions from posts *and comments* when they read as promotional, and Rule 5 bans market-research posts. One rule edit turned a top-five source into noise.

⚠️ Posture drifts. Re-pull rules every cycle and hash the text; [13-algorithm.md](13-algorithm.md) §9 treats a hash change as a trigger to re-evaluate.

## Widening the candidate list is the method, not a fallback

This is the step that decides categories. Before the lists were widened with generalist practitioner subs, only **4 of 20** categories cleared the floor. After widening, **12 of 20** clear it — with the exclusion rule made *stricter*, not looser.

**CRM demonstrates the whole mechanism.** Of its 23 candidates, the 11 carried over from the earlier map yield **4** scorable subs. The 12 generalist practitioner subs added in the re-run yield **12** — every single one scorable. CRM finishes at **16 scorable generalist subs**, the most of any category, on 0.85 brand-bearing comments per hour, which is why it is emphatically the Phase 0 subject.

The added subs were r/msp, r/consulting, r/startups, r/agency, r/RealEstateTechnology, r/InsuranceAgent, r/smallbusinessuk, r/B2BSaaS, r/salesdevelopment, r/SalesOperations, r/revops and r/PPC. None is obvious from the category name. All are places a buyer actually asks.

**Small focused practitioner subs beat large ones.** r/revops (6,593 subscribers, 0.36 comments/hour) measured **5% brand-bearing**. r/startups (2,107,067 subscribers, 16.76 comments/hour) measured **0%** on the same instrument. Enumerate by buyer job function, not by subscriber count.

### Categories clearing the floor (12 of 20)

| Category | Scorable | Candidates | Hostile | Vendor |
|---|---:|---:|---:|---:|
| CRM | 16 | 23 | 3 | 4 |
| Project Management | 10 | 18 | 6 | 5 |
| Applicant Tracking and Recruiting | 8 | 11 | 3 | 0 |
| Marketing Automation | 7 | 14 | 4 | 2 |
| Password Managers and Security | 7 | 15 | 4 | 4 |
| ERP | 7 | 13 | 4 | 4 |
| HR and HRIS | 6 | 10 | 4 | 0 |
| Email Marketing | 6 | 14 | 5 | 4 |
| Cloud Hosting and Infrastructure | 6 | 12 | 2 | 4 |
| Backup and Storage | 6 | 9 | 1 | 2 |
| Help Desk and Customer Support | 5 | 10 | 2 | 3 |
| Team Collaboration and Chat | 5 | 8 | 3 | 2 |

### Still below the floor (8 of 20)

| Category | Scorable | Candidates | Hostile | Vendor |
|---|---:|---:|---:|---:|
| Note-taking and Knowledge Management | 4 | 17 | 11 | 6 |
| Design and Prototyping | 4 | 12 | 6 | 4 |
| Business Intelligence and Analytics | 4 | 9 | 1 | 4 |
| Payroll | 4 | 10 | 6 | 0 |
| Accounting | 3 | 11 | 6 | 2 |
| Video Editing | 3 | 14 | 7 | 5 |
| eCommerce Platforms | 3 | 13 | 7 | 5 |
| Payment Processing | 3 | 11 | 6 | 3 |

**Business Intelligence moved from passing to failing.** It had been carried by vendor subs — r/PowerBI, r/tableau, r/SQL and r/MicrosoftFabric are all four of its exclusions, and only one of its 9 candidates is hostile. Its pass was a classification artefact.

**Hostility now dominates the remaining failures.** Note-taking has 11 hostile of 17 candidates; Video Editing 7 of 14; eCommerce Platforms 7 of 13; Accounting, Payroll, Payment Processing and Design 6 each. Widening helps less where the generalist subs themselves delete brand talk — but Payroll shows the ceiling is not reached: zero vendor exclusions and still only 4 scorable.

## Traps, verified live

**Name collision.** [r/figma](https://www.reddit.com/r/figma/) is a Japanese action-figure subreddit. The design tool lives in [r/FigmaDesign](https://www.reddit.com/r/FigmaDesign/) (154,580 subscribers, and excluded anyway — it is both hostile and a vendor sub). Never resolve a subreddit by lowercasing a product name; resolve every candidate through `/r/{sub}/about` and read the description.

**Reddit search stem-matches.** Stemming makes short brand names collide with common words: "Descript" queried against r/VideoEditing returned results dominated by the word "description". Apply an exact-token filter locally, after the search returns.

**Subscriber count does not predict signal.** On the same 100-comment instrument, r/PasswordManagers (54,640) returned **42% brand-bearing** while r/privacy (1,652,332) returned **0%** and r/cybersecurity (1,499,373) returned **2%**. r/sysadmin runs 111.96 comments per hour and returned 0%. Size buys traffic, not brand opinion.

**Discovery is broken.** `search_reddit` with `type='sr'` returns zero results under app-only OAuth for every query tried. Candidate lists are built by hand, which is exactly why widening them is a first-class step rather than cleanup.

**Brand-bearing share is per-seed-set, not absolute.** The CSV holds one row per unique subreddit and the probe caches by name, so each sub's share was measured against the five seed brands of whichever category reached it first. A 0% row means *not detected against those five brands in one page* — never *no brand talk*.

## Map per category, ingest per subreddit

The 20 tested categories request **254 candidate slots** that resolve to **156 unique subreddits**. **36 subs serve more than one category**, so deduplicating before scheduling saves 39% of calls.

| Subreddit | Categories served |
|---|---:|
| r/startups | 9 |
| r/Entrepreneur | 7 |
| r/smallbusiness | 7 |
| r/msp | 7 |
| r/consulting | 7 |
| r/agency | 7 |
| r/sysadmin | 7 |

Note that r/Entrepreneur, r/smallbusiness and r/SaaS are hostile and therefore score nothing despite appearing across many lists. Overlap governs ingest cost, not scoring value ([13-algorithm.md](13-algorithm.md) §8).

## The procedure

Run this per category, in order. It produces the candidate set; [13-algorithm.md](13-algorithm.md) §2 scores and truncates it to at most 8 scoring subreddits.

1. **Enumerate candidates wide, by hand,** from four strata: practitioner subs for the buyer's job function (the highest-yield stratum, and the one most often skipped), verified general software and business subs, adjacent workflow subs where a buyer would ask for a recommendation, and one sub per known brand from [data/brand-gazetteer-seed.csv](data/brand-gazetteer-seed.csv). Overshoot deliberately.
2. **Resolve every name** through `/r/{sub}/about`. Read the description. This is the step that catches r/figma.
3. **Pull rules** from `/r/{sub}/about/rules` and classify posture. Hostile subs are dropped regardless of size. `unknown` is not a pass — resolve it by hand.
4. **Flag `is_vendor_sub`.** True if the sub is named for, or dedicated to, one vendor or product. Brand-gazetteer subs from stratum four are vendor subs by construction — they are probed for evidence and never scored.
5. **Measure the live comment rate** from one `/r/{sub}/comments?limit=100` page. The span of that page gives comments per hour, which also sets the ingest cadence and the multireddit bucket in [13-algorithm.md](13-algorithm.md) §3.
6. **Probe brand-bearing share** across that page, with an exact-alias check applied locally so stemmed hits do not count.
7. **Count scorable subs.** Below 5, do not accept the verdict yet — return to step 1 and widen. Only after a genuine widening pass does the category ship as *insufficient Reddit signal to rank*, per the diversity floor in [07-index-methodology.md](07-index-methodology.md).
8. **Write the result back** to [data/subreddit-measurements.csv](data/subreddit-measurements.csv) and [data/category-tests-20.csv](data/category-tests-20.csv), and flip the category's `subreddit_map_status` in [data/phase1-categories.csv](data/phase1-categories.csv), in one commit. Files disagreeing about what is mapped is how this map rots unnoticed.

The harness implementing steps 2-6 is [data/probe.py](data/probe.py). It is resumable — one JSON file per subreddit on disk, so a re-run costs only the gap.

## Open work

**Widen the 8 failing categories.** CRM is the proof that this works: 12 added practitioner subs, 12 scorable. Note-taking, Video Editing and eCommerce Platforms need the harder version of the same pass, since their generalist candidates are heavily hostile rather than merely absent.

**Resolve the 15 `unknown` postures by hand:** r/aws, r/backblaze, r/CRM, r/KeePass, r/Klaviyo, r/NAS, r/node, r/PasswordManagers, r/Payments, r/QuickBooks, r/revops, r/SAP, r/students, r/talentacquisition, r/trello.

**Seven of those are currently counted as scorable** — r/CRM, r/NAS, r/PasswordManagers, r/Payments, r/revops, r/students and r/talentacquisition. Marked as inference, not measurement: if all seven resolved hostile, no passing category would drop below the floor. CRM falls to 14, Applicant Tracking to 7, and Backup and Storage to exactly 5. The floor verdicts are robust to this open question.

**Resolve r/B2BForSales**, the one row returning `unavailable` with no posture recorded.

**Reconcile category names.** The 20 study categories and the 50-row Phase 1 taxonomy use different labels — "HR and HRIS" against "Human Resources", "Applicant Tracking and Recruiting" against two separate rows. Step 8 cannot write back cleanly until one convention wins.

---

[← Back to README](README.md) · [Category tests, measured](14-category-tests.md) · [The algorithm](13-algorithm.md) · [Category taxonomy](03-taxonomy.md) · [Data acquisition](02-data-acquisition.md) · [Index methodology](07-index-methodology.md)
