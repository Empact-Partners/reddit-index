# Category → Subreddit Mapping

How a category becomes a list of subreddits worth ingesting — the method, the exclusion rules, and the traps that a name-based guess walks straight into.

**Method doc.** The measured numbers live in [14-category-tests.md](14-category-tests.md) and [data/subreddit-measurements.csv](data/subreddit-measurements.csv). This file does not restate them as a second source of truth.

## Bottom line

- **Two exclusions decide the map, and neither is size.** Rule posture removes subs that delete brand talk; community type removes subs whose population already bought the product. Together they cut 132 measured subreddits to **51 scorable**.
- **37% of reachable subreddits (48 of 131) are hostile** to brand mentions, read from their own rules. **36% (48 of 132) are single-product communities.** Both figures come from the 20-category study.
- **Single-product ≠ ecosystem.** r/Bitwarden is evidence only. r/salesforce is scoreable and measured **30% brand-bearing** with genuinely comparative discussion. Collapsing the two costs real categories real subs.
- **Only 6 of 20 tested categories reach the 5-scorable-sub floor.** The cause is short candidate lists, not absent discussion, so widening lists is the highest-leverage work left.
- **Map per category, ingest per subreddit.** 187 candidate slots collapse to **132 unique** subreddits; r/Entrepreneur alone appears in 7 categories.
- ⚠️ **No category may be declared dead from this evidence.** At the 95% upper bound all 20 clear the mention threshold ([14-category-tests.md](14-category-tests.md) §4).

## Where the numbers live

| Source | Rows | Authoritative for |
|---|---:|---|
| [14-category-tests.md](14-category-tests.md) | — | The 20-category study, its bounds, and its limits |
| [data/subreddit-measurements.csv](data/subreddit-measurements.csv) | 132 | Per-subreddit posture, community type, live rate, scorability |
| [data/category-tests-20.csv](data/category-tests-20.csv) | 20 | Per-category rollup and the 5-sub floor verdict |
| [13-algorithm.md](13-algorithm.md) §2 | — | The selection score that ranks survivors and caps each category at 8 |
| [data/phase1-categories.csv](data/phase1-categories.csv) | 50 | Which Phase 1 categories are mapped (8) versus pending (42) |

[data/subreddit-map.csv](data/subreddit-map.csv) is the earlier 12-category map, superseded as a measurement source by `subreddit-measurements.csv`. It survives only as the per-category row form.

## Exclusion 1 — rule posture

A sub that deletes product mentions is a dead source at any size. Posture is classified by regex over the full rules text from `/r/{sub}/about/rules`.

| Posture | Count | Meaning | Map action |
|---|---:|---|---|
| `permissive` | 64 | Organic brand discussion allowed | Scoreable |
| `hostile` | 48 | Brand or product mentions actively removed | Drop, any size |
| `unknown` | 13 | Rules endpoint returned nothing parseable | Resolve by hand before shipping |
| `capped` | 6 | Karma gate or weekly-promo-thread confinement | Scoreable, organic threads only |

The largest communities are disproportionately the strictest. The six biggest hostile subs are r/Entrepreneur (5,249,043), r/productivity (4,231,867), r/webdev (3,291,935), r/smallbusiness (2,515,817), r/marketing (1,958,693) and r/FinancialCareers (1,762,260).

**r/smallbusiness changed in June 2026** — Rule 2 now removes product mentions from posts *and comments* when they read as directly or indirectly promotional, and Rule 5 bans market-research posts. One rule edit turned a top-five source into noise.

⚠️ Posture drifts. Re-pull rules every cycle and hash the text; [13-algorithm.md](13-algorithm.md) §9 treats a hash change as a trigger to re-evaluate. A sub that turns prohibitive leaves the scoring corpus.

## Exclusion 2 — single-product versus ecosystem

This distinction is first-class, because it decides scorability for 54 of 132 subreddits and it is not readable from the name.

| Type | Count | Test | Status |
|---|---:|---|---|
| `independent` | 78 | Organised around a job, a craft, or a problem | Scoreable |
| `ecosystem` | 6 | Named for a vendor, populated by practitioners discussing the whole market | **Scoreable, flagged** |
| `single_product` | 48 | Organised around one product; membership is a purchase decision | **Evidence only, never scored** |

**Single-product subs are dense and unusable.** r/paypal measured 50% brand-bearing, r/SAP 49%, r/Bitwarden 37%, r/Notion 33%. Every one is a population that already chose the product, so praise there is worthless. Criticism there is the strongest negative signal available — which is why they stay in the corpus as brand-page evidence, labelled visibly as the product's own subreddit.

**Ecosystem subs are the correction.** The six are r/salesforce, r/shopify, r/aws, r/Adobe, r/reactjs and r/node. r/salesforce carries single-product density (30% brand-bearing) with comparative discussion, and is permissive. Blanket-excluding every vendor-named sub dropped CRM from 5 scorable subs to 4 and would have failed the category on a classification error, not on evidence.

Ecosystem status does not override posture: r/Adobe classifies hostile and is dropped anyway, leaving 5 of the 6 scoreable.

**The structural tension.** The densest brand talk is systematically in the subs we cannot score. Everything the index publishes comes from the thinner, harder, independent middle ([14-category-tests.md](14-category-tests.md) §6).

## Traps, verified live

**Name collision.** [r/figma](https://www.reddit.com/r/figma/) is a Japanese action-figure subreddit. The design tool lives in [r/FigmaDesign](https://www.reddit.com/r/FigmaDesign/) (154,580). Never resolve a subreddit by lowercasing a product name; resolve every candidate through `/r/{sub}/about` and read the description.

**Stem matching.** Reddit search stems query terms. "Descript" in r/VideoEditing returned 15 results, roughly 8 of which matched the word "description". Short brand names need an exact-token filter applied locally after the search returns.

**Discovery is broken.** `search_reddit` with `type='sr'` returns zero results under app-only OAuth, for every query tried. Candidate lists are built by hand. This is the reason short lists are the binding constraint on the whole product.

**Subscriber count does not predict signal.** Measured against the same five seed brands on the same 100-comment instrument: r/PasswordManagers (54,640 subs) returned **42% brand-bearing**, while r/privacy (1,652,332) returned 0% and r/cybersecurity (1,499,373) returned 2%. r/sysadmin runs 112 comments/hour and returned 0% on those seeds. Size buys traffic, not brand opinion.

**Brand-bearing share is per-seed-set, not absolute.** The CSV holds one row per unique subreddit, and the probe caches by subreddit name, so each sub's share was measured against the five seed brands of whichever category reached it first. A 0% row means *not detected against those five brands in one page*, never *no brand talk*.

## Map per category, ingest per subreddit

The 20 tested categories requested **187 candidate slots** that resolve to **132 unique subreddits**. Twenty-eight subs serve more than one category.

| Subreddit | Categories served |
|---|---:|
| r/Entrepreneur | 7 |
| r/smallbusiness | 6 |
| r/SaaS | 5 |
| r/sysadmin | 5 |
| r/shopify | 4 |
| r/ITManagers | 4 |

Ingest is per-subreddit. Deduplicate the ingest set before scheduling or roughly 29% of calls re-fetch the same comment streams. At full taxonomy scale the overlap grows and so does the saving ([13-algorithm.md](13-algorithm.md) §8).

## The procedure

Run this per category, in order. It produces the candidate set; [13-algorithm.md](13-algorithm.md) §2 scores and truncates it to at most 8 scoring subreddits.

1. **Enumerate candidates by hand,** from four strata: the practitioner sub for the buyer's job function, verified general software and business subs, adjacent workflow subs where a buyer would ask for a recommendation, and one sub per known brand from [data/brand-gazetteer-seed.csv](data/brand-gazetteer-seed.csv). Target more independent practitioner subs than feels necessary — short lists are what fail categories.
2. **Resolve every name** through `/r/{sub}/about`. Read the description. This is the step that catches r/figma.
3. **Pull rules** from `/r/{sub}/about/rules` and classify posture. Hostile subs are dropped regardless of size. `unknown` is not a pass — resolve it by hand.
4. **Classify community type** as independent, ecosystem, or single-product, using the vendor-name test above rather than the name alone. Single-product subs are marked evidence-only in the same pass.
5. **Measure the live comment rate** from one `/r/{sub}/comments?limit=100` page. The span of that page gives comments per hour, which also sets the ingest cadence and the multireddit bucket in [13-algorithm.md](13-algorithm.md) §3.
6. **Probe brand-bearing share** across that page, with an exact-alias check applied locally so stemmed hits do not count.
7. **Count scorable subs.** Below 5, the category cannot satisfy the diversity floor in [07-index-methodology.md](07-index-methodology.md) and ships as *insufficient Reddit signal to rank* — a real template, not a stub. Widen the candidate list before accepting that outcome.
8. **Write the result back** to [data/subreddit-measurements.csv](data/subreddit-measurements.csv) and [data/category-tests-20.csv](data/category-tests-20.csv), and flip the category's `subreddit_map_status` in [data/phase1-categories.csv](data/phase1-categories.csv), in one commit. Files disagreeing about what is mapped is how this map rots unnoticed.

The harness that implements steps 2-6 is [data/probe.py](data/probe.py). It is resumable — one JSON file per subreddit on disk, so a re-run costs only the gap. ⚠️ It loads its candidate list from `cat20.json`, while the list shipped in this repo is [data/category-candidates-20.json](data/category-candidates-20.json); reconcile the filename before re-running.

## Open work

**Widen the candidate lists for the 14 categories below the floor.** Note-taking is the clearest case: 10 candidates produced 7 hostile and 6 single-product subs, leaving exactly one scorable (r/Zettelkasten). Video Editing left one (r/editors) out of 9. Both categories have abundant Reddit discussion; the lists simply pointed at product communities.

**Resolve the 13 `unknown` postures by hand:** r/aws, r/backblaze, r/CRM, r/KeePass, r/Klaviyo, r/NAS, r/node, r/PasswordManagers, r/Payments, r/QuickBooks, r/SAP, r/talentacquisition, r/trello.

This is not cosmetic. **Seven of those 13 are currently counted as scorable** — r/aws, r/CRM, r/NAS, r/node, r/PasswordManagers, r/Payments and r/talentacquisition. Marked as inference: if r/CRM's rules resolve to hostile, CRM falls to 4 scorable subs and fails its own floor, and CRM is the current Phase 0 recommendation.

**Reconcile category names.** The 20 study categories and the 50-row Phase 1 taxonomy use different labels for 12 of the 20 — "HR and HRIS" against "Human Resources", "Applicant Tracking and Recruiting" against two separate rows. Step 8 cannot write back cleanly until one naming convention wins.

---

[← Back to README](README.md) · [Category tests, measured](14-category-tests.md) · [The algorithm](13-algorithm.md) · [Category taxonomy](03-taxonomy.md) · [Data acquisition](02-data-acquisition.md) · [Index methodology](07-index-methodology.md)
