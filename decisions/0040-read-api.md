# 0040 — A read API for the team: /api/v1/threads and /api/v1/brands

Date: 2026-10-26. Status: accepted. Decided by Vlad Shvets (Reddit weekly jam, 5 Oct 2026: "an API for the Reddit
Index and the API key" for Heather, so the team can pull a partner's negative threads into GitHub; to-do
`td_nrmgd7jcf6`), built by Claude. Migration 0039.

## Context

Until now redditindex.com served pages and three generated files, and nothing a script could ask a question of.
The team reads a partner's negative mentions off the company page by eye and copies them into the partner's repo
by hand. Everything they need is already in the database: every mention, its thread, its subreddit and its newest
sentiment label.

Two things the index cannot give up decided the shape:

- **The site's role reads schema `site` and nothing else** (0007, `lib/data/site-db.ts`, the bounded-reads gate).
  That is why one bad query can no longer bill the corpus (docs/investigation-2026-10.md). An API that asks for
  mentions must not loosen it.
- **The 2 GB daily egress line** (README "Cost", 0035), shared by every job.

## What exists now

| | |
|---|---|
| `GET /api/v1/threads/` | `brand` (slug, required), `sentiment` (`negative` default, `neutral`, `positive`, `all`), `since` (a date), `limit` (100 default, 500 at most), `cursor` (the previous page's `next`). Rows: `doc_id`, `brand`, `sentiment`, `subreddit`, `thread_url`, `thread_title`, `doc_type` (`comment` or `post`), `permalink`, `excerpt`, `reddit_score`, `posted_at`. Negative first, then Reddit score, then newest |
| `GET /api/v1/brands/` | `q` (optional text): every published brand's `slug`, `name`, `mentions`, `negative` (the site's own counts; null with no page) |
| Auth | `Authorization: Bearer <key>`. 401 for a missing, unknown or revoked key, 429 past 300 calls a key a UTC day, 404 for an unknown brand, 400 for a bad parameter |
| `api.api_keys` | id, name, sha256 of the key, created, last used, revoked, calls today. The key itself is never stored |
| `ops/api_keys.py` | `mint --name`, `list`, `revoke <id>`. `mint` prints the key once |
| `ri_api` | the API's own database role: EXECUTE on `api.threads` and `api.brands` only, 15 s statement timeout. `ops/api_role.py` gives it a login and sets `DATABASE_URL_API` on Vercel; `--check` proves it can reach nothing else |
| `lib/data/api-db.ts` | the API's only connection. The bounded-reads gate (rule 8) fails the build if it names a table, calls anything but the two functions, uses another role's connection string, or is imported by anything but `app/api/v1/` |

## How it was decided

- **A second role, not a wider `ri_site`.** The pages keep exactly the role they had. `ri_api` can call two
  functions, and both check the key's hash before they read anything, so the role's password alone reads nothing:
  a caller also needs a key, whose hash only the functions can see.
- **The work happens in Postgres, and one JSON value leaves it.** The excerpt (280 characters, word for word, opening
  up to 80 characters before the brand's name, whitespace runs collapsed, `…` where it is cut) is cut inside the
  function, so a comment's body never crosses the wire. A 500-row page measured 346 KB; a typical partner pull is a
  few KB. The worst a key can send in a day is 300 full pages, about 0.1 GB, 5% of the line.
- **Bounded work.** The candidates are the brand's newest 20,000 mentions in the window (every partner brand has
  fewer than 1,100; Contabo answers in about a second). For the three largest brands (reddit, youtube, github) a
  full label pass takes 39 s or more, so the page says `complete: false` and the caller narrows `since`. GitHub at
  the cap: 6 s.
- **"Citation weight" is not stored** in the index. The weight it has is the document's Reddit score at collection,
  returned as `reddit_score` and used for the order.
- **The sentiment is the newest label per mention**, the rule `published.mentions` and `site.rail_card` use (0003).
  A document the site would not show is not returned either: a deleted author, a document in `public.removals`.
- **Keyset pagination.** The cursor is the last row's four sort values, base64url JSON; the route rejects any
  cursor it could not have given out before the database is asked.
- **Never cached** (`Cache-Control: no-store`), and covered by the site's `X-Robots-Tag: noindex` like every path.
- **Trailing slash.** The site is `trailingSlash: true`, so `/api/v1/threads` answers 308 to `/api/v1/threads/`;
  curl `-L` and every HTTP client keep the header on a same-host redirect, but the documented URLs carry the slash.

## Operating it

```bash
python3 ops/api_keys.py mint --name heather     # prints the key once; keep it in 1Password
python3 ops/api_keys.py list
python3 ops/api_keys.py revoke kid_xxxxxxxx      # refused from the next call
python3 ops/api_role.py --check                  # what ri_api can and cannot reach
```

A leaked key is revoked, not rotated: revoke it and mint a new one. The caller's guide is `docs/api.md`.
