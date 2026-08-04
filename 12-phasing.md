# Phasing and Scope

## Bottom line

- Four phases, each with a written entry gate and a kill test, so the project can be stopped for the price of the phase it dies in rather than the price of the whole build.
- **Phase 0 is one category: Password Managers / Security** — rated the richest signal in the assessed set, verified live 2026-08-04 ([subreddit map](04-subreddit-mapping.md)). If its ranking does not match what a knowledgeable practitioner would say, the project stops there.
- Phase 1 ships 50 categories, but **only 12 have been assessed**. ERP and Help Desk must ship labeled "insufficient Reddit signal to rank," and the remaining 38 need subreddit mapping before anyone estimates them.
- Phase 2 (full taxonomy) is a 1,000+ category problem on Capterra's flat list and 2,237 on G2's ([taxonomy](03-taxonomy.md)). Audit labor scales linearly with it and legal exposure scales faster.
- Phase 3 is why the name is UGC Ranks, not Reddit Ranks. Hacker News is the natural second source. **NOT VERIFIED** — no non-Reddit source was assessed in the corpus.
- ⚠️ Publishing full Reddit comment text on brand pages is a **deliberate, priced risk** taken by the owner with the exposure in front of him. It stacks Developer Terms §4.2 / §5.2 against per-commenter copyright Reddit cannot license ([legal](01-legal.md)). No phase gate below makes it compliant.

---

## The four phases at a glance

| Phase | Scope | Ships publicly | Hard entry gate |
|---|---|---|---|
| **0** | 1 category (Password Managers / Security) | Nothing | None — this is the first spend |
| **1** | 50 categories | Site, methodology page, corrections desk | Phase 0 passes every test below |
| **2** | Full taxonomy (1,000+) | Same, wider | Phase 1 runs 2 clean cycles at cost |
| **3** | Non-Reddit sources | Multi-source indices | Phase 1 or 2 stable and a second source verified |

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
| G1 | Mention-level entity precision on held-out | **≥0.97** | [entity resolution](05-entity-resolution.md) |
| G2 | Brands clearing `n_eff ≥ 400` after design-effect correction | **≥10 brands** | [index methodology](07-index-methodology.md) |
| G3 | Independence floors: ≥50 authors, ≥5 subreddits, ≤20% single-thread share, ≤5% single-author share | all four, per ranked brand | [index methodology](07-index-methodology.md) |
| G4 | Leave-one-subreddit-out rank stability | top 10 does not reorder beyond ties | [index methodology](07-index-methodology.md) |
| G5 | Human concordance: 3 practitioners blind-rank the top 10 before seeing output, Spearman ρ vs the computed Love Index | **ρ ≥ 0.6** | threshold set here, not derived from the corpus |

G5 is the question the whole phase exists to answer. The ≥0.97 precision / 0.80–0.88 recall figure carried through the research is **inference, never measured on this data** — publishing it before Phase 0 measures it would itself misrepresent the method.

### Phase 0 kill criteria

Stop, permanently, on any of these:

- G1–G5 fails and a documented fix does not recover it inside one rebuild.
- The "most hated" column returns the category incumbents. That is the adoption-model confound: forced enterprise users complain, voluntary self-serve users praise, and no post-hoc correction exists because the confound sits in the exposure population ([index methodology](07-index-methodology.md)).
- Inter-annotator agreement lands where the research expects it (Krippendorff's α 0.60–0.75, below 0.35 on sarcasm) and the low-agreement band is large enough that ranks move when adjudication flips.

**Effort:** 3–5 weeks for one person, gold sets included. **Cost:** ~$250 Bright Data minimum order plus free-tier API for freshness ([data acquisition](02-data-acquisition.md)); infrastructure under $50 for the phase.

---

## Phase 1 — Fifty categories

**What ships:** the ugcranks.com site, 50 category pages (two columns plus the consolidated table), brand pages with mentions and thread links, a frozen version-controlled methodology page, the delete-sync job, and a staffed corrections process with a published SLA.

Freezing the methodology *before* results are seen is the load-bearing detail. The *Suzuki* case reversed summary judgment because a jury could find the method was tampered with, not because the ranking was wrong ([legal](01-legal.md)).

**What does not rank.** Of the 12 categories assessed, **ERP and Help Desk / Support ship as "insufficient Reddit signal to rank"** rather than as rankings. r/CustomerService is a retail-horror-story sub, not a software sub, and the ERP probe returned 15 total results with the top thread from 2023 ([subreddit map](04-subreddit-mapping.md)).

**What is not costed yet.** The other **38 of 50 categories have no subreddit mapping**. Mapping is the first Phase 1 work item and any Phase 1 estimate produced before it lands is guesswork.

**Phase 1 kill criteria:** more than a handful of takedown demands in 90 days, an audit cycle that fails its publish gate (>3 errors in 60 on a stratum sample), or the corrections desk going unstaffed for a full cycle. Any of the three means the artifact is no longer defensible while it is live.

---

## Phase 2 — Full taxonomy

What changes at scale is arithmetic, not architecture. Capterra renders 1,000 leaf categories and truncates mid-W; G2 enumerates 2,237 ([taxonomy](03-taxonomy.md)).

What breaks first is the audit. At 50 categories × ~15 published brands × ≥150 adjudicated mentions the per-cycle label count is already 75K–150K, against a research budget of 400. Multiply by 20 and the per-brand publish gate stops being enforceable at all.

What breaks second is delete-sync. A full sweep over 200–400M items at 100 ids per `/api/info` call is 2–4M requests and weeks of wall-clock ([data acquisition](02-data-acquisition.md)). A stale `[removed]` behind a cited link proves a terms breach and a method-integrity failure in one exhibit.

The corpus itself is not the problem: ~240M items for 1,000 subreddits is ~53 GB compressed and fits one machine. The cost is human, legal, and recurring.

---

## Phase 3 — Beyond Reddit

The product is called UGC Ranks precisely so this phase is possible without renaming. Reddit trademarks cannot appear in a product name under Data API Terms §4.1, and Reddit has won every cited UDRP it filed ([legal](01-legal.md)).

**Hacker News is the natural second source** — a genuinely permissive public API and a population overlapping the developer-tooling categories. **NOT VERIFIED: a direction to verify, not a fact.** No Hacker News terms, API limits, or signal density were assessed in the corpus.

| Source | Status | Note |
|---|---|---|
| Hacker News | 🟡 Direction to verify | Believed permissive; **NOT VERIFIED**, not assessed |
| Stack Overflow | 🟡 Direction to verify | **NOT VERIFIED**, not assessed |
| YouTube comments | 🔴 Not assessed | **NOT VERIFIED** |
| X | 🔴 Not assessed | **NOT VERIFIED** |

Adding a second source does not dilute the Reddit legal exposure. It adds a new terms surface alongside it.

---

## The cheaper alternative

Presented fairly, as the fallback if Phase 0 fails. The owner has chosen the full build.

**Shape:** one dated, positive-only study across the 4 verified-rich categories (CRM, Password Managers, Project Management, Note-taking / KM) as a PDF with a fixed collection window, plus a free private per-prospect diagnostic sent only to the company it describes.

| | Full build | Cheap version |
|---|---|---|
| What it gets | Public leaderboard, standing SEO/AEO surface, brand pages | The same outreach hook, the same PR and citation value |
| Cost | Phases 0–1 below, then perpetual | Days of work on existing skills ([architecture](08-architecture.md)) |
| Corpus | Required | None |
| Recompute obligation | Monthly, forever | None — the study is dated and frozen |
| Corrections desk | Staffed in perpetuity | None |
| What it gives up | — | The public leaderboard, the live property, the compounding search asset |

The one thing it cannot deliver is the thing Phase 1 exists for: a standing public property that ranks brands and keeps ranking them.

---

## Effort and cost per phase

| Phase | Elapsed | Build effort | Infra | Recurring human cost |
|---|---|---|---|---|
| **0** | 3–5 weeks | ~35h annotation + pipeline | ~$250 one-off + <$50 | None (nothing published) |
| **1** | Not estimable until 38 categories are mapped | Site + 38 mappings + corrections process | ~$105/mo at ~300 brands (**NOT VERIFIED** — Railway/Hetzner prices are secondary-sourced) | ~5h/cycle audit at 300 brands; more at 50 categories |
| **2** | Not planned | — | Storage roughly linear | 75K–150K labels/cycle — the number that breaks it |
| **3** | Not planned | Second-source ingest | Not estimated | Not estimated |

Legal costs appear in no line above and are real: an Estonian data-protection opinion and a US media-law read of the final page copy, both one-time, both **not disclosed** as figures anywhere in the research.

---

[← Back to README](README.md) · [00-concept.md](00-concept.md) · [08-architecture.md](08-architecture.md)
