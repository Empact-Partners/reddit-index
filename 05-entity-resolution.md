# Brand Entity Resolution

## Bottom line

- This is the hardest engineering problem in Reddit Index. Everything downstream (counts, rankings, brand pages, the outreach email) is wrong if a mention is attached to the wrong company.
- Off-the-shelf tooling does not solve it. The best published system on the closest benchmark, WNUT-17 emerging/rare entities with a test set drawn from Reddit and StackExchange, scored **41.86 entity F1** ([task page](http://noisy-text.github.io/2017/emerging-rare-entities.html)).
- Knowledge-base linking fails on the head of our own list. Verified live: Wikidata label search for "Linear" returns 10 hits, none of them the issue tracker ([API call](https://www.wikidata.org/w/api.php?action=wbsearchentities&search=Linear&language=en&format=json&limit=10)); "Vercel" returns Q56069184 described only as "San Francisco based cloud computing company", with no aliases ([API call](https://www.wikidata.org/w/api.php?action=wbsearchentities&search=Vercel&language=en&format=json&limit=5)).
- Our own seed list makes the shape of the problem concrete: **35 of 113 brands (31%) are classed high-ambiguity** in [data/brand-gazetteer-seed.csv](data/brand-gazetteer-seed.csv) — Notion, Slack, Monday, Linear, Stripe, Gusto, Workday, Rippling, Craft, Front, Ramp, Make, Render, Segment, Amplitude, Looker, Loom, Motion, Sketch, Close, Bill.com, Confluence, Teams, Roam, Framer, Obsidian and others.
- 🟢 The tractable framing: **a closed gazetteer plus per-surface-form disambiguation, not NER.** We already know our brands. The job is deciding whether *this* occurrence of the string "monday" is the vendor — binary classification with strong Reddit-specific features, with direct precedent in RepLab 2013.
- ⚠️ Precision is the only metric that matters, and it publishes as a **95% Wilson lower bound, never a point estimate**: ≥0.97 overall, ≥0.95 for any brand on a published board. Recall floats at **0.80-0.88**. A brand the pipeline cannot resolve confidently is excluded, not guessed.

---

## 1. Why off-the-shelf tooling fails

Every published option was calibrated against noisy social text before being rejected as a standalone solution. None of them reaches a precision bar suitable for a public ranking.

| Approach | Realistic accuracy on Reddit text | Cost | Verdict |
|---|---|---|---|
| Gazetteer (Aho-Corasick / FlashText) + disambiguation | Recall ~0.95 at the match layer; precision set entirely by the disambiguation layer | Free, microseconds/doc | 🟢 Use as the candidate layer |
| Supervised NER (spaCy / Flair) | WNUT-17 supervised reference point T-NER 55.11 avg F1 ([ELLEN](https://arxiv.org/pdf/2403.17385); NOT VERIFIED against the PDF, taken from a search summary) | Needs labeled data we do not have | 🔴 Reject |
| Zero-shot NER (GLiNER) | Bi-encoder SOTA 61.5% F1 on CrossNER; authors note social-media performance is flat across model sizes ([GLiNER NAACL 2024](https://aclanthology.org/2024.naacl-long.300.pdf), [bi-encoder](https://arxiv.org/pdf/2602.18487)) | CPU-cheap, ~ms/doc | 🟡 Not needed on a closed list |
| Entity linking (ReFinED / BLINK / REL) | ReFinED has best overall F1 in the independent ELEVANT evaluation and is 6× faster than BLINK's bi-encoder, whose average F1 is 9 points lower ([ELEVANT](https://arxiv.org/pdf/2305.14937), [ReFinED](https://arxiv.org/pdf/2207.04108)) | Moderate GPU | 🔴 Reject — the KB lacks our entities |
| LLM open extraction | WNUT-17 zero-shot GPT-4 43.72 / GPT-3.5 39.96 vs supervised 55.11 (same ELLEN caveat) | Highest per-token | 🟡 Adjudicator only |

The knowledge-base failure is decisive. Entity linkers resolve a span to a KB node, and for Linear the correct node does not exist while for Vercel it exists with no aliases and a description that never mentions hosting or deployment.

Commercial precedent confirms the framing rather than the tooling. Octolens markets Reddit B2B SaaS monitoring with "relevance scoring... to handle common-word brand names" ([octolens.com](https://octolens.com/reddit-monitoring)) — scoring, not extraction.

---

## 2. Pipeline

Five stages. Each one is separately testable, and the confidence gate is the only thing that decides publication.

| # | Stage | What it does | Output |
|---|---|---|---|
| 1 | Candidate matching | Aho-Corasick automaton over the alias table plus a domain matcher, run on normalized document text | Every span that could be a brand, recall ~0.95 |
| 2 | Feature extraction | Builds the signal vector for each candidate span (see §4) | Feature row per candidate |
| 3 | Disambiguation classifier | Logistic regression or shallow GBM scoring P(this span is the vendor), fit on the gold set | Monotone score 0-1 |
| 4 | Confidence gate | SAFE accept · AMBIGUOUS accept on ≥1 corroborating signal · HOSTILE requires score > τ; low-margin band goes to a Haiku-class LLM adjudicator, batched 20-40 spans with subreddit and a 300-char window | Accept / reject / exclude |
| 5 | Human audit queue | Stratified sample per refresh, adjudicated against the source document | Measured precision, publish or refuse |

The ambiguity classes map straight onto the seed CSV: `low` = SAFE, `medium` = AMBIGUOUS, `high` = HOSTILE. Rules gate, a classifier scores, and an LLM only adjudicates the residual.

That split is deliberate. Rules alone cannot be tuned to a stated precision, and a pure-LLM pass is expensive, non-reproducible run to run, and gives no monotone score to threshold.

---

## 3. Document parity and resolution unit

A brand named in a post body (`selftext`) and a brand named in a comment are the same kind of evidence: both are counted identically and both are displayed. The unit of resolution is **(document × brand × category)**, where a document is either a comment or a post. Carry `doc_type` through every pipeline stage so the displayed card can label the source as a post or comment and link to its correct permalink.

`doc_type` does not change order, prominence, scoring weight, or any other scoring treatment. The practical distinction is only for disambiguation: post bodies are longer and usually give more context per occurrence, so they are generally easier to resolve; a post title is weak evidence on its own.

### Measured confirmation of ambiguity classes

A naive substring pass over live comment pages produced the expected false matches: `Monday` matched the weekday in r/nfl and r/rugbyunion, `SAP` matched the fluid in r/worldbuilding, `Rippling` matched water, and `Sage` matched the herb. This is measured confirmation of the ambiguity classes in [data/brand-gazetteer-seed.csv](data/brand-gazetteer-seed.csv), specifically its `ambiguity_class` column. Word-boundary matching, together with restricting probe terms to the gazetteer's low-ambiguity brands, removed those false matches.

---

## 4. Disambiguation features

The signal list is standard practice; the ranking by discriminative power is our inference, to be re-fit against the gold set.

| Rank | Signal | Example | Strength |
|---|---|---|---|
| 1 | Domain or URL in the same document | `monday.com`, `vercel.com` | Auto-accept, near-zero false positives |
| 2 | Co-occurring confirmed brand within ~400 chars | "we moved from Asana to Monday" | Very strong |
| 3 | Subreddit prior | r/ProductManagement, r/SaaS, r/webdev, r/nocode vs r/investing, r/running | Strong; learn per-brand × per-subreddit from the audit set |
| 4 | Verb and possessive frames | `(use\|using\|switched to\|migrated to\|moved off\|on) X`, `X's (pricing\|API\|free tier\|board)` | Strong for monday, notion, linear |
| 5 | Category vocabulary in window | app, tool, workspace, board, seat, plan, pricing, tier, self-host, integration, workflow | Moderate |
| 6 | Capitalization mid-sentence | "Notion" vs "notion" | Weak on Reddit — a feature, never a gate |

The subreddit map in this repo supplies feature 3 directly, and the category assignment in the gazetteer supplies feature 5's vocabulary per category.

RepLab 2013 is the academic precedent for this framing: participants classified 140k+ tweets as related or unrelated to an ambiguous company name, with best reported results around Reliability 0.72 / Sensitivity 0.45 ([overview](https://www.researchgate.net/publication/258110327_Overview_of_RepLab_2013_Evaluating_Online_Reputation_Monitoring_Systems)).

Those numbers are the reason we gate rather than classify everything. Dedicated systems on this exact task do not reach a publishable precision across the board, so we accept only where the evidence is strong.

---

## 5. Alias and surface-form handling

⚠️ Treat every surface form as its own row with its own learned precision prior. A surface form is never simply an alias that inherits the brand's confidence.

| Case | Rule |
|---|---|
| `monday.com` vs bare `monday` | `monday.com` is high-precision and auto-accepts. Bare lowercase `monday` is near-zero and **default-rejects unless two corroborating signals fire** |
| `MS Teams` / `Teams` | `Teams` accepts only with "MS", "Microsoft", or "Office 365" in window |
| `GSuite` / `G Suite` → Google Workspace | Legacy alias still dominates Reddit usage; map forward, keep both as matchable forms |
| Product vs company (Atlassian → Jira, Confluence) | Model as two levels. **Publish at product level**, roll up to vendor only on request |
| Renames (Integromat → Make) | Carry `valid_from` / `valid_to` plus `redirect_to`. **Must not retroactively rewrite past periods** in a ranking |
| Misspellings | Bounded Levenshtein ≤1, only for forms ≥6 characters that are not English dictionary words |
| Never fuzzy-match | monday, linear, front, range, arc, bench, craft, motion, pitch, ramp, sift |

---

## 6. Precision doctrine

**False positives are categorically worse than false negatives, and the asymmetry is not close.** A brand's team can open one cited thread, find their name was never mentioned, and the entire ranking becomes anecdote.

A false negative moves a count slightly. Unbiased under-counting preserves rank order when the miss rate is roughly uniform across brands.

It is not uniform here. Ambiguous-name brands lose more recall than clean-name brands, so the caveat must be stated on the methodology page and a per-brand recall band published from the audit.

| Target | Value | How measured |
|---|---|---|
| Mention-level precision, overall | Wilson 95% **lower bound ≥0.97** | Stratified random sample of **1,000** accepted mentions per cycle, strata = ambiguity class |
| Mention-level precision, any brand on a published board | Wilson 95% **lower bound ≥0.95** | **150** adjudicated mentions per brand, rolling certification |
| Recall | 0.80-0.88 expected (inference, not measured) | Gold-set coverage |
| Publish refusal, whole cycle | overall lower bound below 0.95 | No board publishes that cycle |
| Publish refusal, single brand | more than 2 errors in 150 | Brand is pulled from that cycle |

### Why the audit is 1,000 and not 400

The Wilson interval is `(p̂ + z²/2n ± z·√(p̂(1−p̂)/n + z²/4n²)) / (1 + z²/n)`, with z = 1.96 at 95% ([Wilson 1927, JASA 22(158):209-212](https://doi.org/10.1080/01621459.1927.10502953)).

At n = 400 and p̂ = 0.97 that evaluates to **[0.948, 0.983]** — a half-width of ±1.7pp. The half-width is tight. The placement is not: the lower bound sits under 0.95, so the sample is consistent with a true precision of 0.949 and cannot separate 0.97 from 0.95.

Failing to reject a target is not evidence for it. A 400-item audit can therefore neither certify the 0.97 claim nor refuse a publication on it, which makes it a reporting exercise rather than a gate.

At n = 1,000 the same arithmetic gives thresholds that decide something:

| Errors in 1,000 | p̂ | Wilson 95% interval | Consequence |
|---|---|---|---|
| ≤19 | ≥0.981 | [0.971, 0.988] at 19 errors | 0.97 floor certified — publish the figure |
| 20-36 | 0.964-0.980 | [0.951, 0.974] at 36 errors | Publish the interval; the ≥0.97 claim is not supported this cycle |
| ≥37 | ≤0.963 | [0.949, 0.973] at 37 errors | Lower bound under 0.95 — the cycle does not publish |

Per published brand at n = 150: 0 errors gives [0.975, 1.000], 1 gives [0.963, 0.999], 2 gives [0.953, 0.996], 3 gives [0.943, 0.993]. A 0.95 lower bound tolerates two errors and no more.

The rule this replaces — 3 errors in 60 — carries the interval **[0.863, 0.983]**. It clears a brand whose true precision is 0.87, so it was never a gate at the stated bar.

⚠️ These are audit sample sizes, not the eligibility gate. A brand's score publishes only when `n_eff` meets its category's `n_min` after the design-effect correction: Deep 600, Standard 400, or Thin 200 opinionated mentions ([index methodology](07-index-methodology.md)). The sizes here govern the labelled sample that measures whether those mentions are attached to the right company.

Expected end-to-end performance is **precision 0.96-0.98, recall 0.80-0.88**, concentrated recall loss on HOSTILE names. That is inference, not a measurement: the 42-F1 WNUT ceiling covers open-vocabulary emerging entities, whereas a closed 113-name gazetteer with URL and co-occurrence evidence is a strictly easier problem.

An expected 0.97 is uncomfortably close to the bar. At p̂ = 0.97 even a 1,000-item audit lands at [0.958, 0.979] and misses the 0.97 floor, so the pipeline has to run nearer 0.98 for the claim to certify. Publishing the interval is what keeps that honest cycle to cycle.

---

## 7. Gold set and manual review budget

| Item | Size | Effort | Frequency |
|---|---|---|---|
| Gold set | ~1,000 mentions, 200-item overlap between two annotators for kappa | 12-15 hours | Once |
| Standing audit | 1,000 stratified samples | 12-15 hours | Every refresh cycle (weekly) |
| Per-brand certification | 150 mentions per published brand | ~2 hours per brand | Rolling; re-run on any alias, ambiguity-class, or classifier change |

Below these sizes the precision claim is unfalsifiable: a smaller sample fails to reject the target and gets read as confirming it. The gold set is also the training data for stage 3 — there is no other source of labels.

The per-brand line is what does not scale. At a 50-category expansion and roughly 15 published brands each it is 75K-150K adjudicated labels per cycle ([phasing](12-phasing.md)), which is why certification is rolling rather than weekly, and why audit labor rather than infrastructure is the binding constraint on how many brands can ship.

---

## 8. Where the brand list, aliases, and domains come from

| Source | What it gives | Legality | Use |
|---|---|---|---|
| Wikidata | P1448 official name, P1813 short name, P856 official website | Structured data is **CC0**, bulk-downloadable ([database download](https://www.wikidata.org/wiki/Wikidata:Database_download)) | 🟢 Cleanest legally, but coverage fails as shown in §1 |
| Vendor's own site | Canonical product names, official aliases | Public pages, factual extraction | 🟢 Primary for aliases |
| DNS | Domain verification for each brand | Public | 🟢 Verification step |
| Brandfetch | Domain → canonical name, firmographics | Logo API free to 500k requests/month; Brand API $99/mo for 100 brands, $0.10 overage ([pricing](https://brandfetch.com/developers/pricing)) | 🟡 Enrichment only |
| Crunchbase | Company records | Free API tier gone; Basic from ~$49/mo ([2026 write-up](https://dev.to/agenthustler/crunchbase-api-in-2026-free-tier-gone-what-startup-data-hunters-do-now-1177)). Historic CC BY-NC framing is NOT VERIFIED as current | 🔴 Licensed only |
| G2 / Capterra | Category taxonomies, product lists | Terms of Use expressly prohibit automated extraction ([G2 ToU](https://legal.g2.com/terms-of-use), [content usage](https://sell.g2.com/content-usage-guidelines)); Cloudflare bot management in place | 🔴 Do not scrape |
| Product Hunt | Product records | API terms NOT VERIFIED | 🔴 Do not use until verified |

Curate the registry by hand. 113 brands is one afternoon of work, and Phase 2 scaling is a repeat of the same afternoon rather than a new technique.

⚠️ Reddit's own data carries a separate constraint: the Responsible Builder Policy prohibits commercial redistribution of retrieved data and use for AI model training without written approval ([policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy)). Aggregate counts sit comfortably inside it; the decision to display full comment text on brand pages does not, and is documented as a deliberate, priced risk in [01-legal.md](01-legal.md).

---

## 9. What happens to a brand we cannot resolve

It is excluded, not guessed. A brand whose mentions fail the confidence gate does not get a low count, an estimated count, or a footnote — it does not appear in that cycle's ranking at all.

The exclusion is recorded per brand per cycle with the reason and the audit numbers that triggered it. That record is what lets us tell a brand exactly why they are absent when they ask.

Silent guessing is the failure mode that ends the project. An excluded brand is a gap; a wrongly-counted brand is a public error with a named victim who can disprove it in one click.

---

[← Back to README](README.md) · [Sentiment classification →](06-sentiment.md) · [Seed gazetteer (CSV)](data/brand-gazetteer-seed.csv)
