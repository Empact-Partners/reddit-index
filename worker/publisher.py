#!/usr/bin/env python3
"""Periodic score + publish — decoupled from both collection and labelling.

depth_run.py used to score and publish inline, after every category, on the
same thread that fetched Reddit: a full 100-category rescore ~99 times per
run, each one blocking collection entirely. Publishing is now its own timer.

It only works when there is something to publish: a cheap query counts labels
committed since the last run and skips the whole cycle below --min-new-labels.
That matters now that the classifier commits continuously — without it this
would rebuild the site every half hour for noise.

    python3 worker/publisher.py                 # loop every 30 min
    python3 worker/publisher.py --once          # one cycle, then exit
    python3 worker/publisher.py --every 6h --min-new-labels 2000
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import db  # noqa: E402
import leases  # noqa: E402

STATE_FP = os.path.join(HERE, ".cache", "depth", "publish.json")
CRED_FP = os.path.expanduser("~/.claude/.reddit-index.json")
SCORE_TIMEOUT = 7200
STOP = {"v": False}


def parse_every(s):
    m = re.fullmatch(r"(\d+)([smh]?)", str(s).strip())
    if not m:
        raise ValueError(f"bad --every: {s}")
    n, unit = int(m.group(1)), m.group(2) or "m"
    return n * {"s": 1, "m": 60, "h": 3600}[unit]


def load_state():
    try:
        return json.load(open(STATE_FP))
    except Exception:
        return {"last_labels": 0, "last_publish": None, "publishes": 0}


def save_state(st):
    os.makedirs(os.path.dirname(STATE_FP), exist_ok=True)
    with open(STATE_FP + ".tmp", "w") as f:
        json.dump(st, f, indent=1)
    os.replace(STATE_FP + ".tmp", STATE_FP)


def label_count(state):
    def _q(c):
        with c.cursor() as cur:
            cur.execute("SELECT count(*)::int FROM mention_sentiment")
            return cur.fetchone()[0]
    return db.run(state, _q, label="label count")


def deploy_hook():
    try:
        return json.load(open(CRED_FP)).get("deploy_hook") or None
    except Exception:
        return None


def _git(args, timeout=300):
    return subprocess.run(["git", "-C", REPO] + args, capture_output=True,
                          text=True, timeout=timeout)


def publish(allow_git):
    hook = deploy_hook()
    if hook:
        err = None
        for attempt in range(5):
            try:
                with urllib.request.urlopen(
                        urllib.request.Request(hook, data=b"", method="POST"),
                        timeout=30) as f:
                    f.read()
                print("  published (deploy hook)", flush=True)
                return True
            except Exception as e:
                err = e
                time.sleep(min(120, 10 * 2 ** attempt))
        print(f"  deploy hook failed after 5 tries: {err} — data is safe, the "
              f"next cycle republishes", flush=True)
        return False
    if not allow_git:
        print("  no deploy_hook and --allow-git-publish not set — skipped", flush=True)
        return False
    try:
        if _git(["status", "--porcelain"], timeout=60).stdout.strip():
            # never stash or commit a human session's work from a daemon
            print("  working tree dirty — publish skipped", flush=True)
            return False
        for a in (["pull", "--ff-only", "--quiet"],
                  ["commit", "--allow-empty", "-q", "-m",
                   f"publish {time.strftime('%F %H:%M')}"],
                  ["push", "-q"]):
            r = _git(a)
            if r.returncode != 0:
                print(f"  git publish failed at {a[0]}: "
                      f"{(r.stderr or '').strip()[:140]}", flush=True)
                return False
    except subprocess.TimeoutExpired:
        print("  git publish TIMED OUT — skipped", flush=True)
        return False
    print("  published (git empty-commit)", flush=True)
    return True


def cycle(args, state, st):
    labels = label_count(state)
    new = labels - (st.get("last_labels") or 0)
    if new < args.min_new_labels and not args.force:
        print(f"  {new} new labels since last publish (< {args.min_new_labels}) "
              f"— skipping", flush=True)
        return False
    print(f"  {new} new labels — scoring…", flush=True)
    try:
        r = subprocess.run([sys.executable, "-u", os.path.join(HERE, "score_db.py")],
                           cwd=HERE, timeout=SCORE_TIMEOUT)
    except subprocess.TimeoutExpired:
        print(f"  score_db exceeded {SCORE_TIMEOUT}s — killed, will retry", flush=True)
        return False
    if r.returncode != 0:
        print("  score_db refused to load (systemic calibration failure) — "
              "previous scores stay live", flush=True)
        return False
    blocked_fp = os.path.join(HERE, ".cache", "index", "_blocked.json")
    if os.path.exists(blocked_fp):
        try:
            b = json.load(open(blocked_fp)).get("blocked", {})
            print(f"  note: {len(b)} category(ies) quarantined, rest published: "
                  f"{', '.join(sorted(b))[:120]}", flush=True)
        except Exception:
            pass
    ok = publish(args.allow_git_publish)
    st["last_labels"] = labels
    st["last_publish"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    st["publishes"] = (st.get("publishes") or 0) + (1 if ok else 0)
    save_state(st)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", default="30m", help="cycle period (30m, 6h, 900s)")
    ap.add_argument("--min-new-labels", type=int, default=500,
                    help="skip the cycle below this many new labels")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--force", action="store_true", help="ignore --min-new-labels")
    ap.add_argument("--allow-git-publish", action="store_true")
    args = ap.parse_args()
    period = parse_every(args.every)

    # one publisher, ever: score_db's prune is a global DELETE and load.py
    # re-stamps every category, so two concurrent publishes can interleave
    # into one week_start and race the prune
    lock = leases.Lease("publisher")
    if not lock.acquire():
        print("another publisher holds the lock — exiting", flush=True)
        return 1

    def _sig(*_):
        STOP["v"] = True
        print("\nstopping after this cycle…", flush=True)
    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    state = {"conn": db.connect()}
    st = load_state()
    print(f"publisher: every {args.every}, min_new_labels={args.min_new_labels}",
          flush=True)
    try:
        while not STOP["v"]:
            print(f"[{time.strftime('%H:%M')}] cycle", flush=True)
            try:
                cycle(args, state, st)
            except Exception as e:
                print(f"  cycle error: {str(e).splitlines()[0][:140]}", flush=True)
            if args.once or STOP["v"]:
                break
            lock.beat(note=f"idle until +{period}s")
            for _ in range(int(period)):
                if STOP["v"]:
                    break
                time.sleep(1)
    finally:
        try:
            state["conn"].close()
        except Exception:
            pass
        lock.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
