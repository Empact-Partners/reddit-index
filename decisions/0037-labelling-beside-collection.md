# 0037 — A daytime pass labels beside its collection

Date: 2026-10-15. Status: accepted (the commission: full speed). Changes the order of decision 0032's daytime pass;
its rule (the mentions already waiting take their share of the room first) stands.

## Context

Since six-hour checkpoints (decision 0036) a collected mention sends about half what it did, and the watchdog's day
(decision 0035) leaves the passes room from 07:00. The bound on collection is now Reddit: the first pass under both,
15 Oct 07:03 to 12:28, waited on Reddit for 16,801 of its 17,100 collection seconds, and the shared app's other users
took 67% of its calls.

A daytime pass still collected, then labelled. Of that pass's 325 minutes, collection had 285 and labelling the last
40, and in those 40 minutes nobody called Reddit for the index. Passes now run back to back from 07:00 to 23:15 (the
next one started at 12:30), so about an eighth of the day's Reddit time went unused.

Labelling needs GLM, Jev and the database, never Reddit.

## Decision

A daytime pass that asks for both collect and classify starts `worker/alongside.py` before collecting: a thread with
its own database connection that runs the classifier (`worker/classify_sweep.py run`) in rounds while collection runs.
A round labels what is in the queue; a round that found nothing waits two minutes for collection to add more. The
thread stops when collection ends, at the collection deadline, when the stop switch is off, when a round reports an
error (the pass's own classify stage then tries again), or when the pass's GLM credits, Jev dollars or items are used.

Collection then runs until 15 minutes before the pass ends (`reserve_minutes_after_collect_alongside`; 45 without the
thread), and the pass's own classify stage takes what is left with what the thread did not spend of the allowances.
If the thread has not ended when told, the classify stage does not run: two labellers never share the queue. The
receipt carries the thread's work as `label_alongside` (labelled, rejected, not checked, Jev, GLM, rounds, why it
ended). The night's run is unchanged.

The thread never uses the pass's own connection: collection holds a transaction open on it while it writes a
subreddit's rows, and a statement from another thread would land inside it. The egress cap and the line still see
everything: the run's estimate counts the cluster's log and the text the classifier reads, whichever thread read it.

## What it costs

One more database connection by day. GLM jobs at the same width (6 in flight) and the same allowances per pass.

## How it is judged

The next daytime passes against `a815baa0`: minutes of collection a pass (285 before), mentions a pass, labels a pass,
and what was left in the queue at the pass's end.

## Judged, 16 Oct (deployed to the day service 15 Oct 23:21 UTC)

The first pass, `16 Oct 06:33 to 11:48 UTC`, against `a815baa0` (15 Oct): collection ran 315 minutes (285 before: it
now runs until 15 minutes before the pass ends), 17,411 mentions from 3,685 subreddits on 10,545 Reddit calls, and the
thread labelled beside it in 263 rounds: **15,291 labelled, 2,071 rejected**, Jev $0.48, GLM 930 credits. GLM's share
waited out Z.ai's peak hours (06:00 to 10:00 UTC) with its tries and was labelled after; the classify stage at the
end found 49 mentions, labelled them in six seconds, and left the queue at 0. Mentions per call were lower than on
15 Oct (1.65 against 3.54) because the pass reached the quiet end of the rotation (3,685 subreddits against 2,048),
not because of labelling. The setting stays.

