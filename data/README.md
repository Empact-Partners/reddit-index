# Data — column reference

Four flat CSVs. All measured on **2026-08-04**. Every file opens in Excel or Sheets and renders on GitHub.

Click a file, then **Download raw file** to get the CSV rather than the rendered table.

| File | Rows | What it is |
|---|---:|---|
| [phase1-categories.csv](phase1-categories.csv) | 50 | The Phase 1 category spine |
| [subreddit-map.csv](subreddit-map.csv) | 131 | Category → subreddit mapping with rule posture |
| [brand-gazetteer-seed.csv](brand-gazetteer-seed.csv) | 113 | Seed brand list with ambiguity classification |
| [domain-availability.csv](domain-availability.csv) | 87 | The domain sweep behind the UGC Ranks name |

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
| `subreddit_map_status` | `mapped` / `pending` | Whether this category has rows in `subreddit-map.csv`. 12 of 50 are mapped. |
| `phase` | int | Always `1` in this file. |

**38 of the 50 are `pending`.** Only 12 categories have been mapped and signal-tested so far. That gap is real work, not an oversight.

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

⚠️ **Subscriber count does not predict signal.** r/PasswordManagers (54,639) yields more rankable comparison than r/marketing (1,958,653), because r/marketing's rules delete exactly that content. Full reasoning in [../04-subreddit-mapping.md](../04-subreddit-mapping.md).

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

The sweep that produced the UGC Ranks name. Checked via RDAP against the Verisign `.com` registry.

| Column | Type | Meaning |
|---|---|---|
| `domain` | string | The domain checked. `.com` only — the `.io` and `.co` variants were checked separately and are noted in [../decisions/0001-name-ugc-ranks.md](../decisions/0001-name-ugc-ranks.md). |
| `name_family` | enum | `ugc-neutral` (no trademark exposure), `reddit-trademark` (contains "reddit"), `descriptive` (neither). |
| `status` | `available` / `taken` / `error_*` | RDAP result. `available` = registry returned 404. |
| `registered_date` | ISO date | Creation date when taken. Empty when available. |
| `checked_date` | ISO date | Always `2026-08-04`. |

**61 of 87 available.** Availability moves — re-run before buying.

### Regenerating

RDAP is a public read-only registry lookup, no key needed:

```
GET https://rdap.verisign.com/com/v1/domain/{domain}
# 404 = available, 200 = taken
```

Send a browser User-Agent, cap concurrency at ~8, and retry on 429 and 503.

---

[← Back to README](../README.md) · [Taxonomy](../03-taxonomy.md) · [Subreddit mapping](../04-subreddit-mapping.md) · [Entity resolution](../05-entity-resolution.md)
