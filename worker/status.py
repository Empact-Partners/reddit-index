#!/usr/bin/env python3
"""One screen: are the lanes running, how fast, and is anything stuck.

This exists because its absence is what let a classify stall sit unnoticed for
hours while the Reddit lane was idle behind it. Read-only; safe at any time.

    python3 worker/status.py
    python3 worker/status.py --watch      # refresh every 30s
"""
import argparse
import csv
import glob
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.expanduser("~/.claude/api_helpers"))

import leases  # noqa: E402

RATE_FP = os.path.join(HERE, ".cache", "depth", "status_rate.json")


def procs(pattern):
    try:
        out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
        return [p for p in out.stdout.split() if p]
    except Exception:
        return []


def swept_total():
    n = 0
    for f in glob.glob(os.path.join(HERE, ".cache", "sweep", "*.json")):
        try:
            n += len(json.load(open(f)).get("swept", []))
        except Exception:
            pass
    return n


def core_progress():
    import sweep
    mode_fp = os.path.join(HERE, ".cache", "depth", "mode.json")
    mode = json.load(open(mode_fp)) if os.path.exists(mode_fp) else {"days": 90, "tree_cap": 150}
    subs = set()
    with open(os.path.join(REPO, "data", "category-subreddits.csv")) as f:
        for r in csv.DictReader(f):
            if r.get("is_scoring") == "True" and r.get("is_core") == "True":
                subs.add(r["subreddit"])
    m = sweep.make_mode(mode["days"])
    done = sum(1 for s in subs if sweep.sub_complete(s, m, mode.get("tree_cap")))
    return done, len(subs)


def db_counts():
    from load import sql
    r = sql("""SELECT
        (SELECT count(*) FROM mentions)::int AS mentions,
        (SELECT count(*) FROM mention_sentiment)::int AS labelled,
        (SELECT count(*) FROM threads)::int AS threads,
        (SELECT count(*) FROM brand_category_scores)::int AS scores""")
    return r[0] if r else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true")
    args = ap.parse_args()

    while True:
        now = time.time()
        col = procs("collector.py")
        cls = procs("classify_daemon.py")
        pub = procs("publisher.py")
        held = {k: v for k, v in leases.scan().items() if v.get("held")}
        sub_leases = {k: v for k, v in held.items() if k != "publisher"}

        trees = swept_total()
        counts = {}
        try:
            counts = db_counts()
        except Exception as e:
            counts = {"error": str(e)[:60]}

        prev = None
        if os.path.exists(RATE_FP):
            try:
                prev = json.load(open(RATE_FP))
            except Exception:
                prev = None
        json.dump({"t": now, "trees": trees, "labelled": counts.get("labelled", 0)},
                  open(RATE_FP, "w"))

        tr = lr = None
        if prev and now - prev["t"] > 60:
            dt = now - prev["t"]
            tr = (trees - prev["trees"]) / dt * 60
            lr = (counts.get("labelled", 0) - prev.get("labelled", 0)) / dt * 60

        try:
            load1 = os.getloadavg()[0]
        except OSError:
            load1 = 0
        free_gb = shutil.disk_usage(os.path.join(HERE, ".cache")).free / 2 ** 30
        codex = len(procs("codex exec"))
        try:
            done, total = core_progress()
        except Exception:
            done, total = 0, 0

        print("\033[2J\033[H" if args.watch else "", end="")
        print(f"reddit-index · {time.strftime('%H:%M:%S')}")
        print(f"  collector   {'UP  ' if col else 'DOWN'} | core subs {done}/{total}"
              f" | {len(sub_leases)} leased"
              f"{f' | {tr:.0f} trees/min' if tr is not None else ''}")
        print(f"  classifier  {'UP  ' if cls else 'DOWN'} | {codex} codex procs"
              f"{f' | {lr:.0f} labels/min' if lr is not None else ''}")
        print(f"  publisher   {'UP  ' if pub else 'idle'}", end="")
        pfp = os.path.join(HERE, ".cache", "depth", "publish.json")
        if os.path.exists(pfp):
            try:
                p = json.load(open(pfp))
                print(f" | last {p.get('last_publish')} | {p.get('publishes', 0)} publishes",
                      end="")
            except Exception:
                pass
        print()
        if counts.get("error"):
            print(f"  db          ERROR {counts['error']}")
        else:
            unl = counts.get("mentions", 0) - counts.get("labelled", 0)
            print(f"  corpus      {counts.get('mentions', 0):,} mentions | "
                  f"{counts.get('labelled', 0):,} labelled | {unl:,} backlog | "
                  f"{counts.get('scores', 0):,} scores")
        print(f"  machine     load {load1:.0f} | {free_gb:.0f} GB free")

        blocked = os.path.join(HERE, ".cache", "index", "_blocked.json")
        if os.path.exists(blocked):
            try:
                b = json.load(open(blocked)).get("blocked", {})
                print(f"  ⚠ quarantined categories: {', '.join(sorted(b))[:100]}")
            except Exception:
                pass
        stale = [k for k, v in sub_leases.items() if now - (v.get("last_beat") or now) > 600]
        if stale:
            print(f"  ⚠ leases with no heartbeat >10m: {', '.join(stale[:5])}")

        if not args.watch:
            return 0
        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main())
