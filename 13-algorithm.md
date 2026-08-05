# The Algorithm

How Reddit Index gets from "a category" to "a ranked board", concretely enough to build from.

**Last verified: 2026-08-05** · endpoint behaviour and subreddit measurements taken live against the Reddit API

## Bottom line

- **The comment stream is the unlock.** `/r/{sub}/comments` returns the newest 100 comments in a subreddit regardless of which thread they sit in, with `link_title` attached. It is the only API surface that finds brand opinion in threads whose titles name no brand — which is most of them.
- **Archives are the census, the API is the edge.** Historical coverage comes from per-subreddit dumps. The API maintains the last few days. Search is never a census.
- **Only generalist subreddits score.** Any vendor-named or vendor-dedicated sub is evidence, never a score. Vendor subs carry 50% of measured brand-bearing volume and hostile subs a further 17%, so 32% is retained — paid deliberately, for cross-brand comparability. **125 of 232** measured subs qualify; **all 20** categories clear the 5-subreddit floor ([14-category-tests.md](14-category-tests.md)). Cap each category at 8, chosen by measured yield per call, never by subscriber count.
- **Everything expensive runs last.** Local alias matching is nearly free and cuts the corpus by orders of magnitude before entity resolution or any LLM sees a single comment.
- **Four discovery lanes, not one.** Archives are the census; the multireddit comment stream is the live edge; an external search index reaches comment text Reddit's own API cannot search; Reddit-native search and tree expansion fill the gaps.
- **Continuous ingest, daily publish.** The site is never more than 24 hours stale. Roughly **180 API calls per category per day**, ~9,000/day for 50 categories, under 2 hours of wall clock.

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

**Only generalist subreddits may score a brand.** Any subreddit named for, or dedicated to, a single vendor or product is excluded from scoring outright — r/salesforce, r/shopify and r/aws exactly as much as r/1Password.

The reason is **cross-brand comparability**. A brand with a large active home subreddit would out-score a competitor with a small one or none at all, so rank would partly measure community size — the same confound the index already rejects for raw mention counts. Sentiment was never measured in this study, so no claim about skew in vendor subs is made in either direction.

Vendor subs stay in the corpus as **evidence**: quotable on a brand's own page, and usable for that brand's trajectory against its own baseline, where nothing is compared across brands. They never enter a ranking.

**The cost is real and deliberate.** Generalist-only retains **9% of measured brand-bearing volume** — 4.82 of 54.89 brand-bearing comments per hour across the 156 measured subreddits. Vendor subs alone carry 41.98 of that rate. The excluded data is the densest measured, not the weakest.

### Candidate pool

Built by hand per category, because subreddit discovery is broken under app-only OAuth (`search_reddit` with `type='sr'` returns zero results). Four strata:

1. The practitioner subreddit for the buyer's job function
2. General software and business subreddits already verified in [04-subreddit-mapping.md](04-subreddit-mapping.md)
3. Adjacent workflow subreddits where a buyer would ask for a recommendation
4. One subreddit per known brand — **evidence corpus only, never scored**

Resolve every candidate with `/r/{sub}/about` and `/r/{sub}/about/rules`. **Never infer a subreddit from a product name.** r/figma is a Japanese action-figure community; the design tool lives in r/FigmaDesign.

### Widening the candidate list — required before any category is judged

Widening the lists changed the study's headline. **All 20 categories now clear the 5-subreddit floor**, against 4 under the narrowest lists this probe replaced (those superseded lists are not in the shipped data). The binding constraint was never Reddit's opinion volume, and never the exclusion rule. It was the candidate lists.

Measured in the shipped data: the widening probe added **24 subreddits, 18 of them scorable**. CRM alone gained **10 candidates, all 10 scorable**, taking it from 6 scoring subs to **16** — emphatically the Phase 0 subject, at 0.85 brand-bearing comments/hour live.

**Small focused practitioner subs beat large ones.** Subscriber count predicts nothing:

| Small, focused | Subs | Brand-bearing | Large, general | Subs | Brand-bearing |
|---|---:|---:|---|---:|---:|
| r/revops | 6,593 | 5% | r/startups | 2,107,067 | 0% |
| r/SalesOperations | 18,487 | 6% | r/Entrepreneur | 5,249,043 | 0% |
| r/PasswordManagers | 54,640 | **42%** | r/marketing | 1,958,693 | 0% |

r/PasswordManagers is the highest brand-bearing share of any scoring subreddit measured, on 1/36th of r/marketing's subscriber count. So a category is not thin until its list has been widened once. Probe a widened list of generalist practitioner subs **before** concluding a category lacks signal.

### Hard exclusions

| Excluded | Count | Why |
|---|---:|---|
| Wrong topic, private, or inaccessible | 1 of 156 | Unusable |
| `rule_posture = hostile` | 54 of 156 | The sub deletes the content we came for |
| **Vendor-named or vendor-dedicated subs** | 56 of 156 | Excluded from scoring, full stop, so that a brand's home-sub size cannot enter its rank. Retained as evidence |
| Categories under 5 scoring subs | 8 of 20 | [07-index-methodology.md](07-index-methodology.md) requires each ranked brand across ≥5 subreddits. Below that the category ships as *insufficient Reddit signal to rank* |

The first three overlap — 17 subs are both hostile and vendor — and together remove 94, leaving:

```text
scorable = status ok AND rule_posture ≠ hostile AND NOT is_vendor_sub
```

**62 of 156** measured subreddits qualify ([data/subreddit-measurements.csv](data/subreddit-measurements.csv), [14-category-tests.md](14-category-tests.md)). 15 still carry `rule_posture = unknown`; that is not an exclusion, but the rules must be read before the sub scores anything.

Hostility, not vendor exclusion, now dominates the remaining failures: Note-taking maps 17 candidates and 11 of them are hostile. Business Intelligence and Analytics shows the trade honestly — it sits at 4 scoring subs with 4 vendor subs excluded (r/PowerBI, r/tableau, r/SQL, r/MicrosoftFabric). Readmitting those would clear the floor at 8, and is exactly what the rule refuses.

### Bootstrap score, before any census exists

```text
R = 1.0 permissive · 0.5 capped · 0 hostile
T = 1.0 exact practitioner/category fit · 0.5 adjacent · 0 wrong   (human-coded)
V = min(1, surviving_posts_per_day / 5)
H = min(1, exact_post_hits / 25)
  * min(1, brand_bearing_comments / 50)
  * min(1, distinct_hit_threads / 3)
F = 1 if the best hit is under 3 years old, else 0

bootstrap_signal = 100 * R * T * F * sqrt(V * H)
```

Rules can veto a huge subreddit; volume cannot rescue an off-topic one. Every stemmed search hit must pass an exact alias check locally before it counts toward `H` — Reddit search stem-matches, and "Descript" in r/VideoEditing returned results that merely contained the word "description".

From the qualifying pool, take the best practitioner sub and the best general sub, then add greedily to a cap of **8 scoring subreddits**. A category needing dozens of weak subs to manufacture data does not have signal; it has noise.

### Steady-state score, after the first census

Replace the search proxy with measured marginal value:

```text
delta_b(s)  = max(0, n_eff_b(all selected) − n_eff_b(without s))
worth(s)    = R * T * Σ_b delta_b(s) / ingest_calls(s)
```

Subscriber count never enters the score, at either stage. r/marketing's `rule_posture` is `hostile`: its rules delete exactly the content we came for, which is why 1,958,693 subscribers buy nothing.

---

## 3. Discovery — the core of the design

Four lanes with strictly different jobs. **Only Lane A is a census.** B is the live edge, C reaches what Reddit's own search cannot, and D fills gaps.

| Lane | Source | Job | Coverage claim |
|---|---|---|---|
| **A** | Archive dumps | Historical census | Complete for the window, subject to declared holes |
| **B** | `/r/{subs}/comments` | Live edge, comment-level | Complete since the watermark |
| **C** | External search index | Comment-level targeting | **None.** Opportunistic only |
| **D** | Reddit search, trees, `/duplicates` | Gap fill | None |

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
| r/SaaS | 1.27h | 78.73/h | 6.35h |
| r/CRM | 17.98h | 5.56/h | 24h |
| r/PasswordManagers | 72.80h | 1.37/h | 24h |

Adaptive cadence, so the 1,000-item cap is never the binding constraint:

```python
# target: never let more than ~500 comments accumulate between polls
# (half the 1000-item listing cap, as headroom for bursts)
rate = comments_per_hour_observed(sub)          # rolling 7-day median
interval_h = clamp(500 / max(rate, 1), 1, 24)
```

Store a `before` watermark per subreddit — the fullname of the newest comment seen. Page backwards until the watermark is reached. If a poll ever returns a full page without hitting the watermark, the cadence was too slow: halve the interval and flag the gap for archive reconciliation.

#### Multireddit bucketing — the efficiency win

The comment stream accepts a `+`-joined subreddit list and returns one merged feed. **Verified live 2026-08-04, scaling to at least 40 subreddits in a single call:**

| Subs in one call | URL length | Comments returned | Distinct subs seen | Span of the page |
|---:|---:|---:|---:|---:|
| 8 | 64 chars | 100 | 7 | 64.8 min |
| 15 | 131 chars | 100 | 14 | 18.3 min |
| 25 | 211 chars | 100 | 17 | 16.7 min |
| 40 | 360 chars | 100 | 23 | 7.5 min |

The merged rate is the **sum** of the member rates, so merging does not reduce the number of comments you must retrieve. What it removes is per-call overhead on quiet subreddits: eight sleepy subs polled separately burn eight calls to collect a handful of comments each, while merged they fill one page.

So the rule is **bucket by rate, not by category**:

```python
# Fill roughly one page per poll interval, never more.
TARGET, PAGE = 24, 100                    # hours, comments per call
def bucket(subs, rates):                  # rates in comments/hour
    quiet  = sorted([s for s in subs if rates[s] <  PAGE/TARGET], key=rates.get)
    loud   =        [s for s in subs if rates[s] >= PAGE/TARGET]
    buckets, cur, load = [], [], 0.0
    for s in quiet:                       # pack quiet subs until a bucket fills a page/day
        if load + rates[s] > PAGE/TARGET and cur:
            buckets.append(cur); cur, load = [], 0.0
        cur.append(s); load += rates[s]
    if cur: buckets.append(cur)
    return buckets + [[s] for s in loud]  # loud subs stay solo, on their own cadence
```

Never exceed ~40 members or ~400 URL characters per bucket. A bucket whose page stops covering its interval gets split.

### Lane C — the external index (what Reddit itself cannot search)

Reddit's API cannot search comment bodies. **External search engines can, because they crawl the rendered thread pages.** This lane buys comment-level targeting that no Reddit endpoint offers.

Verified live 2026-08-04 via the Brave Search API, `site:reddit.com "switched from hubspot to" CRM`, reading `extra_snippets`:

> "We too switched from Hubspot to Freshsales for the exact same reasons you mentioned."
> "HubSpot is atrocious. Absolutely the worst CRM I've ever had the misfortune of working with."
> "We switched from HubSpot to Attio this year." · "Switched to AC last year and love it."

Every one of those is a comment body carrying a comparative brand opinion, and none is reachable through `/r/{sub}/search`.

**How to use it.** Not as a census — coverage is whatever the engine indexed, which is unknown and unstable. Use it as a **targeted probe** over the patterns that carry the most decision-grade opinion:

| Pattern | Query shape | What it finds |
|---|---|---|
| Migration | `site:reddit.com "switched from {A} to"` | Two brands, one polarity each, explicit |
| Comparison | `site:reddit.com "{A} vs {B}" {category}` | Head-to-head threads |
| Displacement | `site:reddit.com "alternative to {A}" {category}` | Dissatisfaction with the incumbent |
| Regret | `site:reddit.com "wish we'd" OR "biggest mistake" {A}` | Strong negative signal |
| Advocacy | `site:reddit.com "best decision" OR "never going back" {A}` | Strong positive signal |

The output is a **thread URL**, which becomes a Lane D tree fetch. The snippet is only the lead; the comment is always re-fetched from Reddit's API so the stored text and permalink come from the authoritative source, never from the search index.

Run it per brand-pair on the qualifying set, not per brand. For a category with 15 ranked brands that is 105 unordered pairs — cap it at the pairs that actually co-occur in Lane B data.

### Lane D — Reddit-native boosters

- **Scoped cross-product search.** `/r/{sub}/search?restrict_sr=1&t=all&raw_json=1`, over general-sub × category-noun and domain-sub × intent-verb. Run both `sort=relevance` and `sort=top`; they return materially different sets.
- **Comment-tree expansion** on threads Lane B or Lane C surfaced only partially.
- **`/duplicates/{id}`** to pick up crossposts of a high-value thread into other mapped subs. Verified working.

**Cut, deliberately:** global search, general-sub `top` sweeps, API-only historical backfill, arbitrary timestamp-slicing, default `morechildren` expansion, author-profile crawls, embeddings and vector search.

⚠️ **`type=comment` on Reddit search does not work.** Verified 2026-08-04: `/r/CRM/search?q=hubspot&type=comment` returns `t3` posts, identical in kind to `type=link`. There is no comment search on the Data API, which is the entire reason Lanes B and C exist.

⚠️ **Stickied posts are not megathreads.** Checked across r/CRM, r/PasswordManagers and r/projectmanagement: the stickies are posting-guideline and rules posts, not recurring "what do you use" threads. Recurring threads have to be found by search and registered by id, not harvested from `/about/sticky`.

### Deduplication

Every observation keys on its **Reddit fullname** (`t1_xxxx` for comments, `t3_xxxx` for posts). A comment arriving via archive, comment stream and tree expansion is one row. The scoring unit is **one comment × brand × category**, counted once, so a comment naming a brand three times contributes one observation.

---

## 4. Thread qualification

Post listings are cheap; comment trees are expensive. Only fetch a tree when the thread earns it:

> ⚠️ **MEASURED CORRECTION, 2026-08-05.** `num_comments` is an actively HARMFUL ranking
> key. Measured live during the first harvest: a 1,232-comment r/sales thread returned
> **2** brand-bearing comments; a 34-comment r/CRM thread returned **12**. Big threads are
> general chatter. It is kept as a floor (>= 3) and given a deliberately weak `log1p` weight;
> the ranking is otherwise driven by brand and category density in the title. Recall comes
> from query DIVERSITY, not pagination depth — Reddit search truncates around 250 results
> per (sub, query, sort) however deep you page, and `sort=relevance` against `sort=top`
> overlap only 12-53%, so both run on every query.


| Rule | Threshold |
|---|---|
| ~~Not archived~~ **Archived is recorded, not filtered on** | ⚠️ Corrected 2026-08-05. Reddit's archiving blocks *writes*, not reads. Filtering archived threads out discards everything older than about six months, which is the entire historical corpus Lane D exists to reach. The flag is stored and used to set delete-sync cadence, nothing more |
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

## 7. The loop — continuous ingest, daily publish

Two rhythms, deliberately separated. Ingestion runs on each bucket's own cadence because the comment stream forces it to. Scoring and publishing run **once a day**, so the site is never more than 24 hours stale.

**Continuous — per bucket, every 1-24h (§3 Lane B):**

```
poll_comment_streams   multireddit buckets, watermarked      → append to raw
poll_new               /r/{sub}/new for post metadata          → append to raw
```

**Daily — one ordered pass, ~03:00 UTC:**

```
1.  refresh_subreddit_meta   rules + about; detect rule drift       (~2 calls/sub)
2.  qualify_threads          apply §4 to everything new
3.  fetch_trees              qualifying threads only
4.  boosters                 Lane C external probes + Lane D search
5.  detect_mentions          Aho-Corasick over new comments (local, no API)
6.  resolve_entities         05 — only candidate-bearing comments
7.  classify_sentiment       06 — only resolved mentions
8.  compute_index            07 — n_eff, diversity floors, bootstrap CIs
9.  publish                  revalidateTag per changed brand + category
10. delete_sync              purge removed content, revalidate affected pages
```

**Monthly:** `reconcile_archive` — fills `more`-branch gaps, catches deletions the API missed, and repairs any window a poll under-covered.

**Why daily is nearly free.** Stages 5-8 process only the **delta** — comments arriving since the last run. The expensive work is the one-time backfill; steady state is a small daily increment. Publishing daily rather than weekly multiplies the number of publish events by seven while leaving total classified volume unchanged.

**What daily changes on the serving side.** A full rebuild of ~5,000 pages every day is wasteful and risks Vercel's 45-minute build cap. The daily job calls `revalidateTag` only for brands and categories whose scores actually moved, so a typical day rebuilds tens of pages, not thousands. Full rebuilds stay reserved for code and schema changes ([08-architecture.md](08-architecture.md)).

**Resumability is a hard requirement.** Every stage checkpoints to disk atomically: write to `path.tmp`, then `os.replace()`. One file per thread keyed by post id; a re-run skips ids already present. A job that dies at hour 9 resumes at hour 9.

**Rate discipline:** ~100 req/min budget, run at ≤80. `time.sleep(0.75)` between calls. Back off on 429/500/502/503; re-fetch the token once on 401.

---

## 8. Cost and time

Steady state, per category, **per day**, 8 subreddits:

| Stage | Calls/day | Basis |
|---|---:|---|
| Comment streams | ~90 | rate-bucketed; quiet subs share a bucket |
| `/new` polling | ~16 | 2 pages × 8 subs |
| Subreddit meta | ~16 | 2 × 8 subs, drift detection |
| Comment trees | ~45 | qualifying threads only |
| Boosters (C + D) | ~10 | external probes + scoped search, rotated |
| **Total** | **~180/day** | 1,260/week |

**50 categories ≈ 9,000 calls/day.** At 80 req/min that is **under 2 hours** of wall clock, parallelisable and interruptible at any point. It fits comfortably inside a single free-tier app-only client's budget of ~115,000 calls/day.

Subreddits overlap heavily between categories — r/sysadmin serves Help Desk, Security, Backup and Collaboration — so **dedupe the ingest set before scheduling**. The 347 candidate slots across the 20 tested categories collapse to 232 unique ingest targets ([14-category-tests.md](14-category-tests.md)).

Archive backfill is a separate one-time cost, dominated by download and local scan rather than API calls. **Not yet measured** — its byte count and the machine's scan rate both need benchmarking before anyone quotes a duration.

LLM spend is governed by [06-sentiment.md](06-sentiment.md): only candidate-bearing comments reach the cascade. Daily deltas are small, so the recurring cost is a fraction of the one-time backfill classification.

---

## 9. Failure modes

| Failure | Detection | Response |
|---|---|---|
| Live feed outruns the cap | A poll returns a full page without hitting the watermark | Halve the interval; flag the window for archive reconciliation |
| Subreddit rules change | Rule-text hash differs from last cycle | Re-evaluate `rule_posture`; a sub turning hostile leaves the scoring corpus |
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
