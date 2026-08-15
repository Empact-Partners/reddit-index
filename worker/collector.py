#!/usr/bin/env python3
"""Continuous collection daemon — sweeps subreddits, never waits on the fleet.

This replaces depth_run.py's drive loop, which ran
sweep -> classify -> score -> publish serially per category and therefore made
ZERO Reddit calls for the hours each classification took. Collection and
classification share nothing but Postgres, and every write there is
ON CONFLICT DO NOTHING, so the two lanes are now separate processes that never
block each other.

The unit of work is a SUBREDDIT, not a category. 263 of the 527 core subs sit
in two or more categories (r/sysadmin in 52), so partitioning by category
would put two workers on the same worker/.cache/sweep/<sub>.json, which is a
read-modify-write and would lose swept-tree records. Leases are per sub and
held with flock, so a killed collector frees its sub instantly (see leases.py).

Order of work is category fairness: each sub is scored by the LEAST-covered
category it unlocks, so categories fill in evenly instead of one at a time.

    python3 worker/collector.py                     # run until the core set is done
    python3 worker/collector.py --once              # one sub, then exit (smoke test)
    python3 worker/collector.py --status
"""
import argparse
import json
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import csv  # noqa: E402
import sweep  # noqa: E402
import leases  # noqa: E402
import reddit_client as rc  # noqa: E402

MODE_FP = os.path.join(HERE, ".cache", "depth", "mode.json")
STOP = {"v": False}


def load_mode():
    """The collection mode is PINNED on disk, never retyped on a command line.

    sweep.load_state resets a sub whose stored mode_key differs, which silently
    re-lists every subreddit. days/min_comments/matcher and the tree cap must
    therefore be identical across every process and every restart.
    """
    if os.path.exists(MODE_FP):
        return json.load(open(MODE_FP))
    m = {"days": 90, "tree_cap": 150}
    os.makedirs(os.path.dirname(MODE_FP), exist_ok=True)
    json.dump(m, open(MODE_FP, "w"), indent=1)
    return m


def core_map():
    """sub -> [category slugs], CORE subs only (data/select_core_subs.py)."""
    out = {}
    with open(os.path.join(REPO, "data", "category-subreddits.csv")) as f:
        for r in csv.DictReader(f):
            if r.get("is_scoring") == "True" and r.get("is_core") == "True":
                out.setdefault(r["subreddit"], []).append(r["category_slug"])
    return out


def est_threads(sub):
    """Cheap size estimate from disk state; unknown subs sort mid-pack."""
    try:
        st = json.load(open(sweep.state_path(sub)))
        return len(st.get("post_ids", [])) - len(st.get("swept", []))
    except Exception:
        return 150


def coverage(mapping, sweep_mode, tree_cap):
    """category -> fraction of its core subs already complete."""
    done = {}
    for sub, slugs in mapping.items():
        c = sweep.sub_complete(sub, sweep_mode, tree_cap)
        for s in slugs:
            a, b = done.get(s, (0, 0))
            done[s] = (a + (1 if c else 0), b + 1)
    return {s: (a / b if b else 1.0) for s, (a, b) in done.items()}


def claim_next(mapping, ctx, tree_cap):
    """Lease the most valuable unclaimed, incomplete sub. None when done."""
    cov = coverage(mapping, ctx["mode"], tree_cap)
    cands = []
    for sub, slugs in mapping.items():
        if sweep.sub_complete(sub, ctx["mode"], tree_cap):
            continue
        # the least-covered category this sub unlocks drives priority, so
        # every category advances rather than one finishing at a time
        worst = min((cov.get(s, 0.0) for s in slugs), default=0.0)
        cands.append((worst, -est_threads(sub), sub))
    cands.sort()
    for _, _, sub in cands:
        if leases.is_held(sub):
            continue
        lease = leases.Lease(sub)
        if lease.acquire():
            return sub, lease
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="sweep one sub then exit")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--id", default=os.environ.get("RI_COLLECTOR_ID", "1"))
    args = ap.parse_args()

    mode = load_mode()
    mapping = core_map()

    if args.status:
        ctx_mode = sweep.make_mode(mode["days"])
        done = sum(1 for s in mapping if sweep.sub_complete(s, ctx_mode, mode.get("tree_cap")))
        held = {k: v for k, v in leases.scan().items() if v.get("held")}
        print(f"core subs {done}/{len(mapping)} complete | {len(held)} leased")
        for k, v in sorted(held.items()):
            print(f"   {k:30} pid={v.get('pid')} {v.get('note','')}")
        return 0

    def _sig(*_):
        print("\nstopping after the current subreddit…", flush=True)
        STOP["v"] = True
    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    print(f"collector {args.id}: days={mode['days']} tree_cap={mode['tree_cap']} "
          f"core_subs={len(mapping)}", flush=True)
    ctx = sweep.prepare(mode["days"], core_only=True)
    ctx["tree_cap"] = mode.get("tree_cap") or 10 ** 9

    swept_total = mentions_total = subs_done = 0
    t0 = time.time()
    while not STOP["v"]:
        sub, lease = claim_next(mapping, ctx, ctx["tree_cap"])
        if sub is None:
            print("no claimable subreddit — core set complete or all leased", flush=True)
            break
        try:
            lease.beat(note="sweeping")
            trees, m = sweep.sweep_sub(sub, ctx["mapping"].get(sub, []), ctx,
                                       ctx["tree_cap"])
            swept_total += trees
            mentions_total += m
            subs_done += 1
            el = max(time.time() - t0, 1)
            st = rc.stats()
            print(f"[{subs_done}] {sub}: +{trees} trees +{m} mentions | "
                  f"{swept_total/el*60:.0f} trees/min | "
                  f"{st['calls_per_min']:.0f} req/min", flush=True)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"  {sub}: ERROR {str(e).splitlines()[0][:150]}", flush=True)
            try:
                ctx["conn"].rollback()
            except Exception:
                try:
                    import db
                    ctx["conn"] = db.connect()
                except Exception:
                    pass
            time.sleep(5)
        finally:
            lease.release()
        if args.once:
            break

    try:
        ctx["conn"].close()
    except Exception:
        pass
    el = max(time.time() - t0, 1)
    print(f"collector stopped: {subs_done} subs, {swept_total} trees, "
          f"{mentions_total} mentions in {el/60:.0f} min", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
