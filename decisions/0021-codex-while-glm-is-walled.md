# 0021 — Codex labels the residue while GLM's allowance is used up

Date: 2026-10-07. Status: accepted (Vlad: "continue at full speed").

## Context

The classifier is Jev in front and GLM-5.3 on what Jev cannot settle (decision 0017). On 7 Oct Z.ai refused every GLM
call: "Weekly/Monthly Limit Exhausted. Your limit will reset at 2026-10-10 21:12:22". The allowance is shared with the
other projects on the plan. Jev alone settles 12-34% of the newest mentions, so about 300,000 would wait three days.

## Decision

A laptop-only lane, `ops/codex_lane.py`, labels what Jev looked at and could not settle (`classify_queue.jev_checked_at`,
migration 0029) with Codex `gpt-5.6-luna` at low effort, no web search, through the estate's Codex job standard
(`codex_job`: the no-search clause, the pilot's events checked, a weekly ceiling). The prompt is GLM's: the calibrated
rubric verbatim. Labels carry their model (`gpt-5.6-luna-absa-1`).

- Codex is the ChatGPT subscription and never goes on a server: the lane runs on the laptop.
- Amended the same day (Vlad: "use Codex instead of GLM, go for it"): the lane runs Jev itself on what Jev has not
  seen, then Codex on the rest, over the backlog older than 26 hours from the HIGH end of the brand order (the sweep's
  classify takes the newest and starts at the low end). It makes no Reddit calls, so it runs at any hour, under the
  day's 2 GB egress line on the node counter (at 1.90 GB it waits for the next UTC day), and stops at a Codex weekly
  ceiling of 45%. One receipt per UTC day (stage `repair`), so the schedule check sees its writes. It ends on
  11 Oct 00:00 UTC, when GLM's allowance is back.
- First batch (60 mentions from the alphabetical tail): Jev settled 24, Codex 35; 58 were not the product
  ("user flow" is not Userflow, "what converts" is not WhatConverts).
- When GLM's allowance returns, the lane stops being needed: GLM takes the residue again and the lane is not started.

## Evidence (pilot, 7 Oct, 400 mentions GLM had already judged: 300 labels, 100 rejections)

| Model | Agreement with GLM | Rejections agreed | Input tokens per mention | Web searches |
|---|---:|---:|---:|---:|
| gpt-5.6-luna, low | 85.8% | 91 of 100 | 586 | 0 |
| gpt-5.6-terra, low | 83.0% | 89 of 100 | 617 | 0 |

The methodology already reports 85% pairwise agreement between the earlier engines; luna is on par, terra below it
and dearer. Luna's main difference: it calls 28 of GLM's 228 neutral mentions positive or negative.

## Cost

About 590 input tokens a mention: 200,000 mentions is about 120M tokens, 8 to 12% of a Codex week. Egress is the
reading of the 1,200-character windows and the label writes, inside the day's line.

## Amendment, 9 Oct: Claude on the Max plan as a second engine

Vlad, 9 Oct: "use my Claude Code max tokens for now". The Codex week stood at 59% (other sessions included) against
the lane's 60% ceiling, and GLM was still walled. `ops/codex_lane.py` gains a Claude engine (`--model claude-…`):
the same rubric verbatim and the same answer shape, through the locked-down `claude -p` helper
(`~/.claude/api_helpers/claude_cli.py`: no tools, no user settings, no MCP), 40 mentions a call, 3 in flight,
each batch's answer kept on disk. A usage-limit answer stops the lane, so it never eats into Vlad's own sessions.

Pilot, the same 400 GLM-judged mentions (300 labels, 100 rejections):

| Engine | Agreement with GLM | Rejections matched | Minutes | Where it disagrees |
|---|---|---|---|---|
| Codex gpt-5.6-luna, low (7 Oct) | 85.8% | 91/100 | | |
| Claude Haiku 4.5 | 80.0% | 80/100 | 3.5 | calls neutral comments positive (26) or negative (19) |
| **Claude Sonnet 5.5** | **85.0%** | **95/100** | **0.8** | toward neutral (neg→neu 18, pos→neu 11): the safe side of a lower-bound score |

Sonnet 5.5 runs the lane (`claude-sonnet-5-5-absa-1`).
