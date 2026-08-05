# Data — column reference

## Bottom line

- Seven flat CSVs (693 rows), the JSON that seeded the 20-category probe, and two scripts. Every CSV opens in Excel or Sheets and renders on GitHub.
- The newest layer is that probe, re-run on **2026-08-05** over discovery-widened candidate lists. [subreddit-measurements.csv](subreddit-measurements.csv) measures **232 unique subreddits**: 231 are reachable, 50 are vendor-named, 56 are hostile to brand talk, and **125 are scorable**. [../14-category-tests.md](../14-category-tests.md) reads the result.
- **Only generalist subreddits score a brand.** Any subreddit named for or dedicated to a specific vendor or product is excluded outright, for cross-brand comparability. [Why, in full](#the-is_vendor_sub-rule).
- With the wider lists, **20 of 20** categories clear the five-scorable-subreddit floor ([category-tests-20.csv](category-tests-20.csv)). The binding constraint was always the candidate lists.
- ⚠️ Four columns are easy to misread — `comment_span_hours` is velocity and not coverage, `brand_bearing_share` is a 5-brand floor, `density_ub95` is why a zero never means absence, and `threshold_tier` is provisional category-level flow rather than per-brand evidence. [Details below](#the-four-columns-people-misread).

Click a file, then **Download raw file** to get the CSV rather than the rendered table.

| File | Rows | What it is |
|---|---:|---|
| [phase1-categories.csv](phase1-categories.csv) | 50 | The Phase 1 category spine |
| [subreddit-map.csv](subreddit-map.csv) | 131 | Category → subreddit mapping with rule posture |
| [subreddit-measurements.csv](subreddit-measurements.csv) | 232 | Every unique subreddit in the 20-category probe, measured live |
| [category-tests-20.csv](category-tests-20.csv) | 20 | Category rollup of those measurements, with 95% bounds |
| [categories.csv](categories.csv) | 20 | Category presentation metadata, scorable coverage, and provisional threshold tiers |
| [category-candidates-20.json](category-candidates-20.json) | 20 | The probe's **input**: 347 candidate slots and 5 seed brands per category |
| [probe.py](probe.py) | — | The measurement harness. Resumable |
| [analyze.py](analyze.py) | — | Regenerates the measurement and category-test CSVs, and the tier columns in `categories.csv`, from raw probe output |
| [brand-gazetteer-seed.csv](brand-gazetteer-seed.csv) | 113 | Seed brand list with ambiguity classification |
| [domain-availability.csv](domain-availability.csv) | 120 | The sweep behind the Reddit Index name |

Measurement dates differ by file. The 2026-08-05 re-run carries a per-row `measured_at`; the older files were taken on 2026-08-04.

---

## What is deliberately NOT here

No copy of Capterra's category catalog and no product counts. Their `numberOfItems` figures were used as a **selection signal** to pick the 50 and are cited as evidence inside [../03-taxonomy.md](../03-taxonomy.md). They are not republished as a dataset. Legal reasoning is not repeated here: [../01-legal.md](../01-legal.md) is authoritative for this repo.

---

## phase1-categories.csv

The 50 categories for Phase 1, ordered by size.

| Column | Type | Meaning |
|---|---|---|
| `rank` | int 1-50 | Position by size signal. Rank 1 is the largest category. |
| `category` | string | Our category name. Industry-standard vocabulary, not a verbatim Capterra label. |
| `size_tier` | `XL` / `L` / `M` | Coarse size band replacing the raw product count. XL ≈ ranks 1-10, L ≈ 11-31, M ≈ 32-50. |
| `reddit_signal_verdict` | enum | Whether Reddit carries enough opinion to rank this category honestly. See the enum table below. `not_assessed` means the mapping work has not been done yet. |
| `subreddit_map_status` | `mapped` / `pending` | Whether this category has rows in `subreddit-map.csv`. 8 of 50 are mapped. |
| `phase` | int | Always `1` in this file. |

**42 of the 50 are `pending`.** Eight are mapped. A separate 20-category study ([../14-category-tests.md](../14-category-tests.md)) probed different labels — only 8 join this taxonomy exactly, and **no crosswalk ships yet**. Do not add the two figures together.

---

## subreddit-map.csv

One row per (category, subreddit) pair. Subscriber counts pulled individually via the Reddit API on 2026-08-04.

| Column | Type | Meaning |
|---|---|---|
| `category` | string | Joins to `phase1-categories.csv.category`. |
| `subreddit` | string | Prefixed `r/`. Case as Reddit displays it. |
| `subscribers` | int | Subscriber count at measurement time. |
| `category_signal_verdict` | enum | The verdict for the **category**, repeated on each row. Not a per-subreddit judgement. |
| `rule_posture` | enum | How the subreddit's own rules treat brand and vendor talk. `not_assessed` means the rules were not read. |
| `is_vendor_owned_sub` | `yes` / `no` | Whether the subreddit is the vendor's own community. The forerunner of `is_vendor_sub` in the measurements file, and excluded from scoring for the same reason: [comparability](#the-is_vendor_sub-rule). |

### `category_signal_verdict`

| Value | Meaning |
|---|---|
| `richest` | Dense, opinionated, comparative. Rank with confidence. |
| `rich` | Enough signal to rank. |
| `rich_rule_suppressed` | The audience exists but moderation deletes brand talk. Volume understates reality. |
| `rich_dtc_skewed` | Plenty of signal, but weighted toward direct-to-consumer ecommerce users. |
| `rich_monoculture` | One brand dominates. The leader is rankable; ranks 4-10 are not separable. |
| `rich_nle_thin_saas` | Rich for desktop editors, thin for SaaS tools in the same category. |
| `thin` | 🔴 **Do not rank.** Ships as "insufficient Reddit signal" on the site. |

### `rule_posture`

| Value | Meaning |
|---|---|
| `permissive_organic_vendor_talk_ok` | Organic brand discussion is allowed. Highest-quality source. |
| `restrictive_*` | Allowed but constrained (link limits, mention caps, posting windows). |
| `restricted_promo_thread_only_50_karma_gate` | Vendor talk confined to a weekly thread behind a karma gate. |
| `hostile_*` | Brand mentions are actively removed. `hostile_removes_product_mentions_since_2026_06` is r/smallbusiness, 2.5M subscribers, deleting product mentions since June 2026. |
| `not_assessed` | Rules not read yet. |

⚠️ **Subscriber count does not predict signal.** In the 2026-08-05 re-run, r/PasswordManagers (54,640 subscribers) carried a 0.42 brand-bearing share while r/marketing (1,958,693) carried 0.0, because r/marketing's rules delete exactly that content. Full reasoning in [../04-subreddit-mapping.md](../04-subreddit-mapping.md).

---

## subreddit-measurements.csv

Every unique subreddit touched by the 20-category probe, re-measured live on 2026-08-05 over the widened candidate lists.

One row per **subreddit**, not per (category, subreddit) pair. The 347 candidate slots collapse to 232 unique subreddits, because subreddits overlap across categories.

This is a different instrument from `subreddit-map.csv` above, over a different category set ([../14-category-tests.md](../14-category-tests.md)). Names here carry **no `r/` prefix**, so strip the prefix from `subreddit-map.csv` before joining the two.

| Column | Type | Meaning |
|---|---|---|
| `subreddit` | string | Bare name, no `r/`. Case as sent to the API. |
| `status` | `ok` / `unavailable` | Whether `/r/{sub}/about` returned a `t5`. 231 `ok`, 1 `unavailable`. |
| `subscribers` | int | Count at measurement time. Empty when unavailable. Deliberately **not** a selection signal. |
| `rule_posture` | enum | How the subreddit's own rules treat brand talk. Four values, table below. |
| `is_vendor_sub` | `True` / `False` | **`True` means the subreddit is named for, or dedicated to, a specific vendor or product — and is excluded from scoring outright.** 50 True, 182 False. Replaces the retired `community_type` column. |
| `comment_page_n` | int | Comments actually returned by the one page. 230 of 231 returned the full 100. |
| `comments_per_hour` | float | `comment_page_n ÷ comment_span_hours` — the page's **actual** size, which is *up to* 100 and was 24 for r/talentacquisition. Feeds rate-bucketing in [../13-algorithm.md](../13-algorithm.md) §3. |
| `comment_span_hours` | float | How far back that one 100-comment page reached. ⚠️ Velocity, not coverage. |
| `brand_bearing_share` | float 0-1 | Share of those comments containing any of the category's 5 seed brands. ⚠️ A floor. |
| `density_ub95` | float | 95% one-sided upper bound on brand density given a 100-comment sample. |
| `bb_per_hour` | float | `comments_per_hour` × `brand_bearing_share`. The rate-adjusted yield, and the selection signal. |
| `scorable` | `True` / `False` | `status = ok` **and** `rule_posture ≠ hostile` **and** `is_vendor_sub = False`. True on **125 of 232**. |
| `distinct_threads_in_page` | int | Distinct `link_id`s among the comments. A concentration check: a low value means the page is one busy thread rather than the subreddit. |
| `measured_at` | ISO UTC | Per-subreddit timestamp. Empty on the unavailable row. |

These are one-time measurements, not the pipeline's running state. Ingest runs continuously per bucket and scoring publishes once daily ([../13-algorithm.md](../13-algorithm.md) §7).

### How 232 becomes 125

| Bucket | Rows |
|---|---:|
| Scorable — reachable, non-hostile, generalist | **125** |
| Vendor sub, rules otherwise fine | 34 |
| Hostile rules, generalist | 56 |
| Both vendor and hostile | 16 |
| Unreachable (`B2BForSales`) | 1 |

Of the 125 scorable rows, 93 are `permissive`, 22 `unknown` and 10 `capped`.

### `rule_posture`

| Value | Count | Meaning |
|---|---:|---|
| `permissive` | 120 | Organic brand discussion is allowed. |
| `hostile` | 72 | The rules remove promotional or product-mention content. 56 are generalist and therefore hostile to scoring; 16 are vendor subs too. |
| `unknown` | 28 | The rules endpoint returned nothing parseable. **Not** a synonym for permissive. |
| `capped` | 11 | Allowed behind a karma gate or a weekly thread. |

Posture is classified by regex over the full `/about/rules` text, not by a human read. The largest communities skew strictest: r/smallbusiness (2,515,817) and r/Accounting (1,272,896) both classify hostile. The blank posture on the unavailable row is not a fifth value.

### The `is_vendor_sub` rule

A `True` here is a hard exclusion from every ranking. The reason is **cross-brand comparability, not sentiment.**

A brand with a large active home subreddit would gain a structural advantage over a competitor with a small one or none at all. Rank would then partly measure community size — the same confound the index already rejects for raw mention counts. A ranking table has to stand on neutral ground.

Detection is derived from the brand gazetteer plus each category's seed brands, then token-matched against the subreddit name; it is not a hand-maintained regex. The earlier handwritten regex silently missed r/ObsidianMD, r/logseq and r/Anytype, and scored them as generalist. In Note-taking and Knowledge Management, estimated 3-year brand-bearing volume was 369,652 with those product communities and 17,395 without them: the category was being carried almost entirely by its own vendors. An intermediate prefix matcher also falsely classified r/Frontend because `Front` is a brand prefix; token splitting fixes that boundary.

Sentiment was never measured in this study, so no directional claim about vendor subs is supportable in either direction. r/paypal is plausibly a support-seeking population and r/ObsidianMD plausibly an enthusiast one; neither was tested.

**The excluded data is the densest measured, not the weakest.** r/ObsidianMD measures 13.236 `bb_per_hour`, and is a vendor sub. That is a deliberate and expensive exclusion, never a free one.

Vendor subs stay usable as **evidence** on a brand's own page, and for that brand's trajectory against its own baseline, where cross-brand comparability does not apply. They never enter a ranking.

The rule supersedes the earlier three-class model: a subreddit is either a vendor/product community and excluded, or it is eligible for the remaining scoring checks.

The best scorable rows come from the generalist middle, rather than a product's home community.

### The four columns people misread

**`comment_span_hours` measures velocity, not coverage.** One 100-comment page reached back 0.58h in r/recruitinghell and 72,797.87h in the slowest measured subreddit. Median 27.52h. The same instrument samples the last hour in one subreddit and years in another, so it can never be read as how much of a subreddit was seen.

**`brand_bearing_share` is a floor, not an estimate.** Each subreddit was probed with only the 5 seed brands of its category. Real gazetteers run 20-100 brands, so every share here understates by roughly the ratio of the two lists. 69 of the 231 reachable subreddits measured exactly zero.

**`density_ub95` exists so a zero is never read as absence.** It is the 95% one-sided upper bound on brand density given a 100-comment sample, using the rule of three where the observed count was zero. Across reachable rows it runs 0.01 to 0.51. A `0.0` share means *not detected in that page*, bounded above by this column.

⚠️ **Filter on `status = ok` first.** The one unavailable row, `B2BForSales`, has empty measurements and `density_ub95 = 3.0`. That is the rule-of-three formula run against an empty sample, not a density.

**`threshold_tier` is provisional, not a per-brand sample result.** It is assigned mechanically from estimated 3-year brand-bearing volume across the category's scorable generalist subreddits. That is category-level comment flow; Phase 0 must confirm real per-brand `n_eff` before a tier informs publication.

---

## category-tests-20.csv

One row per tested category, rolled up from the subreddit rows over that category's own candidate list. A subreddit serving several categories contributes to each of them, so the columns below are **slot** sums and exceed the 232 unique subreddits. The reading is in [../14-category-tests.md](../14-category-tests.md).

| Column | Type | Meaning |
|---|---|---|
| `category` | string | Joins to `category-candidates-20.json`. ⚠️ Only 8 of the 20 match a `phase1-categories.csv` label verbatim; the rest are the same domains under longer labels, and no crosswalk ships yet. |
| `candidates` | int | Candidate slots for this category. Sums to 347 across the file. |
| `ok` | int | Candidates whose `/about` resolved. Sums to 346 — one subreddit was unavailable. |
| `hostile` | int | Generalist candidate slots whose own rules remove brand talk. Sums to 97. |
| `vendor_subs` | int | Candidate slots that are a specific vendor's or product's own community. Sums to 57. Replaces the retired `single_product` column. |
| `scorable` | int | Candidate slots passing the `scorable` predicate. Sums to 192. |
| `live_bb_per_hour` | float | Σ `bb_per_hour` across this category's scorable subs. The measured live yield. |
| `live_bb_per_hour_ub95` | float | The same sum computed at `density_ub95` instead of the observed share. |
| `seed_bb_3y` | int | The live rate projected across a 3-year archive window (26,280 hours). |
| `seed_bb_3y_ub95` | int | The same projection at the upper bound. |
| `meets_5_sub_floor` | `True` / `False` | `scorable ≥ 5`. **True for 20 of 20.** |
| `threshold_tier` | `deep` / `standard` / `thin` | Provisional mechanical tier from the category's estimated 3-year brand-bearing volume across scorable generalist subs. It is not a per-brand `n_eff` result. |
| `precision_target_pp` | int | Provisional target precision, in percentage points: 4 for `deep`, 5 for `standard`, 7 for `thin`. |
| `n_min` | int | Provisional minimum per-brand effective sample size: 600 for `deep`, 400 for `standard`, 200 for `thin`. Phase 0 must confirm it from real per-brand `n_eff`. |

Both rate columns are computed from unrounded per-subreddit values, so multiplying the rounded rate by 26,280 reproduces `seed_bb_3y` only approximately — CRM stores 25,224 where the rounded 0.96 recomputes to 25,229.

### Clearing the floor (20)

| Category | Candidates | Vendor | Hostile | Scorable | `live_bb_per_hour` | Tier |
|---|---:|---:|---:|---:|---:|
| CRM | 26 | 4 | 5 | **17** | 0.96 | deep |
| Project Management | 20 | 5 | 4 | 11 | 0.36 | standard |
| Accounting | 16 | 2 | 7 | 7 | 0.34 | standard |
| HR and HRIS | 10 | 0 | 4 | 6 | 0.21 | standard |
| Email Marketing | 17 | 3 | 6 | 8 | 0.11 | thin |
| Marketing Automation | 22 | 2 | 6 | 13 | 0.89 | deep |
| Password Managers and Security | 19 | 4 | 5 | 10 | 1.13 | deep |
| Note-taking and Knowledge Management | 21 | 6 | 8 | 7 | 0.66 | standard |
| Design and Prototyping | 26 | 3 | 7 | 16 | 2.05 | deep |
| Video Editing | 23 | 4 | 9 | 10 | 2.19 | deep |
| Help Desk and Customer Support | 11 | 3 | 2 | 6 | 0.17 | thin |
| ERP | 13 | 4 | 2 | 7 | 0.1 | thin |
| Business Intelligence and Analytics | 18 | 3 | 1 | 14 | 2.37 | deep |
| eCommerce Platforms | 19 | 5 | 8 | 6 | 0.18 | thin |
| Applicant Tracking and Recruiting | 11 | 0 | 3 | 8 | 0.14 | thin |
| Payroll | 11 | 0 | 6 | 5 | 0.13 | thin |
| Cloud Hosting and Infrastructure | 18 | 0 | 3 | 15 | 0.57 | standard |
| Team Collaboration and Chat | 18 | 2 | 4 | 12 | 12.25 | deep |
| Backup and Storage | 12 | 3 | 1 | 8 | 0.71 | standard |
| Payment Processing | 16 | 4 | 6 | 6 | 4.71 | deep |

Passing means the category has enough neutral ground to compare brands on, not that the discussion is loud. The 20 categories span 5 to 17 scorable generalist subreddits.

### Threshold tiers

The tiers are assigned mechanically from estimated 3-year brand-bearing volume across each category's scorable generalist subreddits. Their round cut points are stated and provisional: this study measures category-level comment flow, not per-brand `n_eff`, so Phase 0 must confirm every tier before anything publishes.

| Tier | Estimated 3-year brand-bearing volume | Target precision | `n_min` | Categories |
|---|---:|---:|---:|---:|
| `deep` | ≥ 20,000 | ±4pp | 600 | 8 |
| `standard` | ≥ 5,000 | ±5pp | 400 | 6 |
| `thin` | < 5,000 | ±7pp | 200 | 6 |

---

## categories.csv

One row per category in the 20-category study. It joins presentation metadata to the re-run's scorable coverage and provisional threshold decision.

| Column | Type | Meaning |
|---|---|---|
| `category` | string | Category name; joins to `category-tests-20.csv.category`. |
| `slug` | string | URL-safe category identifier. |
| `icon` | string | Lucide icon name. |
| `hex` | string | Category colour in hex notation. |
| `oklch` | string | The same category colour in OKLCH notation. |
| `contrast_space_black` | float | Contrast ratio against Space Black. |
| `contrast_snowbelt` | float | Contrast ratio against Snowbelt. |
| `dE_loved` | float | Colour distance from the Loved state. |
| `dE_hated` | float | Colour distance from the Hated state. |
| `dE_nearest_category` | float | Distance to the nearest other category colour. |
| `threshold_tier` | `deep` / `standard` / `thin` | Provisional tier regenerated from `category-tests-20.csv`. |
| `precision_target_pp` | int | Provisional target precision, in percentage points. |
| `n_min` | int | Provisional minimum per-brand effective sample size. |
| `scorable_subreddits` | int | Scorable generalist subreddit slots for this category. |
| `meets_5_sub_floor` | `True` / `False` | Whether `scorable_subreddits ≥ 5`. True for all 20. |

---

## category-candidates-20.json

The **input** to the probe, not an output. Twenty objects, each with a `category`, exactly 5 seed `brands`, and a discovery-widened `subreddits` list. This 2026-08-05 re-run used Reddit's `/subreddits/search` over 8 topical seed queries per category, yielding 3,526 new candidates. A one-call screen of the best-ranked 562 measured live brand-bearing density; only subs with at least one brand-bearing comment on the live page were promoted. The result is **347 slots, 232 unique subreddits.**

```json
{"category":"CRM","brands":["HubSpot","Salesforce","Pipedrive","Zoho","Attio"],
 "subreddits":["CRM","sales","salesforce","techsales","hubspot","gohighlevel",
               "Zoho","smallbusiness","Entrepreneur","EntrepreneurRideAlong","SaaS",
               "msp","consulting","startups","agency","RealEstateTechnology",
               "InsuranceAgent","smallbusinessuk","B2BSaaS","salesdevelopment",
               "SalesOperations","revops","PPC"]}
```

Two properties of this file decide how every result reads. The 5-brand lists are what make each yield figure a floor. And the subreddit lists were the study's binding constraint: discovery widening took the number of categories clearing the five-sub floor to 20 of 20, on the same exclusion rule.

Widening works by adding **small practitioner subreddits, not large ones.** The lists now yield 5 to 17 scorable generalist subreddits per category.

⚠️ `probe.py` caches by `sub.lower()`, so any join must be case-insensitive.

⚠️ `probe.py` loads its category list from a sibling file named `cat20.json`. Rename this file or repoint that path before the first run.

---

## probe.py

The raw measurement harness. Five API calls per **unique reachable** subreddit — `/r/{sub}/about`, `/r/{sub}/about/rules`, `/r/{sub}/comments?limit=100`, and `/r/{sub}/search` for the first 2 seed brands. An unreachable subreddit costs one call and stops.

**The harness caches by subreddit**, so repeated candidate slots do not repeat work on a cold run. A re-run costs only the gap: subreddits already on disk are served from disk at zero calls. Retries are additional and unlogged.

**Resumable by design.** It writes one JSON per subreddit atomically (`.tmp`, then `os.replace`) and returns the on-disk record for any subreddit already measured. A run interrupted at slot 140 resumes at slot 140, and widening a candidate list only pays for the new names.

**Credentials are read, never written.** It pulls `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` and `REDDIT_USER_AGENT` from the existing Reddit MCP config and mints an app-only `client_credentials` token. App-only OAuth is read-only — it cannot post, vote or comment. Nothing is hardcoded, and no secret lands in this repo.

Rate discipline: `time.sleep(0.75)` between calls, retry on 429/500/502/503, one token re-fetch on 401.

### Regenerating

```bash
python3 probe.py
python3 analyze.py      # rebuilds the shipped CSVs from raw probe JSON
```

Set two things before the first run. `OUT`, at the top of `probe.py`, is an absolute scratch path for the per-subreddit JSON. `PROBE_DIR`, for `analyze.py`, must point to that same directory. Both scripts also default to a sibling `cat20.json`; this repo ships that input as `category-candidates-20.json`, so rename it or repoint the paths before the first run.

The per-subreddit JSON stays in `OUT` and is not committed here. `probe.py` measures, prints progress, and stops; `analyze.py` folds raw probe output into `subreddit-measurements.csv`, `category-tests-20.csv`, and the tier columns of `categories.csv`.

---

## analyze.py

The regeneration step for the shipped measurement outputs. It reads the raw per-subreddit JSON, applies the gazetteer-derived, token-matched vendor rule, writes `subreddit-measurements.csv` and `category-tests-20.csv`, then refreshes `threshold_tier`, `precision_target_pp`, `n_min`, `scorable_subreddits`, and `meets_5_sub_floor` in `categories.csv`.

---

## brand-gazetteer-seed.csv

The seed for entity resolution. Not exhaustive — it is the starting gazetteer, sized to expose the ambiguity problem rather than to cover the market.

| Column | Type | Meaning |
|---|---|---|
| `brand` | string | Canonical brand name as the site would display it. |
| `category` | string | Primary category. A brand may legitimately appear in several; this file lists its main one. |
| `aliases` | `;`-separated | Surface forms seen in the wild. Empty means no alias beyond the canonical name. |
| `ambiguity_class` | `low` / `medium` / `high` | How hard it is to tell a real mention from a false positive. |
| `ambiguity_note` | string | Why, for `medium` and `high`. Empty for `low`. |

### Ambiguity distribution

| Class | Count | Share |
|---|---:|---:|
| `low` | 58 | 51% |
| `medium` | 20 | 18% |
| `high` | 35 | **31%** |

**31% of software brands have names that collide with common English words** — Notion, Slack, Monday, Linear, Stripe, Gusto, Workday, Craft, Front, Ramp, Make, Render, Segment, Amplitude, Looker, Loom, Motion, Sketch, Close, Bill, Confluence, Teams, Roam, Framer, Obsidian and more.

This single number is why [../05-entity-resolution.md](../05-entity-resolution.md) treats disambiguation as the hardest problem in the project.

The first live screen used naive substring matching and produced exactly the collisions the ambiguity classes predict: r/nfl and r/rugbyunion for Project Management (`Monday` the weekday), r/worldbuilding for ERP (`SAP` the fluid), and r/baseball for HR (`Rippling`, `Workday`). The correction is word-boundary matching with probe terms restricted to the gazetteer's `low`-ambiguity brands.

---

## domain-availability.csv

The sweep that produced the Reddit Index name, checked via RDAP against the registry for each TLD. It records a Reddit-named choice: `redditindex.com` is the primary, with `redditbrandindex.com` registered defensively and redirecting to it.

| Column | Type | Meaning |
|---|---|---|
| `domain` | string | The domain checked. 104 `.com`, plus the `.co` / `.io` / `.net` / `.org` variants of four shortlisted names. |
| `name_family` | enum | Where the Reddit mark sits inside the name. Five values, table below. A trademark-posture classification, not a filing convenience. |
| `status` | `available` / `taken` | RDAP result. `available` = registry returned 404. No `error_*` rows survived this run. |
| `registered_date` | ISO date | Creation date when taken. Empty when available. |
| `note` | `CHOSEN` / `DEFENSIVE` / `LIVE-COMPETITOR` | Marks the three rows that carry a decision. Empty on the other 117. |
| `checked_date` | ISO date | Always `2026-08-04`. |

**92 of 120 available.** Availability moves — re-run before buying.

`CHOSEN` is `redditindex.com`, `DEFENSIVE` is `redditbrandindex.com`. `LIVE-COMPETITOR` is `whatredditthinks.com`, registered 2026-05-25 and live with an adjacent per-brand audit product — see [../00-concept.md](../00-concept.md). The trademark exposure of the chosen name was priced and knowingly accepted; the full record, including the migration target, is [../decisions/0001-name-reddit-index.md](../decisions/0001-name-reddit-index.md).

### `name_family`

| Value | Rows | Available | Meaning |
|---|---:|---:|---|
| `reddit-named` | 82 | 57 | Contains "reddit" as a leading or embedded element: `redditindex.com`, `theredditverdict.com`. The chosen family. |
| `reddit-named-hyphenated` | 9 | 9 | The same, hyphenated: `reddit-index.com`. |
| `reddit-derived` | 3 | 3 | Built on "subreddit": `subredditindex.com`, `subredditrankings.com`. |
| `descriptive-phrase` | 16 | 13 | Reddit is the object of a phrase: `brandsonreddit.com`, `whatredditsays.com`. |
| `no-reddit` | 10 | 10 | No Reddit token at all: `upvoteindex.com`, `forumverdict.com`. |

### Why `descriptive-phrase` is a family of its own

Because the construction changes the trademark posture, which is a real finding rather than a way of sorting rows. In a `reddit-named` domain, REDDIT leads and the name reads as a Reddit sub-brand. In a `descriptive-phrase` domain, Reddit is the *subject being covered*.

The two adjacent families buy nothing. Hyphens are treated as irrelevant to confusing similarity, so `reddit-named-hyphenated` carries the same posture with worse typability, and "subreddit" is Reddit's own product term.

`brandsonreddit.com` is available and is materially the better name on this axis. It was not taken, and it is the documented migration target.

### Regenerating

RDAP is a public read-only registry lookup, no key needed. Verisign serves `.com` and `.net`; `.co`, `.io` and `.org` sit on their own endpoints, resolvable through the IANA bootstrap file:

```
GET https://rdap.verisign.com/{tld}/v1/domain/{domain}   # .com and .net
GET https://data.iana.org/rdap/dns.json                  # bootstrap for every other TLD
# 404 = available, 200 = taken
```

Send a browser User-Agent, cap concurrency at ~8, and retry on 429 and 503.

---

[← Back to README](../README.md) · [Taxonomy](../03-taxonomy.md) · [Subreddit mapping](../04-subreddit-mapping.md) · [Category tests](../14-category-tests.md) · [The algorithm](../13-algorithm.md) · [Entity resolution](../05-entity-resolution.md) · [Legal](../01-legal.md) · [Name decision](../decisions/0001-name-reddit-index.md)
