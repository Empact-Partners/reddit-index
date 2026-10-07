#!/usr/bin/env python3
"""The Codex lane for the classifier's residue while GLM's plan allowance is used up (2026-10-07).

GLM is the classifier's second judge. When Z.ai refuses with "Weekly/Monthly Limit Exhausted", Jev still settles what
it is sure of and marks the rest (classify_queue.jev_checked_at); everything else waits for GLM. The doctrine routes a
walled GLM lane to Codex (no search, explicit low effort, through codex_job). This lane runs on the LAPTOP only: Codex
is the ChatGPT subscription, which never goes on a server.

  * The prompt is GLM's, the calibrated rubric verbatim (worker/rubric.py), with the output asked as a JSON object per
    item (Codex's --output-schema). codex_job adds the no-search clause and checks the pilot's events for searches.
  * Every label carries its model, e.g. gpt-5.6-luna-absa-1, so it can be told apart and re-judged.
  * Daytime only (05:30 to 23:40 UTC: the night belongs to the sweep), under the day's 2 GB egress line read on the
    node counter (stops at 1.90 GB, the same mark as ops/day_passes.py), and under a Codex weekly ceiling.

  ops/codex_lane.py pilot --model gpt-5.6-luna            # 300 GLM labels + 100 GLM rejections, compared; writes nothing
  ops/codex_lane.py run --model gpt-5.6-luna --ceiling 45 # label the residue (run it through ops/backfill_run.py)
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, d) for d in ("worker", "ops", "scripts")]
sys.path.insert(0, os.path.expanduser("~/Projects/claude-sops/scripts/lib"))

import classify_sweep as cs  # noqa: E402
from codex_job import LaneSpec, SearchPolicy, make_job, run_wave, job_usage  # noqa: E402

STATE = Path(os.path.expanduser("~/Library/Application Support/reddit-index-codex"))
PER_JOB = 50
LINE_GB = 1.90
OUTPUT = ("Also return:\n"
          "  confidence  0.0 to 1.0, how sure you are of the label\n"
          "  entity_ok   false if the marked span is NOT this software product at all —\n"
          "              the weekday, the herb, the verb, a different company's product\n\n"
          "Return ONE JSON object with an entry for every item id (i1, i2, ...): "
          "{\"label\": \"pos\"|\"neg\"|\"neu\"|\"abstain\", \"confidence\": number, \"entity_ok\": boolean}.")


def log(*a):
    print(f"[{dt.datetime.now(dt.timezone.utc):%H:%M:%S}]", *a, flush=True)


def prompt(items: list[dict]) -> str:
    blocks = [f"### i{n}\nsubreddit: r/{it['subreddit']}\nthread: {it['thread']}\nproduct: {it['brand_name']}\n"
              f"comment:\n{it['text']}" for n, it in enumerate(items, 1)]
    return (cs.GLM_RULES + "\n\n" + OUTPUT + "\n\nLabel each item below. Every id present, no id skipped.\n\n"
            + "\n\n".join(blocks))


def schema(n: int, d: Path) -> Path:
    p = d / f"schema_{n}.json"
    if not p.exists():
        one = {"type": "object", "additionalProperties": False, "required": ["label", "confidence", "entity_ok"],
               "properties": {"label": {"type": "string", "enum": ["pos", "neg", "neu", "abstain"]},
                              "confidence": {"type": "number"}, "entity_ok": {"type": "boolean"}}}
        ids = [f"i{k}" for k in range(1, n + 1)]
        p.write_text(json.dumps({"type": "object", "additionalProperties": False, "required": ids,
                                 "properties": {i: one for i in ids}}))
    return p


def judge(items: list[dict], model: str, stage: str, ceiling: float | None, width: int = 4) -> list[tuple | None]:
    """-> per item ("reject", conf) | (label, conf) | None (not answered: stays queued)."""
    d = STATE / stage
    out = d                                  # job_usage reads the events next to the outputs, in the state dir
    out.mkdir(parents=True, exist_ok=True)
    spec = LaneSpec(model=model, effort="low", policy=SearchPolicy(kind="none"), items_per_job=PER_JOB,
                    state_dir=d, chunk=24, stall_s=600, ceiling=lambda: ceiling)
    jobs, spans = [], []
    for s in range(0, len(items), PER_JOB):
        chunk = items[s:s + PER_JOB]
        # the key names exactly these items: a finished job is reused only for the same items in the same order
        key = "j" + hashlib.sha1("|".join(f"{i['brand_id']}:{i['doc_id']}:{i['created_utc']}" for i in chunk)
                                 .encode()).hexdigest()[:16]
        jobs.append(make_job(spec, key, prompt(chunk), schema(len(chunk), d), out, d))
        spans.append((s, len(chunk)))
    run_wave(jobs, spec, stage=stage, width=width, items_total=len(items), marker_dir=d, marker_name="CODEX_CEILING_HIT")
    verdicts: list[tuple | None] = [None] * len(items)
    for job, (s, n) in zip(jobs, spans):
        try:
            ans = json.loads(job.out.read_text())
        except (OSError, ValueError):
            continue
        for k in range(n):
            verdicts[s + k] = cs._glm_answer(ans.get(f"i{k + 1}"))
    return verdicts


def mv(model: str) -> str:
    return f"{model}-absa-1"


# ---------------------------------------------------------------------------------------------- pilot

def pilot(a) -> int:
    import db
    with db.connect() as c:
        lab = c.execute("select m.brand_id, m.doc_id, m.created_utc, s.label from public.mention_sentiment s "
                        "join public.mentions m on m.doc_id = s.doc_id and m.brand_id = s.brand_id "
                        "where s.model_version = 'glm-5.3-absa-1' and s.scored_at > now() - interval '4 days' "
                        "order by md5(s.doc_id || s.brand_id) limit 300").fetchall()
        rej = c.execute("select m.brand_id, m.doc_id, m.created_utc from public.mention_rejections r "
                        "join public.mentions m on m.doc_id = r.doc_id and m.brand_id = r.brand_id "
                        "where r.model_version = 'glm-5.3-absa-1' and r.rejected_at > now() - interval '4 days' "
                        "order by md5(r.doc_id || r.brand_id) limit 100").fetchall()
        truth = {(b, d): {0: "neu", 1: "pos", 2: "neg", 3: "abstain"}[l] for b, d, _, l in lab}
        truth.update({(b, d): "reject" for b, d, _ in rej})
        items = cs.fetch_items(c, [(b, d, t) for b, d, t, *_ in lab] + [(b, d, t) for b, d, t in rej])
    items.sort(key=lambda it: (it["brand_id"], it["doc_id"]))
    stage = f"pilot-{a.model}-{dt.date.today()}"
    t0 = time.time()
    v = judge(items, a.model, stage, None, width=a.width)
    agree, conf_m = 0, collections.Counter()
    answered = 0
    for it, x in zip(items, v):
        g = truth[(it["brand_id"], it["doc_id"])]
        c_ = x[0] if x else "none"
        answered += x is not None
        agree += c_ == g
        conf_m[(g, c_)] += 1
    use = job_usage(STATE / stage)
    toks = sum(r.get("input", 0) for r in use)
    print(json.dumps({"model": a.model, "items": len(items), "answered": answered, "agree_with_glm": agree,
                      "agreement": round(agree / max(1, answered), 3), "minutes": round((time.time() - t0) / 60, 1),
                      "input_tokens": toks, "input_per_item": round(toks / max(1, len(items))),
                      "searches": sum(r.get("searches", 0) for r in use),
                      "glm_vs_codex": {f"{g}->{c}": n for (g, c), n in sorted(conf_m.items())}}, indent=1))
    return 0


# ---------------------------------------------------------------------------------------------- run

def used_today() -> float:
    import day_passes
    return day_passes.used_today(None)


def run(a) -> int:
    import db
    stop_at = dt.time(23, 40)
    done = {"labelled": 0, "rejected": 0, "not_answered": 0, "batches": 0}
    cursor = (-1, "", dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc))
    with db.connect() as c:
        c.autocommit = True
        while True:
            now = dt.datetime.now(dt.timezone.utc)
            if now.time() >= stop_at or now.time() < dt.time(5, 30):
                log("outside 05:30-23:40 UTC: the night belongs to the sweep; stopping")
                break
            try:
                u = used_today()
            except Exception as e:  # noqa: BLE001 - no reading, no run: the line is the rule
                log(f"no egress reading ({e}); stopping")
                break
            if u >= LINE_GB:
                log(f"the day's egress is {u:.2f} GB, at the {LINE_GB} GB mark; stopping")
                break
            keys = c.execute("select brand_id, doc_id, created_utc from public.classify_queue "
                             "where attempts < 5 and jev_checked_at is not null "
                             "and (brand_id, doc_id, created_utc) > (%s, %s, %s) "
                             "order by brand_id, doc_id, created_utc limit %s", (*cursor, a.batch)).fetchall()
            if not keys:
                if not a.wait:
                    log("no residue left")
                    break
                # the sweep's runs mark more as Jev looks at them: wait and start again from the top
                log("no residue left for now; next look in 15 minutes")
                for _ in range(3):
                    time.sleep(300)
                    log("waiting for residue")
                cursor = (-1, "", dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc))
                continue
            cursor = tuple(keys[-1])            # this run never re-selects what it took; the next run retries misses
            items = cs.fetch_items(c, keys)
            v = judge(items, a.model, f"run-{a.model}", a.ceiling, width=a.width)
            # what Codex did not answer keeps its tries (a failed job is not the item's fault) and waits for GLM
            w = cs.write(c, items, v, [mv(a.model)] * len(items), tried=[False] * len(items))
            missed = [it for it, x in zip(items, v) if x is None]
            done["labelled"] += w["labelled"]
            done["rejected"] += w["rejected"]
            done["not_answered"] += len(missed)
            done["batches"] += 1
            log(f"batch {done['batches']}: {w['labelled']} labelled, {w['rejected']} not this product, "
                f"{len(missed)} not answered; day {u:.2f} GB")
    print(json.dumps(done))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pilot"); p.add_argument("--model", default="gpt-5.6-luna"); p.add_argument("--width", type=int, default=4)
    r = sub.add_parser("run"); r.add_argument("--model", default="gpt-5.6-luna"); r.add_argument("--width", type=int, default=4)
    r.add_argument("--wait", action="store_true", help="when the residue is empty, wait for more instead of stopping")
    r.add_argument("--batch", type=int, default=1200); r.add_argument("--ceiling", type=float, required=True,
                                                                       help="Codex weekly gauge % at which to stop")
    a = ap.parse_args()
    return pilot(a) if a.cmd == "pilot" else run(a)


if __name__ == "__main__":
    sys.exit(main())
