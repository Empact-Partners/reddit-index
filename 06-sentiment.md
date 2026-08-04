# Sentiment Classification

## Bottom line

- **Document-level sentiment is the wrong task.** One Reddit comment naming three brands has one document label and up to three different target polarities. The correct formulation is targeted / aspect-based sentiment (TABSA/ABSA), emitting `(brand_mention, polarity)` per span.
- Off-the-shelf **VADER, SiEBERT, and twitter-roberta all emit document labels** and will systematically mis-rank brands in exactly the comparative threads that carry the most signal.
- **No single model wins.** Fine-tuned encoders beat zero-shot LLMs on structured ABSA (XLM-R **68.86 F1** vs GPT-4o **49.85**, SemEval-2016 five-language, [arXiv 2412.12564v3](https://arxiv.org/html/2412.12564v3), Dec 2024), but LLMs are the plausible fix for the hard cases encoders silently botch. Hence a cascade.
- **The classifier emits four labels — `pos`, `neg`, `neu`, `abstain` — and only two of them score.** The denominator is `N_opinionated = pos + neg`; `neutral_share` and `abstain_share` are first-class published outputs beside every score ([07-index-methodology.md](07-index-methodology.md)).
- **Cascade cost at batch pricing ≈ $31–53 per 1M comments** with a Haiku stage 2, **≈ $3–6** with a nano-class stage 2, against $200 to batch every mention through Haiku. Like for like that is a 2–7× saving. All totals are our arithmetic, marked INFERENCE.
- ⚠️ **The operator conflict runs both ways, and bot filtering closes only one direction.** Empact-influenced threads are excluded before any polarity is assigned; separately, partner status is disclosed on `/methodology` and is never an input to a score.
- **Validation is the first thing built, not the last.** 1,000–1,500 stratified human-labelled comments, ≥2 annotators, Krippendorff's α reported per class on `/methodology`.

---

## 1. The framing error

Every general-purpose sentiment model takes a document and returns one label. UGC Ranks needs a label per brand per mention. Those are different tasks, and the difference is not cosmetic.

| Comment | Document label | Correct targeted labels |
|---|---|---|
| "We switched from Brand X to Brand Y last year, best decision we made." | Positive | X = negative, Y = positive |
| "Brand A is fine, but Brand B is a nightmare and Brand C is worse." | Negative | A = neutral/mild-positive, B = negative, C = negative |
| "Try Brand D, it does that." | Neutral or Positive | D = recommendation, not polarity |

Applying the document label to every brand in row one gives Brand X a positive credit it did not earn. Do that across a category and the "most loved" column inverts.

Comparative opinion is a separately named research task, not an edge case: **COQE — Comparative Opinion Quintuple Extraction** ([EMNLP 2021](https://aclanthology.org/2021.emnlp-main.322/), [COLING 2025](https://aclanthology.org/2025.coling-main.217/)). Any pipeline emitting one label per comment is structurally incapable of handling it.

**Correct formulation.** Input `(comment_text, target_span, thread_context)`. Output `polarity ∈ {pos, neg, neu, abstain}`, plus `is_comparative` and `is_recommendation` flags. Target spans come from the mention detection described in [05-entity-resolution.md](05-entity-resolution.md).

Tooling: **PyABSA** (29 models, 26 datasets, modular ATE + ASC, [arXiv 2208.01368](https://arxiv.org/abs/2208.01368)) and **Instruct-DeBERTa** (InstructABSA extraction + DeBERTa-v3-base-absa classification, [arXiv 2408.13202](https://arxiv.org/pdf/2408.13202)). Frontier: [SemEval-2026 DimABSA](https://arxiv.org/pdf/2604.07066).

⚠️ Every canonical ABSA dataset (SemEval-2014/15/16, SentiHood, MAMS, M-ABSA) is reviews, hotels, or restaurants. **None is Reddit.** In-domain labels are mandatory; the domain gap is not something a good prompt closes.

---

## 2. What the benchmarks actually say

| Model | Reported number | Task shape | Source |
|---|---|---|---|
| VADER (lexicon) | 69% accuracy on Reddit posts vs RoBERTa's 66% in a depression-language study | Document, binary-ish | [arXiv 2405.18061](https://arxiv.org/pdf/2405.18061) |
| TextBlob | Weakest of three in a Reddit study; **403 on fetch, NOT VERIFIED** | Document | [ScienceDirect S1877050925014280](https://www.sciencedirect.com/science/article/pii/S1877050925014280) |
| `twitter-roberta-base-sentiment-latest` | TweetEval fine-tune. **Card publishes no F1.** | Document, 3-class | [model card](https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest) |
| TweetEval sentiment | RoBERTa-Retrained 72.8, TimeLMs-2021 73.7 macro-recall | Document, 3-class | [tweeteval leaderboard](https://github.com/cardiffnlp/tweeteval) |
| SiEBERT | 93.2% mean accuracy across 15 datasets | Document, **binary, no neutral**, review-shaped text | [model card](https://huggingface.co/siebert/sentiment-roberta-large-english) |
| Zero-shot LLMs, ABSA | GPT-4o 49.85, Gemini-1.5 49.94, Claude-3.5 43.28 avg F1 | Structured ABSA | [arXiv 2412.12564v3](https://arxiv.org/html/2412.12564v3) |
| Fine-tuned encoders, ABSA | XLM-R 68.86, mBERT 62.65 | Structured ABSA | [arXiv 2412.12564v3](https://arxiv.org/html/2412.12564v3) |

Read that table carefully. SiEBERT's 93.2% is binary on review text; TweetEval's ~73 is 3-class macro-recall on tweets. Not comparable, and neither predicts brand-target accuracy on Reddit.

**NOT VERIFIED:** no published F1 exists for Claude Haiku, GPT-5-nano, or open-weight models on a Reddit brand-sentiment benchmark. That benchmark does not appear to exist publicly. Treat all LLM accuracy as unmeasured until measured on our own gold set.

---

## 3. The recommended cascade

| # | Stage | What it does | What it hands on |
|---|---|---|---|
| 0 | Ingest + dedupe | Hash-dedupe, drop deleted/removed, strip `>` quoted blocks into a separate field | Clean records, quoted text isolated |
| 1 | **Bot / astroturf filter** | Account-feature classifier + cross-account n-gram fingerprinting. Flags, never deletes | Comments tagged organic / suspect / Empact-influenced |
| 2 | Brand mention detection | Gazetteer, alias and fuzzy match, NER disambiguation ([05-entity-resolution.md](05-entity-resolution.md)) | `(comment, target_span)` pairs |
| 3 | **Stage-1 TABSA** | Fine-tuned DeBERTa-v3 / PyABSA ASC head on target-marked input, our in-domain labels | Polarity + calibrated confidence per pair |
| 4 | Router | Escalates on: low confidence, ≥2 targets, comparative cue, sarcasm flag, negation in scope. Expect 15–25% escalation | Escalation queue |
| 5 | **Stage-2 LLM** | Claude Haiku 4.5 Batch API or gpt-5-nano, structured output: per-target polarity, `is_comparative`, `is_recommendation`, and `abstain` as a distinct label from `neu` | Resolved labels for the hard tail |
| 6 | Human loop | Stage disagreements plus a random 1% sample, 2 annotators, adjudication | Gold labels, retraining set |
| 7 | Aggregate | Per-brand `pos` / `neg` / `neu` / `abstain` counts, `N_opinionated = pos + neg` as the scoring denominator, plus `neutral_share`, `abstain_share`, coverage %, suspect share, and cluster-bootstrap CIs resampled by thread and author ([07-index-methodology.md](07-index-methodology.md)) | Published ranking inputs |

**The label set is four-way, and the fourth is not a bin.** Only `pos` and `neg` enter a score. `neu` is a real judgment: the comment names the brand without an opinion about it. `abstain` is the classifier declining. Collapsing either into the other, or into a polarity, changes the denominator and therefore the rank.

Build stage 6 and the gold set **first**. Every other stage is unmeasurable without them.

---

## 4. Cost per 1M comments

Assumptions, which drive everything: ~250 input tokens per item (comment, parent, thread title, instruction) and ~30 output tokens. **All totals below are our arithmetic — INFERENCE, not quoted totals.** Unit prices are quoted.

| Approach | Standard | Batch | How the number is built |
|---|---|---|---|
| Stage-1 encoder alone (DeBERTa-v3, `g5.xlarge`) | **$1–3 all-in** | — | $1.006/hr on-demand, $0.4419/hr spot ([Vantage](https://instances.vantage.sh/aws/ec2/g5.xlarge)); ~500 items/s ⇒ ~33 min ⇒ $0.25–0.56, called $1–3 with loading, retries, tokenization |
| Claude Haiku 4.5, every pair | **$400** | **$200** | 250 MTok in × $1.00 + 30 MTok out × $5.00 = $250 + $150; Batches 50% off ([Anthropic](https://platform.claude.com/docs/en/pricing)) |
| GPT-5-nano, every pair | **$24.50** | **$12.25** | 250 MTok in × $0.05 + 30 MTok out × $0.40 = $12.50 + $12.00; batch 50% off ([OpenAI](https://developers.openai.com/api/docs/pricing)) |
| **Cascade, Haiku stage 2** | **$61–103** | **$31–53** | encoder $1–3 + (15–25% escalation) × the Haiku price in the same column |
| **Cascade, nano stage 2** | **$4.68–9.13** | **$2.84–6.06** | encoder $1–3 + (15–25% escalation) × the nano price in the same column |

Worked at the router's central 20%, batch pricing: Haiku = $1–3 + 0.20 × $200 = **$41–43**. Nano = $1–3 + 0.20 × $12.25 = **$3.45–5.45**. Every cascade cell is those same two components, nothing else.

**The saving, stated like for like.** Same model, same pricing tier: Haiku batch $200 → $31–53 is **3.8–6.5×**; nano batch $12.25 → $2.84–6.06 is **2.0–4.3×**. Call it 2–7×. Larger multiples come from pricing a Haiku standard full pass against a nano batch cascade, which moves two variables at once.

The cost case is solid. The quality case is not yet made: no F1 exists for any of these models on Reddit brand sentiment (§2), so "the LLM resolves what the encoder botched" is the cascade's premise, not a measured result. The gold set in §7 is what tests it. If tail accuracy does not beat stage 1, the router is only spending money.

---

## 5. Hard cases and how each is handled

| Case | Failure at document level | Handling |
|---|---|---|
| **Sarcasm** ("support is *fantastic*, only waited nine days") | Lexical cues point positive | Sarcasm detector as a router signal, escalate to Stage 2. Literature treats sarcasm as sentiment-inverting and context-dependent ([Computers 14(3):95](https://www.mdpi.com/2073-431X/14/3/95)) |
| **Negation** ("not a fan of Brand X's pricing") | Cue exists, scope missed | Solved by construction in targeted formulation; negation-in-scope is a router trigger |
| **Comparative** ("Brand Y beats Brand X") | One label, two opposite targets | COQE-shaped; always escalated |
| **Recommendation without sentiment** ("try Brand D") | Collapsed into positive, inflating every brand uniformly | Separate `RECOMMENDED` label, excluded from `N_opinionated` (INFERENCE — design conclusion, not a cited finding) |
| **Complaint about the category** ("all these CRMs are bloated, including X") | Category gripe attributed to the brand | Attribution check at Stage 2; labelled category-negative, not brand-negative |
| **Quoted criticism** (commenter quotes, then disagrees) | Quoted polarity credited to the commenter | Stage 0 strips `>` blocks into a separate field before classification |
| **"Switched from X to Y"** | Two polarities in one clause | Pure TABSA case; per-span labels, always escalated |

⚠️ On sarcasm: the widely repeated claim that it costs ~50% of sentiment accuracy could not be traced to a primary paper. **Treat it as folklore, not a figure.**

---

## 6. Bot and astroturf filtering runs first

Filtering after sentiment means the ranking has already been computed on contaminated input. Run it at stage 1, before any polarity is assigned.

Converging signals: account age and karma, posting velocity, inter-comment reply time, subreddit spread, co-voting inside tight windows, and cross-account linguistic fingerprints ([Conbersa, vendor source](https://www.conbersa.ai/learn/reddit-bot-detection-2026)). Roughly 74% of accounts in documented astroturf campaigns show co-post coordination rare among organic users ([arXiv 2408.01257v2](https://arxiv.org/html/2408.01257v2)).

⚠️ **There is no Botometer equivalent for Reddit.** Tooling is thin and dated ([pushshift/Reddit-Bot-Detector](https://github.com/pushshift/Reddit-Bot-Detector)), and Pushshift access restrictions broke most existing pipelines. We build our own account-feature classifier; a drop-in does not exist.

### The conflict of interest, both directions

Empact Partners runs Reddit marketing for paying partners and also operates UGC Ranks. That is two separate exposures, and the stage-1 filter closes only one of them.

**Inbound contamination.** Comments an Empact campaign produced or prompted are not organic sentiment about the brands involved. They must be identifiable from our own campaign records, tagged at stage 1, and excluded from published scores, with the exclusion rate reported per category and per brand.

**Operator incentive.** An Empact partner, a Qvery competitor, or an outreach target sitting in a published ranking gives the operator a reason to shade the number — and [11-outreach-play.md](11-outreach-play.md) sells the fix for the metric this site publishes. Two controls, neither optional:

- **Disclosure.** Current partners and related entities (Empact Partners, Qvery, MarketSplash, Mystery Demo) are listed on `/methodology`. Any ranked or profiled brand on that list carries a visible "Empact Partners works with this company" label on its brand page.
- **Blind scoring.** Partner status is not an input to any stage of this pipeline, is not shown to annotators in the stage-6 human loop, and is never a reason to suppress, delay, or re-run a score. Suppression happens only through the published eligibility rules in [07-index-methodology.md](07-index-methodology.md).

**What those controls do not fix.** Recusal — Empact not running Reddit marketing in any category UGC Ranks ranks — is the only control that removes the incentive rather than disclosing it. It is not proposed, because it would mean closing the service that funds the site. Disclosure plus blind scoring stands in its place, and that gap is the exposure.

---

## 7. Validation protocol

**Gold set.** 1,000–1,500 comments stratified by brand, subreddit, comment length, and predicted class. Minority (negative) classes need ≥150–200 items to mean anything. Hold out a second 500-item set nobody looks at until the end.

**Annotators.** At least two, working independently, with adjudication of disagreements. Report **Krippendorff's α per class**, not raw agreement.

**Expected agreement.** Practitioner thresholds put inherently subjective tasks at **α 0.60–0.75**, with sarcasm legitimately below 0.35 ([datavlab guide](https://datavlab.ai/post/inter-annotator-agreement-llm-evaluation-guide)). Reporting practice 2018–2025 is surveyed in [arXiv 2606.02255](https://arxiv.org/abs/2606.02255).

⚠️ **`/methodology` discloses the measured α, per class, including the sarcasm collapse.** An α of 0.65 disclosed is credible; an α of 0.65 concealed is what a journalist finds later.

**LLM-as-annotator** is an accepted pattern for fine-grained opinion spans ([arXiv 2601.16800](https://arxiv.org/pdf/2601.16800)), but only after it demonstrably hits human-human α on our data.

---

## 8. Neutral, abstain, and the denominator

Thresholds are calibrated on the gold set, never inherited from softmax defaults. Below-threshold items route to Stage 2, then to humans, and if still unresolved they land in `abstain`.

**Scores are computed over opinionated mentions only: `N_opinionated = pos + neg`.** Neutral mentions are excluded from the denominator rather than scored as half-positive, and abstentions never silently vanish into it. [07-index-methodology.md](07-index-methodology.md) specifies how that denominator enters the estimator.

That is why `neutral_share` and `abstain_share` are first-class outputs of this pipeline, emitted per brand and per category and published beside every score. They are the two numbers that tell a reader how much of the evidence a score is actually built on.

Worked case. A ubiquitous tool draws 4,000 mentions, 3,600 of them plumbing chatter — "export it to X", "the X API" — carrying no opinion. `N_opinionated = 400`. Publishing 4,000 as the sample size would be a lie of denominator; publishing 400 with `neutral_share = 0.90` is the honest version.

The same logic applies upward. A score resting on 40% of a brand's mentions with 60% abstained is a materially different claim from one resting on 90%. Dropping abstentions quietly turns the second claim into the first, which is why both shares ship on the page and not only in the data files.

---

## 9. Standing risk note

Brand pages display **full Reddit comment text** with links back to the source thread. That is a deliberate owner decision, taken with the contractual and copyright exposure understood and priced ([0002-display-full-mentions.md](decisions/0002-display-full-mentions.md)). It is not a compliant design.

It bears on this document in one way: a misclassified comment is a verbatim quotation published under a "Most Hated" heading ([0005-superlative-labels.md](decisions/0005-superlative-labels.md)), not merely a wrong data point.

---

[← Back to README](README.md) · [05-entity-resolution.md](05-entity-resolution.md) · [07-index-methodology.md](07-index-methodology.md)
