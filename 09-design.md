# Reddit Index — Design Specification

## Bottom line

- ⚠️ The product is named **Reddit Index** and the name uses the Reddit mark ([decisions/0001](decisions/0001-name-reddit-index.md)). The site therefore carries **no** Reddit trade dress: no `#FF4500`, no Snoo, no Reddit Sans, no speech-bubble mark. That is a legal constraint, not a taste one.
- The footer's non-affiliation notice has fixed wording, its own slot, and a size floor of Small. It ships on every page, uncollapsed, or the site does not ship.
- Loved is **Lucky Green #40C890**. Hated is **Sugar Grape #A155FF**, not a red. Red is not in the Empact palette, and importing one adds a "system failure" register the score cannot support.
- 🟢 Green and purple are the only palette accents far enough apart in hue to read as opposing axes, and unlike red-green they stay separable under common colour vision deficiencies.
- Meaning is never carried by colour alone. Every loved/hated surface also carries a word label, an icon shape, and a column heading.
- Every score chip carries the measured variable beside the superlative: index value, interval, opinionated-mention count, `n_eff`, and window. That line is the condition [decisions/0005](decisions/0005-superlative-labels.md) ships under, so it is never truncated, hidden behind hover, or moved into a tooltip.
- 🟡 Both accents fail text contrast at their brand values. Derived deep tints handle text; brand values stay for fills, rules, and chips.
- The **insufficient-signal state is a first-class component**, not an error page. ERP and Help Desk cannot be ranked honestly from Reddit, and the design must say so on the same page furniture.
- ⚠️ Brand pages render full Reddit comment text and usernames. That is the owner's priced decision, documented in [01-legal.md](01-legal.md); the design's job is to make attribution and permalinks impossible to miss, not to hide the risk.

Page content is specified in [00-concept.md](00-concept.md). This file specifies the visual treatment of that content and never changes it.

---

## The Reddit trade-dress exclusion

The product ships as **Reddit Index** on `redditindex.com`. That name uses the Reddit mark and breaches [Data API Terms §4.1](https://www.redditinc.com/policies/data-api-terms) and [Developer Terms §5.3](https://www.redditinc.com/policies/developer-terms). The exposure was priced and accepted; the record is [decisions/0001](decisions/0001-name-reddit-index.md).

One rule follows for design. **The name is the entire budget for Reddit resemblance, and it is already spent.**

Proceedings of this kind turn on implied affiliation, not on damage or traffic. In [*Reddit, Inc. v. Phil Carey*](https://www.wipo.int/amc/en/domains/decisions/text/2020/d2020-1834.html) (D2020-1834) the panel held that even noncommercial use of an identical mark "carries with it a high risk of implied affiliation."

Trade dress stacked on a name that already reads as a sub-brand is the cheapest way to make that finding easy. So the reason below is legal, not aesthetic. There is no version of "a nod to the source" that survives it.

### Banned outright

| Element | Rule |
|---|---|
| **Reddit orange `#FF4500`** | Banned, with every orange, amber, and warm red near it. No fills, no accents, no favicon, no chart series, no hover or focus state, no gradient stop |
| **Snoo** | Banned in every form: full mascot, head alone, antennae, alien silhouette, and any redraw, homage, or "inspired by" derivative |
| **Reddit Sans** | Banned, with any lookalike. Syne Medium and Public Sans only, per the type scale below. No substitution, no fallback stack that can land near it |
| **The speech-bubble mark** | Banned. No circular badge, no rounded speech bubble, no bubble-with-a-face construction, no glyph that survives a squint test against Reddit's |
| **Reddit UI furniture** | Upvote and downvote arrows, karma pills, awards, nested-thread rails, and Reddit-styled comment chrome. Covered again under [What to avoid](#what-to-avoid) |

### What the identity may be

The wordmark is the two words **Reddit Index**, set in Syne Medium, Sherpa Blue `#02454F` on Snowbelt, with no glyph, no lockup, and no icon beside it. The favicon is the same wordmark's initials on a plain Sherpa Blue field. A symbol invites the comparison; a wordmark does not offer one.

A wordmark-only identity is also the portable one. `brandsonreddit.com` is the documented migration target in [decisions/0001](decisions/0001-name-reddit-index.md), and a bespoke glyph built around the current name would have to be thrown away on a rename. Text can be reset in an afternoon.

The word "Reddit" appears in the site name, in headings, and in descriptive copy. It never appears in Reddit's typeface, in Reddit's colour, or inside a Reddit-shaped container. That is the line between naming the subject and dressing as it.

### The pre-deploy check

This is a build gate, not a guideline. A deploy is blocked unless a search of the built CSS, SVG, and font manifest for `FF4500`, `ff4500`, `orange`, `snoo`, and `reddit-sans` returns nothing, and every SVG in the asset directory has been checked by eye against Reddit's mark.

A single stray token here is a line a complainant quotes back. The check is cheap and the failure mode is not.

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

Syne Medium from Display through H4, Public Sans below. All numerals use `font-variant-numeric: tabular-nums` so scores align. There is no third face, and the fallback stack is specified explicitly so no system font can resolve near Reddit Sans.

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

Every number a reader is entitled to check sits at Small or larger. That covers the score-chip metadata line and the threshold figures. The footer's non-affiliation notice sits at Small for a different reason: a legal statement a reader has to zoom to read is not a statement.

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
| **Footer** | Four slots in fixed order: methodology link, Empact Partners attribution, Reddit source attribution, non-affiliation notice | Identical on every page. Slot 4 is required wording at Small or larger, never collapsed, never optional. Specified below |

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

The body sits inside a left rule in Sherpa Blue at 12% alpha. Nothing in the styling may let a reader mistake a Reddit user's words for the site's own. The sentiment label is a word first, accent hue on the chip only.

The quoting has to work harder here than it would elsewhere. The site is named Reddit Index, so a reader arrives already primed to read quoted comments as something the site is party to, and the visual separation is the only thing correcting that.

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

Snowbelt on Sherpa Blue, identical on every page, never collapsed into a menu or an accordion. Four slots in fixed order. Slots 2 and 4 are the two the site is obliged to carry, so neither is treated as decoration.

| # | Slot | Content | Size |
|---|---|---|---|
| 1 | Methodology | Link to `/methodology`. Present on every page, never nested inside a menu | Body |
| 2 | **Attribution** | "Created by Empact Partners", linked to [empact.partners](https://empact.partners) | Body |
| 3 | Source | Names Reddit as the source of the underlying content, with the collection window and a link to `/methodology` | Small |
| 4 | **Non-affiliation** | The notice below, verbatim | Small |

Slot 3 names one source because the index has one. The name is Reddit-locked, so any additional source in [12-phasing.md](12-phasing.md) requires a rename before this slot can change ([decisions/0001](decisions/0001-name-reddit-index.md)).

### Slot 2 — attribution

"Created by Empact Partners", linked to empact.partners, at Body size beside the methodology link. It is the operator's name on a site that publishes negative judgments about companies, so it sits at reading size and is never rendered as a Micro credit line.

### Slot 4 — non-affiliation notice

The string is fixed. It ships exactly as written, with no rewording, shortening, or softening:

> Not affiliated with, endorsed by, or sponsored by Reddit, Inc. 'Reddit' is a trademark of Reddit, Inc., used here descriptively.

This is a mandatory condition of shipping under this name, set by [decisions/0001](decisions/0001-name-reddit-index.md). The product name uses the Reddit mark, so the notice is the one place on the page that states the relationship the name implies but does not have.

Rules for slot 4, all of them binding:

- Small size, never Micro. Snowbelt at full opacity, never dimmed to 60% or set in a muted grey.
- Real text in the DOM. Never an image, never `title`-only, never `aria-hidden`.
- Present on every route without exception, including `/methodology`, the insufficient-signal state, paginated brand pages, and error pages.
- Never inside a `<details>`, a "legal" drawer, a modal, or anything requiring a click to reveal.
- Never adjacent to a call to action, a badge embed, or anything commercial.

A page rendering without slot 4 is a bug of the same severity as a page rendering the wrong score.

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

⚠️ The name already implies affiliation. Everything below exists so the design does not confirm it ([decisions/0001](decisions/0001-name-reddit-index.md), [01-legal.md](01-legal.md)).

| Never | Why |
|---|---|
| Reddit orange `#FF4500`, Snoo, Reddit Sans, or a Reddit-shaped mark | Banned outright by [the trade-dress exclusion](#the-reddit-trade-dress-exclusion), with a pre-deploy check |
| Any orange at all, anywhere in the palette | The strongest affiliation signal in the colour space, and a near-miss reads as a deliberate near-miss |
| A logo, favicon, or glyph resembling Reddit's speech bubble | The wordmark is the whole identity. A symbol offers a comparison the name would lose |
| Reddit-styled threading, karma pills, upvote arrows, awards | Rebuilds Reddit's interface inside a third-party product already carrying Reddit's name |
| Any copy or visual implying partnership, licensing, or an official tie | A standing condition of the naming decision, not a style preference |
| Brand logos on any ranking surface | Nominative fair use narrows sharply next to a negative claim |
| Photography of people beside a score | Puts a face next to a negative judgment about a company |
| A superlative column heading with no score chip under it | Strips the measured variable the label ships under ([decisions/0005](decisions/0005-superlative-labels.md)) |

---

[← Back to README](README.md) · [00-concept.md](00-concept.md) · [01-legal.md](01-legal.md) · [07-index-methodology.md](07-index-methodology.md) · [decisions/0001](decisions/0001-name-reddit-index.md) · [decisions/0005](decisions/0005-superlative-labels.md)
