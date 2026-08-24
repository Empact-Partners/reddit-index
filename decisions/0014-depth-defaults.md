# 0014 — The sweep's depth defaults are pinned and documented

**Status:** Accepted · **Date:** 2026-08-24 · **Decided by:** Vlad Shvets
**Relates to:** `docs/depth-execution-plan.md` Stage 3, `docs/post-mortem-2026-08-24.md`

## Bottom line

The 90-day sweep runs at **150 trees per subreddit**, and that number is now stated in the
methodology instead of living only in a cache file. Every sweep invocation passes `--tree-cap`
explicitly, sourced from `worker/.cache/depth/mode.json`. A driver that cannot read that pin
**refuses to run** rather than inheriting `sweep.py`'s `100000` default.

## Context

`docs/depth-execution-plan.md:174-176` says Stage 3 fetches "trees for **every qualifying
90-day thread**". The sweep that actually built the shipped index did not do that. It ran
through `worker/collector.py`, which pins on disk:

```json
{ "days": 90, "tree_cap": 150 }
```

That 150 appeared in exactly two places — `worker/collector.py:53` and the cache file — and in
**no markdown anywhere in the repo**. `docs/worker.md` marks `collector.py` "superseded"
without ever stating the cap it enforced. Meanwhile the defaults everyone else inherits are:

| | default |
|---|---|
| `worker/sweep.py:486` | **100000** (effectively uncapped) |
| `worker/depth_run.py` | `0` → `10 ** 9` |
| `data/run_collection_all.py` | passes **no cap at all** |

So every new-category sweep after the original build ran roughly **50× the per-subreddit work**
that built the index, and the documentation would have told nobody. On 2026-08-24 a
51-category sweep queued 4,769 trees for r/SideProject and 3,235 for r/AI_Agents against 150
apiece under the shipped method — a 33-hour projection where ~12 was correct. Hours were spent
inside that before anyone compared the two runs.

## The decision

1. **150 is the depth default**, recorded in `docs/depth-execution-plan.md` under "What
   ACTUALLY ran", with the reasoning and the measured cost of not capping.
2. **The pinned file is the only source.** `data/run_depth90.py::pinned_mode()` reads
   `worker/.cache/depth/mode.json` and raises `SystemExit` if it is missing or malformed. It
   does not fall back, because a silent fallback to 100000 is the exact failure this prevents.
3. **Every driver passes the cap explicitly.** No sweep invocation relies on a default.
4. **The cap is revisable, not sacred.** Raising it and re-running is safe and additive:
   `swept` tracks post ids, so a higher cap continues from where the last one stopped rather
   than redoing. That is the sanctioned way to deepen the tail later.

## Why a cap is not a quality cut

`worker/sweep.py:283-289` orders threads **richest-first** on a measured yield curve: a
2-comment thread returns 1.2 mentions, a 10-24-comment thread 3.8, a 100+-comment thread 9.2.
A cap therefore takes the most valuable threads, never an arbitrary slice by post id. And
`sub_complete` (`:373-390`) is cap-aware, so a capped subreddit reads as finished instead of
blocking its category forever.

This is the same reasoning that already justifies `is_core` (`data/select_core_subs.py:12-16`):
bounding *fetch order* is not a methodology change, because `is_scoring` — which governs what
COUNTS — is untouched.

## Consequences

- `data/run_collection_fast.py` (the 30-day wave ladder built on 2026-08-24) is retired. It was
  never the documented method: wrong depth, wrong cadence, and 416 subreddit-passes against 285
  unique subreddits.
- `data/run_depth90.py` replaces it and implements Stage 3 as written — category by category,
  classify/score/publish after each, so categories come online whole.
- `SOP.md`'s "adding a category" recipe states the cap.
- A fixture asserts no sweep driver invokes `sweep.py` without `--tree-cap`.

## The general rule this establishes

**A production constant that lives only in a cache file is not documented.** If the value that
actually ran differs from the value the plan states, the plan is wrong and the next person will
trust it. Either the code matches the doc, or the doc records what the code really does.
