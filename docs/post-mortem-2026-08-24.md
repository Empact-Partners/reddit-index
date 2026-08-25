# Post-mortem — the 51-category expansion, 2026-08-22 → 24

**Status:** written 2026-08-24, during the run it describes.
**Scope:** the never-replied expansion (`decisions/0012`) — adding 51 categories and collecting
90-day depth for them.
**Outcome:** the work landed. It took roughly three times longer than it should have.

Every number here traces to a commit hash or a log timestamp in `data/.pipeline/pipeline.log`.
Nothing is softened, because the point of the document is that the next person does not repeat
any of it.

---

## The one that matters most

The same 20 subreddits, swept twice:

| | Trees | Mentions |
|---|---:|---:|
| With a gazetteer missing 989 brands | 3,263 | **8,544** |
| After the repair | 6,734 | **24,295** |

**Two thirds of the signal was being discarded, and every log line reported success.**

That is the shape of nearly every failure below: not a crash, but a stage completing normally
while producing wrong or missing data. A crash costs minutes. A silent success costs hours and
is only found by someone deciding to check a number that looked fine.

---

## The root cause of the whole episode

`docs/depth-execution-plan.md` already specified this work in full — Stage 3, `--days 90`,
category-by-category with classify/score/publish after each. **It was not read before work
started.** What got built instead was a 30-day wave ladder across all categories at once, over
8 core subreddits each.

Worse, the plan's own text ("trees for every qualifying 90-day thread") does not match what
actually shipped. The completed 527-subreddit sweep ran at **150 trees per subreddit**, pinned
in `worker/.cache/depth/mode.json` by `worker/collector.py:53` — a number that appeared in **no
markdown file in this repo**, while `sweep.py`'s default is `100000` and
`run_collection_all.py` passed no cap at all.

So a new-category sweep ran ~50× the per-subreddit work that built the index. r/SideProject
alone queued 4,769 trees against 150 under the shipped method. Projected 33 hours instead of
~12.

**Two lessons, and they are different:**
1. Read the spec in the repo before designing. It was there.
2. **A production constant that lives only in a cache file is not documented.** If the value
   that actually ran differs from the value the plan states, the plan is wrong and someone will
   trust it. Fixed in `depth-execution-plan.md` ("What ACTUALLY ran") and `decisions/0014`.

---

## Class A — a generator rebuilding a shared file it does not fully own

Three occurrences. Same shape every time: a script rebuilds a whole-file artifact from its own
inputs, silently deleting rows another path wrote.

### A1 · `is_core` column wipe — caught before firing

`discover_v2.stage_qualify` rewrote `category-subreddits.csv` with a hardcoded 29-column list
and `extrasaction="ignore"`, against a 30-column file. `is_core` was added later.

Would have zeroed **1,741 core slots** and collapsed collection for the shipped 100 categories.
No exception anywhere.

Found by writing the fixture, not by running. Fix `cb368bb`: union the hardcoded list with the
file's real columns and refuse to drop one. **Cost: 0.** Test: `data/test_csv_preservation.py`.

### A2 · `brand-seed-expand.csv` scoped rebuild — caught, hours from unattended execution

`enumerate_brands --expand --only <51 slugs>` rebuilds its seed CSV from the categories it was
asked about. Would have deleted the other 100 categories' rows — **6,132 of 7,194**.

The commit is blunt: *"This was live: run_finish_all.py calls exactly that command, and it was
due to run unattended tonight."* Fix `4d2cc9f`: `carry_forward_rows()` + `assert_no_shrink()`,
which deletes the temp file so a lossy one cannot be promoted. **Cost: 0.** Test:
`data/test_seed_csv_preservation.py`.

### A3 · `gen_brands` deleted 989 roster brands — THIS ONE FIRED

`gen_brands` rebuilds **both** `brands.csv` and `brand-aliases.csv` from the hand dicts plus its
seed files. `import_roster.py` writes roster brands **straight into `brands.csv`** — a path the
generator cannot see. The expansion merge deleted 989 of them.

`resolve.py` loads its gazetteer from those files. Collection then swept for **59 minutes**
discarding every mention of the never-replied companies the entire wave exists to find.

**The first fix was wrong and this is the part worth remembering.** It carried the brands
forward but not their **surface forms** — which live in the second file the same generator also
rebuilds. A brand restored without aliases sits in the gazetteer completely unmatchable, which
in the data is *indistinguishable from still being missing*. Caught only by testing the
resolver directly rather than counting rows.

Fix `9b5ed4b`: `OWNED_SOURCES`, both files carried together, refuses to write if either would
shrink **or** if any carried brand has no surface form. **Cost: ~3h15m.** Test:
`data/test_gazetteer_preservation.py` — which re-runs the real generator against a copy of live
data, because a mocked test would have passed on the broken fix.

---

## Class B — completion markers that outran the work

### B1 · The launchd interpreter had no `psycopg`

The plist ran `/usr/bin/python3` (3.9). `sys.executable` propagates to every child. Earlier
stages survived **only because they never touch the database**. The seed was the first DB stage
and died; sweep, classify, score and publish would all have failed identically.

Fix: plist repointed at `/opt/homebrew/bin/python3`. **Cost: ~25 min.**
**No regression test.** Nothing asserts the plist's interpreter can import what the pipeline
needs.

### B2 · `DISCOVERY COMPLETE` printed after the seed failed

Printed unconditionally. The supervisor **trusts that marker to skip discovery** — it would have
gone straight to collection and swept into a database with no subreddit rows, reporting success.

The log carries the retraction verbatim, which is the right way to handle a marker that lied:

```
DISCOVERY-COMPLETE-RETRACTED (seed failed: no psycopg under the launchd python) 10:10:11
DISCOVERY COMPLETE 10:35:22 (re-asserted after the seed genuinely succeeded)
```

Fix `33289b0`. **Cost: 0, caught.** **No regression test** on the producer withholding it.

---

## Class C — the supervisor's decision logic

Three wrong classifications, each found only after it misbehaved.

| | What | Consequence | Fix |
|---|---|---|---|
| C1 | A network drop spent the **runaway** budget | 4 more wifi blips would have made it give up and uninstall mid-run | `99935c8` — separate `MAX_NET_ATTEMPTS=40`, classify from the log **tail only** |
| C2 | A **preflight refusal** charged to the network budget | **3 budget units in 5 minutes with zero attempts started**, heading for permanent give-up in ~80 min | `8e2af25` — refusal is a third outcome, charges nothing, waits 900s |
| C3 | A `ModuleNotFoundError` charged to the network budget | Would have retried a **deterministic** crash 40 times | `33289b0` — a traceback outranks the network heuristic |

C2 and C3 have **no regression test**. The exact 08-24 input — a traceback *alongside* fresh
network lines — is not a fixture.

---

## Class D — observability that broke, twice, from one idea

The progress probe inferred position by sampling the lane's open files with `lsof`.

**D1** — memoising the cache readers (a good optimisation, same session) **removed the file
opens the probe depended on**. It went blind within minutes while reporting nothing wrong.

**D2** — sampling hard enough to catch a fast loop **starved the process**. One `lsof` pass
costs ~72 ms; 900 passes stole 65 seconds of CPU. The probe then reported *"cpu IDLE —
investigate now"* about a lane at 67% CPU. Fifteen minutes after sampling stopped it read
"burning" again.

**D3** — during a fleet stage the process is legitimately blocked at zero CPU for hours. The
probe called that a stall every 15 minutes. From the fix commit: *"An alarm that fires for eight
hours on a healthy run is worse than no alarm: it trains me to ignore it."*

Fix: explicit counters every 10,000 iterations; the probe reads those. The lsof code was
**deleted rather than tuned**. **No test file exists for the probe at all.**

**The rule:** a progress signal must be something the code *prints*. A probe that reads a side
effect breaks when the side effect is optimised away — and one that samples hard enough to see
a fast loop perturbs what it measures.

---

## Class E — resource guards that refused a healthy box

`fleet_preflight.py` gated on macOS swap **percentage**. macOS sizes the swap pool to demand, so
a busy-but-healthy box reads 90-95% indefinitely.

It refused a run for 20 minutes while free memory (2,623 MB) **exceeded** the need (2,220 MB),
swap was 20,478 MB against a 26,000 MB limit, and swap was **shrinking**.

**This file had already been recalibrated once for the same false positive two days earlier.**
Second occurrence. From the fix: *"A gate that refuses a healthy box gets worked around, which
is worse than no gate."*

Fix: the % backstop fires only when the absolute number also agrees. **Cost: ~40 min**, plus it
fed the C2 retry loop. **No regression test.**

---

## Class F — the expensive silent one

`qualify` was 52% done after 176 minutes, projecting **5.7 hours**. Profiling the live process
took ten seconds and showed `libcrypto`/`libssl`/`dnssd` dominating — it was **network-bound,
not CPU-bound**.

1,463 of 29,658 subreddits had no cached record, and `qual_rec` is **the one reader that returns
`None` without writing a cache file**. `qualify` walks ~9.5 pairs per subreddit, so every
unreachable one paid a full timeout plus 10-40s backoff **about nine times over** — ~13,900
fetch attempts where 1,463 would do.

Fix `be79836`: per-run negative cache. **Cost: ~3-4 h.** **No regression test.**

**The rule:** profile before theorising. Ten seconds of `sample <pid>` beat three hours of
assuming. And read the *unfiltered* histogram — grepping for what you already suspect confirms
your own wrong theory, which is exactly what happened first.

---

## Class G — operational self-harm

| | What | Cost |
|---|---|---:|
| G1 | `caffeinate` started from inside a tool call; the harness SIGTERMs that process tree. The Mac slept, lid open, on mains power | **~9 h** |
| G2 | The Reddit token call sat **outside** the retry loop whose job is waiting for the network. Killed a 5h19m run and a 14h run. Its own docstring claimed this fixed — the earlier fix hardened the retry and left the call site | 2 runs |
| G3 | Lanes spawned with `subprocess.call` share the supervisor's process group. Restarting the supervisor to load a code change **killed the lane** | ~93 min |
| G4 | A blanket `reconcile` cancelled **seven jobs belonging to another session** on the shared fleet | 7 jobs |

G1 fixed by a launchd agent with `KeepAlive` (`decisions/0013`). G2 by moving the call inside
the `try` — and `worker/test_reddit_client_resilience.py:44` asserts the **structural** property
so a refactor cannot move it back out. G3 by `start_new_session=True`; `SOP.md` now says *"Never
`launchctl kickstart` the supervisor while a lane is alive."* G4 by `reconcile(match=…)`.

**G3 has no regression test** — every supervisor fixture stubs `run()`, so the process-group
property that cost 72 minutes is never exercised.

---

## Class H — ordering and artifact correctness

- **Expansion after collection** would have scored the whole wave zero: a sweep resolves each
  tree against the gazetteer *as it stores it*, so brands seeded later never attach to
  already-swept threads. Caught by reasoning before firing (`81624e2`). Expansion now runs
  before collection and writes a marker collection refuses to start without.
- **`counts()` and `split()` looked up different sets** — CapCut, at 1,853 mentions, was filed
  as `zero_mentions`; NordVPN at 898. The artifact would have told someone those companies have
  no Reddit presence (`996a45c`).
- **The split bucketed on `>=5 mentions`** while the README documented `>=5 AND >=1
  opinionated`. The opinionated arm is the condition for a score existing at all (`52e6697`).
- **A commit message asserted something that had not happened** — "Expansion collection
  complete" from a rehearsal where collection had not run. Fixed in `0a57ca0`: *"State what the
  run did, not what it hoped happened. A git log is read later as a record."* This document is
  the proof of that.

---

## Class I — the evening of 2026-08-24, after this document was written

Three more, all of them existing classes recurring rather than anything new. That is the
useful part: the taxonomy held, and each was found by the discipline this document argues
for rather than by luck.

### I1 · The DeepSeek balance went negative mid-run — and would have spun until morning

Classification runs on the DeepSeek API by `decisions/0010`. At roughly 22:15 the balance was
**-$0.82, `is_available: false`**. The Max-plan Haiku fallback exists and is wired, but the
defaults were `--deepseek 16 --haiku 0`, so the next ship would have gone entirely to a lane
that could not bill.

What made it dangerous was not the outage. `worker()` catches the billing error, prints one
line, sleeps 3 seconds, and loops — forever, committing nothing, while every reporter line
still says the stage is working. **Class F, exactly: the expensive silent one.**

Defaults now fall back to the free Haiku lane, and a lane that fails `DEAD_MAX` times in a row
gives up and exits rather than spinning. `ship_batch` calls classify with `fatal=False`, so
score and publish still run and the category ships with the labels that exist.

**The first version of that guard was wrong in an instructive way.** It also required
`STATS[kind][0] == 0` — no items committed. That reads as the safer condition and is strictly
worse: the common shape is a quota dying PART WAY through a run, which leaves committed > 0
forever, so the give-up could never fire. Consecutive failures is the right measure, because
any success resets the counter. Found by testing the guard under a simulated dead lane instead
of trusting it. **Cost: 0, caught before the batch.** Test: proven both from a cold start and
after 500 prior commits.

### I2 · Fourteen and a half minutes of a live sweep writing nothing

The log went silent at 23:04. Both lanes reported alive; the sweep process sat at **0.0% CPU**.
It looked exactly like a hang, and this project has lost hours to real ones.

It was not a hang. `sample(1)` on the pid put it in `time_sleep`, and a direct header read
returned **429, remaining 0, used 1000**. `_read_ratelimit` sets the inter-call floor to
`reset/remaining`, which at zero remaining is the entire window — up to ~600s — and `get()`
then sleeps it in complete silence. It resumed on its own at 23:21, correct throughout.

The behaviour is right. The silence is **Class D**: this document already rules that progress
is a counter the code PRINTS, never a side effect inferred from outside. A deliberate
multi-minute wait needs the same treatment, or the next person spends fifteen minutes proving
nothing is broken. It now announces the wait once and the recovery once. **Cost: ~15 min of
diagnosis, 0 of collection.**

### I3 · A fixture that wrote the live pipeline's state file

While fixturing the wave-2 preflight, the first version wrote synthetic state into the LIVE
`depth90_done.json` — the file the running sweep reads and rewrites as it banks each
subreddit — and restored it afterwards.

It got away with it. "Restored it afterwards" is not a safety property: a subreddit banked
inside that window is simply lost, and the loss is invisible. This is **Class G, operational
self-harm**, and it was committed by the same session that had spent the evening telling six
subagents in writing never to do it.

`INDEX_ROOT` is now a constant the fixture overrides, so the test builds a sandbox index
instead, and one of its checks asserts the live state was never written. **Cost: 0. Verified
undamaged — 172 banked, valid, before and after.**

## Wall-clock loss, ranked

| # | Incident | Loss |
|---|---|---:|
| 1 | G1 · caffeinate SIGTERM'd, box slept | ~9 h |
| 2 | G2 · token call outside the try | 5h19m + a 14h run ended |
| 3 | F · `qual_rec` ~9.5× refetch | ~3-4 h |
| 4 | A3 · 989-brand wipe + half-fix + re-sweep | ~3h15m |
| 5 | G3 · lane killed with its supervisor | ~93 min |
| 6 | E + C2 · false swap refusals and the loop they fed | ~40 min |
| 7 | B1 · launchd python without psycopg | ~25 min |
| 8 | D2 · probe starving its own subject | ~30 min |
| — | A1, A2, B2, H1, K5 — **caught before firing** | **0** |

---

## The coverage ledger, measured

Counts below come from one command, run 2026-08-24:

    python3 data/run_all_fixtures.py --timeout 120 \
        ~/Projects/empact-partners/partner-development/scripts

Exit 0. **13 files, 420 checks evaluated, 0 failed, 2 not evaluated, ~6 s**, fully offline. The
runner self-tests first (18 checks) and refuses to run the suite if that fails; it distinguishes
TIMEOUT from FAIL from CRASH, kills a hung fixture's process group so it cannot outlive the
runner, and reports checks EVALUATED against declared so a partial run cannot read as a small
clean run.

**All 13 previously-unguarded classes now have a check that was broken on purpose and watched
fail.** Each was reverted in a tempdir copy and the named fixture went red for the incident's own
reason — not merely exited non-zero:

| Class | Fixture |
|---|---|
| preflight-refusal outcome | `test_supervisor_decisions` + `test_resource_guards` |
| traceback-outranks-network | `test_supervisor_decisions` (7 checks fail on revert) |
| `DISCOVERY COMPLETE` producer | `test_progress_reporting` |
| the launchd interpreter | `test_out_of_repo_contract` (actually imports psycopg under the plist's interpreter) |
| `qual_rec` single-attempt | `test_refetch_cache` (the ~9.5x refetch, reproduced) |
| the swap guard | `test_resource_guards`, both directions |
| the progress probe | `test_progress_reporting` (lsof regression + a STALL that stops naming its position) |
| `start_new_session` | `test_supervisor_decisions` (asserts the value, not the key) |
| the expansion gate | `test_stage_order_and_cap` (observed argv, before the first Postgres call) |
| `counts()`/`split()` divergence | `test_wave_split_invariants` |
| the split criterion | `test_wave_split_invariants` |
| `reconcile(match=…)` scoping | `test_wave_split_invariants` |
| lane detection vs its own pgrep | `test_supervisor_decisions`, coverage and wiring halves independently |

**It took four rounds, and the reason is the finding that matters most.** Each round's audit
found checks that could not fail for the reason they advertised:

- Round 2 found two provably vacuous checks that a verifier had already passed.
- Round 3 found the **oldest fixture in the project confidently wrong**. `test_csv_preservation`
  named class A1, its docstring claimed it proved the writer refuses to lose a column, and
  reverting `discover_v2.py:1090` to the exact `is_core`-wipe code left it printing `6/6 passed`.
  It re-implemented the column union in its own body and never called the writer under test.
  **A1 had been counted as covered for three days on the strength of it.**
- Round 4 found eight more. `test_import_roster` printed `26/26` against a `merge()` gutted of its
  ambiguity rule, G5, the reserved-slug pre-check and the G1 dedupe. Two checks in
  `test_seed_csv_preservation` asserted a bare digit that came from the **tempdir path**, not the
  guard's message — one of them flaky-green about 1 run in 6. And a try-block check anchored by
  `str.index` to the FIRST eight-space `try` — the cache read, 1,574 characters before the network
  try it meant — so reverting G2, the token call that ended a 14-hour run, left it green.

**One known open defect, declared rather than hidden.** `gate()` at
`data/pipeline_supervisor.py:223-235` catches `except Exception` around the out-of-repo preflight
import and **returns True**: a rename, a signature drift or a missing file starts a wave with no
RAM or swap check at all, while `test_resource_guards` spends 44 checks certifying a guard that
can vanish. Two `xfail` rows in `test_out_of_repo_contract` pin the current behaviour and print
the consequence on every run; the runner counts them as "2 not evaluated", never as passes.
Deferred only because the supervisor is mid-run — it is a one-line change once the sweep ends.

**Still thin, honestly.** Coverage is measured, not complete: a majority of the 420 checks have
been observed failing under mutation, but not all of them. `reserved_slugs()`'s call site, the
`looked_like_*` tail windows and the runner's own "self-test failed, suite NOT run" branch are
each guarded more weakly than the green line suggests.

**The pattern the first draft of this ledger named is closed.** The supervisor's decision logic
(69 checks), stage ordering (50), the resource guards (44) and the observability layer (26) — the
four areas where the most wall-clock was lost, and which previously had nothing — are now the four
largest fixtures in the suite.

**And the rule that came out of all four rounds:** a check that cannot fail is worse than no
check, because it advertises a guard that is not there. Break it on purpose, or do not believe it.

---

## What to do differently

1. **Read the spec in the repo first.** `docs/depth-execution-plan.md` existed the whole time.
2. **A constant that only lives in a cache file is undocumented.** If what ran differs from what
   the plan says, fix the plan.
3. **Before rebuilding any shared file, ask what else writes to it.** `grep -l '<file>' **/*.py`
   answers it in seconds. Three occurrences say this check is not optional.
4. **Restore every file in a set, and assert the link between them.** A half-restore passes a
   row count and still breaks resolution.
5. **Profile before theorising**, and read the unfiltered histogram.
6. **A progress signal must be printed by the code**, never inferred from a side effect.
7. **A guard that refuses a healthy system gets ignored** — which is worse than no guard.
8. **Suspect the lookup table before the collector** when a stage succeeds with too little data.
