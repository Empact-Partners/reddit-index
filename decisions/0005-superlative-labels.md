# 0005 — The columns are labelled "Most Loved" and "Most Hated"

**Status:** Accepted, with known exposure · **Date:** 2026-08-04 · **Decided by:** Vlad Shvets

## Context

The research recommended never publishing a superlative. The safe label is the measured variable: "Lowest Reddit Sentiment Scores in [Category], [Date Range]" rather than "Most Hated."

The reasoning is sound. US defamation doctrine protects a **disclosed-methodology comparative rating** as opinion, because a reader who can see the method can judge the conclusion. A bare superlative reads as a statement about the world, and a statement about the world can be provably false.

The distinction is [*Milkovich v. Lorain Journal*](https://supreme.justia.com/cases/federal/us/497/1/): the question is whether a statement implies a provably false assertion of fact. "Lowest sentiment score in our index, Jan–Jun 2026" is a measurement anyone can check. "Most hated CRM" is a claim about how the world feels.

## Decision

**The columns stay labelled "Most Loved" and "Most Hated."**

The owner specified them and reaffirmed them. They are the product — the two-column board is the thing people will screenshot, and "lowest aggregate sentiment score" is not a thing anyone screenshots.

## Why this was not free

This is the second priced risk in the project, after [0002](0002-display-full-mentions.md). It is smaller, and unlike 0002 it has real mitigations.

| Exposure | Detail |
|---|---|
| Defamation / trade libel | A superlative is more likely to be read as a factual assertion than a score is. See [01-legal.md](../01-legal.md). |
| EU posture | Empact Partners OÜ is Estonian. [*Delfi AS v. Estonia*](https://globalfreedomofexpression.columbia.edu/cases/delfi-as-v-estonia/) held an Estonian publisher liable for third-party comments it merely hosted. We actively select and republish, which is a worse posture. |
| Commercial speech | Using the ranking as an outreach hook converts editorial speech into commercial speech, which loses some protection and picks up EU comparative-advertising rules. |

## Mandatory conditions

The label is accepted **only** with all of these. They are cheap, and they are what carries the opinion defence.

1. **The measured variable appears next to the superlative on every surface.** The column header may say "Most Hated"; the row must say `sentiment index 21/100 · 412 opinionated mentions · Jan–Jun 2026`. The superlative is never alone.
2. **The methodology is one click from every ranking**, at `/methodology`, with the formulas, the thresholds, and the known limitations.
3. **The exposure confound is disclosed on every category page**, not buried in the methodology: rank reflects who complains loudest, and users forced onto enterprise software complain more than users who chose a self-serve tool.
4. **Never extend the superlative beyond the data.** "Most hated" is scoped to this index, this source, this window. No "worst software", no "companies people hate", no page title that drops the scope.
5. **Free correction and right of reply**, never bundled with a commercial offer.
6. **The methodology is frozen and version-controlled before results are seen.** [*Suzuki Motor Corp. v. Consumers Union*, 330 F.3d 1110 (9th Cir. 2003)](https://caselaw.findlaw.com/court/us-9th-circuit/1359248.html) survived summary judgment because a jury could find the method had been tampered with. Changing the method after seeing who lands where is the fatal fact.

## Revisit when

- Any named brand's counsel makes contact. Revisit immediately.
- Before any non-US launch, since the opinion privilege travels badly.
- If the index is ever used in paid advertising, which strengthens the commercial-speech characterisation.

## Alternatives rejected

| Option | Why not |
|---|---|
| "Lowest sentiment score" as the column header | Safest, and the research's recommendation. Rejected by the owner: it is not a product anyone shares. |
| Publish only the "Most Loved" column | Removes the exposure almost entirely and keeps the badge play. Rejected: the negative column is the outreach hook. |
| Superlative on the page, measured variable in the `<title>` | Splits the difference and fools nobody. A screenshot carries the page, not the title tag. |

---

[← Back to README](../README.md) · [Legal position](../01-legal.md) · [Display decision](0002-display-full-mentions.md) · [Concept](../00-concept.md)
