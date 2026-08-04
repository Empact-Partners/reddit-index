# Brand Entity Resolution

## Bottom line

- This is the hardest engineering problem in UGC Ranks. Everything downstream (counts, rankings, brand pages, the outreach email) is wrong if a mention is attached to the wrong company.
- Off-the-shelf tooling does not solve it. The best published system on the closest benchmark, WNUT-17 emerging/rare entities with a test set drawn from Reddit and StackExchange, scored **41.86 entity F1** ([task page](http://noisy-text.github.io/2017/emerging-rare-entities.html)).
- Knowledge-base linking fails on the head of our own list. Verified live: Wikidata label search for "Linear" returns 10 hits, none of them the issue tracker ([API call](https://www.wikidata.org/w/api.php?action=wbsearchentities&search=Linear&language=en&format=json&limit=10)); "Vercel" returns Q56069184 described only as "San Francisco based cloud computing company", with no aliases ([API call](https://www.wikidata.org/w/api.php?action=wbsearchentities&search=Vercel&language=en&format=json&limit=5)).
- Our own seed list makes the shape of the problem concrete: **35 of 113 brands (31%) are classed high-ambiguity** in [data/brand-gazetteer-seed.csv](data/brand-gazetteer-seed.csv) — Notion, Slack, Monday, Linear, Stripe, Gusto, Workday, Rippling, Craft, Front, Ramp, Make, Render, Segment, Amplitude, Looker, Loom, Motion, Sketch, Close, Bill.com, Confluence, Teams, Roam, Framer, Obsidian and others.
- 🟢 The tractable framing: **a closed gazetteer plus per-surface-form disambiguation, not NER.** We already know our brands. The job is deciding whether *this* occurrence of the string "monday" is the vendor — binary classification with strong Reddit-specific features, with direct precedent in RepLab 2013.
- ⚠️ Precision is the only metric that matters. Target mention-level precision **≥0.97**, let recall float at **0.80-0.88**, and exclude any brand the pipeline cannot resolve confidently rather than guessing it.

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
| 1 | Candidate matching | Aho-Corasick automaton over the alias table plus a domain matcher, run on normalized comment text | Every span that could be a brand, recall ~0.95 |
| 2 | Feature extraction | Builds the signal vector for each candidate span (see §3) | Feature row per candidate |
| 3 | Disambiguation classifier | Logistic regression or shallow GBM scoring P(this span is the vendor), fit on the gold set | Monotone score 0-1 |
| 4 | Confidence gate | SAFE accept · AMBIGUOUS accept on ≥1 corroborating signal · HOSTILE requires score > τ; low-margin band goes to a Haiku-class LLM adjudicator, batched 20-40 spans with subreddit and a 300-char window | Accept / reject / exclude |
| 5 | Human audit queue | Stratified sample per refresh, adjudicated against the source comment | Measured precision, publish or refuse |

The ambiguity classes map straight onto the seed CSV: `low` = SAFE, `medium` = AMBIGUOUS, `high` = HOSTILE. Rules gate, a classifier scores, and an LLM only adjudicates the residual.

That split is deliberate. Rules alone cannot be tuned to a stated precision, and a pure-LLM pass is expensive, non-reproducible run to run, and gives no monotone score to threshold.

---

## 3. Disambiguation features

The signal list is standard practice; the ranking by discriminative power is our inference, to be re-fit against the gold set.

| Rank | Signal | Example | Strength |
|---|---|---|---|
| 1 | Domain or URL in the same comment | `monday.com`, `vercel.com` | Auto-accept, near-zero false positives |
| 2 | Co-occurring confirmed brand within ~400 chars | "we moved from Asana to Monday" | Very strong |
| 3 | Subreddit prior | r/ProductManagement, r/SaaS, r/webdev, r/nocode vs r/investing, r/running | Strong; learn per-brand × per-subreddit from the audit set |
| 4 | Verb and possessive frames | `(use\|using\|switched to\|migrated to\|moved off\|on) X`, `X's (pricing\|API\|free tier\|board)` | Strong for monday, notion, linear |
| 5 | Category vocabulary in window | app, tool, workspace, board, seat, plan, pricing, tier, self-host, integration, workflow | Moderate |
| 6 | Capitalization mid-sentence | "Notion" vs "notion" | Weak on Reddit — a feature, never a gate |

The subreddit map in this repo supplies feature 3 directly, and the category assignment in the gazetteer supplies feature 5's vocabulary per category.

RepLab 2013 is the academic precedent for this framing: participants classified 140k+ tweets as related or unrelated to an ambiguous company name, with best reported results around Reliability 0.72 / Sensitivity 0.45 ([overview](https://www.researchgate.net/publication/258110327_Overview_of_RepLab_2013_Evaluating_Online_Reputation_Monitoring_Systems)).

Those numbers are the reason we gate rather than classify everything. Dedicated systems on this exact task do not reach a publishable precision across the board, so we accept only where the evidence is strong.

---

## 4. Alias and surface-form handling

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

## 5. Precision doctrine

**False positives are categorically worse than false negatives, and the asymmetry is not close.** A brand's team can open one cited thread, find their name was never mentioned, and the entire ranking becomes anecdote.

A false negative moves a count slightly. Unbiased under-counting preserves rank order when the miss rate is roughly uniform across brands.

It is not uniform here. Ambiguous-name brands lose more recall than clean-name brands, so the caveat must be stated on the methodology page and a per-brand recall band published from the audit.

| Target | Value | How measured |
|---|---|---|
| Mention-level precision, overall | ≥0.97 | Stratified random sample of 400 accepted mentions per cycle, strata = ambiguity class |
| Mention-level precision, any published top-N brand | ≥0.95 | Per-brand stratum |
| Recall | 0.80-0.88 expected (inference, not measured) | Gold-set coverage |
| Publish refusal rule | >3 errors in 60 for a brand's stratum | Brand is pulled from that cycle |

At n=400 and p̂=0.97 the Wilson 95% interval is roughly ±1.7pp, which is tight enough to publish as a stated figure.

Expected end-to-end performance is **precision 0.96-0.98, recall 0.80-0.88**, concentrated recall loss on HOSTILE names. That is inference, not a measurement: the 42-F1 WNUT ceiling covers open-vocabulary emerging entities, whereas a closed 113-name gazetteer with URL and co-occurrence evidence is a strictly easier problem.

---

## 6. Gold set and manual review budget

| Item | Size | Effort | Frequency |
|---|---|---|---|
| Gold set | ~1,000 mentions, 200-item overlap between two annotators for kappa | 12-15 hours | Once |
| Standing audit | 300-400 stratified samples | ~5 hours | Every refresh cycle |

Anything less than this makes the 0.97 precision claim unfalsifiable. The gold set is also the training data for stage 3 — there is no other source of labels.

---

## 7. Where the brand list, aliases, and domains come from

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

## 8. What happens to a brand we cannot resolve

It is excluded, not guessed. A brand whose mentions fail the confidence gate does not get a low count, an estimated count, or a footnote — it does not appear in that cycle's ranking at all.

The exclusion is recorded per brand per cycle with the reason and the audit numbers that triggered it. That record is what lets us tell a brand exactly why they are absent when they ask.

Silent guessing is the failure mode that ends the project. An excluded brand is a gap; a wrongly-counted brand is a public error with a named victim who can disprove it in one click.

---

[← Back to README](README.md) · [Sentiment classification →](06-sentiment.md) · [Seed gazetteer (CSV)](data/brand-gazetteer-seed.csv)
