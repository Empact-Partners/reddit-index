# Sentiment — the four-way verdict

The unit is **(document, target brand)**, not the document: "we moved off
HubSpot to Pipedrive" is one negative for HubSpot and one positive for
Pipedrive. The target is marked inline (`<<TARGET:name>>`) inside a
1,200-character window of the document so a 6,000-character rant cannot
drown the thing being judged.

A document is a comment (`doc_type 1`) or a post (`doc_type 2`), and a
post's document is **its title plus its selftext**. That matters here and
not only in collection: a headline is where Reddit names brands most often,
so the judge now sees "Anyone moved off HubSpot?" as text to label rather
than as context it was never shown. A link post, whose selftext is empty, is
judged on its title alone — before 2026-08-17 it produced no document at all.

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

Classification runs through **`worker/classify_api.py`**: provider pools
pulling from one shared backlog cursor, batches of 40, each batch cached to
disk before it is committed so a crash never loses paid work. Two providers:

- **`claude -p` Haiku (`haiku-4.5-absa-1`)** — 16 workers by default, free
  on the Max plan, one local process per worker.
- **DeepSeek `deepseek-v4-flash` (`deepseek-v4-flash-absa-1`)** — plain HTTP,
  **metered**, and **switched off by ruling** since 2026-08-17: it needs
  `--allow-metered` on top of `--deepseek N` or the run refuses to start.
  It was used deliberately once — $27.22 of credit labelled 153,748 items in
  112 minutes at ~1,100 items/min during the 2026-08-16 backlog — which is why
  its labels are in the corpus. Classification is now free Haiku only; when a
  backlog is deep, it drains overnight rather than for money.

The corpus carries three `model_version` values — `claude-cli-absa-1` (the
original `claude -p` lane in `worker/classify.py`),
`deepseek-v4-flash-absa-1` and `haiku-4.5-absa-1`. On the cross-check below
the lanes produced an identical label distribution, so which one judged a
row does not move `n_op` or `pos/(pos+neg)`.

**Codex is retired** (commit 071de98). `classify_codex.py` and
`classify_daemon.py` are still on disk because `classify_api.py` imports
the prompt from the first and the backlog cursor from the second; nothing
imports `classify_daily.py` and nothing runs any of the three as a driver.
The reason is not preference. `codex exec` is an agent session, not
an API call: it reasons, and our prompt then made it write a file, which
costs a second tool round trip. Measured on ONE identical 40-item batch —

| lane | wall time | cost |
|---|---|---|
| `codex exec` (the old production path) | >600s, timed out | subscription |
| `claude -p` haiku 4.5 | 108s | free, Max plan |
| deepseek-v4-flash (HTTP) | 84s | metered |
| Anthropic API haiku (HTTP) | 21s | metered |

— and all three non-codex lanes agreed with codex's own labels on 34/40 =
85% while producing the IDENTICAL label distribution (neu 22 / pos 12 /
neg 6).

The concurrency lesson is worth keeping because it cost a morning: 100
concurrent codex processes looked safe on memory (119 procs, 1.8 GB) and
returned zero batches in 13 minutes. A local agent process costs kernel
scheduling, not RAM. So `classify_api.py` never trusts a resource gauge
alone — it reports completed ITEMS PER MINUTE and the operator ramps on that
number. HTTP lanes can go wide; the CLI pool is a local process per worker
and is ramped carefully. (The older rule that `claude -p` must run *strictly
serial* is obsolete: 16 CLI workers is the tested default.)

Measured cross-engine agreement on an 80-item held-out set, Claude against
Codex: **81% exact on the 4-way label, 96% on polarity** (3 pos↔neg flips) —
around human inter-annotator range for this task. That measurement predates
the Codex retirement and stands as the engine-substitutability evidence
behind it, alongside the 40-item check above.

`mention_sentiment.model_version` records **which lane produced the label**.
The insert conflicts on `(doc_id, brand_id, model_version)` rather than on
the pair, so the schema permits one row per lane per mention; no pair
carries two today, because a decided item is skipped from disk before it is
ever sent again.

The published `published.mentions` view therefore takes the **most recently
scored label per (doc, brand)**, with `model_version` as a deterministic
tiebreak. It used to pin one `model_version` read out of
`methodology_params`, which was correct while one engine labelled everything
and became a silent outage when the corpus went multi-engine: the frozen
parameter now reads `multi-lane`, which matches no row, and **115,820 labels
were invisible to the site** until the pin was lifted by hand on 2026-08-16
(commit 74923ce). That hand-edit existed in no file, so the next
`supabase db push` onto a fresh database would have blanked every sentiment
on the site again. `supabase/migrations/0003` writes it down. A re-label now
wins by being newer, not by matching a string.

One frozen row is knowingly stale and cannot be repaired in place:
`methodology_params` is append-only, and its newest `sentiment_engine` value,
written at 2.2.0, still reads `codex_fleet_local_subscription`. Correcting it
is a version bump, not an edit. Until then this page and the code are the
authority on which engine ran.
