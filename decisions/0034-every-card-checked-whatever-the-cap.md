# 0034 — Every document on a page is checked, whatever the night's call cap

Date: 2026-10-14. Status: accepted (decision 0002's condition: every card the site shows is checked against Reddit
every day).

## Context

The takedown check asks Reddit about the documents on pages first, then the rest, in one list cut at the night's
call cap (`caps.takedown_calls`, 2,000 calls of 100 documents). Past 200,000 documents on pages, the cut fell inside
the pages' own documents: the last ones would have gone unchecked, with nothing on the receipt to say so.

Documents on pages: 118,678 on 13 Oct, 122,148 on 14 Oct. A company page shows up to 80 comments and 40 posts; with
the comment listing (decision 0029) bringing two to three times the mentions, more companies fill their cards, and
the count grows faster than it did.

## Decision

`worker/takedown.py`: the list is every document on a page, then the rest while the cap allows (`build_queue`). When
the pages alone need more calls than the cap, they are all made and nothing else is checked that night; the receipt
carries `on_pages`, `calls_planned` (the list's calls) and `calls_over_cap_for_pages`, and the log says it. The cap
bounds what comes after the pages: the documents shown nowhere, first checks and the slow lap (decision 0028).

With the calls no longer bounded, the time is: the check ends by the run's end less the reserve that collection
keeps for labelling, refresh and publish (`reserve_minutes_after_collect`, 105 minutes; 03:45 UTC on a night). And
the condition is now verified, not assumed: the receipt counts `on_pages_not_checked` (documents on a page Reddit was
not asked about, or whose batch failed), and any is a problem on the run, which the owner hears of.

## What it costs

Past the cap, about 22 KB sent and 1.5 seconds a call (14 Oct: 2,000 calls in 41 minutes, 43.6 MB on 13 Oct), taken
from the night's Reddit calls before collection. At 250,000 documents on pages: 500 calls more, about 12 minutes.

## Review

An independent read by GLM-5.3 (clean clone, read-only), four findings, all taken: a check cut short by its time or
by Reddit's failures still left the run "ok" (now `on_pages_not_checked`, a problem on the run); with the calls
unbounded the check could take the night's reserve (now bounded by it); `calls_planned` was the ceiling, not the list
(now the list's calls); and the guard was a string search (now a test that runs the stage against a fake database
and Reddit: past the cap, under it, a failed batch, out of time). A second read found two more, both taken: a call
that started just before the check's end could ride out a network outage for up to an hour past it (the wait is now
bounded by the check's end, and restored after it), and the run's part was still checked by searching its source
(now `takedown_deadline` and `takedown_problems`, tested).

A third read found one more, not taken here: a token refresh during a network outage keeps its own wait, so a call
started near the check's end can still run past it, by at most what was left of the check again (at most an hour,
inside the 105-minute reserve). It is the Reddit client's behaviour for every stage, not something this change made,
and a network outage that long stops the night whatever the takedown check does. Recorded as a known limit.
