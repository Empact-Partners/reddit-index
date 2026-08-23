#!/usr/bin/env python3
"""Keep the expansion pipeline running across sleeps, kills and reboots — without ever
becoming the runaway that caused the 2026-08-21 OOM.

The runaway was an UNCAPPED retry loop that resubmitted 25-minute-timeout fleet jobs on top
of in-flight ones. Every property below exists to make that impossible here:

  never two lanes      it refuses to start anything while ANY Reddit/pipeline process is
                       alive. The single reddit_client at 0.75s is the shared budget; two
                       lanes deadlock (proven 2026-08-22).
  capped, on disk      MAX_ATTEMPTS total restarts, counted in state.json. A SIGKILL and a
                       launchd revival do NOT reset the counter — that is the whole point of
                       keeping it on disk rather than in memory.
  cooldown             COOLDOWN_S between attempts, so a fast-failing stage cannot spin.
  preflight            free-RAM + swap-growth gate before each attempt (never a % of the
                       macOS swap pool — that reads ~90% on a healthy box).
  exits 0 when done    launchd runs this with KeepAlive/SuccessfulExit=false, so a clean
                       exit — complete OR capped — ends supervision. Only a crash revives it.

Resume point is read from the log, not guessed: stages are individually resumable because
discover_v2 keys its caches by subreddit, never by run.

  python3 data/pipeline_supervisor.py            # supervise (launchd runs this)
  python3 data/pipeline_supervisor.py --status   # report, change nothing
"""
import argparse, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PDIR = os.path.join(HERE, '.pipeline')
LOG = os.path.join(PDIR, 'pipeline.log')
STATE = os.path.join(PDIR, 'state.json')

AGENT_LABEL = 'com.vladshvets.reddit-index-pipeline'
AGENT_PLIST = os.path.expanduser(f'~/Library/LaunchAgents/{AGENT_LABEL}.plist')

MAX_ATTEMPTS = 6
COOLDOWN_S = 600
POLL_S = 60
STAGES = ['enumerate', 'evidence', 'rescue', 'siblings', 'candidates', 'qualify']

# any of these alive means a lane is already running; we wait, we never race it
LANE_PATTERNS = [
    'resume_chain.py', 'run_discovery_all.py', 'run_collection_all.py',
    'run_finish_all.py', 'enumerate_brands.py',
    'discover_v2.py', 'worker/sweep.py', 'worker/daily.py',
    'classify_brands.py', 'backfill_posts.py', 'delete_sync.py', 'publish.py',
]

sys.path.insert(0, os.path.expanduser('~/.claude/scripts'))


def uninstall():
    """Remove the launchd agent. This is what keeps the supervisor from becoming the thing
    decisions/0010 bans.

    0010 forbids schedulers, watchdogs and auto-resumers in this repo, because an unbounded
    one cost $513 for zero completions. The exception granted for this run is that a bounded
    supervisor may carry ONE already-started job to its end. A job that has ended has no
    supervisor: the plist is deleted so it cannot come back at next login, and the agent is
    booted out. Nothing here survives the run it was installed for."""
    try:
        if os.path.exists(AGENT_PLIST):
            os.remove(AGENT_PLIST)
            say(f'removed {AGENT_PLIST}')
        subprocess.call(['launchctl', 'bootout', f'gui/{os.getuid()}/{AGENT_LABEL}'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        say('launchd agent uninstalled — no automation left behind (decisions/0010)')
    except Exception as e:
        say(f'could not uninstall the agent ({e}) — remove {AGENT_PLIST} by hand')


def say(msg):
    line = f'{time.strftime("%Y-%m-%d %H:%M:%S")} [supervisor] {msg}'
    print(line, flush=True)
    os.makedirs(PDIR, exist_ok=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')


def state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {'attempts': 0, 'done': False, 'gave_up': False, 'history': []}


def save(s):
    os.makedirs(PDIR, exist_ok=True)
    tmp = STATE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(s, f, indent=2)
    os.replace(tmp, STATE)


def lane_pids():
    """PIDs of running pipeline work, excluding this supervisor.

    Only PYTHON processes count. A shell whose command line merely mentions a script — a
    `while pgrep -f resume_chain.py` monitor, say — matches pgrep but is not a lane, and one
    of those satisfies its own condition forever, which would deadlock this supervisor."""
    me = {os.getpid()}
    out = []
    for pat in LANE_PATTERNS:
        try:
            r = subprocess.run(['pgrep', '-f', pat], capture_output=True, text=True)
        except Exception:
            continue
        for pid in r.stdout.split():
            p = int(pid)
            if p in me:
                continue
            try:
                comm = subprocess.run(['ps', '-p', str(p), '-o', 'comm='],
                                      capture_output=True, text=True).stdout.strip()
            except Exception:
                continue
            if 'python' in os.path.basename(comm).lower():
                out.append((p, pat))
    return sorted(set(out))


# The chain that was already running when this supervisor was installed writes to a log in
# the session scratchpad. Its completion markers must be visible here or the supervisor would
# restart work that had already finished — and the scratchpad is wiped on reboot, which is why
# everything new writes to LOG instead.
LEGACY = ('/private/tmp/claude-501/-Users-vladshvets--claude/'
          'a1692ad3-6a83-4c15-a278-cf20122c2225/scratchpad/chain_rest.log')


def log_text():
    out = []
    for p in (LOG, LEGACY):
        try:
            out.append(open(p, errors='replace').read())
        except Exception:
            pass
    return '\n'.join(out)


def collection_done():
    return 'COLLECTION COMPLETE' in log_text()


def finish_done():
    return 'FINISH COMPLETE' in log_text()


def discovery_done():
    return 'DISCOVERY COMPLETE' in log_text()


def resume_stage():
    """Last stage the log shows STARTED. Stages are resumable, so restarting the one that
    was interrupted is correct and mostly cache hits."""
    seen = re.findall(r'^=== (\w[\w-]*) ·', log_text(), re.M)
    for s in reversed(seen):
        if s in STAGES:
            return s
    return None


def gate(width):
    """Refuse to start a wave on a box that cannot carry it. Absolute headroom + swap GROWTH,
    never % of the macOS swap pool."""
    try:
        from fleet_preflight import preflight
        preflight(want=width)
        return True
    except SystemExit as e:
        say(f'preflight refused: {e}')
        return False
    except Exception as e:
        say(f'preflight unavailable ({e}) — proceeding without it')
        return True


def run(args, label):
    say(f'starting {label}: {" ".join(os.path.basename(a) for a in args[1:3])}')
    with open(LOG, 'a', buffering=1) as f:
        f.write(f'\n{time.strftime("%H:%M:%S")} SUPERVISOR START {label}\n')
        rc = subprocess.call(args, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        f.write(f'{time.strftime("%H:%M:%S")} SUPERVISOR {label} exited {rc}\n')
    say(f'{label} exited {rc}')
    return rc


def attempt():
    """One full pass: discovery, then collection, then the finishing leg. Each part is
    skipped if its completion marker is already in the log. Finite; no inner retries."""
    if not discovery_done():
        st = resume_stage()
        args = [sys.executable, f'{HERE}/run_discovery_all.py', '--width', '6']
        if st:
            args += ['--from', st]
        if not gate(6):
            return 90
        rc = run(args, f'discovery (from {st or "start"})')
        if rc != 0:
            return rc
    else:
        say('discovery already complete — going straight to collection')

    if not collection_done():
        if not gate(2):
            return 90
        rc = run([sys.executable, f'{HERE}/run_collection_all.py'], 'collection')
        if rc != 0:
            return rc
    else:
        say('collection already complete — going straight to the finishing leg')

    # outreach expansion + wave-2 queues + gates. The only fleet stage in it runs alone,
    # because discovery is finished by the time we get here.
    if not gate(6):
        return 90
    return run([sys.executable, f'{HERE}/run_finish_all.py'], 'finish')


def status():
    s = state()
    lanes = lane_pids()
    print(f'discovery={discovery_done()} collection={collection_done()} '
          f'finish={finish_done()} attempts={s["attempts"]}/{MAX_ATTEMPTS} '
          f'gave_up={s.get("gave_up")}')
    print(f'resume stage: {resume_stage()}')
    print(f'lanes alive: {lanes if lanes else "none"}')
    tail = log_text().splitlines()[-5:]
    print('log tail:')
    for t in tail:
        print(' ', t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--status', action='store_true')
    a = ap.parse_args()
    if a.status:
        return status()

    os.makedirs(PDIR, exist_ok=True)
    say(f'supervising (cap {MAX_ATTEMPTS} attempts, cooldown {COOLDOWN_S}s)')

    while True:
        # done is recorded in BOTH places on purpose. The log is the detailed record but it
        # is a file that can be rotated, truncated or lost, and a supervisor that forgets it
        # finished would redo a multi-day run from the start.
        if state().get('done'):
            say('state.json says this run finished — nothing to do')
            uninstall()
            return 0
        if finish_done():
            s = state(); s['done'] = True; save(s)
            say('FINISH COMPLETE seen in log — pipeline done end to end, supervision ends')
            uninstall()
            return 0

        s = state()
        if s.get('gave_up'):
            say(f'already gave up after {s["attempts"]} attempts — not restarting. '
                f'A human must look at {LOG}')
            uninstall()
            return 0

        lanes = lane_pids()
        if lanes:
            # a lane is running: watch it, start nothing. This is the normal state.
            time.sleep(POLL_S)
            continue

        if s['attempts'] >= MAX_ATTEMPTS:
            s['gave_up'] = True; save(s)
            say(f'GIVING UP after {MAX_ATTEMPTS} attempts. Nothing further will start.')
            uninstall()
            return 0

        if s.get('history'):
            since = time.time() - s['history'][-1]['at']
            if since < COOLDOWN_S:
                time.sleep(min(POLL_S, COOLDOWN_S - since))
                continue

        s['attempts'] += 1
        s.setdefault('history', []).append({'at': time.time(), 'n': s['attempts']})
        save(s)
        say(f'no lane running and work outstanding — attempt {s["attempts"]}/{MAX_ATTEMPTS}')
        rc = attempt()
        s = state()
        s['history'][-1]['rc'] = rc
        save(s)
        if rc == 0 and finish_done():
            s['done'] = True; save(s)
            say('pipeline finished cleanly')
            uninstall()
            return 0
        say(f'attempt returned {rc}; cooling down {COOLDOWN_S}s before reconsidering')
        time.sleep(COOLDOWN_S)


if __name__ == '__main__':
    sys.exit(main())
