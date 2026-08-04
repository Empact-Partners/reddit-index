# UGC Ranks — Design Specification

## Bottom line

- Loved is **Lucky Green #40C890**. Hated is **Sugar Grape #A155FF**, not a red. Red is not in the Empact palette, and importing one adds a "danger / system failure" register the score does not support.
- 🟢 Green and purple are the only palette accents far enough apart in hue to read as opposing axes, and unlike a red-green pair they stay separable under the common colour vision deficiencies.
- Meaning is never carried by colour alone. Every loved/hated surface also carries a word label, an icon shape, and a column heading.
- 🟡 Both accents fail text contrast at their brand values. Two derived deep tints handle text; the brand values stay for fills, rules, and chips only.
- The **insufficient-signal state is a first-class component**, not an error page. ERP and Help Desk cannot be ranked honestly from Reddit, and the design has to say so on the same furniture as a ranked category.
- ⚠️ Brand pages render full Reddit comment text and usernames. That is the owner's priced decision, documented in [01-legal.md](01-legal.md); the design's job is to keep attribution and permalinks impossible to miss, not to make the risk disappear.

---

## Colour semantics

### The loved / hated pair

| Candidate | Verdict | Reason |
|---|---|---|
| Lucky Green #40C890 → loved | **Adopted** | Only unambiguously positive accent in the palette |
| Off-brand red → hated | Rejected | Not in the palette; reads as "error / outage", overstating a sentiment index |
| Virtual Goal #C6FF53 → hated | Rejected | A lime; sits beside Lucky Green in hue, reads as a second positive |
| Sherpa Blue #02454F → hated | Rejected | Already the structural colour. Cannot also carry a sentiment meaning |
| **Sugar Grape #A155FF → hated** | **Adopted** | Far from green in hue, strong, tonally neutral. Asserts "the other axis", not "bad" |

The two-axis model is the reason. Love and hate are separate indices, not two ends of one bar, so two unrelated hues fit better than a red-to-green gradient, which implies a single continuum.

Neutral, abstain, and unranked states use Snowbelt #EEF1ED fills with Space Black #171616 text. No accent hue at all, which is itself the signal.

### Tokens and measured contrast

Ratios are computed from the hex values, not estimated.

| Token | Hex | Use | On Snowbelt | On Sherpa |
|---|---|---|---|---|
| Sherpa Blue | #02454F | Nav, footer, headings, dark sections | 9.38 | — |
| Space Black | #171616 | Body text | 15.86 | — |
| Snowbelt | #EEF1ED | Page background | — | 9.38 |
| Lucky Green | #40C890 | Loved fills, bars, chips | 1.87 ✗ | 5.02 ✓ |
| Green Deep *(derived)* | #267856 | Loved text and icons on light | 4.72 ✓ | — |
| Sugar Grape | #A155FF | Hated fills, bars, chips | 3.51 ✗ | 2.67 ✗ |
| Grape Deep *(derived)* | #7940BF | Hated text and icons on light | 5.59 ✓ | — |
| Grape Light *(derived)* | #D0AAFF | Hated accents on dark | — | 5.53 ✓ |
| Virtual Goal | #C6FF53 | CTA fills, Space Black text | 15.33 on black | 9.07 ✓ |

Derived tints are display tokens, not additions to the Empact brand palette. They exist only because the brand accents are mid-luminance and fail as text.

Text on a Lucky Green fill is Space Black (8.5:1). Text on a Sugar Grape fill is Space Black (4.52:1). White on Sugar Grape is 3.99:1 and is banned for body text.

---

## Type scale

Syne Medium for every heading. Public Sans for everything else. All numerals render with `font-variant-numeric: tabular-nums` so scores stay aligned down a column.

| Role | Desktop | Mobile | Line height | Face |
|---|---|---|---|---|
| Display | 61px | 39px | 1.05 | Syne Medium |
| H1 | 49px | 31px | 1.10 | Syne Medium |
| H2 | 39px | 25px | 1.15 | Syne Medium |
| H3 | 31px | 21px | 1.20 | Syne Medium |
| H4 | 25px | 19px | 1.25 | Syne Medium |
| Lead | 20px | 18px | 1.55 | Public Sans |
| Body | 17px | 17px | 1.60 | Public Sans |
| Small | 15px | 15px | 1.50 | Public Sans |
| Micro | 13px | 13px | 1.40 | Public Sans |

Micro is reserved for timestamps, usernames, and table metadata. It never carries a claim a reader has to act on. Measure caps at 68 characters for comment text, which is the widest content on the site.

## Spacing, grid, and surface

| Property | Value |
|---|---|
| Base unit | 4px. Scale: 4, 8, 12, 16, 24, 32, 48, 64, 96, 128 |
| Container | 1200px max, 24px gutters desktop, 16px mobile |
| Grid | 12 columns desktop, 8 tablet, 4 mobile |
| Section rhythm | 96px desktop, 56px mobile |
| Card radius | 6px. Chips and badges: 999px. Tables: 0 |
| Borders | 1px Sherpa Blue at 12% alpha |
| Elevation | None. Borders and background steps only |

The linear module runs as a band behind category headers; the dotted module fills the insufficient-signal state and section breaks. Photography appears only on `/about` and `/methodology`, always black and white, never next to a negative score or a named brand.

---

## Component inventory

| Component | Contains | Behaviour |
|---|---|---|
| **Loved / hated board** | Two equal columns headed "Most loved" and "Most hated", 5-10 rows each: rank, brand, score chip, mention count | Independent rankings, never a mirrored pair. A brand can appear in both |
| **Ranking table row** | Rank, brand, love index, hate index, mentions, distinct authors, subreddits, qualification badge | Sortable by any numeric column. Statistically tied ranks share a rank number and a tie marker |
| **Score chip** | Index value, scale denominator, confidence interval | Pill, accent fill, Space Black text, tabular numerals. Interval always visible, never hover-only |
| **Mention card** | Brand, subreddit, username, timestamp, sentiment label, full comment text, permalink | Permalink is the primary link and wraps the timestamp. Comment text is quoted, never restyled as site copy |
| **Qualification badge** | "Ranked" or "Below threshold", plus the numeric threshold | Always paired with the figure that failed. A badge that does not name its number is not shippable |
| **Breadcrumbs** | Home → Category → Brand | On every page below the homepage. Ordered list with `aria-label="Breadcrumb"` |
| **Category selector** | Searchable grouped list of all categories, showing ranked vs unrankable | Unrankable categories stay listed and clickable. Hiding them looks like cherry-picking |
| **Methodology callout** | Method summary, version number, collection window, link to the methodology page | Once per ranked surface, directly above the first score |
| **Insufficient-signal state** | See below | Replaces the board entirely. Never renders alongside a partial ranking |

### The mention card, specifically

Attribution is structural, not decorative. Subreddit, username, and timestamp sit in a single Micro-size row above the comment body, and the permalink is the largest tap target on the card.

The comment body sits inside a left rule in Sherpa Blue at 12% alpha. Nothing in the styling should let a reader mistake a Reddit user's words for UGC Ranks' words.

The sentiment label is a word first (`Positive`, `Negative`, `Neutral`), with the accent hue on the label chip only, never on the comment text.

### The insufficient-signal state

This is the design's honesty valve. A category that cannot clear its thresholds gets a full-width panel on the dotted pattern field, not a thin ranking and not a 404.

| Element | Content |
|---|---|
| Heading | "Not enough signal to rank {Category}" |
| Body | Which threshold failed, in plain language, observed number beside required number |
| Table | Every brand found, with mention count, distinct authors, and subreddit count, all marked "Below threshold" |
| Link | To the methodology page, and to two categories that do clear the bar |

The panel uses no accent hue. A category with no verdict should look different from a category with a verdict before anyone reads a word.

---

## Page layouts

| Page | Above the fold | Below |
|---|---|---|
| **Homepage** | Product line, collection window, count of ranked categories, category search | Featured category boards (3), a "recently updated" strip, the methodology callout, footer |
| **Category page** | Breadcrumb, category H1 on the linear-pattern band, methodology callout, the two-column board | Full consolidated ranking table, threshold explanation, unranked-brands list, related categories |
| **Brand page** | Breadcrumb, brand H1, score chips for both indices, qualification badge, category link | Index trajectory, subreddit distribution, then the mention card list, paginated, newest first |

### Responsive behaviour

The two-column board does not become two narrow columns on mobile. Below 768px it stacks: the full "Most loved" column, then the full "Most hated" column, each keeping its own heading and accent.

Stacking order is fixed at loved-then-hated everywhere, so the order never implies an editorial judgment about a specific category.

The consolidated ranking table scrolls horizontally inside its own container below 768px, with rank and brand frozen as the first column. The page body never scrolls sideways.

---

## Footer

Three lines, Snowbelt text on Sherpa Blue, present on every page.

1. **Created by Empact Partners**, linked to empact.partners.
2. The Reddit attribution line, naming Reddit as the source of the underlying content.
3. A non-affiliation line stating UGC Ranks is not affiliated with, endorsed by, or sponsored by Reddit, Inc.

The non-affiliation line is Small size, not Micro. It is a legal statement and must be readable without zooming. Exact wording is owned by [01-legal.md](01-legal.md).

---

## Accessibility

| Requirement | Rule |
|---|---|
| Contrast | Body text ≥ 4.5:1, large text and UI borders ≥ 3:1. Token-table values are measured, not assumed |
| Colour independence | Every loved/hated signal carries a word label and a shape (▲ loved, ■ hated) alongside the hue |
| Focus | 2px Sugar Grape outline, 2px offset, on light surfaces; Virtual Goal on Sherpa Blue. Never `outline: none` |
| Tables | Real `<table>` with `<caption>`, `<th scope="col">`, `<th scope="row">` on the brand cell. No div grids |
| Sort state | `aria-sort` on the active column header, plus a visible arrow |
| Mention lists | Each card is an `<article>`; the list is an `<ol>` so position is announced |
| Motion | No entrance animation on rankings. Transitions ≤ 150ms, disabled under `prefers-reduced-motion` |
| Targets | 44×44px minimum on every link inside a mention card |

Colour vision deficiency simulation for deuteranopia, protanopia, and tritanopia is a build gate on the board and chip components. Green-purple is expected to survive it, but that is design rationale, **NOT VERIFIED** by a simulator run.

---

## What to avoid

⚠️ Nothing on this site may imply affiliation with Reddit. That is the exact trademark risk described in [01-legal.md](01-legal.md), and visual mimicry is the easiest way to create it.

| Never | Why |
|---|---|
| Reddit orange, or any orange, anywhere | The strongest affiliation signal in the palette space |
| Snoo, alien motifs, upvote-arrow iconography | Reddit trade dress. Use a neutral triangle or nothing |
| Reddit Sans or a lookalike | Syne and Public Sans only |
| Reddit-styled threading, karma pills, award icons | Recreates Reddit's UI inside a third-party product |
| "Reddit" in the logo, wordmark, favicon, or nav | The name decision in [00-concept.md](00-concept.md) exists for this reason |
| Brand logos anywhere on a ranking surface | Nominative fair use narrows sharply next to a negative claim |
| Photography of people beside a score | Puts a face next to a negative judgment about a company |

Plain-text brand names, set in Public Sans at Body size, are the only permitted brand representation on any ranking surface.

---

[← Back to README](README.md) · [00-concept.md](00-concept.md) · [01-legal.md](01-legal.md)
