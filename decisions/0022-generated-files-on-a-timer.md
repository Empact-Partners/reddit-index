# 0022 — The three generated files refresh on a timer

Date: 2026-10-09. Status: accepted (the commission: keep the index running and healthy).

## Context

`/freshness.json` (the footer date on every page), `/llms.txt` and `/sitemap.xml` are route handlers, built at deploy
time. The sweep expired them through `/api/revalidate` after every run, and the endpoint answered 200. They never
changed. Measured on 9 Oct, against the live site:

| Path | Expired, then fetched four times | What it served | What the database held |
|---|---|---|---|
| `/freshness.json` | HIT every time, age 16 h and growing | last run 8 Oct 04:20 | last run 9 Oct 04:31 |
| `/llms.txt` | HIT every time, age growing | 1,279,919 mentions, 6,280 companies | 1,200,406 mentions, 6,065 pages |
| `/sitemap.xml` | not expired in the test | 6,441 URLs | 6,065 company pages, plus categories |
| `/hubspot/` (control) | REVALIDATED, then HIT age 3 | | |
| `/` (control, built at deploy) | REVALIDATED, then HIT age 3 | | |

Pages regenerate on an expiry; route handlers do not. Next's own reference says it: for a route handler,
`revalidatePath` "invalidates cached data accessed within route handlers", not the handler's built response. The three
files therefore showed the state of the last code deploy (8 Oct 14:40), and before that of the one before.

## Decision

Each of the three carries a timer, the only timers on the site:

| File | Interval | What one refresh reads |
|---|---|---|
| `/freshness.json` | 300 s | one row of `site.meta` |
| `/llms.txt` | 3,600 s | the index rows, under 0.5 MB |
| `/sitemap.xml` | 3,600 s | the slug list |

A timer here is incremental static regeneration: the cached file is served to every request, and at most one refresh
runs per interval, whatever the traffic or the query string. The upper bound is under 20 MB a day for all three
together, against a 1.9 GB daily line. Every page keeps `revalidate = false` and changes only when the sweep names it.

- The bounded-reads gate names the three files and a floor for each; a timer anywhere else, a shorter one, or one of
  the three without its timer fails the build (self-test: 11 violations, all caught).
- The sweep no longer expires the three files (it had no effect). After a successful run it reads `/freshness.json`
  back for up to eight minutes and records a problem on the receipt if the site does not show the run's time.
- Unrelated, found on the way: the build-skip rule rebuilt the whole site for a change under `data/` (8 Oct 14:40,
  the alias blocklist). The site reads only `data/categories.csv`; every other file under `data/` no longer builds.

## What this replaces

Decision 0017's "data never triggers a build, and a page changes only when the sweep names it" still holds for pages.
The footer's "date of the last successful run" is now at most five minutes behind the run instead of one deploy behind.
