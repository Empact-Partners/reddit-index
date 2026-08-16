#!/usr/bin/env python3
"""Find the fastest DeepSeek config that does NOT degrade the labels.

Two independent knobs, and only one of them is safe to push:

  BATCH SIZE is bounded by OUTPUT TOKENS. deepseek-v4-flash emits ~333 output
  tokens per item, so a 40-item batch already spends ~13.3k. Push the batch
  without pushing max_tokens and the JSON truncates mid-object — which is
  exactly how the first test returned 0 of 40 items while still billing for
  8,000 tokens. Truncation is the expensive failure: you pay in full and get
  nothing, so every run here asserts finish_reason == "stop".

  CONCURRENCY is nearly free because these are HTTP calls, not local
  processes. That is the knob that actually buys wall-clock.

Quality is verified per config, never assumed:
  - completeness  : every item id present in the response
  - schema        : label in the allowed set, intensity/conf numeric in range
  - agreement     : vs the labels already in the DB for the same items
  - distribution  : pos/neu/neg mix, to catch a model that collapses to one

    python3 worker/bench_deepseek.py --sizes 40,80,120 --concurrency 1
    python3 worker/bench_deepseek.py --sizes 60 --concurrency 8,16,32
"""
import argparse
import csv
import json
import os
import re
import statistics
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import db  # noqa: E402
from classify import LABEL_CODE, mark_target  # noqa: E402
from classify_codex import SYSTEM  # noqa: E402

MODEL = "deepseek-v4-flash"
URL = "https://api.deepseek.com/chat/completions"
OUT_TOK_PER_ITEM = 333          # measured; drives the max_tokens we request
INV = {v: k for k, v in LABEL_CODE.items()}
_lk = threading.Lock()
SPEND = {"in": 0, "out": 0, "calls": 0}


def key():
    cfg = json.load(open(os.path.expanduser("~/.claude.json")))

    def find(d):
        if isinstance(d, dict):
            for k, v in d.items():
                if k == "deepseek" and isinstance(v, dict) and v.get("env"):
                    return v["env"]
                r = find(v)
                if r:
                    return r
    return (find(cfg) or {})["DEEPSEEK_API_KEY"]


def sample(n):
    """Items that ALREADY have labels, so agreement is measurable."""
    state = {"conn": db.connect()}

    def q(c):
        with c.cursor() as cur:
            cur.execute("""
                SELECT m.doc_id, b.slug, s.name, coalesce(t.link_title,''),
                       m.body, m.matched_form, ms.label
                FROM mentions m
                JOIN brands b ON b.id=m.brand_id
                JOIN subreddits s ON s.id=m.subreddit_id
                LEFT JOIN threads t ON t.id=m.thread_id
                JOIN mention_sentiment ms
                  ON ms.doc_id=m.doc_id AND ms.brand_id=m.brand_id
                WHERE length(m.body) BETWEEN 120 AND 1600
                ORDER BY m.created_utc DESC
                LIMIT %s""", (n,))
            return cur.fetchall()
    rows = db.run(state, q, label="bench sample")
    state["conn"].close()
    brand_names = {r["slug"]: r["brand"] for r in
                   csv.DictReader(open(os.path.join(REPO, "data", "brands.csv")))}
    items = []
    for doc_id, bslug, sub, title, body, form, label in rows:
        off = (body or "").lower().find((form or "").lower())
        items.append({"item_id": f"{doc_id}:{bslug}", "brand_slug": bslug,
                      "subreddit": sub, "link_title": title, "doc_id": doc_id,
                      "gold": label, "brand": brand_names.get(bslug, bslug),
                      "marked": mark_target(body or "", form or "", max(0, off))})
    return items


def prompt_for(items):
    lines = [f"### {it['item_id']}\nsubreddit: r/{it['subreddit']}\n"
             f"thread: {(it.get('link_title') or '')[:160]}\n"
             f"product: {it['brand']}\ncomment:\n{it['marked']}\n" for it in items]
    return (SYSTEM +
            "\n\nLabel each item below. Return ONE JSON object mapping every item "
            "id to its result object — every id present, no id skipped. Return "
            "ONLY the JSON object.\n\n" + "\n".join(lines) +
            "\n\nBe terse: evidence at most 12 words.")


def call(items, api_key, timeout=1200):
    mt = min(64000, int(len(items) * OUT_TOK_PER_ITEM * 1.6) + 2000)
    body = json.dumps({"model": MODEL,
                       "messages": [{"role": "user", "content": prompt_for(items)}],
                       "max_tokens": mt,
                       "response_format": {"type": "json_object"}}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": f"Bearer {api_key}", "content-type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.load(r)
    dt = time.time() - t0
    u = resp.get("usage", {})
    with _lk:
        SPEND["in"] += u.get("prompt_tokens", 0)
        SPEND["out"] += u.get("completion_tokens", 0)
        SPEND["calls"] += 1
    ch = resp["choices"][0]
    return {"dt": dt, "finish": ch.get("finish_reason"),
            "txt": ch["message"]["content"], "max_tokens": mt,
            "in": u.get("prompt_tokens", 0), "out": u.get("completion_tokens", 0)}


def grade(res, items):
    """Every quality gate that decides whether this config is usable."""
    out = {"finish": res["finish"], "truncated": res["finish"] != "stop",
           "dt": res["dt"], "in": res["in"], "out": res["out"]}
    m = re.search(r"\{.*\}", res["txt"], re.S)
    obj = None
    if m:
        try:
            obj = json.loads(m.group(0))
        except Exception:
            obj = None
    if not isinstance(obj, dict):
        out.update(parsed=0, complete=False, agree=None, bad_schema=None, dist={})
        return out
    present = sum(1 for it in items if isinstance(obj.get(it["item_id"]), dict))
    ag = dis = bad = 0
    dist = {}
    for it in items:
        r = obj.get(it["item_id"])
        if not isinstance(r, dict):
            continue
        lab = str(r.get("label", "")).lower()
        if lab not in LABEL_CODE:
            bad += 1
            continue
        try:
            inten = float(r.get("intensity") or 0)
            conf = float(r.get("confidence") or 0)
            if not (-1.01 <= inten <= 1.01) or not (0 <= conf <= 1.01):
                bad += 1
        except Exception:
            bad += 1
        dist[lab] = dist.get(lab, 0) + 1
        code = LABEL_CODE[lab]
        if code == it["gold"]:
            ag += 1
        else:
            dis += 1
    out.update(parsed=present, complete=present == len(items),
               agree=(ag / max(ag + dis, 1)), bad_schema=bad, dist=dist)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="40,80,120")
    ap.add_argument("--concurrency", default="1")
    ap.add_argument("--reps", type=int, default=1)
    args = ap.parse_args()
    api_key = key()
    sizes = [int(x) for x in args.sizes.split(",")]
    concs = [int(x) for x in args.concurrency.split(",")]

    pool = sample(max(sizes) * max(concs) * args.reps + 50)
    print(f"sampled {len(pool)} already-labelled items for grading\n")
    print(f"{'batch':>6} {'conc':>5} {'sec':>7} {'items/min':>10} {'parsed':>8} "
          f"{'agree':>7} {'trunc':>6} {'schema':>7}  dist")
    print("-" * 82)

    results = []
    for size in sizes:
        for conc in concs:
            need = size * conc
            if need > len(pool):
                print(f"{size:>6} {conc:>5}   skipped (need {need} items)")
                continue
            chunks = [pool[i * size:(i + 1) * size] for i in range(conc)]
            t0 = time.time()
            with ThreadPoolExecutor(max_workers=conc) as ex:
                futs = [ex.submit(call, c, api_key) for c in chunks]
                res = []
                for f, c in zip(futs, chunks):
                    try:
                        res.append((f.result(), c))
                    except Exception as e:
                        print(f"{size:>6} {conc:>5}   ERROR {str(e)[:50]}")
            wall = time.time() - t0
            if not res:
                continue
            gs = [grade(r, c) for r, c in res]
            done = sum(g["parsed"] for g in gs)
            ipm = done / wall * 60
            agr = [g["agree"] for g in gs if g["agree"] is not None]
            trunc = sum(1 for g in gs if g["truncated"])
            schema = sum(g["bad_schema"] or 0 for g in gs)
            dist = {}
            for g in gs:
                for k, v in g["dist"].items():
                    dist[k] = dist.get(k, 0) + v
            complete = sum(1 for g in gs if g["complete"])
            print(f"{size:>6} {conc:>5} {wall:>7.0f} {ipm:>10.0f} "
                  f"{done}/{size*conc:>3} ({complete}/{len(gs)} full) "
                  f"{statistics.mean(agr)*100 if agr else 0:>6.0f}% "
                  f"{trunc:>6} {schema:>7}  {dist}")
            results.append({"size": size, "conc": conc, "wall": wall, "ipm": ipm,
                            "parsed": done, "expected": size * conc,
                            "agree": statistics.mean(agr) if agr else 0,
                            "trunc": trunc, "schema": schema})

    print("\n" + "-" * 82)
    ci, co, cc = SPEND["in"], SPEND["out"], SPEND["calls"]
    print(f"benchmark spend: {cc} calls, {ci:,} in + {co:,} out tokens")
    json.dump(results, open("/tmp/ri_bench_ds.json", "w"), indent=1)
    print("results -> /tmp/ri_bench_ds.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
