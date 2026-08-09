# Sentiment — the four-way verdict

The unit is **(document, target brand)**, not the document: "we moved off
HubSpot to Pipedrive" is one negative for HubSpot and one positive for
Pipedrive. The target is marked inline (`<<TARGET:name>>`) inside a window
of the comment so a 6,000-character rant cannot drown the thing being judged.

## Labels

| label | meaning | enters the score? |
|---|---|---|
| pos | the author is positive about this product | yes |
| neg | negative about this product (price complaints count) | yes |
| neu | named without an opinion — lists, questions, "we use X" | no (published) |
| abstain | the judge can't tell (sarcasm risk defaults here) | no (published) |

Hard rules baked into the prompt: switching away is negative for the origin
and positive for the destination; a category-wide gripe is not a gripe about
this product; quoted text is not the author's opinion; `entity_ok=false`
(the span isn't this product at all — the weekday, the herb) DROPS the
mention rather than labelling it.

## Engines

Classification runs on subscription compute, never metered APIs:

- **Codex fleet (gpt-5.6-luna)** — the production engine: 40-item batches,
  40 concurrent, disk-idempotent out-files, an item-level label cache shared
  across every run so nothing is ever judged twice.
- **Claude (`claude -p`, Haiku)** — the original engine; still legal for
  small runs, STRICTLY serial (concurrent headless sessions wedge).

Measured cross-engine agreement on a held-out set: **81% exact on the 4-way
label, 96% on polarity** (3 pos↔neg flips in 80) — around human
inter-annotator range for this task.

`mention_sentiment.model_version` records the *pipeline* version; the
engine that produced each label is recorded per-item in the cache. The
published views pin one model_version so a pipeline change is a deliberate
re-publish, never a silent drift.
