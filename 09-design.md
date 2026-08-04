# UGC Ranks — Design Specification

## Bottom line

- Loved is **Lucky Green #40C890**. Hated is **Sugar Grape #A155FF**, not a red. Red is not in the Empact palette, and importing one adds a "system failure" register the score cannot support.
- 🟢 Green and purple are the only palette accents far enough apart in hue to read as opposing axes, and unlike red-green they stay separable under common colour vision deficiencies.
- Meaning is never carried by colour alone. Every loved/hated surface also carries a word label, an icon shape, and a column heading.
- Every score chip carries the measured variable beside the superlative: index value, interval, opinionated-mention count, `n_eff`, and window. That line is the condition [decisions/0005](decisions/0005-superlative-labels.md) ships under, so it is never truncated, hidden behind hover, or moved into a tooltip.
- 🟡 Both accents fail text contrast at their brand values. Derived deep tints handle text; brand values stay for fills, rules, and chips.
- The **insufficient-signal state is a first-class component**, not an error page. ERP and Help Desk cannot be ranked honestly from Reddit, and the design must say so on the same page furniture.
- ⚠️ Brand pages render full Reddit comment text and usernames. That is the owner's priced decision, documented in [01-legal.md](01-legal.md); the design's job is to make attribution and permalinks impossible to miss, not to hide the risk.

Page content is specified in [00-concept.md](00-concept.md). This file specifies the visual treatment of that content and never changes it.

---

## Colour semantics

### The loved / hated pair

| Candidate | Verdict | Reason |
|---|---|---|
| Lucky Green #40C890 → loved | **Adopted** | Only unambiguously positive accent in the palette |
| Off-brand red → hated | Rejected | Not in the palette; reads as "outage", overstating a sentiment index |
| Virtual Goal #C6FF53 → hated | Rejected | A lime; sits beside Lucky Green in hue, reads as a second positive |
| Sherpa Blue #02454F → hated | Rejected | The structural colour already. Cannot also carry sentiment |
| **Sugar Grape #A155FF → hated** | **Adopted** | Far from green in hue, strong, tonally neutral. Asserts "the other axis", not "bad" |

The two-axis model is the reason. Love and hate are separate indices, not two ends of one bar, so two unrelated hues beat a red-to-green gradient, which implies one continuum. Neutral, abstain, and unranked states get Snowbelt fills, Space Black text, no accent hue.

### Tokens and measured contrast

| Token | Hex | Use | On Snowbelt | On Sherpa |
|---|---|---|---|---|
| Sherpa Blue | #02454F | Nav, footer, headings, dark bands | 9.38 | — |
| Space Black | #171616 | Body text | 15.86 | — |
| Snowbelt | #EEF1ED | Page background | — | 9.38 |
| Lucky Green | #40C890 | Loved fills, bars, chips | 1.87 ✗ | 5.02 ✓ |
| Green Deep *(derived)* | #267856 | Loved text and icons, light | 4.72 ✓ | — |
| Sugar Grape | #A155FF | Hated fills, bars, chips | 3.51 ✗ | 2.67 ✗ |
| Grape Deep *(derived)* | #7940BF | Hated text and icons, light | 5.59 ✓ | — |
| Grape Light *(derived)* | #D0AAFF | Hated accents on dark | — | 5.53 ✓ |
| Virtual Goal | #C6FF53 | CTA fills, Space Black text | 15.33 on black | 9.07 ✓ |

Ratios are computed from the hex values, not estimated. Derived tints are display tokens, not palette additions; they exist because the brand accents are mid-luminance and fail as text.

Text on either accent fill is Space Black: 8.5:1 on green, 4.52:1 on grape. White on Sugar Grape is 3.99:1, banned for body text.

---

## Type scale

Syne Medium from Display through H4, Public Sans below. All numerals use `font-variant-numeric: tabular-nums` so scores align.

| Role | Desktop | Mobile | Line height |
|---|---|---|---|
| Display | 61px | 39px | 1.05 |
| H1 | 49px | 31px | 1.10 |
| H2 | 39px | 25px | 1.15 |
| H3 | 31px | 21px | 1.20 |
| H4 | 25px | 19px | 1.25 |
| Lead | 20px | 18px | 1.55 |
| Body | 17px | 17px | 1.60 |
| Small | 15px | 15px | 1.50 |
| Micro | 13px | 13px | 1.40 |

Micro is reserved for timestamps, usernames, and table metadata; it never carries a claim a reader must act on. Measure caps at 68 characters for comment text, the site's widest content.

Every number a reader is entitled to check sits at Small or larger. That covers the score-chip metadata line, the threshold figures, and the non-affiliation line in the footer.

## Spacing, grid, and surface

| Property | Value |
|---|---|
| Base unit | 4px; scale 4, 8, 12, 16, 24, 32, 48, 64, 96, 128 |
| Container | 1200px max; gutters 24px / 16px |
| Grid | 12 / 8 / 4 columns, desktop / tablet / mobile |
| Section rhythm | 96px / 56px |
| Radius | Cards 6px, chips 999px, tables 0 |
| Borders | 1px Sherpa Blue at 12% alpha. No shadows |

The linear module runs behind category headers; the dotted module fills the insufficient-signal state and section breaks. Photography appears only on `/methodology`, black and white, never beside a score or brand. There is no second `/about` route.

---

## Component inventory

| Component | Contains | Behaviour |
|---|---|---|
| **Exposure-confound line** | One sentence: rank reflects what Reddit says, not product quality, and enterprise-sold incumbents skew negative | Persistent, above the first board on every ranked surface, per [07-index-methodology.md §8](07-index-methodology.md). A distinct component from the methodology callout; both appear |
| **Loved / hated board** | Two equal columns, **Most Loved** and **Most Hated**, top 10 each: rank, brand, category on pooled boards, score chip | Ranked independently on two different indices, never mirrored |
| **Ranking table row** | Rank, brand, Love Index, Hate Index, raw `n`, `n_eff`, distinct authors, distinct subreddits, distinct threads, top-thread share, qualification badge | Sortable by any numeric column, with the default sort key named on the page. Tied ranks share a rank number and a tie marker |
| **Score chip** | See below | Five fields, fixed order, never truncated and never hover-only |
| **Mention card** | Brand, subreddit, username, timestamp, sentiment label, full comment text, permalink | Permalink is the primary link and wraps the timestamp. Comment text is quoted, never styled as site copy |
| **Qualification badge** | "Ranked", "Statistically tied", or "Below threshold", plus the numeric threshold | Always paired with the figure that failed. A badge hiding its number is not shippable |
| **Breadcrumbs** | Home → Category → Brand | Every page below the homepage. Ordered list, `aria-label="Breadcrumb"` |
| **Category grid** | Every Phase 1 category, linked, with brand count and last-updated date; ranked and unrankable both listed | Unrankable categories stay listed and clickable. Hiding them reads as cherry-picking. Searchable and grouped above 24 entries |
| **Methodology callout** | Method summary, version, collection window, link to `/methodology` | Once per ranked surface, directly above the first score. Never a substitute for the confound line |
| **Insufficient-signal state** | See below | Replaces the board entirely. Never alongside a partial ranking |

The two columns rank on different indices, so they are not two views of one ordering. Before shrinkage `L + H = 1` by construction, which puts the top of one column near the bottom of the other. A brand surfacing in both top tens is an anomaly to investigate, not a feature to design for.

Polarization is therefore never inferred from the board. It is a low `neutral_share` with both shrunk rates near 0.5, and it gets its own published field ([07-index-methodology.md](07-index-methodology.md)).

### The score chip, specifically

The chip is the superlative's receipt. Wherever a column is headed **Most Loved** or **Most Hated**, the chip beneath it states what was actually measured, on one line, at Small or larger:

`Hate Index 21/100 · CI 18–24 · 1,240 opinionated mentions · n_eff 412 · Jan–Jun 2026`

Five fields, always in that order. On mobile the line wraps; it never truncates to an ellipsis and never collapses into a tooltip. A chip that shows only the index value fails the condition the label ships under ([decisions/0005](decisions/0005-superlative-labels.md)).

Both counts appear because they mean different things. Raw `n` is what was collected; `n_eff = n / DEFF` is what the clustered sample is worth, and the `n_eff ≥ 400` gate runs on the second. Showing raw `n` alone overstates the evidence.

Scores are computed against opinionated mentions only, `N_opinionated = pos + neg`, so the excluded share has to be visible too. `neutral_share` and `abstain_share` sit in a line directly under the chip on category and brand pages, at the same size, not in the methodology.

Pill shape, accent fill, Space Black text, tabular numerals. The confidence interval is part of the chip, never a hover state, because an interval a reader cannot see is an interval that does not constrain the claim.

### The mention card, specifically

Attribution is structural, not decorative. Subreddit, username, and timestamp sit in one Micro row above the body; the permalink is the card's largest tap target.

The body sits inside a left rule in Sherpa Blue at 12% alpha. Nothing in the styling should let a reader mistake a Reddit user's words for UGC Ranks' words. The sentiment label is a word first, accent hue on the chip only.

### The insufficient-signal state

The design's honesty valve. A category that cannot clear its thresholds gets a full-width panel on the dotted field, not a thin ranking and not a 404.

| Element | Content |
|---|---|
| Heading | "Not enough signal to rank {Category}" |
| Body | Which floor failed, plainly, observed number beside required number |
| Table | Every brand found, with raw `n`, `n_eff`, authors, subreddits, threads, top-thread share, marked "Below threshold" |
| Link | The methodology page, plus two categories that do clear the bar |

The table carries all four diversity floors and the effective-sample gate, because a category can fail on thread concentration while its raw count looks healthy. Naming the wrong reason is worse than naming none.

The panel uses no accent hue. A category with no verdict must look different from one with a verdict before a word is read.

---

## Page layouts

Content and ordering follow [00-concept.md](00-concept.md). This table specifies where each element sits.

| Page | Top of page | Below |
|---|---|---|
| **Homepage** `/` | Hero: one sentence naming what is measured and over what window, no marketing copy. Methodology callout, then the exposure-confound line, then the two-column board, all categories pooled, top 10 each | Consolidated table of every qualifying brand, sortable, paginated, default sort key named. Category grid. Footer |
| **Category page** `/category/{slug}` | Breadcrumb, H1 on the linear band, methodology callout, exposure-confound line, the two-column board scoped to this category | Full ranked table with the window and last-updated date at its head, the below-threshold block collapsed and labelled with the floor it missed, related categories |
| **Brand page** `/brand/{slug}` | Breadcrumb, brand H1, both score chips with intervals and both counts, qualification badge, window, category link | Confound disclosure with `neutral_share` and `abstain_share`, trajectory against the brand's own baseline, per-category rank rows, subreddit distribution, paginated mention cards newest first, correction path |

The correction path is a plain link on the brand page, never a form behind a contact step and never adjacent to anything commercial. That is a legal condition, not a layout preference ([01-legal.md](01-legal.md)).

### Responsive behaviour

The board never becomes two narrow columns. Below 768px it stacks: the full **Most Loved** column, then the full **Most Hated** column, each keeping its heading, its accent, and its full score chips. The order is fixed on every page so the stacking never reads as a ranking of the two columns.

The consolidated table scrolls horizontally inside its own container below 768px, rank and brand frozen. The page body never scrolls sideways. Columns are never dropped at narrow widths, because the dropped ones would be the diversity floors.

---

## Footer

Three lines, Snowbelt on Sherpa Blue, every page.

1. **Created by Empact Partners**, linked to empact.partners, beside a link to `/methodology`. The methodology link is present on every page and never nested inside a menu.
2. The Reddit attribution line, naming Reddit as the source of the underlying content.
3. A non-affiliation line: UGC Ranks is not affiliated with, endorsed by, or sponsored by Reddit, Inc.

Line 3 is Small size, not Micro. It is a legal statement and must be readable without zooming. Exact wording is owned by [01-legal.md](01-legal.md).

---

## Accessibility

| Requirement | Rule |
|---|---|
| Contrast | Body ≥ 4.5:1 ([WCAG 2.2 §1.4.3](https://www.w3.org/TR/WCAG22/#contrast-minimum)), large text and non-text ≥ 3:1 ([§1.4.11](https://www.w3.org/TR/WCAG22/#non-text-contrast)). Token values above are measured |
| Colour independence | Every loved/hated signal carries a word label and a shape (▲ loved, ■ hated) |
| Focus | 2px Sugar Grape outline, 2px offset, on light; Virtual Goal on dark. Never `outline: none` |
| Tables | Real `<table>` with `<caption>`, `<th scope="col">`, `<th scope="row">`. No div grids |
| Sort state | `aria-sort` on the active column header, plus a visible arrow |
| Mention lists | Each card an `<article>`; the list an `<ol>` so position is announced |
| Score chips | The metadata line is text in the DOM, never an image, a title attribute, or `aria-label` only |
| Motion | No entrance animation. Transitions ≤ 150ms, off under `prefers-reduced-motion` |
| Targets | 44×44px minimum on every mention-card link |

Deuteranopia, protanopia, and tritanopia simulation is a build gate on the board and chip. Green-purple should survive it, but that is rationale, **NOT VERIFIED** by a simulator run.

---

## What to avoid

⚠️ Nothing here may imply affiliation with Reddit. That is the trademark risk in [01-legal.md](01-legal.md), and visual mimicry is the easiest way to create it.

| Never | Why |
|---|---|
| Reddit orange, or any orange | The strongest affiliation signal in the palette space |
| Snoo, alien motifs, upvote arrows | Reddit trade dress. Use a neutral triangle or nothing |
| Reddit Sans or a lookalike | Syne and Public Sans only |
| Reddit-styled threading, karma pills, awards | Recreates Reddit's UI inside a third-party product |
| "Reddit" in the logo, favicon, or nav | The naming decision in [00-concept.md](00-concept.md) exists for this reason |
| Brand logos on any ranking surface | Nominative fair use narrows sharply next to a negative claim |
| Photography of people beside a score | Puts a face next to a negative judgment about a company |
| A superlative column heading with no score chip under it | Strips the measured variable the label ships under ([decisions/0005](decisions/0005-superlative-labels.md)) |

---

[← Back to README](README.md) · [00-concept.md](00-concept.md) · [01-legal.md](01-legal.md) · [07-index-methodology.md](07-index-methodology.md) · [decisions/0005](decisions/0005-superlative-labels.md)
