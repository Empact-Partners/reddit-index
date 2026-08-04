# Sentiment Classification

## Bottom line

- **Document-level sentiment is the wrong task.** One Reddit comment naming three brands has one document label and up to three different target polarities. The correct formulation is targeted / aspect-based sentiment (TABSA/ABSA), emitting `(brand_mention, polarity)` per span.
- Off-the-shelf **VADER, SiEBERT, and twitter-roberta all emit document labels** and will systematically mis-rank brands in exactly the comparative threads that carry the most signal.
- **No single model wins.** Fine-tuned encoders beat zero-shot LLMs on structured ABSA (XLM-R **68.86 F1** vs GPT-4o **49.85**, SemEval-2016 five-language, [arXiv 2412.12564v3](https://arxiv.org/html/2412.12564v3), Dec 2024), but LLMs win the hard cases encoders silently botch. Hence a cascade.
- **Cascade cost ≈ $45–85 per 1M comments** (Haiku stage 2), or ≈ $8–15 with a nano-class stage 2, versus $400 for LLM-everything. All totals are our arithmetic, marked INFERENCE.
- ⚠️ **Bot / astroturf filtering runs BEFORE sentiment, never after.** Empact Partners runs Reddit marketing for its own partners, so Empact-influenced threads must be detectable and excluded. This is a conflict-of-interest control, not only a data-quality one.
- **Validation is the first thing built, not the last.** 1,000–1,500 stratified human-labelled comments, ≥2 annotators, Krippendorff's α reported per class on the published methodology page.

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

**Correct formulation.** Input `(comment_text, target_span, thread_context)`. Output `polarity ∈ {pos, neg, neu, unclear}`, plus `is_comparative` and `is_recommendation` flags. Target spans come from the mention detection described in [05-entity-resolution.md](05-entity-resolution.md).

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
| 5 | **Stage-2 LLM** | Claude Haiku 4.5 Batch API or gpt-5-nano, structured output: per-target polarity, `is_comparative`, `is_recommendation`, `abstain` | Resolved labels for the hard tail |
| 6 | Human loop | Stage disagreements plus a random 1% sample, 2 annotators, adjudication | Gold labels, retraining set |
| 7 | Aggregate | Per-brand pos/neg/neu with coverage %, abstain %, suspect share, bootstrap CIs ([07-index-methodology.md](07-index-methodology.md)) | Published ranking inputs |

Build stage 6 and the gold set **first**. Every other stage is unmeasurable without them.

---

## 4. Cost per 1M comments

Assumptions, which drive everything: ~250 input tokens per item (comment, parent, thread title, instruction) and ~30 output tokens. **All totals below are our arithmetic — INFERENCE, not quoted totals.** Unit prices are quoted.

| Approach | Standard | Batch | Basis |
|---|---|---|---|
| Local transformer (DeBERTa-v3, `g5.xlarge`) | **$1–3 all-in** | — | $1.006/hr on-demand, $0.4419/hr spot ([Vantage](https://instances.vantage.sh/aws/ec2/g5.xlarge)); ~500 items/s ⇒ ~33 min |
| Claude Haiku 4.5, everything | **$400** | **$200** | $1.00 / $5.00 per MTok, Batches 50% off ([Anthropic](https://platform.claude.com/docs/en/pricing)) |
| GPT-5-nano, everything | **$25** | **$12** | $0.05 / $0.40 per MTok, batch 50% ([OpenAI](https://developers.openai.com/api/docs/pricing)) |
| **Cascade, Haiku stage 2** | — | **≈$45–85** | Encoder over 1M + ~20% tail at Haiku batch (~$40) |
| **Cascade, nano stage 2** | — | **≈$8–15** | Encoder over 1M + ~20% tail at nano batch (~$5) |

The cascade is a 5–50× saving over LLM-everything at materially better quality on the hard tail. That is the entire argument for it.

---

## 5. Hard cases and how each is handled

| Case | Failure at document level | Handling |
|---|---|---|
| **Sarcasm** ("support is *fantastic*, only waited nine days") | Lexical cues point positive | Sarcasm detector as a router signal, escalate to Stage 2. Literature treats sarcasm as sentiment-inverting and context-dependent ([Computers 14(3):95](https://www.mdpi.com/2073-431X/14/3/95)) |
| **Negation** ("not a fan of Brand X's pricing") | Cue exists, scope missed | Solved by construction in targeted formulation; negation-in-scope is a router trigger |
| **Comparative** ("Brand Y beats Brand X") | One label, two opposite targets | COQE-shaped; always escalated |
| **Recommendation without sentiment** ("try Brand D") | Collapsed into positive, inflating every brand uniformly | Separate `RECOMMENDED` label, excluded from polarity aggregation (INFERENCE — design conclusion, not a cited finding) |
| **Complaint about the category** ("all these CRMs are bloated, including X") | Category gripe attributed to the brand | Attribution check at Stage 2; labelled category-negative, not brand-negative |
| **Quoted criticism** (commenter quotes, then disagrees) | Quoted polarity credited to the commenter | Stage 0 strips `>` blocks into a separate field before classification |
| **"Switched from X to Y"** | Two polarities in one clause | Pure TABSA case; per-span labels, always escalated |

⚠️ On sarcasm: the widely repeated claim that it costs ~50% of sentiment accuracy could not be traced to a primary paper. **Treat it as folklore, not a figure.**

---

## 6. Bot and astroturf filtering runs first

Filtering after sentiment means the ranking has already been computed on contaminated input. Run it at stage 1, before any polarity is assigned.

Converging signals: account age and karma, posting velocity, inter-comment reply time, subreddit spread, co-voting inside tight windows, and cross-account linguistic fingerprints ([Conbersa, vendor source](https://www.conbersa.ai/learn/reddit-bot-detection-2026)). Roughly 74% of accounts in documented astroturf campaigns show co-post coordination rare among organic users ([arXiv 2408.01257v2](https://arxiv.org/html/2408.01257v2)).

⚠️ **There is no Botometer equivalent for Reddit.** Tooling is thin and dated ([pushshift/Reddit-Bot-Detector](https://github.com/pushshift/Reddit-Bot-Detector)), and Pushshift access restrictions broke most existing pipelines. We build our own account-feature classifier; a drop-in does not exist.

**The conflict of interest.** Empact Partners runs Reddit marketing for paying partners and also operates UGC Ranks. Comments its campaigns produced or prompted are not organic sentiment about the brands involved.

Empact-influenced threads must be identifiable from our own campaign records, tagged, and excluded from published scores, with the exclusion rate reported per category. This is a governance control on the operator, not a data-hygiene nicety.

---

## 7. Validation protocol

**Gold set.** 1,000–1,500 comments stratified by brand, subreddit, comment length, and predicted class. Minority (negative) classes need ≥150–200 items to mean anything. Hold out a second 500-item set nobody looks at until the end.

**Annotators.** At least two, working independently, with adjudication of disagreements. Report **Krippendorff's α per class**, not raw agreement.

**Expected agreement.** Practitioner thresholds put inherently subjective tasks at **α 0.60–0.75**, with sarcasm legitimately below 0.35 ([datavlab guide](https://datavlab.ai/post/inter-annotator-agreement-llm-evaluation-guide)). Reporting practice 2018–2025 is surveyed in [arXiv 2606.02255](https://arxiv.org/abs/2606.02255).

⚠️ **The published methodology page discloses the measured α, per class, including the sarcasm collapse.** An α of 0.65 disclosed is credible; an α of 0.65 concealed is what a journalist finds later.

**LLM-as-annotator** is an accepted pattern for fine-grained opinion spans ([arXiv 2601.16800](https://arxiv.org/pdf/2601.16800)), but only after it demonstrably hits human-human α on our data.

---

## 8. Low-confidence classifications

Thresholds are calibrated on the gold set, never inherited from softmax defaults. Below-threshold items route to Stage 2, then to humans, and if still unresolved land in a **neutral/unclear bucket**.

That bucket is a first-class published label, not a bin. Coverage % and abstain % ship next to every ranking, per brand and per category.

A ranking over 40% of mentions with 60% abstained is a materially different claim from one over 90%. Silently dropping abstentions turns the second claim into the first. See [07-index-methodology.md](07-index-methodology.md) for how coverage enters the score.

---

## 9. Standing risk note

Brand pages display **full Reddit comment text** with links back to the source thread. That is a deliberate owner decision, taken with the contractual and copyright exposure understood and priced. It is not a compliant design.

It bears on this document in one way: a misclassified comment is a verbatim quotation published under a "most hated" heading, not merely a wrong data point.

---

[← Back to README](README.md) · [05-entity-resolution.md](05-entity-resolution.md) · [07-index-methodology.md](07-index-methodology.md)
