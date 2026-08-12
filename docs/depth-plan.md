# Depth plan — from 903 score rows to thousands of ranked companies

*Written 2026-08-12, the day methodology 2.0.0 shipped. This is a design and
a budget, not a build. Nothing below is running yet.*

## Where depth actually stands

Measured against the live database:

| Fact | Value |
|---|---|
| Mentions collected, ever | 48,655 (35,049 inside the 365-day scoring window) |
| Distinct threads, ever | 9,116 stored / 4,188 with mentions — **~20 per subreddit** |
| Brands in the taxonomy | 1,742 (median 19 per category, min 5, max 25) |
| Brands with **zero** mentions | 605 (35%) |
| Brands clearing the n_op ≥ 3 display floor | ~5.6 per category |
| Scoring subreddits per category | avg 5.6 (min 1, max 10); 94/100 categories have any |

## Why it is shallow — four causes, in order of weight

1. **The thread corpus is tiny.** ~20 threads per subreddit ever fetched. The
   one-shot harvest was scoped search with small tree-fetch caps; the daily
   top-up reads only `/r/{sub}/new` (≤3 pages). Reddit exposes ~1,000 posts
   per listing and five `/top` windows — **3-4k reachable threads per
   subreddit that were never taken.**
2. **Brand rosters were capped.** Enumeration stopped at ~25 brands per
   category and under-filled some to 5 (marketing-automation holds exactly
   5 brands, which is why the board shows 2-3).
3. **Category scoping discards signal.** A mention counts toward a category
   only when found in that category's own scoring subreddits; the same brand
   named in an adjacent or general subreddit feeds nothing.
4. **The display floor then hides the remainder** — and until 2.0.0 the
   broken prior scrambled what did show.

## The four lanes to depth

### 1. Roster expansion (fleet enumeration v2)
Uncapped re-enumeration: 100-300 candidates per category through the same
G1-G6 gates + adversarial review (`data/enumerate_brands.py` pattern:
gpt-5.6-sol enumerate → terra adversarial review → luna topicality).
Target: **8-15k brands after dedup**. ~300-500 fleet jobs.

### 2. Corpus deepening (the big one)
Per scoring subreddit: `/new` to the listing cap + `/top` at t=all/year/
month + per-brand scoped search lanes. Widen scoring subs from 5.6 to
10-12 per category (~1,100 subs total; fixes the 6 zero-sub categories).
Expected: **threads 4.2k → 400-700k, mentions 48k → 1.5-5M.**

### 3. Classification at scale (Codex fleet, luna)
The existing `classify_codex.py` lane unchanged: 25 mentions per batch,
disk-idempotent out-files, item-level label cache. Only the volume grows.

### 4. Daily steady state
The existing Railway (04:00 UTC fetch) + Mac launchd (03:30 classify →
score → publish) loop, with per-lane budgets so backfill and daily top-up
share the same rate limit without starving each other.

## Spend + time projections

**Reddit API (fetch) — the wall-clock constraint, zero cash.**
App-only OAuth at a self-imposed ~60-100 QPM sustained ≈ **85-140k
requests/day**. The full historical sweep costs roughly: listings ~1,100
subs × ~40 pages ≈ 45k requests; comment trees ~400-700k threads × ~1.3 ≈
520-910k; brand-scoped search ≈ 45k. **Total ≈ 0.6-1.0M requests ≈ 7-12
days of unattended fetching** on the existing worker. No credits, no paid
API — this is plain Reddit OAuth within rate limits.

**Classification (Codex fleet) — the quota constraint, zero cash.**
1.5M mentions ÷ 25/batch = **60k luna jobs**. At 40-wide with ~75s/job the
fleet clears ~45k jobs/day flat-out, so the mechanical floor is ~1.5 days —
but the real pacer is the ChatGPT 20x **weekly quota** shared with all other
Codex work. Paced plan: **2-4 weeks of off-hours burns** (10-20k jobs per
burn window). API-equivalent value of the whole backfill ≈ $1,000-1,500 at
luna list prices; actual cash on the subscription: **$0**. Claude tokens:
**zero** — nothing in this pipeline touches the Max plan.

**Steady state after backfill:** ~2-5k new mentions/day ≈ 100-200 luna
jobs/day ≈ 1-2% of fleet capacity. Rounding error.

**The only potential cash cost: Supabase.** 1.5-5M mention rows ≈ 2-6 GB —
past the free tier. Budget **Supabase Pro, $25/mo**, and watch the egress
quota (the reddit-agent stall precedent: quota exhaustion presents as
"couldn't write", not downtime).

**Vercel/build:** 8-15k brands ≈ 10k+ static routes. The force-static
publish survives to roughly 5k routes; past that, move company pages to
on-demand rendering with the same daily revalidate. A seam change, not a
redesign — flagged now so it is not discovered at route 9,000.

## Phasing

| Phase | What | Wall-clock | Bottleneck |
|---|---|---|---|
| P0 | Methodology 2.0.0 + calibration gate | **shipped 2026-08-12** | — |
| P1 | Roster 1.7k→8-15k brands, subs 5.6→10-12/cat | 2-3 days | fleet review passes |
| P2 | Historical sweep + classify backfill | 3-4 weeks, unattended | Reddit QPM + Codex weekly quota |
| P3 | Deep steady state | ongoing | none |

Outcome at P2 exit: brands clearing the display floor go from ~500 to an
estimated **4,000-8,000**, and category boards field 15-30+ ranked brands
instead of 5. The v1 statistical gates (n_eff ≥ 200-600) stop being
aspirational and start retiring the "directional" caveat on real boards.
