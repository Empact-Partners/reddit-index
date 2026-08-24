# THE DEPTH EXECUTION PLAN — every subreddit, every 90-day thread

*Written 2026-08-12 on Vlad's explicit instruction. This is THE plan to
execute in a dedicated session. The ask, verbatim in spirit: "Find me every
subreddit that makes sense for every category — 20, 30, 40, 50 per category,
or as many as make sense — and then every thread that makes sense in the
last 90 days on those subreddits. Category by category." Nothing here has
been launched. Invoking this plan in a session IS the authorization to run
it, stage by stage, with a report at every stage gate.*

---

## 0. Context a fresh session needs

- Repo `~/Projects/reddit-index` (`Empact-Partners/reddit-index`, gh account
  `vsshvets`). Live site redditindex.com (noindex). Supabase project ref in
  `~/.claude/.reddit-index.json` (scoped db password; the org PAT never
  enters any container). DB access: `worker/db.py` (session pooler, IPv4).
- Gazetteer: **6,040 brands / 20,798 aliases** (fleet-expanded 2026-08-12),
  in `data/brands.csv` + `data/brand-aliases.csv` AND loaded in the DB.
- Scoring subs today: 607 slots / ~245 unique subs (`data/
  category-subreddits.csv`, `is_scoring`). **38 categories are under the
  5-sub floor, 6 at zero.** Median measured-but-rejected pool exists (3,270
  candidate rows with probe measurements).
- Scoring: methodology 2.0.0 (pooled-LOO prior K=10 + calibration gate in
  `worker/gate_calibration.py`). Daily loop: Railway cron 04:00 UTC fetch
  (`worker/daily.py`) + Mac launchd 03:30 classify/score/publish
  (`worker/daily_mac.sh`), classifier capped at 30k/night
  (`CLASSIFY_DAILY_CAP` — a safety cap on the UNSUPERVISED nightly job
  only, never a schedule; supervised burns run until the backlog is empty).
- A 90-day-scoped sweep engine can reuse `worker/sweep.py` (built, pilot-
  validated: listings + trees + per-sub disk state + resumability). It is
  currently ALL-TIME; Stage 3 retargets it.
- **No deadlines, no pacing (Vlad's explicit instruction).** Every stage
  runs continuously until it is DONE. Do not throttle a stage to fit a time
  budget, do not defer work to "later windows", do not estimate-and-stop.
  The only limits are the platforms' own standard ones.
- Hard rules: **zero external API credits** (all LLM = Codex fleet on the
  ChatGPT sub; Reddit = plain app-only OAuth) · **standard Reddit API
  limits** — honor the rate-limit headers (~100 QPM for app-only OAuth),
  never exceed them, and do not artificially sit far below them either ·
  fleet jobs go through the disk-idempotent pattern (out-files + journal,
  rounds recomputed from disk) · fleet job timeout for deep jobs =
  **1500s** (54/95 died at the 600s default once) · Management-API SQL
  retries 429/5xx (already in `worker/load.py::sql`) · classification
  batches of 25 on `gpt-5.6-luna`, enumeration/judgment on `gpt-5.6-terra`.

**Why the current sub list is thin (measured, not guessed):** the one-shot
discovery generated ~34 candidates/category from one angle, then a top-8
"worth" cap threw away eligible subs; of the rejected candidates in starved
categories, the two dominant failure buckets are **topicality < 0.5**
(candidates were generic, not the profession subs where those buyers
actually talk — r/restaurantowners for restaurant-pos, r/eventplanning for
event-management, r/msp for rmm) and **"hostile rules"** — a REGEX posture
that misreads "no self-promotion" as "no brand discussion". Both are fixed
at the root below.

---

## Stage 1 — Exhaustive candidate discovery (per category, four angles)

New script: `data/discover_v2.py` (resumable: per-category JSON state in
`data/.discover-v2/`; `--category slug` and `--stage` flags; every angle
cached to disk before the next runs).

Angle A — **fleet knowledge enumeration** (terra, 1 job/category, timeout
1500s): "List every subreddit where {category} software is discussed by the
people who buy, use, or administer it. Include: dedicated tool subs,
PROFESSION subs (the job that uses these tools), industry subs, workflow-
adjacent subs, and self-hosted/OSS alternatives subs. For each: name, type
tag (dedicated|profession|industry|adjacent), one line on why, and a
confidence." Ask for 30-80. The profession-sub instruction is the fix for
the starved-category failure mode.

Angle B — **evidence from Reddit search** (where discussions actually
happen): per category, search ~10 top brand names + ~5 category nouns
(`/search`, `restrict_sr=off`, sort=relevance and sort=new, t=year), tally
the subreddits of the returned threads. Subs discovered by evidence outrank
subs discovered by opinion. (~15 queries × 100 categories ≈ 1,500 requests.)

Angle C — **rescue re-audit of the existing 3,270 measured candidates**:
fleet posture judgment v2 (terra, batched): given the sub's ACTUAL rules
text (already cached from the first discovery run), answer "does this sub
allow members to discuss and recommend software brands?" allow | restricted
| forbid. Only **forbid** excludes. This replaces the regex that killed
~300 candidates for banning self-promotion.

Angle D — **one-hop sibling expansion**: for every accepted sub, parse its
`about.json` public description + sidebar for named sister subs; add as
candidates (tagged `sibling`).

Output: `data/.discover-v2/candidates.csv` — category_slug, subreddit,
angle(s), type tag, evidence count. Expected: 150-250 candidates/category
before qualification, ~6-12k unique subs total.

**Gate 1 (report to Vlad):** candidates per category (min/med/max), the 38
starved categories' candidate lists eyeballed, angle contribution split.

---

## Stage 2 — Qualification: the "makes sense" bars (NO top-N cap)

Same script, `--stage qualify`. Per unique candidate sub (cached per sub,
shared across categories):

| Bar | Test | Source |
|---|---|---|
| Exists & open | not banned/private/quarantined | `about.json` |
| Alive | ≥ ~2 posts/week on `/new` sample | 1 listing page |
| Not vendor-run | existing vendor-sub detector | `data/discover.py` logic |
| Rules posture v2 | fleet judgment on rules text; only **forbid** excludes | Angle C machinery |
| Topicality | fleet 1.0/0.5/0.0 per (category, sub) pair; keep ≥ 0.5 | `topicality_fleet.py` pattern, luna batched |
| Evidence floor | ≥ 1 brand/noun-bearing thread observed in the hot/new sample OR found via Angle B | probe instrument |

**Selection rule: EVERY sub that passes ALL bars becomes `is_scoring` for
that category.** No cap, no "worth" ranking — the ranking dies. Mega-subs
(r/smallbusiness, r/sysadmin) legitimately serve many categories at 0.5;
thread-level qualification (Stage 3) scopes what is actually taken from
them. Subscribers are NEVER a bar on their own (a 3k-member niche sub with
real brand talk is exactly what we want).

Writes: `data/category-subreddits.csv` v2 (all measured columns kept, new
`posture_v2`, `type_tag`, `angle` columns) → `worker/load.py`
`seed_category_subreddits()` (upsert, retry-safe) → Railway redeploy (the
daily fetch reads the CSV baked into the image).

Freeze the rule change: append methodology params `2.0.1` —
`scoring_subreddit_selection: all_qualifying` (was top-8-by-worth) with the
dated rationale, via `worker/freeze_methodology.py` (append-only).

Scale: ~6-12k unique subs to qualify; fleet ~100 terra enumeration jobs +
~600-1,000 judgment batches. Runs until done.

**Gate 2 (report):** final scoring-sub counts per category (expect 20-50
mainstream, 10-20 niche), the 38 starved categories' before/after, posture-
rescue count, and the per-category sub lists for Vlad to eyeball. **Vlad
approves before Stage 3 fetch starts** — this is the one human checkpoint,
because Stage 3 spends the entire fetch on this list.

---

## Stage 3 — Every qualifying thread, last 90 days, category by category

Retarget `worker/sweep.py` → `--days 90` mode (small diff, keep the
engine): per sub — `/new` paginated **until posts are older than 90 days**
(that alone fully covers any sub under ~11 posts/day, the vast majority);
for the ~top-30 busiest subs where `/new`'s 1,000-cap is younger than 90
days, add `/top t=month` + `/top t=year` (client-filtered to 90d) + per-noun
scoped search (sort=new, t=year, client-filtered) and document coverage as
approximate for those subs. Raise tree fetch `limit` 200 → 500 (one
request, deeper comment coverage).

Thread qualification: brand alias (6,040-brand automaton) or owning-
category noun in title/selftext · not removed/locked · `num_comments ≥ 2`
(a thread nobody answered holds no opinions; tunable constant, stated).

**Category-by-category cadence (the actual ask):** process in category
order (default: current mention volume descending — deepest boards first;
Vlad can reorder at launch). A sub shared by several categories is swept
once and credited to all. After each category's subs finish:
1. targeted classify burn for that category's unclassified mentions
   (fleet luna, the `classify_codex.py` machinery, supervised),
2. `worker/score_db.py` (calibration gate runs inside),
3. publish (deploy hook / empty-commit push).
So categories come online WHOLE, visibly deeper, one after another —
never everything half-done at once.

State/ops: per-sub disk state (existing), `--status` table extended to
per-CATEGORY progress (subs done / threads / mentions / classified /
scored). Run under `nohup caffeinate -is`, kill-safe any time. The daily
loop keeps running unchanged alongside (shared rate budget tolerated;
Reddit 429s just slow both).

Scale (scope, not schedule): listings over ~2-4k unique subs; trees for
every qualifying 90-day thread (est. 150-500k); classification of every
resulting mention (est. 0.5-1.5M ≈ 20-60k luna jobs). **It all runs at
standard API rates, continuously, until done — however long that is.**
Classification burns run supervised back-to-back until the backlog is
empty; the nightly cap only bounds the unattended 03:30 job. Cash: $0;
watch Supabase storage/egress (Pro $25/mo likely at ~1M+ rows).

### What ACTUALLY ran — the tree cap this plan does not name

The paragraph above says "every qualifying 90-day thread", and the 527-subreddit sweep that
built the shipped index **did not run that way**. It ran at **150 trees per subreddit**,
richest-first.

That number lives in `worker/collector.py:53` and on disk in
`worker/.cache/depth/mode.json` (`{"days": 90, "tree_cap": 150}`). Until 2026-08-24 it
appeared in **no markdown file in this repo**, while:

- `worker/sweep.py`'s `--tree-cap` default is **100000** — effectively uncapped
- `data/run_collection_all.py` passed **no cap at all**
- `worker/depth_run.py`'s default is `0` → `10 ** 9`

So every new-category sweep after the original build ran ~50x the per-subreddit work that
built the index, and nothing anywhere would tell you. On 2026-08-24 a 51-category sweep hit
this: r/SideProject alone queued 4,769 trees and r/AI_Agents 3,235, against 150 apiece under
the method that actually shipped. Projected 33 hours instead of ~12. See
`docs/post-mortem-2026-08-24.md`.

**Why a cap is not a quality cut.** `sweep.py:283-289` orders threads richest-first on a
measured yield curve — a 2-comment thread returns 1.2 mentions, a 10-24-comment thread 3.8, a
100+-comment thread 9.2. The cap therefore takes the *most valuable* threads, not an arbitrary
slice by post id, and `sub_complete` (`:373-390`) is cap-aware so a capped sub still reads as
finished. The tail is recoverable later by raising the cap and re-running: `swept` tracks post
ids, so a higher cap continues rather than redoing.

**Rule going forward (decisions/0014).** Every sweep invocation states its cap explicitly, and
the pinned mode file is the only source for it. `data/run_depth90.py` reads it and REFUSES to
run if the pin is missing, rather than inheriting 100000.

**Gate 3 (rolling report):** after each batch of ~10 categories, the
per-category table + spot-check links.

---

## Stage 4 — Steady state (already built, inherits everything)

The Railway daily fetch + Mac classify/score/publish loop picks up the new
sub list automatically (CSV in the image) and keeps every category current
from there. No new machinery.

---

## Failure modes already paid for (do not rediscover)

- Fleet: 600s default timeout kills deep jobs → **1500s**; fleet idle + no
  new out-files 180s → break round early and resubmit (both already in
  `data/enumerate_brands.py::run_fleet_phase` — reuse it).
- Management API SQL throttles at ~30 batches → `load.py::sql` retries
  429/5xx with backoff; ALWAYS verify DB counts after a bulk load.
- `next start` serves a stale replaced `.next` → fresh port per QA run.
- Mentions PK is `ON CONFLICT DO NOTHING` — refetch/reinsert is always
  safe; `ensure_partitions` before any insert (monthly partitions).
- The shell cwd resets between calls — absolute paths in drivers.
- A Codex out-file that fails to parse may be MID-WRITE — never "repair",
  re-poll.
- Never re-run `data/refine_local.py` over the shipped CSV (its keyword
  topicality would overwrite fleet judgments) — Stage 2 writes v2 columns
  additively.

## What this plan deliberately does NOT do

- No deltas/history on the site (standing rule: one truthful snapshot).
- No archive/census claim: 90-day coverage is complete for normal subs,
  approximate for the busiest ~30 (disclosed in methodology).
- No score-methodology changes beyond the frozen 2.0.1 selection-rule note.
- Nothing launches from THIS document's authoring session.

## Launch sequence (next session, in order)

```
1. python3 data/discover_v2.py --stage enumerate      # Angle A (fleet)
2. python3 data/discover_v2.py --stage evidence       # Angle B (search)
3. python3 data/discover_v2.py --stage rescue         # Angle C (posture v2)
4. python3 data/discover_v2.py --stage siblings       # Angle D
   -> GATE 1 report
5. python3 data/discover_v2.py --stage qualify        # Stage 2 bars
6. python3 worker/freeze_methodology.py               # params 2.0.1
7. python3 -c "import load; load.seed_category_subreddits()"  # + verify counts
8. git commit + push; railway up --detach
   -> GATE 2 report; VLAD APPROVES THE SUB LISTS
9. nohup caffeinate -is python3 worker/sweep.py --days 90 > /tmp/ri-sweep90.log &
   + per-category classify/score/publish as categories complete
   -> GATE 3 rolling reports
```

`discover_v2.py` and the `--days 90` sweep mode are the only new code; both
compose from machinery that already exists and is listed above by file.
