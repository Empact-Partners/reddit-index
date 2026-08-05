# Build Prompt — Reddit Index

*Paste everything below the line into a new Claude Code session, working in a fresh clone of `Empact-Partners/reddit-index`. It is written to be executed top to bottom with no clarifying questions.*

---

You are building **Reddit Index** — a public site at [redditindex.com](https://redditindex.com) that ranks software brands by what Reddit actually says about them. It is Empact Partners' property and a cold-outreach asset: the value is being able to send a company a link to a page about itself.

This repository already contains ~17 research documents, 9 architecture decision records, and a measured 20-category subreddit study. **Everything is specified. Nothing needs to be invented.** Your job is to build what the documents say, in the milestone order below.

## Before you write a line of code

Read these, in this order. They are the contract.

| File | Why |
|---|---|
| [00-concept.md](00-concept.md) | Product, page-by-page UX |
| [07-index-methodology.md](07-index-methodology.md) | The statistics. A hostile CMO attacks this doc first |
| [08-architecture.md](08-architecture.md) | Flow, storage split, schema, env vars, what runs when |
| [13-algorithm.md](13-algorithm.md) | The four discovery lanes and the daily ingest loop |
| [09-design.md](09-design.md) | Visual spec, trade dress, component inventory, accessibility |
| [16-design-system.md](16-design-system.md) | Tokens, shadcn/lucide map, category colours, build gates |
| [15-empact-brand.md](15-empact-brand.md) | The inherited brand, and what this site deliberately refuses |
| [decisions/](decisions/) | 0005 through 0009 govern behaviour you must not deviate from |
| [14-category-tests.md](14-category-tests.md) | Which categories can be ranked, and on what evidence |
| [01-legal.md](01-legal.md) | Why attribution, delete-sync and the footer are not optional |

Then read [HANDOFF.md](HANDOFF.md) for known open defects.

## Infrastructure that already exists

Do not create these. They are provisioned.

| Thing | State |
|---|---|
| Domain | `redditindex.com`, verified, A record → `216.150.1.1`, `misconfigured: false` |
| Vercel project | `reddit-index` on the **empact-partners** team, framework `nextjs` |
| Git link | `Empact-Partners/reddit-index` → pushes to `main` deploy |
| Reddit API | App-only OAuth (`client_credentials`), read-only, credentials already in `~/.claude.json` under the `reddit` MCP server env |
| `www` subdomain | ⚠️ **Not configured.** No CNAME. Apex works. Flag it, do not block on it |

You must create: the Supabase project, the Railway worker service, and the environment variables in both places.

---

# The non-negotiables

These are the rules that make the site defensible. A milestone is not complete if it breaks one.

## Routes

```
/                  pooled board, all categories
/{category}/       one category
/{company}/        one company, across every category it qualifies in
/methodology       the frozen method
/search            optional standalone; search is primarily inline
```

**Categories and companies share one path segment.** Precedence: framework paths → site routes → category slugs → company slugs. **A duplicate across that union fails the build.** Published slugs are frozen and never regenerated from display names — a company URL that moves after indexing loses the ranking that made it worth sending. ([decisions/0007](decisions/0007-flat-url-namespace.md))

## The metric

**One published number: the Reddit Love Score, integer 0–100.**

```
N_op  = pos + neg                            opinionated mentions only
p̃     = (x_pos + α₀) / (N_op + α₀ + β₀)      empirical-Bayes, leave-one-out category priors
Reddit Love Score = round(100 · p̃)
```

Sorting it descending **is** the consolidated view: most loved at the top, most hated at the bottom. "Most Hated" is a label on a position in one ordering, never a second fit. Never write "raw score" — `raw` already means raw `n` as opposed to `n_eff`. ([decisions/0006](decisions/0006-single-reddit-love-score.md))

**Two headline metrics per row:** Reddit Love Score, and total mention count. Everything else is evidence, still published, behind a disclosure.

## Eligibility

Four diversity floors, **all absolute at every tier**:

| Floor | Value |
|---|---|
| Distinct authors | ≥ 50 |
| Distinct subreddits | ≥ 5 |
| Max share from one thread | ≤ 20% of `n` |
| Max share from one author | ≤ 5% of `n` |

Plus **one eligibility gate**, which is per category and scales — `n_eff ≥ n_min`, where `n_min` comes from the category's published precision target (Deep ±4pp → 600, Standard ±5pp → 400, Thin ±7pp → 200). The gate is **not** a floor; never write "five floors" or count the gate among them. `n_eff = n / DEFF`, and `DEFF` is computed twice — clustered by thread and by author — carrying the larger. ([decisions/0009](decisions/0009-category-scaled-thresholds.md))

A brand failing anything publishes as **Not enough data** with the failing test named. It is never silently omitted. **"This category cannot be ranked" and "this brand is below threshold" are different states with different wording** — a brand can pass every brand-level test inside a category that fails viability.

## Mentions

A brand named in a **post body** and a brand named in a **comment** are counted identically and both displayed. They differ only by `doc_type`, which changes the label and the permalink target — never the size, order, prominence or scoring weight.

Every mention card renders **seven fields, none optional**:

1. Brand · 2. Subreddit (`r/name`, linked) · 3. Username (`u/name`, real text in the DOM, never an avatar or initial) · 4. Timestamp (absolute, ISO in `title`) · 5. Sentiment label (the word first) · 6. **Full comment text, never truncated, no "read more", no fade mask** · 7. Permalink, the card's largest tap target at 44×44px minimum, labelled "View on Reddit"

No vote arrows, no karma pills, no awards, no nested-reply rails. Cards for content deleted at the source disappear on the next nightly sync — no tombstone, no cached copy, no `[deleted]` placeholder.

## Trade dress — banned outright

`#FF4500` and **every orange, amber and warm red near it**. Snoo in any form, including redraws. Reddit Sans and any lookalike. Speech-bubble marks. Reddit UI furniture.

The identity is a wordmark: **Reddit Index**, Syne Medium, Sherpa Blue `#02454F` on Snowbelt. No glyph.

## The footer

Four slots, fixed order, identical on **every** route including error pages and paginated pages. Slot 4 ships **verbatim**:

> Not affiliated with, endorsed by, or sponsored by Reddit, Inc. 'Reddit' is a trademark of Reddit, Inc., used here descriptively.

Small size never Micro, full opacity, real text in the DOM, never inside a `<details>` or a modal, never adjacent to anything commercial. Slot 2 is "Created by Empact Partners", linked, at reading size.

**A page that renders without slot 4 is a bug of the same severity as a page rendering the wrong score.**

## Never

Advertising, sponsorship, affiliate links or paid placement on any surface. Brand logos on any ranking surface. Photography beside a score. Any copy implying partnership with Reddit. A superlative column heading without its score chip.

---

# Milestones

> **Re-cut 2026-08-05, during the first build.** The ladder below sequenced the
> eligibility gate, the honest below-threshold and insufficient-signal states, and
> `/methodology` **after** the milestone that computes and renders a score. Three
> documents make that ordering unworkable: [decisions/0005](decisions/0005-superlative-labels.md)
> makes the methodology page and the measured-variable-beside-the-superlative rule
> *conditions* of using "Most Loved" and "Most Hated" at all;
> [decisions/0009](decisions/0009-category-scaled-thresholds.md) says "a flag is not a
> gate — anything on a board is a claim"; and [07 §9](07-index-methodology.md) requires
> the method frozen with its commit hash recorded *before the first production crawl*.
>
> So the honesty layer shipped first, and the data made that the only sensible order
> anyway: on a sample corpus almost every company sits below threshold and several
> categories cannot be ranked, which makes those two states the site's dominant
> surface rather than an edge case. The pre-deploy gates in M4 also run from the
> first build — they are cheap, and the apex is live.
>
> A collection **window** is also missing from every milestone below. It is a trailing
> 12 months, uniform weight, per [07 §6](07-index-methodology.md), frozen in
> `methodology_params` — without it a builder scores 2022 threads, because Lane D
> searches `t=all`.
>
> What actually shipped, and the state of each gate, is in [HANDOFF.md](HANDOFF.md).

Work them in order. Each has an acceptance gate; **do not start the next milestone until the current gate passes**. Stopping cleanly at any gate is a valid end state.

## M1 — Vertical slice: CRM, end to end, real data

The point is to prove the whole pipeline on one category before scaling anything.

**Build:**

1. Supabase project. Schema per [08-architecture.md §3](08-architecture.md), which is the authority: `categories`, `subreddits`, `category_subreddits`, `brands`, `brand_aliases`, `threads`, `mentions`, `mention_sentiment`, `brand_category_scores`, `leaderboards`, `brand_pages`, `removals`, `ingest_state` — thirteen tables. (`documents` and `scores` appeared in an earlier draft of this line and exist nowhere in §3; they were `threads` and `brand_category_scores`.) Include `doc_type`, the frozen `slug` column, persisted rank columns, and the per-category threshold tier.
2. Railway worker, long-lived. Ingest **CRM only**, using the scorable generalist subreddits in [data/subreddit-measurements.csv](data/subreddit-measurements.csv). Lane B (`/r/{sub}/comments` with multireddit rate-bucketing) plus Lane D, per [13-algorithm.md](13-algorithm.md). Respect ~80 req/min and `time.sleep(0.75)`.
3. Entity resolution over the CRM slice of [data/brand-gazetteer-seed.csv](data/brand-gazetteer-seed.csv). **Word-boundary matching, never substring** — a naive pass matched "Monday" the weekday in r/nfl and "SAP" the fluid in r/worldbuilding. Use the gazetteer's `ambiguity_class`. Target precision ≥ 0.97 ([05-entity-resolution.md](05-entity-resolution.md)).
4. Targeted ABSA sentiment — one comment naming three brands has three polarities ([06-sentiment.md](06-sentiment.md)).
5. Score computation per the formula above, with cluster-bootstrap intervals.
6. Next.js app: `/`, `/crm/`, `/hubspot/`. shadcn/ui + lucide + Tailwind, tokens from [16-design-system.md §2](16-design-system.md), fonts self-hosted.

**Gate:**
- `/hubspot/` renders real Reddit mentions with working permalinks that resolve to the actual comments.
- A Reddit Love Score computes from real ingested data and matches a hand-recomputation on a 20-mention sample.
- The footer's four slots render on every one of the three routes.
- Vendor-named subreddits contributed **zero** scoring mentions.

## M2 — Index, thresholds, and the honest states

**Build:**

1. `DEFF` by thread and by author, carrying the larger; `n_eff`.
2. The four diversity floors and the per-category tier gate.
3. The **insufficient-signal** state as a first-class component — a full-width panel on the dotted field, naming which floor failed with the observed number beside the required one, listing every brand found, using **no accent hue**.
4. The distinct **below-threshold** state for an individual brand inside a rankable category.
5. Score chip: five fields, one line, Small or larger, never truncated, never tooltip-only.
6. `/methodology`, with the version, the collection window, the tier and its precision target.

**Gate:**
- A brand below threshold renders the **named** failing floor with both numbers.
- A category that cannot be ranked renders the insufficient-signal panel, not a thin ranking and not a 404.
- Freeze and version the methodology **before** looking at any ranking output. Commit the version.

## M3 — All 20 categories, the pooled board, daily refresh

**Build:**

1. Ingest all 20 measured categories ([data/categories.csv](data/categories.csv), [14-category-tests.md](14-category-tests.md)). **v1 is the 20 measured categories, not the 50-row Phase 1 taxonomy** — no crosswalk between the two label sets exists yet.
2. Category identity: icon tile (40/32px, **6px radius, never circular or pill**, category-colour fill, Space Black lucide glyph at `strokeWidth 2`) and the category chip. Category colour **never touches a score surface**.
3. The pooled homepage board: top 100 most loved + top 100 most hated by published Reddit Love Score, **max 5 brands per category in each list, disclosed on the page**, third column = category. The two lists are drawn from opposite ends of one ordering and **must be disjoint** — if the qualifying population is under 200, each takes at most `floor(N/2)` and the page states the actual counts.
4. The category-page switcher: shadcn/ui `Tabs` styled as a segmented control, state in `?view=list`, canonical to the bare category URL, `noindex` on the variant, boards as default. Both panels rendered, inactive one `inert`, no layout shift on switch.
5. Daily pass at ~03:00 UTC → `revalidateTag` for changed categories and companies only. Plus `delete_sync`.

**Gate:**
- 20 category pages live; every company page reachable from at least one.
- The daily pass runs end to end and revalidates only what changed.
- No category colour appears on any score surface (grep the built CSS).
- The pooled board's two lists share zero brands.

## M4 — Search, responsive, accessibility, and the deploy gates

**Build:**

1. Category-scoped company search — shadcn/ui `Command`, static client-side index (company name, aliases, slug, category, score). Scope is all categories on the homepage, that category on a category page. **Two distinct honest not-found states**: "tracked but below threshold" and "not tracked at all". They are different answers.
2. Responsive per [16-design-system.md §6](16-design-system.md). Below 768px the board **stacks** — full Most Loved, then full Most Hated, each keeping its heading, accent and score chips. Tables scroll inside their own container with rank and brand frozen. **The page body never scrolls sideways, and columns are never dropped** — the dropped ones would be the diversity floors.
3. Accessibility per [09-design.md](09-design.md) and [16-design-system.md §7](16-design-system.md).
4. `sitemap.xml`, self-canonical on every page, structured data that never implies a company published its own rating.

**The pre-deploy gates, all mechanical, all blocking:**

| Gate | Check |
|---|---|
| Trade dress | Built CSS, SVG and font manifest contain no `FF4500`, `ff4500`, `orange`, `snoo`, `reddit-sans` |
| Slug uniqueness | Categories ∪ companies ∪ reserved paths asserted unique |
| Category constraints | Every colour in `categories.csv` re-verified against its generation constraints |
| Icon names | Every icon name resolves in the installed lucide version |
| Footer slot 4 | The non-affiliation string present as text on every rendered route |
| Contrast | Token pairs re-measured, not trusted from a document |

**Gate:** every check above fails the build when deliberately violated. Prove it by breaking one and watching it fail, then revert.

---

# Environment variables

Never commit a value. ([08-architecture.md §7](08-architecture.md))

**Vercel (Production, Preview, Development):** Supabase URL and anon key, `REVALIDATE_SECRET`.

**Railway only, never set on Vercel:** Supabase service-role key, direct Postgres connection string, Reddit client id and secret, Reddit user agent, the LLM key for the sentiment tail, `REVALIDATE_SECRET` (the worker is the caller).

---

# How to work

- **Commit at every gate**, not at the end. Push to `main` deploys.
- When a document and your instinct disagree, **the document wins** — or you change the document first, in the same commit, with the reason.
- If you find a contradiction between two documents, fix it rather than picking one silently, and record it in [HANDOFF.md](HANDOFF.md).
- Do not add a feature that is not in the specification. The scope is deliberately small.
- Data quality beats page count. A category that cannot be ranked honestly renders the insufficient-signal panel, and that is a **correct** outcome, not a failure to fix by lowering a threshold.
