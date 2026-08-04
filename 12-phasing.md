# Phasing and Scope

## Bottom line

- Four phases, each with a written entry gate and a kill test, so Reddit Index can be stopped for the price of the phase it dies in rather than the price of the whole build.
- **Phase 0 is one category: Password Managers / Security** — the richest signal in the assessed set, verified live 2026-08-04 ([subreddit map](04-subreddit-mapping.md)). It publishes nothing. If its ranking does not match what a knowledgeable practitioner would say, the project stops there.
- **Phase 1 is the first public spend.** Fifty categories on redditindex.com — but **only 12 have been assessed**. ERP and Help Desk ship labeled "insufficient Reddit signal to rank," and the remaining 38 need subreddit mapping before anyone estimates the phase.
- Phase 2 is a 1,000+ category problem on Capterra's flat list, 2,237 on G2's ([taxonomy](03-taxonomy.md)). Audit labor scales linearly with it, and the per-brand publish gate stops being enforceable somewhere inside that multiple.
- **Phase 3 opens with a naming fork, not with ingest work.** The product is Reddit Index, so a non-Reddit source means a rename or a separately-branded second property ([0001](decisions/0001-name-reddit-index.md)).
- **Infrastructure is not the constraint.** Roughly **$85/month for Phase 1**, roughly **$330/month at full scale** ([architecture §8](08-architecture.md)). What binds is audit labor and a corrections desk staffed in perpetuity.

---

## The four phases at a glance

| Phase | Scope | Ships publicly | Hard entry gate |
|---|---|---|---|
| **0** | 1 category (Password Managers / Security) | Nothing | None — this is the first spend |
| **1** | 50 categories | Site, `/methodology`, corrections desk | Phase 0 passes G1–G5, and the Phase 1 ship checklist is green |
| **2** | Full taxonomy (1,000+) | Same, wider | Phase 1 runs 2 clean cycles at cost |
| **3** | Non-Reddit sources | Multi-source indices | Phase 1 or 2 stable, a second source verified, naming fork resolved |

---

## Phase 0 — Proof of signal

**Nothing is published. No site is built. No domain is pointed anywhere.**

Ingest the 12 mapped subreddits: r/privacy (1,652,252), r/cybersecurity (1,499,209), r/sysadmin (1,307,063), r/selfhosted (812,909), r/netsec (568,416), r/msp (245,249), r/Bitwarden (119,758), r/ITManagers (77,186), r/1Password (56,814), r/PasswordManagers (54,639), r/ProtonPass (35,219), r/KeePass (23,021).

The category was picked because the live probe was unambiguous: "Bitwarden" scoped to r/PasswordManagers returned 100 results plus a cursor, near-100% on-topic, led by ["Bitwarden BAD NEWS"](https://reddit.com/r/PasswordManagers/comments/1te4lcp/bitwarden_bad_news/) at 192 points and 147 comments.

### What gets built first

The gold sets, before the pipeline. Everything downstream is unmeasurable without them ([sentiment method](06-sentiment.md)).

| Artifact | Size | Effort |
|---|---|---|
| Entity gold set | 1,000 mentions, 2 annotators, 200-item overlap for kappa | ~15h |
| Sentiment gold set | 1,000–1,500 stratified, ≥150–200 per minority class | ~20h (estimate, not measured) |
| Held-out set | 500 items, unopened until the end | included above |

### The go/no-go test

All five must pass. Any single failure stops the project.

| # | Test | Threshold | Source |
|---|---|---|---|
| G1 | Mention-level entity precision on held-out | **≥0.97** point estimate, interval reported | [entity resolution](05-entity-resolution.md) |
| G2 | Brands clearing **`n_eff ≥ 400`**, where `n_eff = n / DEFF` and `DEFF = 1 + (m̄ − 1)·ICC` | **≥10 brands** | [index methodology](07-index-methodology.md) |
| G3 | All four diversity floors hold: distinct authors ≥50, distinct subreddits ≥5, distinct threads above the floor set in 07, max single-thread share ≤20% of `n` | all four, per ranked brand | [index methodology](07-index-methodology.md) |
| G4 | Leave-one-subreddit-out rank stability | top 10 does not reorder beyond ties | [index methodology](07-index-methodology.md) |
| G5 | Human concordance: 3 practitioners blind-rank the top 10 before seeing output, Spearman ρ vs the computed Love Index | **ρ ≥ 0.6** | threshold set here, not derived from the corpus |

G2 gates on the **design-effect-corrected** count, not the raw one. Reddit mentions cluster inside a few mega-threads and within threads by author, so raw `n` overstates independent information. Both `n` and `n_eff` publish on every brand page, with intervals from a cluster bootstrap resampled by thread and by author.

G1's threshold is a point estimate, not a tight one. On a 500-item held-out set an observed 0.97 carries a Wilson 95% interval of roughly [0.949, 0.980], so it cannot separate 0.97 from 0.95. Either the held-out set grows or the published claim states the interval rather than the point.

G5 is the question the whole phase exists to answer. The ≥0.97 precision / 0.80–0.88 recall figure carried through the research is **inference, never measured on this data**.

### Phase 0 kill criteria

Stop, permanently, on any of these:

- G1–G5 fails and a documented fix does not recover it inside one rebuild.
- The "most hated" column returns the category incumbents. That is the adoption-model confound: forced enterprise users complain, voluntary self-serve users praise, and no post-hoc correction exists because the confound sits in the exposure population ([index methodology](07-index-methodology.md)).
- Inter-annotator agreement lands where the research expects it (Krippendorff's α 0.60–0.75, below 0.35 on sarcasm) and the low-agreement band is large enough that ranks move when adjudication flips.

**Effort:** 3–5 weeks for one person, gold sets included.

**Cost:** bandwidth, essentially. The acquisition shape is Arctic Shift per-subreddit dumps for backfill plus the official free-tier API for increments, and 12 subreddits sit far inside the free tier ([data acquisition](02-data-acquisition.md)). Infrastructure runs under $50 for the whole phase.

A commercial vendor is a targeted gap-fill option, not the Phase 0 route. Bright Data's $250 minimum order is a cost only if a gap-fill is actually placed, and its per-record pricing makes it unusable as a census ([data acquisition](02-data-acquisition.md)).

---

## Phase 1 — Fifty categories

**What ships:** redditindex.com, 50 category pages (two columns plus the consolidated table), brand pages with mentions and thread links, a frozen version-controlled methodology page at `/methodology`, the delete-sync job, and a staffed corrections process with a published SLA.

### Phase 1 ship checklist

Every box is green before the domain resolves publicly. These are build requirements, and the reasoning behind them — including the two risks the owner priced and accepted — is in [01-legal.md](01-legal.md).

- [ ] Phase 0 passed G1–G5, with intervals published rather than point estimates alone.
- [ ] Nightly delete-sync runs and is verified against a seeded set of deleted, removed, and edited items.
- [ ] Every mention renders permalink + username + "from Reddit."
- [ ] Removal route live: free, fast, no questions, no sales offer attached, reachable from every brand page.
- [ ] `/methodology` published, frozen, and version-controlled **before** the first scoring run — never adjusted after seeing where a company landed, in either direction.
- [ ] Non-affiliation notice in the footer of every page.
- [ ] Zero ads anywhere on the domain, and no Reddit trade dress: no `#FF4500`, no Snoo, no Reddit Sans, no lookalike mark ([design](09-design.md)).
- [ ] Plain-text company names, no logos, and the measured variable printed beside every superlative ([0005](decisions/0005-superlative-labels.md)).
- [ ] Defensive `redditbrandindex.com` registered and redirecting to the primary.
- [ ] Canonical host in exactly one config value, every internal link relative, so a forced move costs a day rather than a quarter.
- [ ] Corrections desk staffed, with the SLA published on the site.

**What does not rank.** Of the 12 categories assessed, **ERP and Help Desk / Support ship as "insufficient Reddit signal to rank"** rather than as rankings. r/CustomerService is a retail-horror-story sub, not a software sub, and the ERP probe returned 15 total results with the top thread from 2023 ([subreddit map](04-subreddit-mapping.md)).

**What is not costed yet.** The other **38 of 50 categories have no subreddit mapping**. Mapping is the first Phase 1 work item, and any Phase 1 estimate produced before it lands is guesswork.

**What it costs to run.** Roughly **$85/month** of infrastructure — $84/mo exactly across R2, the ingest worker, Supabase, Vercel Pro and Cloudflare, at ~50 categories / ~500 brands / ~200 subs / ~1k pages on a weekly refresh ([architecture §8](08-architecture.md)). The audit labor is the expensive line.

### Phase 1 kill criteria

Any one of these means the artifact is no longer defensible while it is live:

- More than a handful of takedown demands in 90 days.
- An audit cycle that fails its publish gate (>3 errors in 60 on a stratum sample).
- The corrections desk going unstaffed for a full cycle.

---

## Phase 2 — Full taxonomy

What changes at scale is arithmetic, not architecture. Capterra renders 1,000 leaf categories and truncates mid-W; G2 enumerates 2,237 ([taxonomy](03-taxonomy.md)).

What breaks first is the audit. At 50 categories × ~15 published brands × ≥150 adjudicated mentions, Phase 1's per-cycle label count is already 75K–150K, against a research budget of 400. The 20× category expansion puts Phase 2 at roughly 1.5M–3M labels a cycle, at which point the per-brand publish gate stops being enforceable at all.

What breaks second is delete-sync. A full sweep over 200–400M items at 100 ids per `/api/info` call is 2–4M requests and weeks of wall-clock ([data acquisition](02-data-acquisition.md)). A stale `[removed]` sitting behind a cited link is the failure this phase is most likely to ship.

The corpus itself is not the problem: ~240M items for 1,000 subreddits is ~53 GB compressed and fits one machine. Storage is budgeted from those compressed bytes, not from the 0.5–1.5 TB raw-JSON figure ([architecture](08-architecture.md)). The cost is human and recurring.

---

## Phase 3 — Beyond Reddit

**The name does not travel.** The product ships as Reddit Index on redditindex.com, so a Hacker News or Stack Overflow index cannot sit under it. This phase therefore opens with a naming fork rather than with ingest work, and the fork is the entry gate.

| Fork | What it means | What it costs |
|---|---|---|
| **Rename the property** | Move everything to a source-neutral name. `brandsonreddit.com`, the migration target recorded in [0001](decisions/0001-name-reddit-index.md), does not solve this one — it is Reddit-scoped too, so a genuinely multi-source name is a third choice still to be made. | Redirects, plus every citation and inbound link earned under the old name. |
| **Run a second property** | Reddit Index stays as it is and the non-Reddit index ships under its own brand. | Two sites, two frozen methodology pages, two corrections desks, no combined leaderboard. |

Neither is cheap, and the fork was priced when the name was chosen: legibility in a cold email was judged worth more than keeping the multi-source option open.

**Hacker News is the natural second source** — a genuinely permissive public API and a population overlapping the developer-tooling categories. **NOT VERIFIED: a direction to verify, not a fact.** No Hacker News terms, API limits, or signal density were assessed in the corpus.

| Source | Status | Note |
|---|---|---|
| Hacker News | 🟡 Direction to verify | Believed permissive; **NOT VERIFIED**, not assessed |
| Stack Overflow | 🟡 Direction to verify | **NOT VERIFIED**, not assessed |
| YouTube comments | 🔴 Not assessed | **NOT VERIFIED** |
| X | 🔴 Not assessed | **NOT VERIFIED** |

A second source adds its own terms surface and its own ship checklist. It removes nothing from Phase 1's.

---

## The cheaper alternative

Presented fairly, as the fallback if Phase 0 fails. The owner has chosen the full build.

**Shape:** one dated, positive-only study across the 4 verified-rich categories (CRM, Password Managers, Project Management, Note-taking / KM) as a PDF with a fixed collection window, plus a free private per-prospect diagnostic sent only to the company it describes.

| | Full build | Cheap version |
|---|---|---|
| What it gets | Public leaderboard, standing SEO/AEO surface, brand pages | The same outreach hook, the same PR and citation value |
| Cost | Phase 0 bandwidth, then ~$85/mo plus audit labor, forever | Days of work on existing report skills ([outreach play](11-outreach-play.md)) |
| Corpus | Required | None |
| Recompute obligation | Weekly, forever ([architecture](08-architecture.md)) | None — the study is dated and frozen |
| Corrections desk | Staffed in perpetuity | None |
| What it gives up | — | The public leaderboard, the live property, the compounding search asset |

The one thing it cannot deliver is the thing Phase 1 exists for: a standing public property that ranks brands and keeps ranking them.

---

## Effort and cost per phase

| Phase | Elapsed | Build effort | Infra | Recurring human cost |
|---|---|---|---|---|
| **0** | 3–5 weeks | ~35h annotation + pipeline | Bandwidth + **<$50** for the phase | None (nothing published) |
| **1** | Not estimable until 38 categories are mapped | Site + 38 mappings + corrections process | **≈ $84/mo**, quoted as roughly $85/month ([architecture §8](08-architecture.md)) | 75K–150K adjudicated labels/cycle at 50 categories, plus a staffed corrections desk |
| **2** | Not planned | — | **≈ $328/mo** at full scale, quoted as roughly $330/month ([architecture §8](08-architecture.md)) | 1.5M–3M labels/cycle — the number that breaks it |
| **3** | Not planned | Second-source ingest, plus a rename or a second brand | Not estimated | Not estimated |

Both infra totals come from the line-item table in [08-architecture.md §8](08-architecture.md) and are the same figures the README carries. Inside them, only the ingest-worker line (Railway, or a Hetzner box) is secondary-sourced; verify it before committing. Every other line is a vendor-published price.

Two one-time reviews sit outside every line above: an Estonian data-protection opinion and a US media-law read of the final page copy. **Neither is costed** — no figure for either appears anywhere in the research.

---

[← Back to README](README.md) · [00-concept.md](00-concept.md) · [01-legal.md](01-legal.md) · [08-architecture.md](08-architecture.md)
