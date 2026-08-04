# Method — how this research was done

How the findings in this repo were produced, what was measured versus inferred, and how to re-run any of it.

**Research date: 2026-08-04.** Everything here has that timestamp unless stated otherwise.

## Bottom line

- Twelve parallel research lanes plus three adversarial critics, all against **primary sources** — Reddit's own terms pages, live API calls, live registry lookups, court records, and published benchmarks.
- **Numbers were measured, not estimated,** wherever measurement was possible. The Reddit listing cap, subreddit subscriber counts, corpus volumes, category counts and domain availability were all pulled live.
- The adversarial pass was instructed to **kill the project**, not improve it. Its surviving objections are recorded in [01-legal.md](01-legal.md), [07-index-methodology.md](07-index-methodology.md) and [11-outreach-play.md](11-outreach-play.md) rather than quietly dropped.
- The research does **not** include a working prototype, a labelled gold set, or any ingested Reddit data. Nothing has been built.

## How it ran

| Stage | What happened |
|---|---|
| 1. Fan-out | 12 research lanes ran in parallel, each scoped to one question and each required to cite primary sources inline. |
| 2. Adversarial | 3 critics received the full corpus with instructions to refute it through a legal, a data-validity and a business lens. |
| 3. Synthesis | One agent reconciled corpus and critique into a decision brief. |
| 4. Owner decisions | Four calls taken by Vlad Shvets and recorded in [decisions/](decisions/). |
| 5. Documentation | One agent per file, each fed its own lane's evidence, then a three-lens review for fabrication, self-flattery and mechanics. |

The lanes: Reddit terms and licensing · data acquisition · prior art · sentiment methodology · index methodology · entity resolution · category taxonomy · subreddit mapping · SEO and AI citation · defamation and privacy risk · technical architecture · outreach play.

## What was measured live

| Measurement | Method | Result |
|---|---|---|
| Reddit listing cap | Paged `/r/SaaS/new` to exhaustion | 995 items over 10 pages, then `after=None` |
| Reddit search scope | Inspected available search types | Posts only. No comment-body search. |
| Subreddit subscribers | `get_subreddit_info` per subreddit | 16 general + ~130 category subs |
| Post volume | 10 newest posts per subreddit, extrapolated | Measures *surviving* posts, not submissions |
| Subreddit rules | `get_subreddit_rules` on the large subs | 9 subs with signal-killing rules |
| Corpus volumes | Arctic Shift `time_series` | r/SaaS 146K/936K, r/sysadmin 332K/7.11M, r/devops 70K/700K |
| Capterra taxonomy | Scraped `/categories/`, parsed schema.org JSON-LD | 1,000 leaf URLs, `numberOfItems` across 184 categories |
| G2 taxonomy | Scraped `/categories` | 2,237 category URLs |
| Domain availability | RDAP against the Verisign `.com` registry | 87 domains, 61 available |
| Competitor sites | Fetched and parsed live | `redditbrands.com` and `whatredditthinks.com` both live |
| Wikidata coverage | `wbsearchentities` API calls | "Linear" returns 10 hits, none the issue tracker |

## What is inference, not measurement

These are marked in place throughout, and are flagged again here because they drive real decisions:

- **Cost per million comments** for the sentiment cascade. Calculated from published API prices, not from a benchmark run.
- **Total corpus size** for ~1,000 subreddits. Extrapolated from measured per-subreddit volumes.
- **The IMDb / Beta-Binomial equivalence** in [07-index-methodology.md](07-index-methodology.md). An algebraic derivation, checkable but not cited.
- **Monthly infrastructure cost.** Built from published vendor list prices with assumed usage.
- **Precision and recall targets** for entity resolution. Targets set from benchmark expectations, not achieved figures.
- Every legal reading. Clause text is quoted verbatim; what it *means for us* is analysis, and this repo is not legal advice.

## Known gaps

- **38 of the 50 Phase 1 categories have no subreddit mapping.** Twelve were mapped and signal-tested. See [data/phase1-categories.csv](data/phase1-categories.csv).
- **No gold set exists.** Every accuracy figure is a target, not a measurement.
- **No sentiment pipeline has been run** against real Reddit data. The cascade design is untested.
- **G2's terms of use were not read.** Assumed similar to Capterra's post-acquisition. Marked NOT VERIFIED in [03-taxonomy.md](03-taxonomy.md).
- **Reddit's commercial pricing is unknown.** No public rate card exists. The often-quoted $0.24/1,000 calls is the June 2023 announced developer rate and is not verified as a current enterprise price.
- Some claims found in secondary reporting could not be confirmed against a Reddit primary source and are labelled NOT VERIFIED where they appear.

## Re-running it

Everything here is reproducible without a paid seat except the Reddit API calls, which need an OAuth client.

```bash
# Domain availability — public registry, no key
curl -H "User-Agent: Mozilla/5.0" \
  https://rdap.verisign.com/com/v1/domain/ugcranks.com
# 404 = available, 200 = taken

# Reddit terms — the load-bearing primary sources
# redditinc.com/policies/data-api-terms      (last revised 2026-07-20)
# redditinc.com/policies/developer-terms     (last revised 2026-03-24)

# Capterra category count + size signal
# Fetch capterra.com/categories/, extract /{slug}-software/ links,
# then read schema.org ItemList "numberOfItems" from each category page.
```

The Reddit measurements used the `mcp__reddit__*` tooling under app-only OAuth. Note that `search_reddit` with `type='sr'` returns zero results under that auth mode, so subreddit discovery has to supply candidate names by hand.

The full research corpus — twelve lane reports, three critiques and the synthesis — was generated into a scratch directory and is **not committed**. It is regenerable from the questions listed above, and committing 270KB of intermediate agent output would bury the twenty files that matter.

## How to check this work

1. Pick any statistic in any file and follow its inline link to the source.
2. Re-run the RDAP loop against [data/domain-availability.csv](data/domain-availability.csv). Availability moves.
3. Re-pull three subreddit subscriber counts from [data/subreddit-map.csv](data/subreddit-map.csv).
4. Read Data API Terms §4.1 and Developer Terms §4.1 yourself. They are short, and they are the whole argument in [01-legal.md](01-legal.md).

---

[← Back to README](README.md) · [Sources](sources.md) · [Legal position](01-legal.md)
