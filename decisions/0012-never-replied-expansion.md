# 0012 — Expand the index with the never-replied outbound cohort

**Status:** Accepted · **Date:** 2026-08-20 · **Decided by:** Vlad Shvets

## Bottom line

The index takes on **4,152 SaaS companies** that Empact cold-emailed and never heard back
from: 1,457 into existing categories, 1,078 into **51 new categories**, and the rest held.
The index grows from 100 to **151 categories** and from 6,040 to roughly 8,500 brands.

The categories are built because the roster demanded them, not to hit a number. A company
that fits no category is **not** forced into a neighbouring one — a forced fit pollutes a
published leaderboard, and the mapping pass demotes them on purpose.

## Context

`Empact-Partners/partner-development` docs/11 established that 7,013 companies were emailed
and never replied, 4,944 of them SaaS. 484 already had index pages. The remaining 4,454 are
the input here, minus 302 already in the gazetteer.

Two audiences are served by one build. The index gets real coverage in categories it had no
rows for — contract lifecycle management, cloud cost management, application security
testing, carbon accounting. Empact gets a second outbound wave that can link each recipient
to a page about their own company, which is the whole premise of the Reddit Index campaign
(docs/10 in partner-development).

## The decision

**A company page is earned by mentions, not by import.** Being added to the gazetteer only
makes a company *matchable*. Its page exists once it has ≥1 collected mention and shows a
score at ≥1 opinionated mention (0011). Most of the import will never get a page, and that
is the correct outcome, not a shortfall.

**The 5-mention floor is an outreach bar, never an index bar.** It decides who gets an email
linking to their page. It has no bearing on who appears on the site.

**New categories are evidence-gated.** A cluster becomes a category only with ≥8 roster
members and real Reddit evidence behind it. Clusters below that bar stay unbuilt and their
companies go to an email angle that does not reference the index at all.

**Published identity is frozen, and enforced.** The 100 existing categories keep their hex
and icon byte-identical through the regeneration; `gen-categories-100.mjs` now throws on
drift rather than trusting the operator. Slugs were already frozen (0007); this adds colour
and icon to the same guarantee.

**Existing collection is never narrowed to fund new categories.** `select_core_subs.py`
gains an additive mode, because the global mode reallocates the whole thread budget from
scratch — a dry run at the time of writing produced 800 core slots where 1,741 were applied,
i.e. re-running it to add categories would have silently halved existing coverage.

## Consequences

**Colour headroom is nearly spent.** 151 categories place at min pairwise ΔE **0.0308**
against a 0.030 floor, down from 0.0373 at 100. An expansion of this size again will not
place. Doing it needs a decisions-level call first: widen the legal region, lower the floor,
or accept collisions. It is not a code change.

**Publication bars in existing categories will move.** A category's display floor is the
median opinionated-mention count across its scored brands, clamped [3,30]. 96 companies
land in `recruiting`, 83 in `marketing-automation`, 64 in `help-desk`. The baseline was
captured before the import (`data/threshold_baseline.py`) so the movement is measured
rather than discovered later.

**Historical comments are not recoverable for new brands.** Comment bodies are only stored
when they resolve to a known brand, so a brand added today has no comment history and no
local text to re-scan. Posts *are* recoverable (`worker/backfill_posts.py` re-resolves every
stored thread). Comments accrue from the next `update.sh` onward. Re-sweeping trees to
recover them was priced at 31+ hours of API time and **rejected** — the number arrives free
by waiting.

## Alternatives rejected

**Force every unmapped company into the nearest existing category.** It would have avoided
51 new categories entirely. It also puts a virtual data room on the document-management
board and a vacation-rental data provider on business-intelligence, which is how a
leaderboard stops meaning anything.

**Build all 51 categories before shipping anything.** 8–20 hours of Reddit API across
multiple manual runs before a single email could go out. Wave 2 ships from existing-category
matches; new categories land behind them.
