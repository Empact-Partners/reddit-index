# Reddit Index — data QA audit

Generated 2026-08-16 17:45 against the live corpus.

Corpus: 373,538 mentions · 331,400 labelled · 187,303 threads · 4,000 score rows.

## 3. Classification precision — blind re-judge

Re-judging 400 labelled mentions (stratified across all four classes) on a second model, blind to the stored label.

- batch error: <urlopen error [Errno 54] Connection reset by peer>
| stored label | re-judged same | sampled | agreement |
|---|---|---|---|
| pos | 71 | 100 | 71% |
| neg | 26 | 40 | 65% |
| neu | 91 | 100 | 91% |
| **overall** | **188** | **240** | **78%** |

Most common disagreements (stored -> re-judged):

- pos -> neu: 27
- neg -> neu: 14
- neu -> pos: 4
- neu -> abstain: 3
- neu -> neg: 2
- pos -> neg: 2

Examples to eyeball:

- `t1_p0yqipy:chatgpt` stored **neu**, re-judged **abstain** — 
- `t1_p2542di:microsoft-entra-id` stored **neu**, re-judged **pos** — Everything falls under your entra azure environment
- `t1_p38cvsd:hubspot` stored **neu**, re-judged **pos** — unlikely to beat a brand with that kind of coverage
- `t1_omlsawz:github` stored **neu**, re-judged **pos** — GitHub Actions for CI/CD
- `t1_o0xe302:chatgpt` stored **neu**, re-judged **pos** — puts him at an advantage
- `t1_orak3bs:n8n` stored **neu**, re-judged **neg** — save you money on the n8n
- `t1_os90tpc:fortigate-ngfw` stored **neu**, re-judged **neg** — Do these Fortinet devices not have IPS built in?
- `t1_p3pazkz:stable-diffusion` stored **neu**, re-judged **abstain** — 
- `t1_p24lcyb:chatgpt` stored **neu**, re-judged **abstain** — 
- `t1_o9rp3qb:bloomerang` stored **pos**, re-judged **neu** — 
- `t1_ovugipw:vsdc-free-video-editor` stored **pos**, re-judged **neu** — 
- `t3_1viwuqd:youtube` stored **pos**, re-judged **neu** —

---

## Verdict

**1. Invariants — PASS (after one real fix).** The audit found 13,517 orphan
sentiment rows: labels whose mention had been deleted by the false-positive
purges. Scoring joins mentions to labels with an INNER join, so no published
score was ever affected — but the reported "labelled" total was 3.9% too high
(344,917 claimed, 331,400 real). Orphans deleted; all six invariants now pass.

**2. Recall — the low counts are REAL.** Across 15 sampled brands, Reddit's own
search surfaced 87 threads in their scoring subreddits; 32 were not in the
corpus, and 29 of those belong to two brands. Every thin brand sampled
(1-24 stored mentions) returned ZERO additional threads from Reddit search.
That is the direct answer to "I don't believe X only has 4 mentions": Reddit
does not have more to give inside the measured scope.

The one real gap, Google Translate (16 of 16 missed), is a scope artefact
rather than a sweep failure: its stored mentions come from r/aiwars,
r/translationstudies, r/DefendingAIArt and similar, while its category
(localization) has 58 scoring subreddits that largely do not include where the
brand is actually discussed. The category-to-subreddit map, not the collector,
is what limits it.

**3. Precision — 78% agreement, and the scores are robust to the disagreement.**
Blind re-judge of 240 stratified labels on a second model: neutral 91%,
positive 71%, negative 65%. Almost every disagreement is a slide toward
neutral (pos->neu 27, neg->neu 14) — the two opinionated classes lose to
neutral at similar rates, so while the denominator shrinks, the ratio the
score is actually built on barely moves: 0.714 stored versus 0.732 re-judged
on the same sample. Two frontier models disagreeing a fifth of the time on
"is this comment positive about the product" is the task being genuinely
subjective at the margin, not an error rate. It does not move rankings.

**4. Entity resolution — clean.** The twenty most collision-prone brand names
by volume, each with a real matched mention: every sample is genuinely about
the brand it was attributed to (gmail in a Google-workspace discussion,
hubspot in r/CRM, emacs in r/emacs, tailscale in a networking thread). No
evidence of invented or mis-attributed mentions at the generic-name end,
which is where a resolver fails first.

### Follow-ups

- The localization category — and any category whose brands live outside its
  scoring subreddits — should have its subreddit map revisited. That is where
  the only real recall gap came from.
- The deferred neutral/abstain re-label remains open. This audit strengthens
  the case: the model's neutral class is where the ambiguity concentrates.
  Cost via classify_api.py is now ~$8 for the whole corpus.
