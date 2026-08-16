#!/usr/bin/env python3
"""Restart a lane that is UP but no longer making progress.

launchd's KeepAlive only notices a process that EXITED. The failure that cost
us a night was different in kind: the lanes were alive in launchctl and making
zero progress, and nothing was watching the one thing that matters — whether
bytes are still landing on disk.

Each lane writes continuously when healthy (measured sub-minute for both), so
STALL_MIN is set an order of magnitude above the healthy interval: a restart
fires only on a genuine stall, never on a slow patch. Restarting mid-subreddit
is safe — sweep state is committed per tree and every write is idempotent.

Also re-asserts the keepawake lane, because sleep protection that depends on a
lane surviving is what let the Mac sleep in the first place.

    python3 worker/watchdog.py --once     # check, act, exit (launchd runs this)
    python3 worker/watchdog.py --dry-run  # report, change nothing
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
UID = os.getuid()

STALL_MIN = 45.0        # ~40x the healthy write interval
GRACE_MIN = 10.0        # don't judge a lane we just restarted

# lane -> directories whose newest mtime proves the lane is doing work
SIGNALS = {
    "collector": [".cache/sweep"],
    "classifier": [".cache/sentiment", ".cache/codex-absa"],
}
LAST_ACTION = os.path.join(HERE, ".cache", "depth", "watchdog.json")


def log(msg):
    print(f"[{time.strftime('%F %H:%M:%S')}] {msg}", flush=True)


def newest_mtime(rel):
    p = os.path.join(HERE, rel)
    best = 0.0
    for root, _dirs, files in os.walk(p):
        for f in files:
            try:
                m = os.stat(os.path.join(root, f)).st_mtime
            except OSError:
                continue
            if m > best:
                best = m
    return best


def idle_minutes(lane):
    """Minutes since this lane last wrote anything. inf if it never has."""
    best = max((newest_mtime(r) for r in SIGNALS[lane]), default=0.0)
    if not best:
        return float("inf")
    return (time.time() - best) / 60.0


def launchctl_pid(label):
    r = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[2].strip() == f"com.reddit-index.{label}":
            return parts[0].strip()
    return None


def kickstart(label, dry):
    if dry:
        log(f"  DRY-RUN would restart {label}")
        return False
    r = subprocess.run(
        ["launchctl", "kickstart", "-k", f"gui/{UID}/com.reddit-index.{label}"],
        capture_output=True, text=True)
    ok = r.returncode == 0
    log(f"  restarted {label}" if ok else
        f"  restart FAILED for {label}: {(r.stderr or '').strip()[:120]}")
    return ok


def recently_acted(lane):
    """A lane restarted a moment ago has not had time to write yet."""
    try:
        import json
        st = json.load(open(LAST_ACTION))
        return (time.time() - st.get(lane, 0)) / 60.0 < GRACE_MIN
    except Exception:
        return False


def record(lane):
    import json
    try:
        st = json.load(open(LAST_ACTION))
    except Exception:
        st = {}
    st[lane] = time.time()
    os.makedirs(os.path.dirname(LAST_ACTION), exist_ok=True)
    with open(LAST_ACTION + ".tmp", "w") as f:
        json.dump(st, f)
    os.replace(LAST_ACTION + ".tmp", LAST_ACTION)


def keepawake_ok():
    """Is SOMETHING holding the idle-sleep assertion right now?"""
    r = subprocess.run(["pmset", "-g", "assertions"], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if "PreventUserIdleSystemSleep" in line and "caffeinate" in line:
            return True
    return False


def check(dry):
    acted = False

    # every lane launchd owns must have a live pid
    for label in ("collector", "classifier", "publisher", "keepawake"):
        pid = launchctl_pid(label)
        if pid in (None, "-", "0"):
            log(f"{label}: no running pid — restarting")
            if kickstart(label, dry):
                record(label)
                acted = True

    # a lane can be UP and doing nothing; that is the case launchd cannot see
    for lane in SIGNALS:
        if recently_acted(lane):
            log(f"{lane}: in restart grace period, skipping stall check")
            continue
        idle = idle_minutes(lane)
        shown = "never" if idle == float("inf") else f"{idle:.1f} min"
        if idle > STALL_MIN:
            log(f"{lane}: STALLED — no write for {shown} (limit {STALL_MIN:.0f})")
            if kickstart(lane, dry):
                record(lane)
                acted = True
        else:
            log(f"{lane}: healthy, last write {shown} ago")

    if not keepawake_ok():
        log("no idle-sleep assertion held — restarting keepawake")
        if kickstart("keepawake", dry):
            acted = True
    else:
        log("sleep protection: asserted")

    return acted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--every", type=int, default=300)
    args = ap.parse_args()
    while True:
        try:
            check(args.dry_run)
        except Exception as e:
            log(f"watchdog error: {str(e).splitlines()[0][:140]}")
        if args.once or args.dry_run:
            return 0
        time.sleep(args.every)


if __name__ == "__main__":
    sys.exit(main())
