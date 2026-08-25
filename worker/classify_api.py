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

    python3 worker/classify_api.py                      # the lane: 16 free Haiku
    python3 worker/classify_api.py --haiku 24           # wider, still free

THE METERED LANE IS THE LANE. Vlad ruled on 2026-08-18 (decisions/0010,
superseding the 2026-08-17 free-Haiku ruling): classification runs on the
DeepSeek API — faster (~1,100 vs ~310 items/min) and off the Claude quota
entirely, at ~$0.18 per 1,000 items. The context: the free Haiku lane was
drawing from the same 5-hour/weekly Max-plan buckets as all interactive work
("free" was never free), and the index has no scheduled jobs any more — a
human runs worker/update.sh, which passes --deepseek 16 --haiku 0
--allow-metered explicitly. The gate stays: --deepseek without --allow-metered
still refuses, so spending money remains a decision written at the call site,
never a default someone inherits by accident. The Haiku lane stays runnable
as a fallback for a day the DeepSeek API is down.
"""
import argparse
import csv
import collections
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
HAIKU_SYSTEM = ("You are a precise sentiment labeller. Follow the user's "
                "instructions exactly and reply with JSON only, no preamble, "
                "no commentary, no code fences.")
DS_MODEL = "deepseek-v4-flash"
OUT_TOK_PER_ITEM = 333          # measured for deepseek-v4-flash
MV = {"haiku": "haiku-4.5-absa-1", "deepseek": "deepseek-v4-flash-absa-1"}

_stop = threading.Event()
_lock = threading.Lock()
STATS = {"haiku": [0, 0, 0], "deepseek": [0, 0, 0]}   # [committed, batches, processed]
DEAD = {"haiku": 0, "deepseek": 0}    # consecutive failures per lane
PARSE_FAIL = {"haiku": 0, "deepseek": 0}   # items dropped, output unparseable
PARSE_RETRY: dict = {}                     # batch key -> attempts, retry-once
UNMATCHED = [0]                            # answers returned but not keyed to an item
DROPPED = {"haiku": 0, "deepseek": 0}      # items lost to an exception
DEAD_MAX = 12                          # ~36s of solid failure before giving up
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


class PromptTooLong(Exception):
    """The CLI refused the prompt outright. Split the batch, do not retry it whole."""


def call_haiku(prompt):
    """Max-plan Haiku through the CLI. Free; costs a local process.

    A CLI REFUSAL IS NOT AN UNPARSEABLE ANSWER. `claude -p` exits 1 and prints
    "Prompt is too long" in plain text, and subprocess.run does not raise without
    check=True — so that sentence used to be fed straight to parse_obj, come back
    None, and be counted as a garbled generation. On 2026-08-25 that mistranslation
    cost the whole night's Haiku classification: BATCH=40 builds a ~10 KB prompt,
    every single batch was refused in 3.6s, and 148 consecutive batches were
    recorded as "unparseable" while the lane was perfectly healthy — a 1-item
    prompt answered correctly, and 15 items returned 15/15 properly keyed.

    BATCH=40 was tuned for DeepSeek, an HTTP provider with its own max_tokens
    scaling. Nothing had ever sized a batch for this lane.
    """
    global CLAUDE_BIN
    if CLAUDE_BIN is None:
        CLAUDE_BIN = _claude_bin()
    # --system-prompt AND --setting-sources: run this as a LABELLER, not as an
    # assistant. Without them `claude -p` auto-discovers the user and project
    # CLAUDE.md, loads settings and fires SessionStart hooks, so every call drags
    # the whole global config in before it sees the batch — the model literally
    # answers "I've absorbed the full CLAUDE.md context". Two consequences:
    #
    #   COST: that context is re-sent on every one of thousands of calls, and it
    #   is what pushes a 40-item batch past the window. Measured 2026-08-25 on
    #   the same 40-item prompt: baseline rc=1 "Prompt is too long", 0/40
    #   answers; with these flags rc=0 and 40/40. The whole night's "unparseable"
    #   epidemic was this.
    #
    #   CORRECTNESS, which matters more: that config is a marketing assistant's
    #   brief — brand voice, content rules, an identity. Handing it to a
    #   sentiment labeller invites exactly the drift the MODEL_VERSION scheme
    #   exists to keep track of. A classifier should see the classification
    #   prompt and nothing else.
    p = subprocess.run([CLAUDE_BIN, "-p", "--model", HAIKU_MODEL,
                        "--setting-sources", "",
                        "--system-prompt", HAIKU_SYSTEM],
                       input=prompt, capture_output=True, text=True, timeout=900)
    out = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0 and "too long" in out.lower():
        raise PromptTooLong(out.strip()[:120])
    if p.returncode != 0:
        raise RuntimeError(f"claude -p exited {p.returncode}: {out.strip()[:120]}")
    return parse_obj(p.stdout or "")


def call_lane(kind, items, brand_names, key, depth=0):
    """One provider call, splitting the batch if the CLI refuses its length.

    Sizing by ITEM COUNT cannot work here: prompt length is driven by comment
    length, so any fixed number is too big for some batches and wastefully small
    for others. Halving on refusal self-tunes to the actual text, costs one
    wasted call per split, and needs no constant anybody has to maintain.
    """
    prompt = build_prompt(items, brand_names, terse=(kind == "deepseek"))
    try:
        return call_haiku(prompt) if kind == "haiku" else \
            call_deepseek(prompt, key, len(items))
    except PromptTooLong:
        if len(items) == 1 or depth > 6:
            raise
        mid = len(items) // 2
        merged = {}
        for half in (items[:mid], items[mid:]):
            got = call_lane(kind, half, brand_names, key, depth + 1)
            if isinstance(got, dict):
                merged.update(got)
        return merged or None


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
    """Map the model's answer back onto the items we sent.

    THE KEY IS `doc_id:brand_slug` and the model does not always use it. Measured
    across the on-disk cache on 2026-08-25: **3.01% of judgments came back keyed
    by the bare doc_id**, and 78 of 4,000 batch files were keyed that way
    ENTIRELY — 100% of a paid batch discarded, 816 opinionated labels in those
    files alone. The old code did `obj.get(it["item_id"])` and `continue`, which
    put a missing answer down the SAME branch as a deliberate entity rejection:
    no row, no counter, no log line, while STATS still counted the batch
    processed. So the loss was invisible and indistinguishable from the normal
    ~1/3 entity-reject rate, and it reached a published score in the same minute,
    because ship_batch runs score_db and publish right after.

    A bare doc_id is accepted ONLY when exactly one item in this batch carries
    that doc_id. Two brands discussed in one comment share a doc_id, and guessing
    there would attach a label to the WRONG brand — worse than losing it.
    """
    by_doc = collections.Counter(it["doc_id"] for it in items)
    rows, missing = [], 0
    for it in items:
        r = obj.get(it["item_id"])
        if r is None and by_doc[it["doc_id"]] == 1:
            r = obj.get(it["doc_id"])          # unambiguous bare key
        if r is None:
            missing += 1
            continue
        if not isinstance(r, dict) or r.get("entity_ok") is False:
            continue
        rows.append((it["doc_id"], mv,
                     LABEL_CODE.get(str(r.get("label", "abstain")).lower(), 3),
                     float(r.get("intensity") or 0),
                     float(r.get("confidence") or 0),
                     STAGE_LLM, bool(r.get("comparative")),
                     bool(r.get("recommendation")), bool(r.get("category_gripe")),
                     pg_text(r.get("evidence"), 300), it["brand_slug"]))
    if missing:
        # SAY IT. An answer we cannot find is lost work we already paid for, and
        # it must never again be silent or look like an entity rejection.
        with _lock:
            UNMATCHED[0] += missing
        print(f"  {missing}/{len(items)} answers had no matching key "
              f"(model keyed them differently) — {UNMATCHED[0]} unmatched so far",
              flush=True)
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
    except Exception as bulk_err:
        # ROLL BACK FIRST. A server-side abort leaves the shared connection in a
        # failed transaction (SQLSTATE 25P02), and every subsequent statement on
        # it raises InFailedSqlTransaction — which db.is_transient() does not
        # match, so db.run re-raises without reconnecting and all 40 per-row
        # retries land in `except Exception: pass`. The comment below says one
        # poison row must not block 39; without this line the inverse happens and
        # one poison row blocks all 40.
        try:
            with dblock:
                state["conn"].rollback()
        except Exception:
            pass
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
        if good < len(rows):
            # SAY IT. Nothing compared this return against len(rows), so a short
            # write was silent — and worse than silent: the disk cache is written
            # one caller up BEFORE commit, so load_judged() adds these ids to a
            # permanent skip-set and no later run will ever retry them. A label
            # lost here is lost for good unless somebody reads this line.
            print(f"  commit wrote {good}/{len(rows)} rows "
                  f"({str(bulk_err).splitlines()[0][:80]}) — the rest are cached "
                  f"as judged and will NOT be retried", flush=True)
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
            # Hold the batch HERE rather than q.put()-ing it back: the queue is
            # bounded, so a worker that requeues can block on a full queue while
            # the feeder is also blocked putting — see the deadlock note below.
            # Sleeping in place keeps the item in this worker and cannot wedge.
            while _swap_free_mb() < min_swap and not _stop.is_set():
                time.sleep(20)
            if _stop.is_set():
                return
        try:
            obj = call_lane(kind, items, brand_names, key)
            if not obj:
                # A BATCH THAT DOES NOT PARSE IS LOST WORK, NOT A NO-OP. This was
                # a bare `continue`: no error, no counter, no requeue — 40 items
                # gone per occurrence, in silence. STATS only advances on success,
                # so the reporter's `processed` line flatlines and the run then
                # reports "stalled at N/M" while it is actually discarding work.
                # Measured 2026-08-25: a 1,088-item pass committed 420 and dropped
                # 400 exactly this way, with ZERO error lines in the log.
                # Retry once — a truncated or preamble-wrapped generation usually
                # parses on a second attempt — then count it and say so.
                # RETRY INLINE, NEVER BY REQUEUEING. The first version of this
                # called q.put(items) to try again later, and that DEADLOCKS: the
                # queue is bounded (maxsize = workers + 8), so once enough batches
                # fail every worker blocks in q.put while the feeder blocks in
                # q.put too, and nothing is left to consume. Observed 2026-08-25
                # on ship batch 8 — main thread and all 8 workers parked in
                # lock_PyThread_acquire_lock, zero `claude` children, zero
                # progress, load 3, no output. A worker must never put back into
                # the queue it drains.
                obj = call_lane(kind, items, brand_names, key)
                if not obj:
                    with _lock:
                        PARSE_FAIL[kind] = PARSE_FAIL.get(kind, 0) + len(items)
                        lost = PARSE_FAIL[kind]
                    print(f"  [{kind}] UNPARSEABLE after a retry — dropping "
                          f"{len(items)} items ({lost} lost so far)", flush=True)
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
            # SAME TREATMENT AS THE PARSE PATH. This branch also drops 40 items,
            # and until now recorded them nowhere: DEAD is a per-lane CONSECUTIVE
            # counter that any sibling worker's success resets, and no summary
            # printed it. So an exception-dropped run announced "committed N
            # labels" as though N were the whole job. Reachable through
            # call_haiku's 900s TimeoutExpired and through a non-numeric
            # intensity in rows_from.
            with _lock:
                DROPPED[kind] = DROPPED.get(kind, 0) + len(items)
                gone = DROPPED[kind]
            print(f"  [{kind}] batch error: {str(e).splitlines()[0][:100]} "
                  f"— dropping {len(items)} items ({gone} dropped so far)", flush=True)
            with _lock:
                DEAD[kind] = DEAD.get(kind, 0) + 1
                n_dead = DEAD[kind]
            # SCOPE, stated plainly because a comment that overclaims is the same
            # defect as a check that cannot fail: this catches a lane that RAISES.
            # It does NOT catch a lane that HANGS — call_haiku waits up to 900s on
            # its subprocess, so a quota-limited `claude -p` that never returns
            # produces no exception and never increments DEAD. On 2026-08-25 at
            # 00:40 that is exactly what happened: 0 batches in 6 minutes, no
            # errors, no give-up. What caught it was the pre-existing aggregate
            # stall detector ("stalled at 0/N — stopping"), which is the right
            # mechanism for that shape. Do not add a second one here; do not
            # assume this guard covers it.
            #
            # A LANE THAT CANNOT BILL MUST NOT SPIN. Both providers can go away
            # without raising anything this loop distinguishes: the DeepSeek
            # balance went negative on 2026-08-24, and the Max-plan Haiku lane
            # stops the moment a session limit trips. Catch-print-sleep-loop then
            # runs forever, committing nothing, while every log line still says
            # the stage is working -- the exact silent stall this project has
            # paid for before. So a lane that fails DEAD_MAX times in a row with
            # nothing committed gives up and lets the process exit non-zero.
            # ship_batch() calls classify with fatal=False, so score and publish
            # still run on whatever labels already exist and the category ships;
            # re-run classification when a lane can bill again.
            # Consecutive, NOT lifetime: the else-branch below resets the
            # counter on any success, so DEAD_MAX in a row means the lane is
            # down right now. An earlier version also required
            # STATS[kind][0] == 0, which looked safer and was strictly worse —
            # a quota that trips PART WAY through a run (the common shape: a
            # Max-plan bucket empties mid-batch) leaves committed > 0 forever,
            # so the give-up could never fire and the lane span until morning.
            if n_dead >= DEAD_MAX:
                print(f"  [{kind}] GIVING UP: {n_dead} consecutive failures "
                      f"with no success in between ({STATS[kind][0]} items "
                      f"committed earlier this run). The lane cannot bill -- "
                      f"check the DeepSeek balance and the Claude session "
                      f"limit. Re-run classification when one can.", flush=True)
                _stop.set()
                return
            time.sleep(3)
        else:
            with _lock:
                DEAD[kind] = 0


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
    ap.add_argument("--haiku", type=int, default=16,
                    help="`claude -p` Haiku workers on the Max plan (fallback lane; "
                         "draws the shared Claude quota)")
    ap.add_argument("--deepseek", type=int, default=0,
                    help="metered DeepSeek workers — THE lane since decisions/0010; "
                         "requires --allow-metered")
    ap.add_argument("--allow-metered", action="store_true",
                    help="acknowledge that --deepseek spends real money")
    ap.add_argument("--limit", type=int, default=0, help="stop after N items (cost probe)")
    ap.add_argument("--min-swap-mb", type=float, default=400)
    args = ap.parse_args()

    if args.deepseek and not args.allow_metered:
        print("--deepseek spends money; pass --allow-metered to acknowledge it. "
              "(DeepSeek IS the ruled lane — decisions/0010, 2026-08-18 — the "
              "gate exists so spend is always explicit at the call site.)",
              flush=True)
        return 1
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
