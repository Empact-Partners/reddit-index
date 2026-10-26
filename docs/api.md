# The Reddit Index read API

For the Empact team: pull a brand's mentions (negative by default) from the index into a partner's repo.
Read-only. Decision 0040.

## Your key

Vlad or Claude mints it (`python3 ops/api_keys.py mint --name <you>`) and sends it to you once. Keep it in
1Password and in an environment variable (`REDDIT_INDEX_KEY`), never in a repo, a doc or a Slack message.
If it leaks, say so: it is revoked in a minute and you get a new one.

## Calls

Base URL: `https://redditindex.com/api/v1/`. Every call sends `Authorization: Bearer $REDDIT_INDEX_KEY`.

```bash
# the 100 most important negative mentions of Contabo
curl -s -H "Authorization: Bearer $REDDIT_INDEX_KEY" "https://redditindex.com/api/v1/threads/?brand=contabo"

# a brand's slug
curl -s -H "Authorization: Bearer $REDDIT_INDEX_KEY" "https://redditindex.com/api/v1/brands/?q=contabo"
```

### GET /api/v1/threads/

| Parameter | |
|---|---|
| `brand` | required, a slug from `/api/v1/brands/` |
| `sentiment` | `negative` (default), `neutral`, `positive`, `all` |
| `since` | a date, `2026-09-01`: only documents posted on or after it |
| `limit` | rows a page, 100 by default, 500 at most |
| `cursor` | the `next` value of the previous page; absent for the first |

Order: negative first, then the Reddit score (highest first), then newest. Each row:

```json
{
  "doc_id": "t3_1wmq17m",
  "brand": "contabo",
  "sentiment": "negative",
  "subreddit": "VPS",
  "thread_url": "https://www.reddit.com/r/VPS/comments/1wmq17m/contabo_deleted_my_live_server_and_gave_my_ip_to/",
  "thread_title": "Contabo deleted my live server and gave my IP to another customer. My domain now shows their site.",
  "doc_type": "post",
  "permalink": "https://www.reddit.com/r/VPS/comments/1wmq17m/contabo_deleted_my_live_server_and_gave_my_ip_to/",
  "excerpt": "Contabo deleted my live server and gave my IP to another customer. …",
  "reddit_score": 32,
  "posted_at": "2026-09-21T21:28:06+00:00"
}
```

`permalink` is the comment itself (or the post, when `doc_type` is `post`); `thread_url` is the thread it sits in.
`excerpt` is 280 characters of the document word for word, around the brand's name. `reddit_score` is the
document's score when the index collected it (the index stores no citation weight).

The page also carries `next` (pass it as `cursor` for the next page; `null` on the last), `scanned` and
`complete`. The index considers a brand's newest 20,000 mentions in the window; `complete: false` means there
are older ones, and `since` narrows the window to reach them. Every partner brand is far below that.

### GET /api/v1/brands/

`q` (optional): only brands whose slug or name contains it. Each brand: `slug`, `name`, `mentions`,
`negative` (the counts on its page; `null` when it has no page yet).

## Answers

| Status | When |
|---|---|
| 200 | the page |
| 400 | a parameter is wrong; `message` says which |
| 401 | the key is missing, unknown or revoked |
| 404 | no published brand has that slug |
| 429 | the key has made 300 calls today (UTC) |
| 503 | the database did not answer; try again in a minute |

## In Claude Code

> Pull the negative threads for contabo from the Reddit Index API (key in env REDDIT_INDEX_KEY) and write them to
> partner-contabo/reddit/negative-threads.md
