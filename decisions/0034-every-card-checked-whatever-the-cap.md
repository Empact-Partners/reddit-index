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
carries `on_pages`, `calls_planned` and `calls_over_cap_for_pages`, and the log says it. The cap bounds what comes
after the pages: the documents shown nowhere, first checks and the slow lap (decision 0028).

## What it costs

Past the cap, about 22 KB sent and 1.5 seconds a call (14 Oct: 2,000 calls in 41 minutes, 43.6 MB on 13 Oct), taken
from the night's Reddit calls before collection. At 250,000 documents on pages: 500 calls more, about 12 minutes.
