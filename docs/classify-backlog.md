# Classifying mentions: who judges, how it was measured, what it costs

Written 2026-10-02. Code: `worker/classify_sweep.py` (the stage), `ops/classify_backlog.py` (the one-time
backlog), `ops/classify_calibrate.py` and `ops/classify_glm_pilot.py` (the measurements),
`worker/resolve.py: address_names_product` and `ops/reject_parent_addresses.py` (the address rule).

## Why it had to be rebuilt

Nothing classified a mention after 25 August 2026. The old lane ran on DeepSeek, whose key died with the laptop
in August and whose provider the estate has retired. By 2 October, 959,245 of 1,437,879 stored mentions had no
label, and the old classifier's "not this product" verdicts had only ever been kept in a file on that laptop.

## Who judges now

1. **A rule, before any model.** A mention that is only a link to a parent company's web address (github.com
   filed under GitHub Actions, google.com under Google Sheets, apple.com under Keynote) is "not this product".
   171,263 stored mentions were recorded that way on 2 October; 1,010 more on the same addresses also name the
   product in their text and go to the judges. The resolver no longer creates such mentions. Undo: delete the
   rows with `model_version = 'rule-parent-address-1'` from `public.mention_rejections`.
2. **Jev** (TypeSafe, pinned `jev-1.13.0`) answers two separate questions for every mention, twenty to a
   request: is the marked word this product, and how does the author feel about it. It settles a mention only
   when both answers clear thresholds measured on a dev split (below).
3. **GLM-5.3** judges everything else, with the old rubric word for word, a hundred mentions a job, through the
   official Codex CLI, never in Z.ai's peak hours (06:00 to 10:00 UTC).
4. **Neither** answered: the mention stays in `public.classify_queue`, counted on the receipt as not checked,
   asked again next run (up to five times). It is never scored as anything.

## How the judges were measured (2 October, all numbers on stored mentions)

| Set | What it is |
|---|---|
| ordinary | 5,000 mentions already labelled by the old engines, drawn at random |
| hard | 1,000 of the 2,837 mentions the old engines disagreed on and re-judged |
| entity | the 190 mentions read by hand for the investigation; 43 are not about their brand |

**The old labels are not a gold standard.** On 350 mentions, both GLM models called about 40 to 50% of the old
positive and negative labels "no opinion". Read by hand, 53 of those cases: GLM was right about 15 times, the old
label about 6, the rest could go either way. The old engines gave opinions to mentions that held none.

**Flash or full GLM-5.3.** Same 350 mentions, same rubric:

| | GLM-5.3-Flash | GLM-5.3 |
|---|---|---|
| known "not this product", rejected | 37 of 43 | 34 of 43 (30 of 43 on the larger run) |
| genuine products wrongly rejected | 1 of 147 | 2 of 147 (1 of 147 on the larger run) |
| real opinions kept, read by hand | missed Cloudflare "great for DNS", a Wix price complaint, "that's Reddit" | kept them |
| credits per mention, off-peak | about 0.07 | about 0.12 |

GLM-5.3 judges. On 2,390 mentions it agreed with the old labels 81.5% of the time (91.5% on the hard set).

**Jev is calibrated against GLM-5.3's answers**, so a mention Jev settles gets the label GLM-5.3 would have
given it. Thresholds chosen for 96% agreement on the full set, then checked held out (chosen on one half, scored
on the other, twenty random splits, `report.held_out` in the thresholds file): Jev settles 36.5% of mentions on
average (never less than 32.7%) at 95.6% agreement with GLM-5.3 (never less than 93.6%); on the full set it agrees
with the old labels 88.9% of the time, more than GLM-5.3's own 81.5%. Pinned in
`ops/classify_thresholds.json`: product at 0.90 (lets 1 of the 43 hand-checked non-product mentions through),
positive 0.76, negative 0.81, no opinion 0.77, reject below 0.20 (0.4% of ordinary mentions).

Measured cost of the measurements: Jev $0.13; GLM about 330 credits.

## Budgets for the one-time backlog (declared before the first job)

| | Ceiling | Why |
|---|---|---|
| GLM-5.3 | 60,000 credits in total (43% of one week's plan), at most 20,000 a run, 8 jobs in flight, never 06:00-10:00 UTC | about 794,000 queued after the address rule, 64% to GLM at about 0.12 credits each is about 59,000 |
| Jev | $60 in total | about $16 projected |
| Database egress | 1.5 GB in total, at most 0.5 GB a UTC day (the text read plus the write-ahead log) | about 1.6 KB read per mention |

The runner reads what earlier runs spent from `public.pipeline_runs` (stage `classify-backlog`) and stops at
whichever ceiling comes first. It shares the daily sweep's lock, so the two never overlap.

## The daily stage

`ops/schedule.json` → `classify`: GLM-5.3, at most 3,000 credits and $1 of Jev a run, 60,000 mentions. A normal
day of about 18,000 new mentions projects to about 1,350 credits and $0.40.

## Known limit

Mentions labelled before 25 August carry the old engines' labels, which give more opinions than GLM-5.3 does.
Pages mix the two until the old labels are re-judged (about 481,000 mentions, about 36,000 credits at the same
mix): an open item, not part of the backlog budget above.
