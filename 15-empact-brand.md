# Empact Partners — Brand System

*Transcribed from the authoritative sources on 2026-08-05. Every value below is read off the source, not remembered.*

## Bottom line

- The source of truth is **Empact Partners Visual Style Guide V1.1** (19 pages, dated *Empact Partners 2022*), held at `~/Projects/empact-partners/brand/`. Where anything else disagrees with it, it loses.
- Seven base colours, two typefaces (**Syne Medium** for headings, **Public Sans** Regular and SemiBold for everything else), two seamless patterns, one stacked-bar symbol, one two-line wordmark.
- **Three source conflicts were found and are resolved below**: the colour name *Virtual Goal* vs *Virtual Golf*, a secondary tint palette that exists in only one of the two colour sources, and a photography rule the guide's own layout pages break.
- Contrast ratios here are **computed from the hex values**, not estimated. Two of the brand's own logo pairings sit below 4.5:1 and are safe only because a logo is non-text.
- Reddit Index **inherits the palette, the type, and the patterns. It refuses the logo, the lockup, and the marketing type scale.** The reasons are in [§9](#9-what-reddit-index-inherits-and-what-it-refuses), and that section is the one a builder must read.

---

## 1. Sources, and what disagrees

| Source | Path | Status |
|---|---|---|
| **Visual Style Guide V1.1** (PDF, 19pp) | `~/Projects/empact-partners/brand/` | **Authoritative** |
| Empact Partners Colors (docx) | same directory | Supplementary — carries tints the PDF omits |
| Logo artwork | `brand/AI Files/EP_Logo.ai`, `brand/PNG Files/` (Full + Mark, 200–1100px, black and white variants) | Authoritative artwork |
| `empact.json` | `~/.claude/skills/claude-ai-visibility-report/branding/` | Derived; report-generator config only |

### The three conflicts

| # | Conflict | Resolution |
|---|---|---|
| 1 | The lime is named **Virtual Goal** on PDF p10 and **Virtual Golf** in the docx | **Virtual Goal.** The PDF is the versioned style guide; the docx is a colour dump. Both agree the value is `#C6FF53` |
| 2 | The docx carries eight **secondary tints**; the PDF has no secondary-colour page at all | Tints are usable but **marked as single-sourced** ([§3](#3-secondary-tints--single-sourced)). Do not treat them as guide-approved |
| 3 | p19 says photography is *"always convert to black and white"*; p18's own layout examples show three full-colour photographs | **The rule wins over the example.** p19 is instruction, p18 is illustration. Black and white |

RGB, CMYK and HEX were cross-checked against each other for all seven base colours. All seven are internally consistent.

---

## 2. Colour — base palette

Read from PDF p10. RGB and CMYK are the guide's own; HEX is confirmed to match the RGB.

| Name | HEX | RGB | CMYK | Role |
|---|---|---|---|---|
| **Sherpa Blue** | `#02454F` | 2, 69, 79 | 97, 13, 0, 69 | The structural dark. Nav, footers, dark bands, headings |
| **Lucky Green** | `#40C890` | 64, 200, 144 | 68, 0, 28, 22 | The primary brand colour. Fills and fields |
| **Virtual Goal** | `#C6FF53` | 198, 255, 83 | 22, 0, 67, 0 | High-energy accent. Calls to action |
| **Sugar Grape** | `#A155FF` | 161, 85, 255 | 37, 67, 0, 0 | Secondary accent |
| **Space Black** | `#171616` | 23, 22, 22 | 0, 4, 4, 91 | Body text, logo on light fields |
| **Snowbelt** | `#EEF1ED` | 238, 241, 237 | 1, 0, 2, 5 | The off-white page ground |
| **White** | `#FFFFFF` | 255, 255, 255 | 0, 0, 0, 0 | — |

### Measured contrast

Every base pair, computed from the hex values against [WCAG 2.2 §1.4.3](https://www.w3.org/TR/WCAG22/#contrast-minimum) (4.5:1 body) and [§1.4.11](https://www.w3.org/TR/WCAG22/#non-text-contrast) (3:1 non-text).

| Pair | Ratio | Verdict |
|---|---|---|
| Space Black / White | 18.06 | AAA |
| Space Black / Snowbelt | 15.86 | AAA |
| Virtual Goal / Space Black | 15.33 | AAA |
| Sherpa Blue / White | 10.68 | AAA |
| Sherpa Blue / Snowbelt | 9.38 | AAA |
| Sherpa Blue / Virtual Goal | 9.07 | AAA |
| Lucky Green / Space Black | 8.50 | AAA |
| Sherpa Blue / Lucky Green | 5.02 | AA |
| Sugar Grape / Space Black | 4.52 | AA |
| Sugar Grape / White | 3.99 | **Non-text only** |
| Sugar Grape / Snowbelt | 3.51 | **Non-text only** |
| Virtual Goal / Sugar Grape | 3.39 | **Non-text only** |
| Sherpa Blue / Sugar Grape | 2.67 | 🔴 Fail |
| Lucky Green / White | 2.12 | 🔴 Fail |
| Lucky Green / Snowbelt | 1.87 | 🔴 Fail |
| Lucky Green / Sugar Grape | 1.88 | 🔴 Fail |
| Lucky Green / Virtual Goal | 1.80 | 🔴 Fail |
| Sherpa Blue / Space Black | 1.69 | 🔴 Fail |
| Snowbelt / White | 1.14 | 🔴 Fail |
| Virtual Goal / White | 1.18 | 🔴 Fail |
| Virtual Goal / Snowbelt | 1.03 | 🔴 Fail |

**The two accents are mid-luminance and cannot carry text on a light ground.** Lucky Green on Snowbelt is 1.87:1 and Sugar Grape on Snowbelt is 3.51:1. Both are fills, rules and chips — never body copy. Any product using them for text has to derive a deeper tint, which is what [16-design-system.md](16-design-system.md) does.

---

## 3. Secondary tints — single-sourced

From the docx only. **Not present in the Visual Style Guide**, so treat as convenience values rather than approved brand colours.

| HEX | Reads as | On Snowbelt | Space Black on it |
|---|---|---|---|
| `#067E84` | Sherpa Blue, lifted | 4.26 | 3.72 |
| `#20BCBC` | Teal | 2.05 | 7.72 |
| `#70E8B4` | Lucky Green, light | 1.33 | 11.95 |
| `#A6FFD7` | Lucky Green, palest | 1.03 | 15.40 |
| `#E3FF9F` | Virtual Goal, light | 1.03 | 16.40 |
| `#F1FFC5` | Virtual Goal, palest | 1.08 | 17.07 |
| `#C09FFF` | Sugar Grape, light | 1.91 | 8.29 |
| `#DBCCFF` | Sugar Grape, palest | 1.31 | 12.12 |

Every tint except `#067E84` fails 3:1 against Snowbelt, so the whole set works as **fills carrying dark text**, not as marks on a light page.

---

## 4. Typography

PDF p11–12.

> *"As a basic headset used Syne Medium. Public Sans used a secondary typeface in Regular and SemiBold."*

| Face | Weights | Use |
|---|---|---|
| **Syne** | Medium | Headings, display, the wordmark |
| **Public Sans** | Regular, SemiBold | Body, subtitles, captions, UI |

There is no third face.

### The brand type scale

| Role | Size / line height |
|---|---|
| Heading 1 | 68px / 72px |
| Heading 2 | 50px / 56px |
| Heading 3 | 38px / 46px |
| Heading 4 | 28px / 36px |
| Heading 5 | 22px / 28px |
| Subtitle 1 | 28px / 34px |
| Subtitle 2 | 24px / 30px |
| Body (Regular) | 16px / 26px |
| Body (SemiBold) | 16px / 26px |
| Caption | 12px / 18px |

This scale is built for marketing pages: a 68px H1 and a 12px caption. **A data-dense ranking site cannot use it unmodified** — see [§9](#9-what-reddit-index-inherits-and-what-it-refuses), where the deviation is declared rather than taken silently.

On composition, p13 asks only that type create a *"vector for reading"* — a deliberate reading path, not centred blocks by default.

---

## 5. Logo

### The parts

| Part | Description |
|---|---|
| **Symbol** | Five stacked horizontal bars, alternately offset left and right, reading as a blocky **E**. Ships at three optical sizes; the smallest is redrawn heavier, so **scale the correct file, never the largest one down** |
| **Wordmark** | "Empact" over "Partners", two lines, Syne Medium, flush left |
| **Lockup** | Symbol left, two-line wordmark right, optically centred |

### Clear space

The guide expresses clear space in `x`, one bar unit of the symbol.

| Configuration | Rule (PDF p4–5) |
|---|---|
| Symbol alone | `x` top, bottom, left and right; `x/2` marked internally |
| Wordmark alone | `2x` left and right outer, `x` inner, `x/2` top and bottom |
| Full lockup | `2/x` around the symbol, `4/x` between symbol and wordmark, then `x` and `2x` to the right edge |

### Colour pairings

Prescribed on p6–9 and measured here.

| Field | Logo colour | Ratio |
|---|---|---|
| Space Black | White | 18.06 |
| Snowbelt | Space Black | 15.86 |
| Virtual Goal | Sherpa Blue | 9.07 |
| Sherpa Blue | Snowbelt | 9.38 |
| Lucky Green | Space Black | 8.50 |
| White | Space Black | 18.06 |
| **Sugar Grape** | **White** | **3.99** |

White on Sugar Grape clears the 3:1 non-text floor and nothing more. It is sanctioned **for the logo only**. White text on Sugar Grape is not sanctioned anywhere.

---

## 6. Patterns

PDF p14. Two modules, both seamless.

| Module | Form |
|---|---|
| **Dotted** | Regular square dot grid |
| **Linear** | 45° hatch |

Rules, verbatim in substance:

- Both are perfectly seamless and fill any size area. **Use a mask to fit the pattern to the shape you want** — never stretch or crop mid-motif.
- Black or white only. 50%–25% opacity is allowed, *"but make sure you keep a good contrast."*
- The dotted module doubles as a **corner frame** — an L of dots bracketing a composition. The guide asks for this explicitly.

---

## 7. Photography and illustration

PDF p19.

| Rule | Detail |
|---|---|
| **Photography** | High contrast, **always converted to black and white**. This is stated as a rule, and it overrides the colour photographs shown on p18 |
| Illustration | Simple, clear plots. Cut-out B&W engravings and photo-collage over a Lucky Green field is the house move |
| Decor | Lines and small compositions of primitives — a square of four circles, dot fields, arrows. **All decor is secondary and must not distract from the main plot** |

---

## 8. Layout language

From p15–18: rectangular colour fields on an offset grid. Blocks of Sherpa Blue, Lucky Green, Virtual Goal and Snowbelt interlock at panel edges, with the logo parked in a corner block and the pattern modules filling one panel per composition. No gradients, no drop shadows, no rounded panels anywhere in the guide.

The recurring line across the layout pages is **"Let's go to market together."**

---

## 9. What Reddit Index inherits, and what it refuses

Reddit Index is **Empact-operated but not an Empact-branded surface**. It carries "Created by Empact Partners" in the footer and nothing more. That distinction drives every row below.

| Element | Reddit Index | Why |
|---|---|---|
| Base palette | ✅ **Inherit unchanged** | All seven values, exact hex |
| Syne Medium + Public Sans | ✅ **Inherit unchanged** | Also the only faces that keep the site away from Reddit Sans, which [09-design.md](09-design.md) bans |
| Dotted and linear patterns | ✅ **Inherit** | Linear behind category headers, dotted on the insufficient-signal state |
| B&W photography rule | ✅ **Inherit**, and tighten | The site restricts photography to `/methodology` and never places it beside a score |
| No gradients, no shadows, hard edges | ✅ **Inherit** | Matches the guide's layout language exactly |
| **Empact logo, symbol, wordmark, lockup** | ❌ **Refuse** | An Empact mark beside a negative ranking of a named company reads as Empact making the accusation. The footer credit is the whole attribution |
| **Brand type scale** | ❌ **Override, declared** | 68px H1 and 12px captions are marketing sizes. A ranking table needs a denser scale, and no figure a reader must check may sit at 12px. The replacement scale and its justification live in [16-design-system.md](16-design-system.md) |
| **Lucky Green and Sugar Grape as free accents** | ❌ **Refuse** | On this site the two carry fixed meaning: `#40C890` = loved, `#A155FF` = hated. Neither may be used decoratively, and no category colour may resemble them |
| Virtual Goal as a CTA fill | 🟡 **Narrow** | Retained for focus rings on dark and for the single methodology CTA. Never behind a score |
| "Let's go to market together" | ❌ **Refuse** | Empact's sales line. This site sells nothing |

The binding constraint, stated once: **the palette arrives with meanings attached that the brand guide never assigned it.** Green and purple stop being brand accents the moment they become the sentiment scale, and everything in [16-design-system.md](16-design-system.md) follows from that.

---

[← Back to README](README.md) · [16-design-system.md](16-design-system.md) · [09-design.md](09-design.md) · [00-concept.md](00-concept.md)
