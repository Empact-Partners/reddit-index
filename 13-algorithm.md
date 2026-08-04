# The Algorithm

How Reddit Index gets from "a category" to "a ranked board", concretely enough to build from.

**Last verified: 2026-08-04** · endpoint behaviour measured live against the Reddit API

## Bottom line

- **The comment stream is the unlock.** `/r/{sub}/comments` returns the newest 100 comments in a subreddit regardless of which thread they sit in, with `link_title` attached. It is the only API surface that finds brand opinion in threads whose titles name no brand — which is most of them.
- **Archives are the census, the API is the edge.** Historical coverage comes from per-subreddit dumps. The API maintains the last few days. Search is never a census.
- **Cap each category at 8 scoring subreddits**, chosen by measured yield per call, not by subscriber count. Vendor-owned subs are evidence only and never touch a score.
- **Everything expensive runs last.** Local alias matching is nearly free and cuts the corpus by orders of magnitude before entity resolution or any LLM sees a single comment.
- Roughly **1,200 API calls per category per weekly cycle**, ~60,000 for 50 categories, ~12.5 hours of wall clock at a safe request rate.

---

## 1. Why the obvious approach fails

The instinct is: search Reddit for each brand, read what comes back, score it.

Three measured facts kill it. Reddit search **does not index comment bodies**. Every listing **hard-caps at ~1,000 items**. And global search returns noise — a 68-query sweep in prior Empact work returned relationship drama and r/pokemon, with 57 of 73 mined shards empty.

The deeper problem is where opinion actually lives. Consider this real comment, pulled live on 2026-08-04:

> *"I've been impressed with proton pass so far"* — r/PasswordManagers, on a thread titled **"Looking for a new free Password Manager"**

The thread title names no brand. Brand-name search cannot reach that comment, and it is a perfect, rankable brand opinion. Most of the corpus looks like this.

So the algorithm is built around comments, not around brand-titled threads.

---

## 2. Subreddit selection

### Candidate pool

Built by hand per category, because subreddit discovery is broken under app-only OAuth (`search_reddit` with `type='sr'` returns zero results). Four strata:

1. The practitioner subreddit for the buyer's job function
2. General software and business subreddits already verified in [04-subreddit-mapping.md](04-subreddit-mapping.md)
3. Adjacent workflow subreddits where a buyer would ask for a recommendation
4. One subreddit per known brand — **evidence corpus only, never scored**

Resolve every candidate with `/r/{sub}/about` and `/r/{sub}/about/rules`. **Never infer a subreddit from a product name.** r/figma is a Japanese action-figure community; the design tool lives in r/FigmaDesign.

### Hard exclusions

| Excluded | Why |
|---|---|
| Wrong topic, private, or inaccessible | Unusable |
| `rule_posture = prohibitive` | The sub deletes the content we came for |
| Vendor-owned / single-product subs | Self-select for invested users. Kept as evidence, never scored |
| Categories with fewer than 5 independent scoring subs | [07-index-methodology.md](07-index-methodology.md) requires each ranked brand to appear across ≥5 subreddits. Below that, the category ships as *insufficient Reddit signal to rank* |

### Bootstrap score, before any census exists

```text
R = 1.0 permissive · 0.5 capped · 0 prohibitive
T = 1.0 exact practitioner/category fit · 0.5 adjacent · 0 wrong   (human-coded)
V = min(1, surviving_posts_per_day / 5)
H = min(1, exact_post_hits / 25)
  * min(1, brand_bearing_comments / 50)
  * min(1, distinct_hit_threads / 3)
F = 1 if the best hit is under 3 years old, else 0

bootstrap_signal = 100 * R * T * F * sqrt(V * H)
```

Rules can veto a huge subreddit; volume cannot rescue an off-topic one. Every stemmed search hit must pass an exact alias check locally before it counts toward `H` — Reddit search stem-matches, and "Descript" in r/VideoEditing returned results that merely contained the word "description".

Take the best practitioner sub and the best general sub, then add greedily to a cap of **8 scoring subreddits**. A category needing dozens of weak subs to manufacture data does not have signal; it has noise.

### Steady-state score, after the first census

Replace the search proxy with measured marginal value:

```text
delta_b(s)  = max(0, n_eff_b(all selected) − n_eff_b(without s))
worth(s)    = R * T * Σ_b delta_b(s) / ingest_calls(s)
```

Subscriber count never enters the score. r/PasswordManagers (54,639) outperforms r/marketing (1,958,653) because r/marketing's rules delete exactly this content.

---

## 3. Discovery — the core of the design

Three lanes with strictly different jobs. **Only lane A is a census.**

### Lane A — historical census (archives)

Per-subreddit Arctic Shift / Academic Torrents dumps, both submissions **and comments**, over a trailing window. Join each `t1` comment to its `t3` submission via `link_id`.

This is the only route to history. The API reaches roughly 3-8 days. See [02-data-acquisition.md](02-data-acquisition.md).

### Lane B — the live edge (the comment stream)

```
GET /r/{sub}/comments?limit=100&raw_json=1[&before=<watermark>]
```

Returns the newest 100 `t1` comments in the subreddit, **irrespective of thread**, each carrying `link_id`, `link_title`, `author`, `score`, `created_utc` and the full `body`. One call yields 100 comment-level observations with no thread traversal at all.

**Measured coverage per 100-comment page, 2026-08-04:**

| Subreddit | Span of one page | Implied rate | Poll interval |
|---|---|---:|---|
| r/SaaS | 1.2h | ~83/h | 4h |
| r/CRM | 19.8h | ~5/h | 24h |
| r/PasswordManagers | 71.7h | ~1.4/h | 24h |

Adaptive cadence, so the 1,000-item cap is never the binding constraint:

```python
# target: never let more than ~500 comments accumulate between polls
# (half the 1000-item listing cap, as headroom for bursts)
rate = comments_per_hour_observed(sub)          # rolling 7-day median
interval_h = clamp(500 / max(rate, 1), 1, 24)
```

Store a `before` watermark per subreddit — the fullname of the newest comment seen. Page backwards until the watermark is reached. If a poll ever returns a full page without hitting the watermark, the cadence was too slow: halve the interval and flag the gap for archive reconciliation.

### Lane C — boosters (never a census)

Run only to raise recall on known gaps and to test coverage:

- **Scoped cross-product search.** `/r/{sub}/search?restrict_sr=1&t=all&raw_json=1`, over general-sub × category-noun and domain-sub × intent-verb ("switching from", "alternative to", "vs", "recommend"). Run both `sort=relevance` and `sort=top` — they return materially different sets.
- **Comment-tree expansion** on qualifying threads that Lane B surfaced only partially.
- **Recurring-thread registry.** Many subs run periodic "what do you use?" megathreads. Register them by id and re-poll their trees directly; they are the densest single source in most categories.

**Cut, deliberately:** global search, general-sub `top` sweeps, API-only historical backfill, arbitrary timestamp-slicing, default `morechildren` expansion, author-profile crawls, embeddings and vector search.

### Deduplication

Every observation keys on its **Reddit fullname** (`t1_xxxx` for comments, `t3_xxxx` for posts). A comment arriving via archive, comment stream and tree expansion is one row. The scoring unit is **one comment × brand × category**, counted once, so a comment naming a brand three times contributes one observation.

---

## 4. Thread qualification

Post listings are cheap; comment trees are expensive. Only fetch a tree when the thread earns it:

| Rule | Threshold |
|---|---|
| Not archived | Reddit locks comments after ~6 months on many subs |
| Comment count | ≥ 3 |
| Substance | Skip short `selftext` unless comment count is high. A one-line post with 40 comments is a good discussion; one with 3 is noise |
| Brand-bearing | At least one alias candidate in the title, body, or any Lane B comment already seen from that thread |

Lane B changes the economics here: a thread proves itself brand-bearing through its own comments before we ever pay for its tree.

---

## 5. Comment harvesting

```
GET /comments/{id}?depth=6&limit=200&raw_json=1&sort=top
```

`/comments/{id}` returns a two-element array: `[post_listing, comment_listing]`. Replies nest under `data.replies`, which is `""` (an empty string) when absent, not `{}`. Flatten recursively; `kind` is `t1` for comments, `t3` for posts, `more` for a truncated branch.

- **Depth 6.** Below that, threads are mostly reply-chains between two users, and the brand-opinion density collapses.
- **`more` branches are not expanded by default.** They are recorded as a coverage gap and resolved at the next archive reconciliation, which is cheaper and more complete than `/api/morechildren`.
- Drop `[deleted]` and `[removed]` bodies at parse time.
- **Copy the permalink from the response.** Never construct it from a title slug — reconstructed URLs silently point at the wrong thread.

Stored per comment: `fullname`, `link_id`, `link_title`, `subreddit`, `author`, `score`, `created_utc`, `depth`, `permalink`, `body`, `retrieved_at`.

---

## 6. Brand mention detection

The cheap local stage that protects everything expensive downstream. It generates *candidates*; [05-entity-resolution.md](05-entity-resolution.md) decides.

1. **Strip before matching:** fenced code blocks, inline code, and `>` quote blocks. A quoted complaint is the quoted author's opinion, not the commenter's.
2. **Normalise:** casefold, NFKC, collapse whitespace, strip possessives (`Notion's` → `Notion`), keep the original offsets for the disambiguator.
3. **Aho-Corasick** over the full alias table — one pass, all aliases, linear in the comment length. At ~10⁸ comments this is the only affordable matcher.
4. **Word-boundary enforcement.** `stripe` inside `pinstripe` is not a match.
5. **Domain signals are strong evidence.** A comment containing `notion.so` or `monday.com` resolves that mention almost regardless of surrounding text. Match URLs before prose.
6. **Emit the candidate** with its offsets, the matched surface form, and the features the disambiguator needs: subreddit, thread title, co-occurring candidates, and the surrounding window.

**Nothing that produces zero candidates ever reaches an LLM.** That single rule is what makes the cost model work.

---

## 7. The weekly loop

```
1. refresh_subreddit_meta      rules + about, detect rule drift        (~1 call/sub)
2. poll_comment_streams        Lane B, adaptive cadence                 (bulk of calls)
3. poll_new                    /r/{sub}/new for post metadata + titles
4. qualify_threads             apply §4
5. fetch_trees                 qualifying threads only
6. boosters                    scoped search + recurring threads
7. reconcile_archive           monthly, fills `more` gaps and deletions
8. detect_mentions             Aho-Corasick (local, no API)
9. resolve_entities            05
10. classify_sentiment         06
11. compute_index              07 — n_eff, diversity floors, bootstrap CIs
12. publish                    rebuild the static site
13. delete_sync                nightly, independent of the above
```

**Resumability is a hard requirement.** Every stage checkpoints to disk atomically: write to `path.tmp`, then `os.replace()`. One file per thread keyed by post id; a re-run skips ids already present. A job that dies at hour 9 resumes at hour 9.

**Rate discipline:** ~100 req/min budget, run at ≤80. `time.sleep(0.75)` between calls. Back off on 429/500/502/503; re-fetch the token once on 401.

---

## 8. Cost and time

Per category per weekly cycle, 8 subreddits:

| Stage | Calls | Basis |
|---|---:|---|
| Subreddit meta | 16 | 2 × 8 subs |
| Comment streams | ~700 | adaptive cadence across mixed-rate subs |
| `/new` polling | ~120 | daily × 8 subs, paged |
| Comment trees | ~300 | qualifying threads only |
| Boosters | ~65 | scoped search, both sorts |
| **Total** | **~1,200** | |

**50 categories ≈ 60,000 calls.** At 80 req/min that is **~12.5 hours** of wall clock, trivially parallelised across subreddits and interruptible at any point.

Subreddits overlap between categories (r/sysadmin serves several), so the real figure is lower — dedupe the ingest set before scheduling.

Archive backfill is a separate one-time cost, dominated by download and local scan rather than API calls. **Not yet measured** — its byte count and the machine's scan rate both need benchmarking before anyone quotes a duration.

LLM spend is governed by [06-sentiment.md](06-sentiment.md): only candidate-bearing comments reach the cascade, at roughly $45-85 per million comments classified.

---

## 9. Failure modes

| Failure | Detection | Response |
|---|---|---|
| Live feed outruns the cap | A poll returns a full page without hitting the watermark | Halve the interval; flag the window for archive reconciliation |
| Subreddit rules change | Rule-text hash differs from last cycle | Re-evaluate `rule_posture`; a sub turning prohibitive leaves the scoring corpus |
| Archive month missing or corrupt | Manifest gap or unparseable records | Mark the window as a declared coverage hole; never silently interpolate |
| Common-word brand fails precision | Audit precision below the published bound | Withhold that brand rather than publish it |
| Astroturf or Empact-influenced threads | Bot filter and the partner-thread register in [06-sentiment.md](06-sentiment.md) | Exclude before sentiment, not after |
| Thin or concentrated evidence | `n_eff < 400` or a diversity floor fails | Brand does not publish. This is correct behaviour, not a bug |
| Category never reaches 5 subs | Selection stage | Ships as *insufficient Reddit signal to rank* |

---

## 10. What this cannot reach

Stated plainly, because a coverage claim without its holes is a marketing claim.

- Comment bodies in subreddits we did not map
- Content deleted before any snapshot captured it
- Comments behind `more` placeholders until the next archive reconciliation
- Subreddits or months absent from archive splits
- Ambiguous common-word mentions rejected to hold the precision bar — a deliberate recall sacrifice, quantified in [05-entity-resolution.md](05-entity-resolution.md)

---

[← Back to README](README.md) · [Data acquisition](02-data-acquisition.md) · [Entity resolution](05-entity-resolution.md) · [Index methodology](07-index-methodology.md) · [Architecture](08-architecture.md)
