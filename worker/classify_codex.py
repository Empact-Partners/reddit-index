#!/usr/bin/env python3
"""ABSA classification on the Codex fleet (gpt-5.6-luna) instead of `claude -p`.

Same task, same SYSTEM prompt, same label set as classify.py — a different
engine on a different subscription. Rationale: classification is judgment-light
bulk (the luna lane), the fleet runs 40-60 jobs wide where `claude -p` must run
SERIAL, and it spends the ChatGPT quota pool instead of Claude Max tokens.

Division of labour:
  THIS script only FILLS the sentiment cache (worker/.cache/sentiment/) with
  codex_<id>.json files in the same {item_id: result} shape classify.py writes.
  classify.py's load_known() merges every cache file by item_id, so a follow-up
  `classify.py --all --window-days 365 --window-only` finds everything cached
  and assembles scored/*.json with ZERO model calls, either engine.

Fleet doctrine applied (codex-assistant skill):
  - recovery pattern: each batch's task ends with "write <out>/out_<id>.json";
    done = out-file exists AND parses; re-running submits only the gaps
  - submit log is append-only jsonl, written BEFORE the submit
  - completion is detected from DISK, never from job status
  - slot accounting from /health with UNKNOWN == FULL, server pinned to skip
    the version probe, submit retries with backoff
  - a mid-write out-file parses as "still running", never as corruption
"""
import argparse, json, os, re, sys, time, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.expanduser("~/.claude/api_helpers"))
from classify import SYSTEM, LABEL_CODE, mark_target, load_known, select_mentions  # noqa: E402
from codex_fleet import CodexFleet  # noqa: E402

CACHE = os.path.join(HERE, ".cache", "sentiment")
RESOLVED = os.path.join(HERE, ".cache", "resolved")
RUN = os.path.join(HERE, ".cache", "codex-absa")
os.makedirs(RUN, exist_ok=True)

MODEL = "gpt-5.6-luna"
SERVER = "local-mac"          # pin: the health probe times out under load
MAX_INFLIGHT = 40

fleet = CodexFleet()


def fleet_running():
    """Real in-flight count, or None if unknown. UNKNOWN == FULL, never free."""
    try:
        h = fleet.health()
        for e in (h if isinstance(h, list) else [h]):
            inner = e.get("health") or e
            if not e.get("ok", True):
                return None
            n = inner.get("running")
            if isinstance(n, int):
                return n + (inner.get("queued") or 0)
    except Exception:
        return None
    return None


def wait_for_slot():
    while True:
        n = fleet_running()
        if n is not None and n < MAX_INFLIGHT:
            return
        time.sleep(20 if n is None else 8)


def journal(rec):
    with open(os.path.join(RUN, "journal.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")


# ── burn lock ───────────────────────────────────────────────────────────────
# A supervised burn and the 03:30 nightly classify share this RUN dir, compute
# the same content-addressed batch ids over the same anti-join universe, and
# both delete out_<bid>.json before resubmit — running them concurrently
# mutually clobbers in-flight out-files. The burn takes this lock; the nightly
# skips classification while it is fresh (score/publish still run).
LOCK = os.path.join(RUN, "burn.lock")


def burn_lock():
    """Acquire (O_CREAT|O_EXCL). Returns True on success. Refresh each cycle
    by calling again after burn_refresh()."""
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, json.dumps({"pid": os.getpid(), "t": time.time()}).encode())
        os.close(fd)
        return True
    except FileExistsError:
        if burn_active():
            return False
        os.remove(LOCK)  # stale — dead pid or >2h old
        return burn_lock()


def burn_refresh():
    try:
        with open(LOCK, "w") as f:
            json.dump({"pid": os.getpid(), "t": time.time()}, f)
    except Exception:
        pass


def burn_release():
    try:
        os.remove(LOCK)
    except FileNotFoundError:
        pass


def burn_active():
    """True when a live burn holds the lock (fresh + pid alive)."""
    try:
        rec = json.load(open(LOCK))
    except Exception:
        return False
    if time.time() - (rec.get("t") or 0) > 7200:
        return False
    try:
        os.kill(int(rec.get("pid") or 0), 0)
        return True
    except (OSError, ValueError):
        return False


def batch_task(items, brand_names, out_fp):
    lines = []
    for it in items:
        lines.append(
            f"### {it['item_id']}\n"
            f"subreddit: r/{it['subreddit']}\n"
            f"thread: {(it.get('link_title') or '')[:160]}\n"
            f"product: {brand_names.get(it['brand_slug'], it['brand_slug'])}\n"
            f"comment:\n{it['marked']}\n")
    return (
        SYSTEM
        + "\n\nLabel each item below. Produce ONE JSON object mapping every item id "
          "to its result object — every id present, no id skipped.\n\n"
        + "\n".join(lines)
        + f"\n\nWrite ONLY that JSON object to the file {out_fp} (create it). "
          "Do not print the JSON to the console. Do not write any other file."
    )


def valid_result(obj, item_ids):
    """A parsed out-file counts when it labels at least 90% of its items."""
    if not isinstance(obj, dict):
        return False
    hit = sum(1 for i in item_ids if isinstance(obj.get(i), dict))
    return hit >= max(1, int(0.9 * len(item_ids)))


def harvest_out(bid, item_ids):
    """out-file -> sentiment-cache file. Returns 'done' | 'pending'."""
    out_fp = os.path.join(RUN, f"out_{bid}.json")
    if not os.path.exists(out_fp):
        return "pending"
    try:
        raw = open(out_fp).read()
        # the model sometimes wraps the object in a fence — tolerate it
        m = re.search(r"\{.*\}", raw, re.S)
        obj = json.loads(m.group(0) if m else raw)
    except Exception:
        return "pending"          # mid-write is not corruption
    if not valid_result(obj, item_ids):
        return "pending"
    keep = {}
    for iid in item_ids:
        r = obj.get(iid)
        if isinstance(r, dict):
            label = str(r.get("label", "abstain")).lower()
            if label not in LABEL_CODE:
                r["label"] = "abstain"
            r["_engine"] = MODEL
            keep[iid] = r
    fp = os.path.join(CACHE, f"codex_{bid}.json")
    with open(fp + ".tmp", "w") as f:
        json.dump(keep, f)
    os.replace(fp + ".tmp", fp)
    return "done"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", action="append")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--batch", type=int, default=40)
    ap.add_argument("--window-days", type=int, default=365)
    ap.add_argument("--pilot", type=int, default=0, help="submit only the first N batches")
    ap.add_argument("--stall", type=int, default=420, help="seconds before resubmit")
    ap.add_argument("--max-rounds", type=int, default=3)
    args = ap.parse_args()

    import csv
    brand_names = {r["slug"]: r["brand"] for r in
                   csv.DictReader(open(os.path.join(os.path.dirname(HERE), "data", "brands.csv")))}

    slugs = ([f[:-5] for f in sorted(os.listdir(RESOLVED)) if f.endswith(".json")]
             if args.all else (args.category or []))
    if not slugs:
        ap.error("pass --category SLUG or --all")

    known = load_known()
    todo = []
    for slug in slugs:
        mentions = json.load(open(os.path.join(RESOLVED, slug + ".json")))["mentions"]
        kept = select_mentions(mentions, args.window_days, True, 0)
        for m in mentions:
            iid = f"{m['doc_id']}:{m['brand_slug']}"
            if iid in kept and iid not in known:
                todo.append({
                    "item_id": iid,
                    "brand_slug": m["brand_slug"],
                    "subreddit": m.get("subreddit") or "",
                    "link_title": m.get("link_title") or "",
                    "marked": mark_target(m.get("body") or "", m["matched_form"],
                                          m.get("char_offset", 0)),
                })
    # one item can appear in two categories' corpora — send it once
    seen, uniq = set(), []
    for it in todo:
        if it["item_id"] not in seen:
            seen.add(it["item_id"])
            uniq.append(it)
    todo = uniq
    print(f"{len(known)} labels cached · {len(todo)} items for the fleet", flush=True)

    by_id = {it["item_id"]: it for it in todo}

    for rnd in range(1, args.max_rounds + 1):
        # Recompute the remaining set from DISK each round: a batch that came
        # back 95% complete leaves its stragglers here, and they get re-batched
        # with fresh stable ids rather than lost.
        have = load_known()
        left = [it for iid, it in by_id.items() if iid not in have]
        if not left:
            break
        batches = {}
        for i in range(0, len(left), args.batch):
            chunk = left[i:i + args.batch]
            bid = hashlib.sha256("".join(it["item_id"] for it in chunk).encode()).hexdigest()[:16]
            batches[bid] = chunk
        if args.pilot:
            batches = dict(list(batches.items())[:args.pilot])
        pending = {b: items for b, items in batches.items()
                   if harvest_out(b, [it["item_id"] for it in items]) == "pending"}
        if not pending:
            break
        print(f"round {rnd}: {len(left)} items in {len(pending)} batches", flush=True)
        for bid, items in pending.items():
            out_fp = os.path.join(RUN, f"out_{bid}.json")
            if os.path.exists(out_fp):
                os.remove(out_fp)   # a failed/partial attempt; rewrite cleanly
            wait_for_slot()
            task = batch_task(items, brand_names, out_fp)
            journal({"batch": bid, "round": rnd, "n": len(items), "t": time.time()})
            for attempt in range(5):
                try:
                    r = fleet.submit(task, server=SERVER, mode="workspace-write",
                                     model=MODEL, workspace=RUN, timeout=args.stall,
                                     reasoning_effort="low")
                    journal({"batch": bid, "job_id": r["job_id"], "t": time.time()})
                    break
                except Exception as e:
                    time.sleep(10 * (attempt + 1))
                    if attempt == 4:
                        print(f"  !! submit failed for {bid}: {e}", flush=True)

        # drain: completion is out-files on disk, stall = leave for next round
        deadline = time.time() + args.stall + 120
        while time.time() < deadline:
            left = [b for b, items in pending.items()
                    if harvest_out(b, [it["item_id"] for it in items]) == "pending"]
            done_n = len(batches) - len([b for b, i2 in batches.items()
                                         if harvest_out(b, [x["item_id"] for x in i2]) == "pending"])
            print(f"  {done_n}/{len(batches)} batches done", flush=True)
            if not left:
                break
            time.sleep(20)

    have = load_known()
    still = [iid for iid in by_id if iid not in have]
    print(f"\nfleet pass complete: +{len(have) - len(known)} labels, "
          f"{len(still)} items unresolved", flush=True)
    return 0 if not still else 1


if __name__ == "__main__":
    sys.exit(main())
