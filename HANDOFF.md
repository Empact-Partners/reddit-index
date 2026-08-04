# Handoff — open items

**State as of 2026-08-04.** The repo is complete and internally consistent enough to read and act on. `validate.py` passes: 0 failures, every relative link resolves.

A third review pass found **6 defects that are still open**. They are listed here rather than silently left, and they are all in one cluster plus one arithmetic slip.

## Bottom line

- The **diversity-floor set diverged** between `07-index-methodology.md` and the five documents that cite it. This is the one real problem. Fix 07 or fix the five — but pick one set.
- One **Wilson interval in `12-phasing.md` is miscomputed**, and its stated conclusion is false as computed.
- Everything else in the defect list is small.
- Outside the docs, **neither domain is registered**, and the name carries a live trademark exposure that was chosen and priced in [decisions/0001](decisions/0001-name-reddit-index.md).

---

## 1. 🔴 The four diversity floors disagree across six files

`07-index-methodology.md` §5 defines:

| Floor | Value |
|---|---|
| Distinct authors | ≥ 50 |
| Distinct subreddits | ≥ 5 |
| Max share from one thread | ≤ 20% of `n` |
| Max share from one **author** | ≤ 5% of `n` |

Every consuming document instead says *distinct threads* is the third floor and drops the max-share-from-one-author floor: `README.md`, `00-concept.md`, `11-outreach-play.md`, `12-phasing.md`, and `09-design.md`.

Five files agree with each other and disagree with the spec they all cite.

**Consequences:** `12-phasing.md` gate G3 references "distinct threads above the floor set in 07" — a dangling reference, because 07 sets no such floor. `09-design.md` specifies a ranking table with a distinct-threads column and no max-share-from-one-author column, so the published table cannot show 07's actual floors.

**Recommended fix:** keep **five** floors — distinct authors ≥50, distinct subreddits ≥5, distinct threads ≥ (set a number), max single-thread share ≤20%, max single-author share ≤5%. Stop calling it "four". Then update `07` and the five consumers together, and give `09-design.md` a column per floor.

## 2. 🔴 Miscomputed Wilson interval in `12-phasing.md`

Line ~58 states: at p̂ = 0.97 on 500 items the Wilson 95% interval is "roughly [0.949, 0.980], so it cannot separate 0.97 from 0.95."

Recomputed, the interval is **[0.9511, 0.9817]**. The lower bound sits *above* 0.95, so the sentence's own conclusion is false.

`05-entity-resolution.md` gets the identical arithmetic right at n=400 and n=1,000. Only `12-phasing.md` is wrong.

## 3. 🟡 `12-phasing.md` gate G1 uses a banned point estimate

G1 gates on "≥0.97 point estimate". `05-entity-resolution.md` now specifies precision publishes as a **95% Wilson lower bound, never a point estimate**. Update G1 to the lower bound.

## 4. 🟡 `12-phasing.md` ships a retired audit gate

Phase 1 kill criteria still uses ">3 errors in 60 on a stratum sample". `05-entity-resolution.md` retired that rule explicitly — it carries the interval [0.863, 0.983] and clears a brand whose true precision is 0.87. The live rule is **more than 2 errors in 150**.

## 5. 🟡 `README.md` Limits section is stale on the audit

It says the planned audit is 400 items and presents the size as an open choice. `05-entity-resolution.md` §5 already raised it to **1,000 per cycle**. The cross-reference also points at `06-sentiment.md`, but entity-precision auditing lives in `05-entity-resolution.md`.

## 6. 🟢 Three small ones

- `11-outreach-play.md`: "`n_eff` is always below `n`" is false as an absolute. `DEFF = 1` when `ICC = 0` or `m̄ = 1`. Correct wording: never *above* `n`.
- `00-concept.md`: a sentence ends mid-comparison — "400 raw mentions can carry far less information than 400." The intended form is in `07-index-methodology.md`: "400 correlated mentions carry less information than 400 independent ones."
- `06-sentiment.md`: the cascade saving is quoted as "2–7×" but the recomputed like-for-like multiples in the same section give 2.0–6.5×. Round honestly or restate.

---

## What is NOT open

These were raised by reviewers and resolved as **false positives** — do not "fix" them:

| Claim | Status |
|---|---|
| Developer Terms §5.3 trademark text | ✅ Verified verbatim from the live page |
| *Suzuki Motor Corp. v. Consumers Union*, 330 F.3d 1110 (9th Cir. 2003) | ✅ Verified |
| G2 acquired Capterra, closed 2026-02-05 | ✅ Verified |
| "roughly 28 partner projects" | 🟡 Internal Empact figure, marked as such |

## Also outstanding, outside the docs

- **Neither domain is registered.** `redditindex.com` is the chosen primary and `redditbrandindex.com` the defensive name that redirects to it. Both verified available 2026-08-04 — availability moves, so re-check before buying. [decisions/0001](decisions/0001-name-reddit-index.md) requires both before launch, not after.
- **The `.io`, `.co`, `.net` and `.org` variants of both names are also recorded available** on the same date in [data/domain-availability.csv](data/domain-availability.csv). Only the `.com` pair is mandatory; the rest is a cheap defensive decision nobody has made yet.
- **The name breaches two Reddit clauses.** [Data API Terms §4.1](https://www.redditinc.com/policies/data-api-terms) and [Developer Terms §5.3](https://www.redditinc.com/policies/developer-terms) both forbid Reddit trademarks in a product name. This is recorded, not overlooked — the owner made the call with the exposure in front of him.
- **Enforcement is a UDRP filing, not a lawsuit.** Reddit runs them *pro se* for roughly $1,500 and has won every one found: [reddit.win](https://www.wipo.int/amc/en/domains/decisions/text/2020/d2020-1834.html) (D2020-1834), [redditpromotion.com / redditshop.com](https://www.wipo.int/amc/en/domains/decisions/text/2019/d2019-2964.html) (D2019-2964), [reddit.co](https://www.wipo.int/amc/en/domains/decisions/text/2018/dco2018-0008.html) (DCO2018-0008).
- **Low traffic is not a defence.** A UDRP is a registrar-level administrative proceeding. It needs no damages, no discovery, and no proof that anyone visited. It needs only that Reddit notices.
- **What a loss costs is the domain, not the project.** The pipeline, the index, the methodology and the content all survive a transfer. That asymmetry is why the risk was accepted, and it is why the next item is a build requirement rather than a preference.
- **Migration dependency: the canonical host lives in exactly one config value, and every internal link stays relative.** That is a build constraint created by [decisions/0001](decisions/0001-name-reddit-index.md) and it binds whoever writes the code. A forced move should cost a day, not a quarter.
- **`brandsonreddit.com` is the documented migration target.** It was available and carries a materially better UDRP posture: a descriptive phrase where Reddit is the subject covered, rather than a compound where REDDIT leads and reads as a sub-brand. It was not taken.
- **The name is Reddit-locked.** Phase 3 in [12-phasing.md](12-phasing.md) contemplates Hacker News, Stack Overflow and other sources. "Reddit Index" cannot carry them without a rename. That option was knowingly sold for legibility in a cold email, and it is the second trigger the one-config-value rule exists for.
- **42 of the 50 Phase 1 categories have no subreddit mapping.** Eight are mapped.
- **No crosswalk ships between the 20 probed categories and the 50-row Phase 1 taxonomy.** Only 8 labels join exactly. Build it before quoting any combined coverage figure.
- **Legal review before launch**, per [01-legal.md](01-legal.md). Nothing here is legal advice.

---

[← Back to README](README.md) · [Index methodology](07-index-methodology.md) · [Phasing](12-phasing.md)
