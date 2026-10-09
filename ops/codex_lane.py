#!/usr/bin/env python3
"""The Codex lane for the classifier's residue while GLM's plan allowance is used up (2026-10-07).

GLM is the classifier's second judge. When Z.ai refuses with "Weekly/Monthly Limit Exhausted", Jev still settles what
it is sure of and marks the rest (classify_queue.jev_checked_at); everything else waits for GLM. The doctrine routes a
walled GLM lane to Codex (no search, explicit low effort, through codex_job). This lane runs on the LAPTOP only: Codex
is the ChatGPT subscription, which never goes on a server.

  * The prompt is GLM's, the calibrated rubric verbatim (worker/rubric.py), with the output asked as a JSON object per
    item (Codex's --output-schema). codex_job adds the no-search clause and checks the pilot's events for searches.
  * Every label carries its model, e.g. gpt-5.6-luna-absa-1, so it can be told apart and re-judged.
  * No Reddit calls, so any hour; the backlog older than 26 hours from the high end of the brand order (the sweep's
    classify starts at the other end); the day's 2 GB egress line on the node counter (waits for the next UTC day at
    1.90 GB, the same mark as ops/day_passes.py); the Codex weekly ceiling (stops); one receipt per UTC day.

  ops/codex_lane.py pilot --model gpt-5.6-luna            # 300 GLM labels + 100 GLM rejections, compared; writes nothing
  ops/codex_lane.py run --model gpt-5.6-luna --ceiling 45 # Jev then Codex over the backlog, until --until (detached)
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


def _receipt(c, run_id: str, status: str, notes: dict) -> None:
    c.execute("insert into public.pipeline_runs (run_id, stage, code_version, started_at, finished_at, status, notes) "
              "values (%s, 'repair', 'codex-lane', now(), case when %s = 'running' then null else now() end, %s, %s) "
              "on conflict (run_id) do update set finished_at = excluded.finished_at, status = excluded.status, "
              "notes = excluded.notes", (run_id, status, status, json.dumps(notes, default=str)))


def _sleep(seconds: float, why: str) -> None:
    end = time.time() + seconds
    while time.time() < end:
        time.sleep(min(300, max(1, end - time.time())))
        log(f"waiting: {why}")


def run(a) -> int:
    """Jev first on what it has not seen, Codex on the rest, over the backlog older than 26 hours, from the HIGH end of
    the brand order (the sweep's own classify takes the newest and walks up from the low end, so the two meet at most
    once). No Reddit calls, so the night is allowed. One receipt per UTC day (stage 'repair'), the day's 2 GB line on
    the node counter (waits for the next day at 1.90 GB), the Codex ceiling (stops)."""
    import uuid
    import db
    until = dt.datetime.fromisoformat(a.until).replace(tzinfo=dt.timezone.utc) if a.until else None
    rid, rday, tot = None, None, None
    cursor, labelled_this_pass = None, 0
    c = None
    while True:
        now = dt.datetime.now(dt.timezone.utc)
        if until and now >= until:
            log(f"past {until:%d %b %H:%M} UTC; stopping")
            break
        try:
            if c is None or c.closed:
                c = db.connect()
                c.autocommit = True
            if rid and rday != now.date():                    # a new UTC day: close yesterday's receipt
                _receipt(c, rid, "ok", tot)
                rid = None
            try:
                u = used_today()
            except Exception as e:  # noqa: BLE001 - no reading, no run: the line is the rule
                log(f"no egress reading yet ({str(e)[:80]}); trying again in 5 minutes")
                time.sleep(300)
                continue
            if u >= LINE_GB:
                if rid:
                    tot["stopped"] = f"the day's egress reached {u:.2f} GB"
                    _receipt(c, rid, "capped", tot)
                    rid = None
                nxt = dt.datetime.combine(now.date() + dt.timedelta(days=1), dt.time(0, 2), dt.timezone.utc)
                log(f"the day's egress is {u:.2f} GB, at the {LINE_GB} GB mark; waiting for {nxt:%d %b %H:%M} UTC")
                _sleep((nxt - now).total_seconds(), "the next UTC day")
                continue
            if rid is None:
                rid, rday = str(uuid.uuid4()), now.date()
                tot = {"what": "codex lane: Jev, then Codex on the rest (decision 0021)", "model": a.model,
                       "jev_decided": 0, "codex_decided": 0, "labelled": 0, "rejected": 0, "not_answered": 0,
                       "batches": 0, "jev_usd": 0.0}
                _receipt(c, rid, "running", tot)
            # While GLM is walled the sweep skips what Jev has looked at (classify_sweep: "jev_checked_at is null"),
            # so that residue is the lane's alone and is taken at once (9 Oct: 8,392 waited a day for the 26-hour
            # line). What Jev has not seen keeps the line, so the lane never races the sweep's own Jev pass. Once
            # the recorded wall has passed, the sweep asks GLM for the residue again and the line applies to all.
            walled = cs.known_glm_wall(c) is not None
            q = ("select brand_id, doc_id, created_utc, jev_checked_at is not null from public.classify_queue "
                 "where attempts < 5 and (enqueued_at <= now() - interval '26 hours'"
                 + (" or jev_checked_at is not null) " if walled else ") "))
            if cursor:
                rows = c.execute(q + "and (brand_id, doc_id, created_utc) < (%s, %s, %s) "
                                 "order by brand_id desc, doc_id desc, created_utc desc limit %s", (*cursor, a.batch)).fetchall()
            else:
                rows = c.execute(q + "order by brand_id desc, doc_id desc, created_utc desc limit %s", (a.batch,)).fetchall()
            if not rows:
                if cursor and labelled_this_pass:
                    cursor, labelled_this_pass = None, 0      # a full pass done: what is left gets another try
                    continue
                cursor, labelled_this_pass = None, 0
                _sleep(900, "nothing the lane may take is queued (or nothing more settled this pass)")
                continue
            cursor = tuple(rows[-1][:3])
            seen = {(r[0], r[1]): r[3] for r in rows}
            items = cs.fetch_items(c, [r[:3] for r in rows])
            fresh = [i for i, it in enumerate(items) if not seen.get((it["brand_id"], it["doc_id"]))]
            verdicts: list = [None] * len(items)
            models = [mv(a.model)] * len(items)
            jev_seen = [False] * len(items)
            if fresh:
                j = cs.jev_judge([items[i] for i in fresh], log=lambda *x, **k: None)
                tot["jev_usd"] = round(tot["jev_usd"] + cs.jev_judge.last_usd, 4)
                th = json.load(open(cs.THRESHOLDS, encoding="utf-8"))
                for i, x in zip(fresh, j):
                    jev_seen[i] = x is not None
                    d = cs.decide(x, th)
                    if d is not None:
                        verdicts[i], models[i] = d, cs.MV_JEV
                        tot["jev_decided"] += 1
            rest = [i for i, v in enumerate(verdicts) if v is None]
            if rest:
                cv = judge([items[i] for i in rest], a.model, f"run-{a.model}", a.ceiling, width=a.width)
                for i, v in zip(rest, cv):
                    if v is not None:
                        verdicts[i] = v
                        tot["codex_decided"] += 1
            # what nobody answered keeps its tries (a failed job is not the item's fault)
            w = cs.write(c, items, verdicts, models, tried=[False] * len(items), jev_seen=jev_seen)
            miss = sum(v is None for v in verdicts)
            labelled_this_pass += w["labelled"] + w["rejected"]
            for k, n in (("labelled", w["labelled"]), ("rejected", w["rejected"]), ("not_answered", miss), ("batches", 1)):
                tot[k] += n
            _receipt(c, rid, "running", tot)
            log(f"batch {tot['batches']}: Jev {sum(1 for m in models if m == cs.MV_JEV)} · Codex "
                f"{len(rest) - miss} · not answered {miss} · {w['labelled']} labelled, {w['rejected']} not this product · "
                f"day {u:.2f} GB")
        except SystemExit as e:                               # the Codex ceiling (WaveRefused): stop, say so
            log(f"stopped: {e}")
            if rid and c is not None and not c.closed:
                tot["stopped"] = str(e)[:200]
                _receipt(c, rid, "capped", tot)
            return 0
        except Exception as e:  # noqa: BLE001 - a dropped connection or one bad batch costs a minute, not the lane
            log(f"batch failed ({type(e).__name__}: {str(e)[:160]}); again in 60 s")
            try:
                if c is not None:
                    c.close()
            except Exception:  # noqa: BLE001
                pass
            c = None
            time.sleep(60)
    if rid and c is not None and not c.closed:
        _receipt(c, rid, "ok", tot)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pilot"); p.add_argument("--model", default="gpt-5.6-luna"); p.add_argument("--width", type=int, default=4)
    r = sub.add_parser("run"); r.add_argument("--model", default="gpt-5.6-luna"); r.add_argument("--width", type=int, default=4)
    r.add_argument("--until", default="2026-10-11T00:00", help="UTC; GLM's allowance is back by then")
    r.add_argument("--batch", type=int, default=1200); r.add_argument("--ceiling", type=float, required=True,
                                                                       help="Codex weekly gauge % at which to stop")
    a = ap.parse_args()
    return pilot(a) if a.cmd == "pilot" else run(a)


if __name__ == "__main__":
    sys.exit(main())
