# Data — column reference

## Bottom line

- Four flat CSVs, 414 rows, all measured on **2026-08-04**. Every file opens in Excel or Sheets and renders on GitHub.
- [domain-availability.csv](domain-availability.csv) records a **Reddit-named** outcome, not a Reddit-free one. The chosen name breaches Reddit's trademark clauses, knowingly. [decisions/0001-name-reddit-index.md](../decisions/0001-name-reddit-index.md) is authoritative.
- No Capterra category catalog and no product counts are republished here. See [what is deliberately NOT here](#what-is-deliberately-not-here).

Click a file, then **Download raw file** to get the CSV rather than the rendered table.

| File | Rows | What it is |
|---|---:|---|
| [phase1-categories.csv](phase1-categories.csv) | 50 | The Phase 1 category spine |
| [subreddit-map.csv](subreddit-map.csv) | 131 | Category → subreddit mapping with rule posture |
| [brand-gazetteer-seed.csv](brand-gazetteer-seed.csv) | 113 | Seed brand list with ambiguity classification |
| [domain-availability.csv](domain-availability.csv) | 120 | The sweep behind the Reddit Index name, and the exposure it carries |

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

⚠️ **The chosen name breaches Reddit's trademark clauses.** [Data API Terms §4.1](https://www.redditinc.com/policies/data-api-terms) forbids using Reddit Trademarks "in, or as part of the name of your App", and [Developer Terms §5.3](https://www.redditinc.com/policies/developer-terms) repeats the prohibition. Neither has an exception this name fits.

The enforcement path is a UDRP filing, not a lawsuit. Reddit files them *pro se* for roughly $1,500 and has won every one found: [`reddit.win`](https://www.wipo.int/amc/en/domains/decisions/text/2020/d2020-1834.html) (D2020-1834), [`redditpromotion.com` / `redditshop.com`](https://www.wipo.int/amc/en/domains/decisions/text/2019/d2019-2964.html) (D2019-2964), [`reddit.co`](https://www.wipo.int/amc/en/domains/decisions/text/2018/dco2018-0008.html) (DCO2018-0008).

Low traffic is not a defence. A UDRP is a registrar-level administrative proceeding: no damages, no discovery, no proof that anyone visited. It needs only that Reddit notices.

**What losing costs is the domain, not the project.** The pipeline, the index, the methodology and the content all survive a transfer. That asymmetry is why the exposure was priced and accepted.

The name is also Reddit-locked. Phase 3 in [../12-phasing.md](../12-phasing.md) contemplates Hacker News, Stack Overflow and other sources, and "Reddit Index" cannot carry them without a rename. That option was sold for legibility in a cold email, knowingly.

### `name_family`

| Value | Rows | Available | Meaning |
|---|---:|---:|---|
| `reddit-named` | 82 | 57 | Contains "reddit" as a leading or embedded element: `redditindex.com`, `theredditverdict.com`. The chosen family. |
| `reddit-named-hyphenated` | 9 | 9 | The same, hyphenated: `reddit-index.com`. |
| `reddit-derived` | 3 | 3 | Built on "subreddit": `subredditindex.com`, `subredditrankings.com`. |
| `descriptive-phrase` | 16 | 13 | Reddit is the object of a phrase: `brandsonreddit.com`, `whatredditsays.com`. |
| `no-reddit` | 10 | 10 | No Reddit token at all: `upvoteindex.com`, `forumverdict.com`. |

### Why `descriptive-phrase` is a family of its own

Because the construction changes the trademark posture, which is a real finding rather than a way of sorting rows.

In a `reddit-named` domain, REDDIT leads and the name reads as a Reddit sub-brand. That is the implied-affiliation problem the [`reddit.win`](https://www.wipo.int/amc/en/domains/decisions/text/2020/d2020-1834.html) panel described. In a `descriptive-phrase` domain, Reddit is the *subject being covered*, which supports a real legitimate-interest argument.

The two adjacent families buy nothing. UDRP panels treat hyphens as irrelevant to confusing similarity, so `reddit-named-hyphenated` carries the same exposure with worse typability. `reddit-derived` is no safer either: "subreddit" is Reddit's own product term.

`brandsonreddit.com` is available and is materially the better name on this axis. It was not taken, and it is the documented migration target — [../decisions/0001-name-reddit-index.md](../decisions/0001-name-reddit-index.md) records why.

### Regenerating

RDAP is a public read-only registry lookup, no key needed. Verisign serves `.com` and `.net`; `.co`, `.io` and `.org` sit on their own endpoints, resolvable through the IANA bootstrap file:

```
GET https://rdap.verisign.com/{tld}/v1/domain/{domain}   # .com and .net
GET https://data.iana.org/rdap/dns.json                  # bootstrap for every other TLD
# 404 = available, 200 = taken
```

Send a browser User-Agent, cap concurrency at ~8, and retry on 429 and 503.

---

[← Back to README](../README.md) · [Taxonomy](../03-taxonomy.md) · [Subreddit mapping](../04-subreddit-mapping.md) · [Entity resolution](../05-entity-resolution.md) · [Name decision](../decisions/0001-name-reddit-index.md)
