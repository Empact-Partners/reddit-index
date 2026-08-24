# 0013 — A bounded supervisor may carry one started run to its end

**Status:** Accepted · **Date:** 2026-08-22 · **Decided by:** Vlad Shvets
**Amends:** 0010 (manual on-demand updates), narrowly and temporarily.

## Bottom line

0010 says this repo has no schedulers, watchdogs or auto-resumers, and that stands. This
adds one exception with a hard shape: **a run a human already started may be supervised to
completion by a capped process that deletes itself when the run ends.** It may not start
work of its own, it may not run on a timer, and it cannot outlive the job it was installed
for.

## Context

The never-replied expansion is a multi-day sequence — discovery, a 90-day sweep, classify,
score, publish, then the outreach expansion and the wave-2 queues. On the night of
2026-08-22 the Mac went to sleep with the lid open and mains connected, and the run stopped.
The `caffeinate` holding it awake had been started from inside a tool call, and the harness
SIGTERMs that process tree when the call ends.

A multi-day job that dies silently at hour nine, in a repo whose rule is "a human runs it",
means a human has to sit with it. That is the thing being fixed, not the rule.

## The decision

1. **`caffeinate` is a launchd agent** (`com.vladshvets.caffeinate`, `KeepAlive`). It holds
   no project state and spends nothing; it keeps the machine awake and re-arms at login.
   This one is permanent and is not an exception to anything.
2. **`data/pipeline_supervisor.py`** may run under launchd for the duration of one started
   run. Its properties are the reason it is allowed, and each is asserted in
   `data/test_pipeline_supervisor.py` (24 checks) rather than described:
   - it starts nothing while any lane is alive — one Reddit client, one fleet lane
   - `MAX_ATTEMPTS = 6`, counted in `state.json` on disk, so a SIGKILL and a launchd revival
     do not hand it a fresh budget
   - it preflights free RAM and swap growth before every attempt
   - **it uninstalls its own launchd agent on every terminal path** — finished, or given up.
     The plist is deleted, so it cannot return at next login.
3. **It resumes; it never initiates.** There is no timer and no cadence. With no outstanding
   work it exits and removes itself.

## Why this is not what 0010 banned

0010 was written after `claude-rq` re-fired 153 dead sessions for $513 and zero completions,
its retry accounting refunding attempts on a mid-run re-cap so the loop was unbounded by
construction. The ban is on **unbounded automation that spends without a human**.

The distinction that matters is not "smaller" — the runaway was small per iteration too. It
is that this has an **end state it cannot escape**: a fixed budget on disk, and self-removal
when spent. A supervisor that deletes itself when the job is done cannot become a scheduler,
which is the failure mode 0010 exists to prevent.

## Consequences

- `SOP.md` documents both agents and how to check and remove them by hand.
- When this expansion completes, the pipeline agent will be gone. Confirm with
  `launchctl print gui/$UID/com.vladshvets.reddit-index-pipeline` returning nothing.
- Reinstalling it for a future long run is a deliberate act, the same as running
  `worker/update.sh`. It is not a standing lane, and nothing may add one without a new ruling.
- The caffeinate agent stays. If it ever needs to go:
  `launchctl bootout gui/$UID/com.vladshvets.caffeinate && rm ~/Library/LaunchAgents/com.vladshvets.caffeinate.plist`
