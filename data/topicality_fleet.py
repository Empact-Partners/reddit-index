#!/usr/bin/env python3
"""Fill refine.py's per-item topicality cache from the Codex fleet.

Same SYSTEM prompt, same T in {0.0, 0.5, 1.0}, same cache files
(.discover-cache/topicality/<cat>_<sub>.json) — refine.py then finds every
pair cached and makes ZERO claude -p calls. The fleet runs 40-wide where
claude -p is capped at 2; at ~2,700 pairs that is the difference between an
hour and an afternoon.

Run AFTER discover.py has rewritten category-subreddits.csv, BEFORE refine.py.
"""
import csv, hashlib, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "worker"))
sys.path.insert(0, os.path.expanduser("~/.claude/api_helpers"))
from codex_fleet import CodexFleet  # noqa: E402

TOPIC = os.path.join(HERE, ".discover-cache", "topicality")
BODIES = os.path.join(HERE, ".discover-cache")
RUN = os.path.join(HERE, ".topicality-fleet")
os.makedirs(TOPIC, exist_ok=True)
os.makedirs(RUN, exist_ok=True)

SERVER = "local-mac"
MAX_INFLIGHT = 40
fleet = CodexFleet()

SYSTEM = """You judge whether a Reddit community is a place where a named
software category is actually evaluated and discussed by its practitioners.

Answer for each item with one number:
  1.0  the community IS about this category, or about the work that uses it
       daily, so buying and switching decisions get discussed there
  0.5  adjacent: the category comes up as a tool of a broader trade
  0.0  wrong: brand names may appear, but never as a product evaluation
       (hobby, sport, local, meme, marketplace, news, or unrelated trade
       communities all score 0.0 even when the words appear constantly)

Be strict. A used-hardware marketplace where people say "PayPal" to arrange a
sale is 0.0 for Payment Processing. A jiu-jitsu community is 0.0 for everything."""


def cache_fp(iid):
    return os.path.join(TOPIC, re.sub(r"[^a-z0-9|]+", "_", iid.lower()) + ".json")


def descriptions():
    """Subreddit descriptions from discover's per-sub measure cache."""
    out = {}
    for fn in os.listdir(BODIES):
        if not fn.endswith(".json") or fn.startswith("_") or "/" in fn:
            continue
        try:
            d = json.load(open(os.path.join(BODIES, fn)))
            name = d.get("subreddit") or d.get("name")
            if name:
                out[str(name).lower()] = (d.get("public_description")
                                          or d.get("description") or "")[:400]
        except Exception:
            pass
    return out


def fleet_running():
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


def parse_out(fp):
    try:
        raw = open(fp).read()
        m = re.search(r"\{.*\}", raw, re.S)
        return json.loads(m.group(0) if m else raw)
    except Exception:
        return None


def main():
    rows = list(csv.DictReader(open(os.path.join(HERE, "category-subreddits.csv"))))
    descs = descriptions()
    todo = []
    for r in rows:
        iid = f"{r['category_slug']}|{r['subreddit']}"
        if not os.path.exists(cache_fp(iid)):
            todo.append((iid, r["category"], r["subreddit"],
                         descs.get(r["subreddit"].lower(), "")))
    print(f"{len(rows)} slots, {len(todo)} uncoded pairs for the fleet", flush=True)

    for rnd in range(1, 4):
        left = [t for t in todo if not os.path.exists(cache_fp(t[0]))]
        if not left:
            break
        batches = {}
        for i in range(0, len(left), 25):
            chunk = left[i:i + 25]
            bid = hashlib.sha256("".join(t[0] for t in chunk).encode()).hexdigest()[:16]
            batches[bid] = chunk
        print(f"round {rnd}: {len(left)} pairs in {len(batches)} batches", flush=True)
        for bid, chunk in batches.items():
            fp = os.path.join(RUN, f"out_{bid}.json")
            if parse_out(fp) is not None:
                harvest(fp, chunk)
                continue
            if os.path.exists(fp):
                os.remove(fp)
            lines = []
            for iid, cat, sub, desc in chunk:
                d = (desc or "").replace("\n", " ")[:260]
                lines.append(f'{iid}\tcategory="{cat}"\tr/{sub}\t{d or "(no description)"}')
            task = (SYSTEM + "\n\nRate each item below. Write ONLY a JSON object "
                    f"mapping every item id (the first tab-separated field) to its "
                    f"number to the file {fp} (create it). Every id present.\n\n"
                    + "\n".join(lines))
            wait_for_slot()
            for attempt in range(5):
                try:
                    fleet.submit(task, server=SERVER, mode="workspace-write",
                                 model="gpt-5.6-luna", workspace=RUN, timeout=300,
                                 reasoning_effort="low")
                    break
                except Exception:
                    time.sleep(10 * (attempt + 1))
        deadline = time.time() + 420
        while time.time() < deadline:
            n_left = 0
            for bid, chunk in batches.items():
                fp = os.path.join(RUN, f"out_{bid}.json")
                obj = parse_out(fp)
                if obj is None:
                    n_left += 1
                else:
                    harvest(fp, chunk)
            done = sum(1 for t in todo if os.path.exists(cache_fp(t[0])))
            print(f"  {done}/{len(todo)} pairs coded", flush=True)
            if not n_left:
                break
            time.sleep(20)

    done = sum(1 for t in todo if os.path.exists(cache_fp(t[0])))
    print(f"fleet topicality complete: {done}/{len(todo)} newly coded", flush=True)
    return 0


def harvest(fp, chunk):
    obj = parse_out(fp)
    if not isinstance(obj, dict):
        return
    for iid, *_ in chunk:
        v = obj.get(iid)
        if v is None:
            continue
        try:
            t = float(v)
        except (TypeError, ValueError):
            continue
        if t in (0.0, 0.5, 1.0):
            json.dump({"t": t}, open(cache_fp(iid), "w"))


if __name__ == "__main__":
    sys.exit(main())
