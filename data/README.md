# Data — column reference

## Bottom line

- Six flat CSVs (566 rows), the JSON that seeded the 20-category probe, and the probe itself. Every measurement here was taken on **2026-08-04**. Every CSV opens in Excel or Sheets and renders on GitHub.
- The newest layer is that probe. [subreddit-measurements.csv](subreddit-measurements.csv) measures 132 unique subreddits live: 37% delete brand talk, 36% are one product's own community, 51 are scorable. [../14-category-tests.md](../14-category-tests.md) reads the result.
- ⚠️ Three of its columns are easy to misread — `comment_span_hours` is velocity and not coverage, `brand_bearing_share` is a 5-brand floor, and `density_ub95` is why a zero never means absence. [Details below](#the-three-columns-people-misread).
- [domain-availability.csv](domain-availability.csv) records a **Reddit-named** outcome, not a Reddit-free one. The chosen name breaches Reddit's trademark clauses, knowingly. [decisions/0001-name-reddit-index.md](../decisions/0001-name-reddit-index.md) is authoritative.
- No Capterra category catalog and no product counts are republished here. See [what is deliberately NOT here](#what-is-deliberately-not-here).

Click a file, then **Download raw file** to get the CSV rather than the rendered table.

| File | Rows | What it is |
|---|---:|---|
| [phase1-categories.csv](phase1-categories.csv) | 50 | The Phase 1 category spine |
| [subreddit-map.csv](subreddit-map.csv) | 131 | Category → subreddit mapping with rule posture |
| [subreddit-measurements.csv](subreddit-measurements.csv) | 132 | Every unique subreddit in the 20-category probe, measured live |
| [category-tests-20.csv](category-tests-20.csv) | 20 | Category rollup of those measurements, with 95% bounds |
| [category-candidates-20.json](category-candidates-20.json) | 20 | The probe's **input**: candidate subreddits and 5 seed brands per category |
| [probe.py](probe.py) | — | The measurement harness. Resumable |
| [brand-gazetteer-seed.csv](brand-gazetteer-seed.csv) | 113 | Seed brand list with ambiguity classification |
| [domain-availability.csv](domain-availability.csv) | 120 | The sweep behind the Reddit Index name |

---

## What is deliberately NOT here

There is no copy of Capterra's category catalog and no product counts.

Capterra's [Terms of Use](https://www.capterra.com/legal/terms-of-use/) §10 bans replicating "the look-and-feel, functionality, information architecture, **category structure**, or user experience", and §3 claims "any analyses, transformations, aggregations, compilations, metadata, scores, ratings, rankings… Derived Data" as their sole property.

Their `numberOfItems` counts were used as a **selection signal** to pick the 50, and are cited as evidence inside [../03-taxonomy.md](../03-taxonomy.md). They are not republished as a dataset. See that file for the derived-spine approach.

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
| `is_vendor_owned_sub` | `yes` / `no` | Whether the subreddit is the vendor's own community. These self-select for invested users and are a sentiment-bias hazard. |

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

⚠️ **Subscriber count does not predict signal.** r/PasswordManagers (54,640) yields more rankable comparison than r/marketing (1,958,693), because r/marketing's rules delete exactly that content. Full reasoning in [../04-subreddit-mapping.md](../04-subreddit-mapping.md).

---

## subreddit-measurements.csv

Every unique subreddit touched by the 20-category probe, measured live on 2026-08-04.

One row per **subreddit**, not per (category, subreddit) pair. The 187 candidate slots collapse to 132 unique subreddits, because subreddits overlap across categories — r/Entrepreneur alone serves 7.

This is a different instrument from `subreddit-map.csv` above, over a different category set ([../14-category-tests.md](../14-category-tests.md)). Names here carry **no `r/` prefix**, so strip the prefix from `subreddit-map.csv` before joining the two.

| Column | Type | Meaning |
|---|---|---|
| `subreddit` | string | Bare name, no `r/`. Case as sent to the API. |
| `status` | `ok` / `unavailable` | Whether `/r/{sub}/about` returned a `t5`. 131 `ok`, 1 `unavailable`. |
| `subscribers` | int | Count at measurement time. Empty when unavailable. Deliberately **not** a selection signal. |
| `rule_posture` | enum | How the subreddit's own rules treat brand talk. Four values, table below. |
| `community_type` | enum | Who the subreddit's population is. Three values, table below. |
| `comment_page_n` | int | Comments actually returned by the one page. 130 of 131 returned the full 100; r/talentacquisition returned 24. |
| `comments_per_hour` | float | `comment_page_n ÷ comment_span_hours` — the page's **actual** size, which is *up to* 100 and was 24 for r/talentacquisition. Feeds rate-bucketing in [../13-algorithm.md](../13-algorithm.md) §3. |
| `comment_span_hours` | float | How far back that one 100-comment page reached. ⚠️ Velocity, not coverage. |
| `brand_bearing_share` | float 0-1 | Share of those 100 comments containing any of the category's 5 seed brands. ⚠️ A floor. |
| `density_ub95` | float | 95% one-sided upper bound on brand density given a 100-comment sample. |
| `bb_per_hour` | float | `comments_per_hour` × `brand_bearing_share`. The rate-adjusted yield, and the selection signal. |
| `scorable` | `True` / `False` | `ok` **and** not hostile **and** not single-product. True on 51 of 132. |
| `distinct_threads_in_page` | int | Distinct `link_id`s among the 100 comments. A concentration check: a low value means the page is one busy thread rather than the subreddit. |
| `measured_at` | ISO UTC | Per-subreddit timestamp. Empty on the unavailable row. |

These are one-time measurements, not the pipeline's running state. Ingest runs continuously per bucket and scoring publishes once daily ([../13-algorithm.md](../13-algorithm.md) §7).

### `rule_posture`

| Value | Count | Meaning |
|---|---:|---|
| `permissive` | 64 | Organic brand discussion is allowed. |
| `hostile` | 48 | The rules remove promotional or product-mention content. **37% of the 131 reachable subreddits.** |
| `unknown` | 13 | The rules endpoint returned nothing parseable. **Not** a synonym for permissive. |
| `capped` | 6 | Allowed behind a karma gate or a weekly thread. |

Posture is classified by regex over the full `/about/rules` text, not by a human read. The largest communities skew strictest: r/smallbusiness (2.5M) and r/Accounting (1.27M) both classify hostile.

### `community_type`

| Value | Count | Meaning |
|---|---:|---|
| `single_product` | 48 | One product's own community — r/Bitwarden, r/Notion, r/CapCut. Dense, and **never scored**: the population already chose the product. Evidence only. |
| `ecosystem` | 6 | Vendor-named but market-wide in population: r/salesforce, r/shopify, r/aws, r/Adobe, r/reactjs, r/node. Scorable, carrying a flag. |
| `independent` | 78 | Neither. The scorable middle. |

The `ecosystem` class was a correction made during analysis. Blanket-excluding every vendor-named subreddit dropped CRM from 5 scorable subs to 4, which would have failed the category on a classification error rather than on evidence.

### The three columns people misread

**`comment_span_hours` measures velocity, not coverage.** One 100-comment page reached back 0.58h in r/recruitinghell and 28,823h — 3.3 years — in r/talentacquisition. Median 27.9h. The same instrument samples the last hour in one subreddit and the last three years in another, so it can never be read as how much of a subreddit was seen.

**`brand_bearing_share` is a floor, not an estimate.** Each subreddit was probed with only the 5 seed brands of its category. Real gazetteers run 20-100 brands, so every share here understates by roughly the ratio of the two lists. 45 of the 131 reachable subreddits measured exactly zero.

**`density_ub95` exists so a zero is never read as absence.** It is the 95% one-sided upper bound on brand density given a 100-comment sample, using the rule of three where the observed count was zero. Across reachable rows it runs 0.0296 to 0.65. A `0.0` share means *not detected in 100 comments*, bounded above by this column.

`bb_per_hour` is what ranks the corpus, and it inverts the intuition. The top rows are r/ObsidianMD (13.24), r/paypal (3.22) and r/Notion (2.70) — all single-product, all unscoreable. What the index can publish comes from the thinner independent middle.

⚠️ **Filter on `status = ok` first.** The one unavailable row, `B2BForSales`, has empty measurements and `density_ub95 = 3.0`. That is the rule-of-three formula run against an empty sample, not a density.

---

## category-tests-20.csv

One row per tested category, rolled up from the subreddit rows over that category's own candidate list. A subreddit serving several categories contributes to each of them. The reading is in [../14-category-tests.md](../14-category-tests.md).

| Column | Type | Meaning |
|---|---|---|
| `category` | string | Joins to `category-candidates-20.json`. ⚠️ Only 8 of the 20 match a `phase1-categories.csv` label verbatim; the rest are the same domains under longer labels, and no crosswalk ships yet. |
| `candidates` | int | Candidate slots for this category. Sums to 187 across the file. |
| `ok` | int | Candidates whose `/about` resolved. Sums to 186 — one subreddit was unavailable. |
| `hostile` | int | Candidates whose own rules remove brand talk. |
| `single_product` | int | Candidates that are one product's own community. |
| `scorable` | int | Candidates passing the `scorable` predicate. |
| `live_bb_per_hour` | float | Σ `bb_per_hour` across this category's scorable subs. The measured live yield. |
| `live_bb_per_hour_ub95` | float | The same sum computed at `density_ub95` instead of the observed share. |
| `seed_bb_3y` | int | The live rate projected across a 3-year archive window (26,280 hours). |
| `seed_bb_3y_ub95` | int | The same projection at the upper bound. |
| `meets_5_sub_floor` | `True` / `False` | `scorable ≥ 5`. True for 6 of 20. |

Both rate columns are computed from unrounded per-subreddit values, so multiplying the rounded rate by 26,280 reproduces `seed_bb_3y` only approximately — CRM stores 53,006 where the rounded column recomputes to 53,086.

⚠️ **This file cannot declare a category dead.** 17 of 20 clear 400 seed-brand mentions on the point estimate and **all 20** clear it at the upper bound. What fails is the five-scorable-subreddit floor, and the cause is short candidate lists rather than absent discussion.

---

## category-candidates-20.json

The **input** to the probe, not an output. Twenty objects, each with a `category`, exactly 5 seed `brands`, and a hand-built `subreddits` list. 187 slots, 132 unique.

```json
{"category":"CRM","brands":["HubSpot","Salesforce","Pipedrive","Zoho","Attio"],
 "subreddits":["CRM","sales","salesforce","techsales","hubspot","gohighlevel",
               "Zoho","smallbusiness","Entrepreneur","EntrepreneurRideAlong","SaaS"]}
```

Two properties of this file decide how every result reads. The 5-brand lists are what make each yield figure a floor. The subreddit lists are the study's binding constraint: widening them is what would move the 14 categories now sitting below the five-sub floor.

⚠️ `probe.py` loads its category list from a sibling file named `cat20.json`. Rename this file or repoint that path before the first run.

---

## probe.py

The harness behind both CSVs. Five API calls per **unique reachable** subreddit — `/r/{sub}/about`, `/r/{sub}/about/rules`, `/r/{sub}/comments?limit=100`, and `/r/{sub}/search` for the first 2 seed brands. The harness caches by subreddit, so the 187 slots cost 131 × 5 + 1 = **656 base calls**, not 187 × 5. Retries are additional and unlogged.

**Resumable by design.** It writes one JSON per subreddit atomically (`.tmp`, then `os.replace`) and returns the on-disk record for any subreddit already measured, so a re-run costs only the gap. A run interrupted at slot 140 resumes at slot 140.

**Credentials are read, never written.** It pulls `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` and `REDDIT_USER_AGENT` from the existing Reddit MCP config and mints an app-only `client_credentials` token. App-only OAuth is read-only — it cannot post, vote or comment. Nothing is hardcoded, and no secret lands in this repo.

Rate discipline: `time.sleep(0.75)` between calls, retry on 429/500/502/503, one token re-fetch on 401.

### Regenerating

```bash
python3 probe.py        # ~25 min for 187 candidate slots at a safe request rate
```

Set two things before the first run. `OUT`, at the top of the file, is an absolute scratch path for the per-subreddit JSON. And the category list loads from a sibling `cat20.json`, shipped here as `category-candidates-20.json`.

Two things the harness does not do. The per-subreddit JSON stays in `OUT` and is not committed here, and the step folding those JSONs into the two CSVs is not part of `probe.py` — it measures, prints progress, and stops. Rebuilding the CSVs from a fresh run needs that step supplied.

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

---

## domain-availability.csv

The sweep that produced the Reddit Index name, checked via RDAP against the registry for each TLD.

It records a Reddit-named choice: `redditindex.com` is the primary, with `redditbrandindex.com` registered defensively and redirecting to it.

| Column | Type | Meaning |
|---|---|---|
| `domain` | string | The domain checked. 104 `.com`, plus the `.co` / `.io` / `.net` / `.org` variants of four shortlisted names. |
| `name_family` | enum | Where the Reddit mark sits inside the name. Five values, table below. A trademark-posture classification, not a filing convenience. |
| `status` | `available` / `taken` | RDAP result. `available` = registry returned 404. No `error_*` rows survived this run. |
| `registered_date` | ISO date | Creation date when taken. Empty when available. |
| `note` | `CHOSEN` / `DEFENSIVE` / `LIVE-COMPETITOR` | Marks the three rows that carry a decision. Empty on the other 117. |
| `checked_date` | ISO date | Always `2026-08-04`. |

**92 of 120 available.** Availability moves — re-run before buying.

`CHOSEN` is `redditindex.com`, `DEFENSIVE` is `redditbrandindex.com`. `LIVE-COMPETITOR` is `whatredditthinks.com`, registered 2026-05-25 and live with an adjacent per-brand audit product — see [../00-concept.md](../00-concept.md).

⚠️ **The chosen name knowingly breaches Reddit's trademark clauses, and the realistic enforcement path is a UDRP filing Reddit wins.** The exposure was priced and accepted; a loss costs the domain, not the project. The full record, including the migration target, is [../decisions/0001-name-reddit-index.md](../decisions/0001-name-reddit-index.md).

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

[← Back to README](../README.md) · [Taxonomy](../03-taxonomy.md) · [Subreddit mapping](../04-subreddit-mapping.md) · [Category tests](../14-category-tests.md) · [The algorithm](../13-algorithm.md) · [Entity resolution](../05-entity-resolution.md) · [Name decision](../decisions/0001-name-reddit-index.md)
