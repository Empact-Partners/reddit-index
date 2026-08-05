# Handoff — open items

**State as of 2026-08-05.** The repo is build-ready. [BUILD-PROMPT.md](BUILD-PROMPT.md) is the entry point for the build session. `validate.py` passes: 0 failures, every relative link resolves.

The **six defects carried in the previous handoff are all closed** — see [What was closed](#what-was-closed). What follows is what is genuinely still open.

## Bottom line

- **`www.redditindex.com` is not configured.** The apex works and is correctly wired. This is the only infrastructure gap.
- **Every threshold tier is provisional.** They are assigned from category-level comment flow, not per-brand counts, and Phase 0 must confirm them from real `n_eff` before anything publishes.
- **The probe's brand matching is coarser than the pipeline's will be**, and two subreddits show the scar.
- **No crosswalk** between the 20 measured category labels and the 50-row Phase 1 taxonomy. Unchanged, and still blocking any combined coverage figure.

---

## 1. 🟡 Threshold tiers are provisional, and the docs must keep saying so

[decisions/0009](decisions/0009-category-scaled-thresholds.md) assigns each category a Deep, Standard or Thin tier from its estimated three-year brand-bearing volume. That estimate comes from a **live comment-stream density measurement extrapolated over three years** — it measures how much a category's generalist subreddits talk about brands, not how many mentions any individual brand accumulates.

The gate runs per brand on `n_eff`. Nothing in this study measures per-brand `n_eff`, because no brand-level ingest has been run.

**Before publishing:** Phase 0 measures real per-brand counts on CRM and confirms or moves every tier. A tier that moves is a methodology change — version bump and dated changelog entry, not a config edit.

## 2. 🟡 Two subreddits expose the probe's matching limits

The screen counts a comment as brand-bearing if it contains a probe term at a word boundary. The production pipeline does per-occurrence disambiguation against a closed gazetteer ([05-entity-resolution.md](05-entity-resolution.md)). The gap shows up in Team Collaboration and Chat:

| Subreddit | Measured brand-bearing | Why it is almost certainly wrong |
|---|---|---|
| r/UkrainianConflict | 12% | "Discord" and "Telegram" in war-reporting context, not software evaluation |
| r/Superstonk | 2% | Same words in a meme-stock community |

Team Collaboration and Chat carries the highest measured volume of any category (321,854 estimated three-year mentions) and it is **the category most inflated by this effect**, because its brand names — Discord, Teams, Zoom, Slack — are the ones that appear constantly outside any purchase conversation.

**Consequence:** treat that category's tier as the least trustworthy of the twenty. Its Deep tier assignment is the one most likely to move after Phase 0.

**Not a blocker for the study's headline finding**, which is about subreddit *counts* clearing the five-subreddit floor, and is unaffected.

## 3. 🟡 22 scorable subreddits have `unknown` rule posture

28 of 231 reachable subreddits returned no parseable rules; 22 of those are currently counted as scorable. A subreddit whose rules were never read could be hostile to vendor talk, which would mean it is scoring brands it should not.

The classifier reads `/r/{sub}/about/rules` and falls back to `unknown` on an empty or unfetchable response. **Fix before Phase 1:** re-fetch the 28, and where rules genuinely do not exist, read the sidebar and the wiki before defaulting a sub to scorable.

## 4. 🟡 No crosswalk between the two category taxonomies

The 20 measured categories in [14-category-tests.md](14-category-tests.md) and the 50-row spine in [data/phase1-categories.csv](data/phase1-categories.csv) use different labels. Only 8 join exactly.

**v1 ships the 20 measured categories.** Do not add the two figures together, and do not quote a combined coverage number until the crosswalk exists.

## 5. 🟢 Small

- **42 of the 50 Phase 1 categories still have no subreddit mapping.** Eight are mapped. Unchanged, and not on the v1 path.
- **`data/subreddit-map.csv` is superseded for scoring** by `subreddit-measurements.csv` but is still shipped. Keep it for the rule-posture history or delete it, but do not let a builder read it as current.

---

## What was closed

Every defect in the previous handoff is fixed. Recorded so a reviewer does not re-raise them.

| # | Defect | Resolution |
|---|---|---|
| 1 | The four diversity floors disagreed across six files | Canonical set is authors ≥50, subreddits ≥5, max single-thread share ≤20%, max single-author share ≤5%. **Distinct threads is published evidence, not a floor.** Fixed in `07`, `08`, `09`, `10`, `11`, `12` and `README` together. The `n_eff` gate is a **gate**, not a fifth floor |
| 2 | Miscomputed Wilson interval in `12-phasing.md` | Recomputed to **[0.9511, 0.9817]**. The lower bound clears 0.95 by four tenths of a point, so the gate now runs on the Wilson lower bound rather than the point estimate |
| 3 | G1 gated on a banned point estimate | Now the Wilson lower bound |
| 4 | Retired audit gate still shipped | Replaced with the live rule: **more than 2 errors in 150** |
| 5 | `README.md` Limits stale on audit size | Now 1,000 items per cycle, cross-referencing `05-entity-resolution.md` rather than `06-sentiment.md` |
| 6 | Three small ones | `n_eff` is never *above* `n` (not "always below"); the truncated `00-concept.md` sentence; the cascade saving restated honestly as **2.0–6.5×** rather than rounded to 2–7× |

## Also closed since the previous handoff

- **`redditindex.com` is registered and live.** Verified on Vercel: domain verified on the `empact-partners` team, attached to project `reddit-index`, A record → `216.150.1.1`, `misconfigured: false`, Git-linked to `Empact-Partners/reddit-index`.
- **12 of 20 categories clearing the five-subreddit floor became 20 of 20**, by widening the candidate lists through discovery rather than by hand.

---

## Outstanding, outside the docs

- **`www.redditindex.com` has no CNAME.** DNS is at NameBright, so the record has to be created there and the domain added in Vercel, redirecting to the apex. The apex resolves correctly without it.
- **`redditbrandindex.com` is not registered.** [decisions/0001](decisions/0001-name-reddit-index.md) requires the defensive name before launch, not after.
- **The name breaches two Reddit clauses.** [Data API Terms §4.1](https://www.redditinc.com/policies/data-api-terms) and [Developer Terms §5.3](https://www.redditinc.com/policies/developer-terms) both forbid Reddit trademarks in a product name. Recorded, not overlooked — the owner made the call with the exposure in front of him.
- **Enforcement is a UDRP filing, not a lawsuit.** Reddit runs them *pro se* for roughly $1,500 and has won every one found: [reddit.win](https://www.wipo.int/amc/en/domains/decisions/text/2020/d2020-1834.html) (D2020-1834), [redditpromotion.com / redditshop.com](https://www.wipo.int/amc/en/domains/decisions/text/2019/d2019-2964.html) (D2019-2964), [reddit.co](https://www.wipo.int/amc/en/domains/decisions/text/2018/dco2018-0008.html) (DCO2018-0008).
- **Low traffic is not a defence.** A UDRP needs no damages, no discovery, and no proof that anyone visited. It needs only that Reddit notices.
- **A loss costs the domain, not the project.** The pipeline, index, methodology and content all survive a transfer. That asymmetry is why the risk was accepted, and it is why the next item binds whoever writes the code.
- **Migration dependency: the canonical host lives in exactly one config value, and every internal link stays relative.** A forced move should cost a day, not a quarter. `brandsonreddit.com` is the documented migration target.
- **The name is Reddit-locked.** Phase 3 in [12-phasing.md](12-phasing.md) contemplates Hacker News and other sources, which "Reddit Index" cannot carry without a rename.
- **Legal review before launch**, per [01-legal.md](01-legal.md). Nothing here is legal advice.

## What is NOT open

Raised by reviewers and resolved as false positives — do not "fix" them:

| Claim | Status |
|---|---|
| Developer Terms §5.3 trademark text | ✅ Verified verbatim from the live page |
| *Suzuki Motor Corp. v. Consumers Union*, 330 F.3d 1110 (9th Cir. 2003) | ✅ Verified |
| G2 acquired Capterra, closed 2026-02-05 | ✅ Verified |
| "roughly 28 partner projects" | 🟡 Internal Empact figure, marked as such |

---

[← Back to README](README.md) · [BUILD-PROMPT.md](BUILD-PROMPT.md) · [Index methodology](07-index-methodology.md) · [Phasing](12-phasing.md)
