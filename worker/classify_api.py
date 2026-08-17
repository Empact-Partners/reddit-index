#!/usr/bin/env python3
"""Classify the backlog through provider pools instead of the Codex agent.

WHY THIS EXISTS
    `codex exec` is not an API call, it is an agent session: it reasons, then
    our prompt made it WRITE A FILE, which costs a second tool round trip.
    Measured on one identical 40-item batch:

        codex exec (production path) : >600s   (timed out)
        claude -p  haiku 4.5         :  108s   free, Max plan
        deepseek-v4-flash (HTTP)     :   84s   metered
        anthropic API haiku (HTTP)   :   21s   metered

    All three non-codex paths agreed with codex's own labels on 34/40 = 85%
    and produced the IDENTICAL label distribution (neu 22 / pos 12 / neg 6),
    so n_op and pos/(pos+neg) are unchanged — the estimator does not care
    which of them labelled a row.

CONCURRENCY, THE LESSON THAT COST A MORNING
    Raising codex to 100 concurrent looked safe on memory (119 procs, 1.8 GB)
    and still collapsed: zero batches returned in 13 minutes, because a local
    agent process costs kernel scheduling, not RAM. So this module never
    trusts a resource gauge alone — it measures COMPLETED ITEMS PER MINUTE and
    the operator ramps on that number. HTTP providers (deepseek) cost almost
    nothing locally and can go wide; the claude CLI pool is a local process
    per worker and must be ramped carefully.

    python3 worker/classify_api.py --haiku 16 --deepseek 0        # free lane only
    python3 worker/classify_api.py --haiku 16 --deepseek 8        # both
    python3 worker/classify_api.py --deepseek 4 --limit 800       # cost probe
"""
import argparse
import csv
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import db  # noqa: E402
import leases  # noqa: E402
from classify import MODEL_VERSION, STAGE_LLM, LABEL_CODE, mark_target  # noqa: E402
from classify_codex import SYSTEM  # noqa: E402
from classify_daemon import Backlog, pg_text, _swap_free_mb  # noqa: E402

BATCH = int(os.environ.get("API_BATCH", "40"))
CACHE = os.path.join(HERE, ".cache", "api-absa")
os.makedirs(CACHE, exist_ok=True)

HAIKU_MODEL = "claude-haiku-4-5-20251001"
DS_MODEL = "deepseek-v4-flash"
OUT_TOK_PER_ITEM = 333          # measured for deepseek-v4-flash
MV = {"haiku": "haiku-4.5-absa-1", "deepseek": "deepseek-v4-flash-absa-1"}

_stop = threading.Event()
_lock = threading.Lock()
STATS = {"haiku": [0, 0, 0], "deepseek": [0, 0, 0]}   # [committed, batches, processed]
SPEND = {"in": 0, "out": 0, "calls": 0, "truncated": 0}

INSERT = """
    INSERT INTO mention_sentiment (doc_id, brand_id, model_version, label,
        intensity, conf, stage, is_comparative, is_recommendation,
        is_category_gripe, evidence_span)
    SELECT %s, b.id, %s, %s, %s, %s, %s, %s, %s, %s, %s
    FROM brands b WHERE b.slug = %s
    ON CONFLICT (doc_id, brand_id, model_version) DO NOTHING
"""


def deepseek_key():
    cfg = json.load(open(os.path.expanduser("~/.claude.json")))

    def find(d):
        if isinstance(d, dict):
            for k, v in d.items():
                if k == "deepseek" and isinstance(v, dict) and v.get("env"):
                    return v["env"]
                r = find(v)
                if r:
                    return r
    env = find(cfg) or {}
    return env.get("DEEPSEEK_API_KEY")


def load_judged():
    """Item ids already decided by ANY lane, from the on-disk caches.

    Entity-rejected items never get a mention_sentiment row, so the backlog
    anti-join returns them forever. Without this skip a second pass re-judges
    — and re-pays for — every reject: measured 34,432 of them against 5,568
    genuinely unprocessed items, i.e. 86% of a naive second run would be
    money spent to re-learn a decision already on disk.
    """
    judged = set()
    for d in (CACHE, os.path.join(HERE, ".cache", "sentiment")):
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if not name.endswith(".json") or name.startswith("_"):
                continue
            try:
                obj = json.load(open(os.path.join(d, name)))
            except Exception:
                continue
            if isinstance(obj, dict):
                judged.update(k for k, v in obj.items() if isinstance(v, dict))
    return judged


def build_prompt(items, brand_names, terse=False):
    lines = []
    for it in items:
        lines.append(
            f"### {it['item_id']}\n"
            f"subreddit: r/{it['subreddit']}\n"
            f"thread: {(it.get('link_title') or '')[:160]}\n"
            f"product: {brand_names.get(it['brand_slug'], it['brand_slug'])}\n"
            f"comment:\n{it['marked']}\n")
    p = (SYSTEM +
         "\n\nLabel each item below. Return ONE JSON object mapping every item "
         "id to its result object — every id present, no id skipped. Return "
         "ONLY the JSON object, no markdown fences, no commentary.\n\n"
         + "\n".join(lines))
    if terse:
        # deepseek is ~3.5x more verbose than haiku and blew a 8k cap once
        p += "\n\nBe terse: evidence at most 12 words."
    return p


def parse_obj(txt):
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


# ── providers ───────────────────────────────────────────────────────────────

def _claude_bin():
    """Absolute path to the claude CLI.

    launchd gives a job PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin and
    nothing else, while the CLI lives in ~/.local/bin. Bare "claude" therefore
    raises FileNotFoundError inside every worker thread, the batch is swallowed
    by the generic handler below, and an unattended run quietly labels NOTHING
    while reporting batch errors nobody reads. Resolve it once, loudly.
    """
    found = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
    if not os.path.exists(found):
        raise RuntimeError(
            f"claude CLI not found (looked on PATH and at {found}). The free "
            "Haiku lane cannot run; pass --deepseek N to use the metered lane.")
    return found


CLAUDE_BIN = None


def call_haiku(prompt):
    """Max-plan Haiku through the CLI. Free; costs a local process."""
    global CLAUDE_BIN
    if CLAUDE_BIN is None:
        CLAUDE_BIN = _claude_bin()
    p = subprocess.run([CLAUDE_BIN, "-p", "--model", HAIKU_MODEL],
                       input=prompt, capture_output=True, text=True, timeout=900)
    return parse_obj(p.stdout or "")


def call_deepseek(prompt, key, n_items):
    # max_tokens MUST scale with the batch. deepseek-v4-flash emits ~333
    # output tokens per item, so a fixed 16k cap truncates any batch past
    # ~40 items — and a truncated response is billed in full while parsing
    # to nothing. Measured: the first 40-item test hit an 8k cap exactly and
    # returned 0 usable labels.
    mt = min(64000, int(n_items * OUT_TOK_PER_ITEM * 1.6) + 2000)
    body = json.dumps({
        "model": DS_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": mt,
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        resp = json.load(r)
    u = resp.get("usage", {})
    ch = resp["choices"][0]
    with _lock:
        SPEND["in"] += u.get("prompt_tokens", 0)
        SPEND["out"] += u.get("completion_tokens", 0)
        SPEND["calls"] += 1
        if ch.get("finish_reason") != "stop":
            SPEND["truncated"] += 1
            print(f"  [deepseek] TRUNCATED at max_tokens={mt} for {n_items} "
                  f"items — batch lost, paid for", flush=True)
    return parse_obj(ch["message"]["content"])


# ── worker ──────────────────────────────────────────────────────────────────

def rows_from(obj, items, mv):
    rows = []
    for it in items:
        r = obj.get(it["item_id"])
        if not isinstance(r, dict) or r.get("entity_ok") is False:
            continue
        rows.append((it["doc_id"], mv,
                     LABEL_CODE.get(str(r.get("label", "abstain")).lower(), 3),
                     float(r.get("intensity") or 0),
                     float(r.get("confidence") or 0),
                     STAGE_LLM, bool(r.get("comparative")),
                     bool(r.get("recommendation")), bool(r.get("category_gripe")),
                     pg_text(r.get("evidence"), 300), it["brand_slug"]))
    return rows


def commit(state, dblock, rows):
    if not rows:
        return 0

    def _ins(c):
        with c.cursor() as cur:
            cur.executemany(INSERT, rows)
            c.commit()
    try:
        with dblock:
            db.run(state, _ins, label="api commit")
        return len(rows)
    except Exception:
        good = 0
        for row in rows:                      # one poison row must not block 39
            try:
                def _one(c, r=row):
                    with c.cursor() as cur:
                        cur.execute(INSERT, r)
                        c.commit()
                with dblock:
                    db.run(state, _one, label="api commit one")
                good += 1
            except Exception:
                pass
        return good


def worker(kind, q, state, dblock, brand_names, key, min_swap):
    while not _stop.is_set():
        try:
            items = q.get(timeout=5)
        except queue.Empty:
            if _stop.is_set():
                return
            continue
        if items is None:
            return
        # the machine comes first: a swapping box helps nobody
        if _swap_free_mb() < min_swap:
            time.sleep(20)
            q.put(items)
            continue
        try:
            prompt = build_prompt(items, brand_names, terse=(kind == "deepseek"))
            obj = (call_haiku(prompt) if kind == "haiku"
                   else call_deepseek(prompt, key, len(items)))
            if not obj:
                continue
            # cache to disk BEFORE the DB, so a crash never loses paid work
            bid = f"{kind}_{items[0]['item_id'][:24]}_{len(items)}"
            bid = re.sub(r"[^A-Za-z0-9_.-]", "_", bid)
            try:
                with open(os.path.join(CACHE, bid + ".json"), "w") as f:
                    json.dump(obj, f)
            except Exception:
                pass
            n = commit(state, dblock, rows_from(obj, items, MV[kind]))
            with _lock:
                STATS[kind][0] += n
                STATS[kind][1] += 1
                STATS[kind][2] += len(items)
        except Exception as e:
            print(f"  [{kind}] batch error: {str(e).splitlines()[0][:100]}", flush=True)
            time.sleep(3)


def reporter(t0, start_backlog):
    while not _stop.is_set():
        time.sleep(30)
        with _lock:
            h, hb, hp = STATS["haiku"]
            d, dbn, dp = STATS["deepseek"]
            si, so = SPEND["in"], SPEND["out"]
        el = max((time.time() - t0) / 60, 0.1)
        tot, proc = h + d, hp + dp
        est = si / 1e6 * 0.28 + so / 1e6 * 0.42   # published flash rates
        # ETA must use PROCESSED items: ~1/3 are entity-rejected and never
        # produce a row, so pacing on committed rows overstates the remaining
        # time by ~3x.
        rate = proc / el
        eta = max(start_backlog - proc, 0) / rate / 60 if rate else 0
        print(f"[{el:5.1f}m] processed {proc:,} ({dbn+hb} b) -> committed {tot:,} "
              f"| {rate:.0f} items/min | ETA {eta:.1f}h | "
              f"ds ${est:.2f} (proj ${est/max(proc,1)*start_backlog:.0f}) | "
              f"trunc {SPEND['truncated']} | load {os.getloadavg()[0]:.0f}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--haiku", type=int, default=16)
    ap.add_argument("--deepseek", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0, help="stop after N items (cost probe)")
    ap.add_argument("--min-swap-mb", type=float, default=400)
    args = ap.parse_args()

    key = deepseek_key() if args.deepseek else None
    if args.deepseek and not key:
        print("no deepseek key found", flush=True)
        return 1

    # ONE classifier at a time. The nightly chain starts one at 04:30 whether or
    # not a hand-started run from the evening is still draining, and two copies
    # over one backlog cursor pay twice for the same batches (harmless to the
    # data — ON CONFLICT DO NOTHING — and pure waste otherwise). flock, so a
    # kill -9 frees it with no TTL window and no reaper.
    lane = leases.Lease("classify")
    if not lane.acquire():
        print("another classifier holds the lane — exiting", flush=True)
        return 0

    brand_names = {r["slug"]: r["brand"] for r in
                   csv.DictReader(open(os.path.join(REPO, "data", "brands.csv")))}
    state = {"conn": db.connect()}
    dblock = threading.Lock()
    backlog = Backlog(state)

    # A SECOND signal is an order, not a request. The first sets _stop and lets
    # in-flight batches land; that drain waits up to 900s for worker threads,
    # and a thread blocked in subprocess.run() can outlive it — three SIGTERMed
    # processes sat alive for 40 minutes holding the lease while doing nothing,
    # which would have blocked the 04:30 chain from classifying at all.
    def _sig(*_):
        if _stop.is_set():
            print("\nsecond signal — exiting now", flush=True)
            os._exit(130)
        _stop.set()
        print("\nstopping… (signal again to exit immediately)", flush=True)
    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    q = queue.Queue(maxsize=args.haiku + args.deepseek + 8)
    t0 = time.time()

    def _count(c):
        with c.cursor() as cur:
            cur.execute("""SELECT count(*)::int FROM mentions m
                           LEFT JOIN mention_sentiment ms
                             ON ms.doc_id=m.doc_id AND ms.brand_id=m.brand_id
                           WHERE ms.doc_id IS NULL""")
            return cur.fetchone()[0]
    start_backlog = db.run(state, _count, label="backlog size")
    judged = load_judged()
    print(f"skip-set: {len(judged):,} items already decided on disk", flush=True)
    print(f"backlog {start_backlog:,} items | haiku={args.haiku} "
          f"deepseek={args.deepseek} batch={BATCH}", flush=True)

    threads = []
    for kind, n in (("haiku", args.haiku), ("deepseek", args.deepseek)):
        for _ in range(n):
            t = threading.Thread(target=worker,
                                 args=(kind, q, state, dblock, brand_names, key,
                                       args.min_swap_mb), daemon=True)
            t.start()
            threads.append(t)
    threading.Thread(target=reporter, args=(t0, start_backlog), daemon=True).start()

    fed = 0
    try:
        while not _stop.is_set():
            rows = backlog.page()
            if not rows:
                # Tell the workers, or the drain below waits its full 900s with
                # a session-pooler connection held open for nothing.
                _stop.set()
                break
            items = []
            for created, doc_id, bslug, sub, title, body, form in rows:
                if f"{doc_id}:{bslug}" in judged:
                    continue          # already decided; never pay for it twice
                off = (body or "").lower().find((form or "").lower())
                items.append({"item_id": f"{doc_id}:{bslug}", "brand_slug": bslug,
                              "subreddit": sub, "link_title": title, "doc_id": doc_id,
                              "marked": mark_target(body or "", form or "", max(0, off))})
            for i in range(0, len(items), BATCH):
                if _stop.is_set():
                    break
                chunk = items[i:i + BATCH]
                q.put(chunk)
                fed += len(chunk)
                if args.limit and fed >= args.limit:
                    _stop.set()
                    break
    finally:
        # let in-flight batches land
        # Let in-flight batches land before reporting. Without this the cost
        # probe abandons daemon threads mid-call and under-reports spend.
        print("draining in-flight batches…", flush=True)
        drain_until = time.time() + 900
        while time.time() < drain_until and any(t.is_alive() for t in threads):
            with _lock:
                busy = sum(1 for t in threads if t.is_alive())
            if q.empty() and busy == 0:
                break
            time.sleep(5)
            if _stop.is_set() and q.empty():
                # workers exit on their own once the queue drains
                alive = [t for t in threads if t.is_alive()]
                if not alive:
                    break
        _stop.set()
        for t in threads:
            t.join(timeout=30)
        el = max((time.time() - t0) / 60, 0.1)
        h, d = STATS["haiku"][0], STATS["deepseek"][0]
        print(f"\ncommitted haiku={h:,} deepseek={d:,} in {el:.1f}m "
              f"= {(h+d)/el:.0f} items/min", flush=True)
        print(f"deepseek tokens in={SPEND['in']:,} out={SPEND['out']:,}", flush=True)
        try:
            state["conn"].close()
        except Exception:
            pass
        lane.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
