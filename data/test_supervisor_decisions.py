#!/usr/bin/env python3
"""Pin the four DECISIONS the supervisor makes, all of which were made wrong on 2026-08-24.

test_pipeline_supervisor.py proves the supervisor's shape (cap, cooldown, resume, stop). It
stubs run() everywhere, so it cannot see any of these four, and all four cost real hours:

  a) preflight refusal is its OWN outcome — pipeline_supervisor.py:402-416.
     The lane returns PREFLIGHT_REFUSED_RC (90) when the box has no headroom. Nothing ran, so
     nothing is owed: charge neither budget, wait BUSY_COOLDOWN_S. Charged to the network
     budget it burned 3 network units in 5 minutes with zero attempts ever started, heading
     for a permanent give-up in ~80 minutes on a box that was merely busy.

  b) a traceback OUTRANKS a network error — pipeline_supervisor.py:404-407, :203-211.
     A ModuleNotFoundError (the launchd python had no psycopg) was charged to the NETWORK
     budget because hours-old 'network unreachable' lines were still in the tail. Wrong
     budget and wrong diagnosis: MAX_NET_ATTEMPTS=40 retries of a deterministic crash. The
     ORDER is the invariant: busy -> code bug -> network -> genuine.

  c) start_new_session=True on the lane Popen — pipeline_supervisor.py:253-254.
     Without it the lane sits in the supervisor's process group, so restarting the supervisor
     (launchctl kickstart -k, to pick up a code change) killed the lane it exists to nurse.
     72 minutes of collection died exactly this way.

  d) lane detection must not match itself or its own watchers — pipeline_supervisor.py:117-141.
     pgrep -f patterns are broad enough to hit a monitor shell (`while pgrep -f
     resume_chain.py`). Such a shell satisfies its own condition forever, so the supervisor
     believes a lane is alive when none is and waits out the entire run. Only PYTHON
     processes count, and never this process.

Three more decisions live in the same two branches and were unpinned until an audit on
2026-08-24 went looking for them. Each is a one-token edit away from the incident above:

  e) the cadence is chosen TWICE — pipeline_supervisor.py:381-388 as well as :430.
     :383-384 is the pre-attempt lookup, and it is the path a launchd-revived supervisor
     takes when it comes back mid-cooldown. Flattened to a bare COOLDOWN_S it would retry a
     merely-busy box on the 10-minute cadence instead of the 15-minute one, which is how (a)
     started. Only the post-attempt copy at :430 was pinned.

  f) an UNRECOGNISED failure is genuine — pipeline_supervisor.py:408-409.
     The tail matches no code sign and no network sign, so nothing is known about it.
     Charging it to the network budget hands an undiagnosed failure 40 retries: the same
     wrong-budget shape as (b), one branch over.

  g) the code-bug window has to be WIDE — pipeline_supervisor.py:203-211.
     looked_like_code_bug reads 40 lines, not the last line. A crash is usually followed by
     teardown chatter, and on 2026-08-24 that chatter was network-flavoured; a window that
     cannot reach back past it re-creates (b) exactly while every sign is still in the log.

  i) the tail windows are the invariant, not just their existence — :203-211, :213-221.
     looked_like_code_bug reads 40 lines and looked_like_network 80, and BOTH numbers were
     unpinned in the direction that matters most: an audit on 2026-08-24 widened either one
     to the whole log and watched every check here stay green. Widening is not a cosmetic
     change — it is (b) with no cure. The whole reason (b) happened is that a supervisor
     reading too far back charged a fresh ModuleNotFoundError to the NETWORK budget on the
     strength of 'network unreachable' lines from hours earlier, and bought 40 retries of a
     deterministic crash. A window that reaches the whole log ALWAYS finds the oldest sign,
     so on a long-running log every failure eventually classifies as whatever went wrong
     first. Pinned here from both sides at the exact boundary: a sign at N lines back is
     seen, the same sign at N+1 is not, for both windows, plus the end-to-end shape — old
     chatter of one kind, a fresh failure of the other.

  h) LANE_PATTERNS must COVER the drivers the supervisor launches — :62-68 vs :275-312.
     (d) is only half of the lane-detection invariant: it proves nothing that ISN'T a lane
     gets counted. The other half went unguarded until an audit on 2026-08-24 deleted
     'run_depth90.py' — the collection driver the supervisor starts itself — from
     LANE_PATTERNS and watched all thirteen fixtures across both repos stay green. A
     supervisor blind to its own lane reads "no lane running", starts a second one against
     the same database and the same single 0.75s reddit_client budget, and the two deadlock
     (proven 2026-08-22). The driver set here is DERIVED from the supervisor — from the argv
     attempt() actually builds, plus the module source — never typed into this fixture,
     because a hardcoded list goes stale exactly the way the patterns did.

Everything here is offline: subprocess is replaced by a recorder/synthetic process table, so
no process is spawned, no DB or socket is opened, and the live run is untouched.

  python3 data/test_supervisor_decisions.py
"""
import importlib.util
import json
import os
import re
import sys
import tempfile
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []


def check(name, ok, detail=''):
    print(('  ok   ' if ok else '  FAIL ') + name + (f'  [{detail}]' if detail and not ok else ''))
    if not ok:
        FAILS.append(name)


def fresh(tmp):
    """The real supervisor module, bound to a throwaway state dir.

    Loaded from HERE, never an absolute repo path, so a copy of the tree in a tempdir tests
    THAT copy — which is how this fixture gets mutation-verified.
    """
    spec = importlib.util.spec_from_file_location(
        f'supdec_{os.path.basename(tmp)}', os.path.join(HERE, 'pipeline_supervisor.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.PDIR = tmp
    m.LOG = os.path.join(tmp, 'pipeline.log')
    m.STATE = os.path.join(tmp, 'state.json')
    m.LEGACY = os.path.join(tmp, 'nonexistent.log')
    # distinct sentinels, so the cooldown actually names which outcome was decided
    m.COOLDOWN_S = 7           # genuine
    m.NET_COOLDOWN_S = 13      # network
    m.BUSY_COOLDOWN_S = 29     # busy (nothing ran)
    m.POLL_S = 0
    # NEVER let a test touch the real launchd agent — the live run is behind that label.
    m.AGENT_PLIST = os.path.join(tmp, 'agent.plist')
    m.uninstall = lambda: None
    open(m.LOG, 'a').close()
    return m


def drive_one_attempt(m):
    """Run main() until it has classified exactly one attempt and reached its cooldown.

    The cooldown sleep is the observation point: it is reached only after the outcome has
    been decided and written to state.json, and its DURATION says which outcome that was.
    """
    sleeps = []

    def sleeper(s):
        sleeps.append(s)
        raise SystemExit('cooldown reached')

    m.time = types.SimpleNamespace(sleep=sleeper, time=time.time, strftime=time.strftime)
    sys.argv = ['x']
    try:
        m.main()
    except SystemExit:
        pass
    return json.load(open(m.STATE)), sleeps


print('Supervisor decisions\n')

# ---------------------------------------------------------------------------------------
# (a) preflight refusal is a THIRD outcome: no budget, busy cadence
# ---------------------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    m.lane_pids = lambda: []
    m.gate = lambda w: False              # the box has no headroom: rc 90, nothing starts
    started = []
    m.run = lambda args, label: started.append(label) or 0
    st, sleeps = drive_one_attempt(m)

    check('a refused preflight never starts a lane', started == [], str(started))
    check('a refused preflight is classified busy', st['history'][-1].get('kind') == 'busy',
          str(st['history'][-1]))
    check('a refused preflight charges NO genuine budget', st['attempts'] == 0,
          f'attempts={st["attempts"]}')
    check('a refused preflight charges NO network budget', st.get('net_attempts', 0) == 0,
          f'net_attempts={st.get("net_attempts")}')
    check('a refused preflight is counted as a busy wait instead',
          st.get('busy_waits') == 1, str(st.get('busy_waits')))
    check('a refused preflight cools down on BUSY_COOLDOWN_S',
          sleeps[-1:] == [m.BUSY_COOLDOWN_S], f'slept {sleeps}')

# the lane's own preflight exits 1, not 90 — the REFUSING: line is the only reliable signal
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    m.lane_pids = lambda: []
    m.gate = lambda w: True

    def refusing_lane(args, label):
        open(m.LOG, 'a').write('REFUSING: want 2,700 MB free, have 1,104 MB\n')
        return 1                          # rc 1, NOT 90 — run_discovery_all runs its own gate
    m.run = refusing_lane
    st, sleeps = drive_one_attempt(m)

    check('a REFUSING: tail is busy even when the rc is 1',
          st['history'][-1].get('kind') == 'busy', str(st['history'][-1]))
    check('a REFUSING: tail charges neither budget',
          st['attempts'] == 0 and st.get('net_attempts', 0) == 0,
          f'genuine={st["attempts"]} net={st.get("net_attempts", 0)}')

# ---------------------------------------------------------------------------------------
# (b) a traceback outranks a network error in the SAME tail
# ---------------------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    m.lane_pids = lambda: []
    m.gate = lambda w: True

    def crashing_lane(args, label):
        # exactly the 2026-08-24 tail: the crash could not reach the network either, so both
        # kinds of sign are present at once
        open(m.LOG, 'a').write(
            '  probe/alive 100/29658\n'
            '  urlopen error [Errno 51] network unreachable — waiting 10s\n'
            '  connection reset by peer\n'
            'Traceback (most recent call last):\n'
            '  File "data/run_depth90.py", line 12, in <module>\n'
            '    import psycopg\n'
            "ModuleNotFoundError: No module named 'psycopg'\n")
        return 1
    m.run = crashing_lane
    st, sleeps = drive_one_attempt(m)

    check('a traceback beside network errors is a CODE BUG',
          st['history'][-1].get('kind') == 'genuine', str(st['history'][-1]))
    check('a traceback spends the genuine budget', st['attempts'] == 1,
          f'attempts={st["attempts"]}')
    check('a traceback spends NO network budget (40 retries of a crash)',
          st.get('net_attempts', 0) == 0, f'net_attempts={st.get("net_attempts")}')
    check('a traceback cools down on COOLDOWN_S, not the network cadence',
          sleeps[-1:] == [m.COOLDOWN_S], f'slept {sleeps}')

# the ordering must not be achieved by breaking the network classification itself
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    m.lane_pids = lambda: []
    m.gate = lambda w: True

    def dropped_link(args, label):
        open(m.LOG, 'a').write('  network down > 3600s — giving up on this stage\n')
        return 1
    m.run = dropped_link
    st, sleeps = drive_one_attempt(m)

    check('a clean network failure is still charged to the network budget',
          st['history'][-1].get('kind') == 'network' and st.get('net_attempts') == 1,
          str(st['history'][-1]))
    check('a clean network failure spends no genuine budget', st['attempts'] == 0,
          f'attempts={st["attempts"]}')

# and the classifier itself, directly. ONE code sign per tail: a tail carrying both a
# traceback header and a ModuleNotFoundError proves neither, because deleting either one
# from CODE_SIGNS leaves the other still matching and the check still green.
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    open(m.LOG, 'w').write('  [Errno 61] connection refused\n'
                           'Traceback (most recent call last):\n'
                           '  File "data/run_depth90.py", line 12, in <module>\n'
                           '    go()\n')
    check('a traceback header ALONE is a code bug', m.looked_like_code_bug() is True)
    check('looked_like_network also sees the drop (so ORDER is what decides)',
          m.looked_like_network() is True)

with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    open(m.LOG, 'w').write('  [Errno 61] connection refused\n'
                           "ModuleNotFoundError: No module named 'psycopg'\n")
    check('a ModuleNotFoundError ALONE is a code bug (no traceback header in the tail)',
          m.looked_like_code_bug() is True)
    check('that tail is network-signed too, so again only the ORDER saves it',
          m.looked_like_network() is True)

# how far back that window reaches is its own decision, and its own incident — see (g).

# ---------------------------------------------------------------------------------------
# (c) the lane is started in its OWN session
# ---------------------------------------------------------------------------------------
class FakeProc:
    def __init__(self, rc=0, boom=None):
        self.pid = 4242
        self._rc = rc
        self._boom = boom
        self.signals = []

    def wait(self):
        if self._boom:
            raise self._boom
        return self._rc

    def kill(self):
        self.signals.append('kill')

    def terminate(self):
        self.signals.append('terminate')


def recording_subprocess(proc):
    calls = []

    def popen(*a, **kw):
        calls.append((a, kw))
        return proc
    return types.SimpleNamespace(Popen=popen, STDOUT=-2, DEVNULL=-3, run=None,
                                 call=None), calls


with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    proc = FakeProc(rc=0)
    m.subprocess, calls = recording_subprocess(proc)
    m.time = types.SimpleNamespace(sleep=lambda s: None, time=time.time,
                                   strftime=time.strftime)
    # a resume argv, because the interesting mangling is not "is the script still there" —
    # it is losing argv[0] or losing the tail. attempt() only ever passes --from when the log
    # says a stage was interrupted, and dropping it silently restarts discovery at the top.
    argv = [sys.executable, f'{m.HERE}/run_discovery_all.py', '--from', 'candidates']
    rc = m.run(argv, 'discovery (from candidates)')

    check('the lane was actually launched', len(calls) == 1, str(calls))
    kw = calls[0][1] if calls else {}
    launched = calls[0][0][0] if calls else None
    check('the lane Popen sets start_new_session=True (else a supervisor restart kills it)',
          kw.get('start_new_session') is True, f'kwargs={sorted(kw)}')
    check('the lane runs from the repo root', kw.get('cwd') == m.ROOT, str(kw.get('cwd')))
    check('the lane runs under THIS interpreter, not whatever python3 is on the PATH '
          '(the launchd python had no psycopg on 2026-08-24)',
          launched[:1] == [sys.executable], str(launched))
    check('the whole argv reaches Popen unmangled, resume flag and all',
          launched == argv, str(launched))
    check('argv is handed over as a list, never a shell string',
          isinstance(launched, list) and kw.get('shell') in (None, False),
          f'argv={type(launched).__name__} shell={kw.get("shell")}')
    check('run returns the lane exit code', rc == 0, str(rc))

with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    proc = FakeProc(boom=KeyboardInterrupt())
    m.subprocess, calls = recording_subprocess(proc)
    m.time = types.SimpleNamespace(sleep=lambda s: None, time=time.time,
                                   strftime=time.strftime)
    raised = None
    try:
        m.run([sys.executable, f'{m.HERE}/run_depth90.py'], 'collection')
    except KeyboardInterrupt:
        raised = 'KeyboardInterrupt'
    check('a supervisor going down re-raises rather than swallowing',
          raised == 'KeyboardInterrupt', str(raised))
    check('a supervisor going down does NOT signal the lane it was nursing',
          proc.signals == [], str(proc.signals))

# ---------------------------------------------------------------------------------------
# (d) lane detection: not itself, not its watchers
# ---------------------------------------------------------------------------------------
SELF_PID = os.getpid()
# pid -> (command line pgrep -f sees, `ps -o comm=` value)
PROCTABLE = {
    101: ('/opt/homebrew/bin/python3 /Users/x/reddit-index/data/run_discovery_all.py --width 10',
          '/opt/homebrew/bin/python3.13'),                       # a real lane
    202: ('/bin/zsh -c while pgrep -f resume_chain.py >/dev/null; do sleep 60; done; echo done',
          '/bin/zsh'),                                           # a WATCHER, not a lane
    303: ('tail -f data/.pipeline/pipeline.log | grep run_depth90.py', '/usr/bin/tail'),
    404: ('/usr/bin/caffeinate -i python3 data/run_finish_all.py', '/usr/bin/caffeinate'),
    SELF_PID: ('/opt/homebrew/bin/python3 data/pipeline_supervisor.py --adopt run_depth90.py',
               '/opt/homebrew/bin/python3.13'),                   # the supervisor itself
}


def fake_ps_subprocess():
    def run(argv, **kw):
        if argv[0] == 'pgrep':
            pat = argv[2]
            hits = [str(p) for p, (cmd, _) in sorted(PROCTABLE.items()) if pat in cmd]
            return types.SimpleNamespace(stdout='\n'.join(hits), returncode=0 if hits else 1)
        if argv[0] == 'ps':
            pid = int(argv[2])
            return types.SimpleNamespace(stdout=PROCTABLE.get(pid, ('', ''))[1] + '\n',
                                         returncode=0)
        raise AssertionError(f'unexpected command in an offline test: {argv}')
    return types.SimpleNamespace(run=run, Popen=None, STDOUT=-2, DEVNULL=-3)


with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    m.subprocess = fake_ps_subprocess()
    lanes = m.lane_pids()
    pids = {p for p, _ in lanes}

    check('a genuine python lane is detected', 101 in pids, str(lanes))
    check('a `while pgrep -f resume_chain.py` watcher is NOT a lane', 202 not in pids,
          str(lanes))
    check('a log-tailing shell that names a lane script is NOT a lane', 303 not in pids,
          str(lanes))
    check('a caffeinate wrapper is NOT a lane (only the python child would be)',
          404 not in pids, str(lanes))
    check('the supervisor never counts ITSELF as a lane', SELF_PID not in pids, str(lanes))
    check('exactly one lane is seen in that table', pids == {101}, str(lanes))

    # and the pattern list itself must not be able to name the supervisor
    sup_cmd = '/opt/homebrew/bin/python3 /Users/x/reddit-index/data/pipeline_supervisor.py'
    matching = [p for p in m.LANE_PATTERNS if p in sup_cmd]
    check('no LANE_PATTERN matches a plain supervisor command line', not matching,
          str(matching))

# ---------------------------------------------------------------------------------------
# (e) the cadence is decided TWICE, and the pre-attempt copy is the resume path
# ---------------------------------------------------------------------------------------
# :430 (post-attempt) was already pinned above by every cooldown assertion. :383-384 is the
# OTHER one: a supervisor that was killed and revived by launchd mid-cooldown has no memory
# of the attempt, only state.json, and re-derives the wait from the last recorded outcome.
# Flatten that lookup to a bare COOLDOWN_S and a busy box gets retried on the genuine
# cadence, which is the busy-loop of (a) coming back through the other door.


def resumed_mid_cooldown(tmp, kind):
    """A supervisor booting onto a state file whose last attempt ended in `kind`."""
    m = fresh(tmp)
    # the pre-attempt sleep is min(POLL_S, wait - since). POLL_S=0 (the default here) would
    # mask every branch behind a 0; make the REMAINING COOLDOWN the smaller of the two so the
    # duration still names which branch was taken.
    m.POLL_S = 1000
    m.lane_pids = lambda: []
    m.gate = lambda w: True
    started = []
    m.run = lambda args, label: started.append(label) or 0
    with open(m.STATE, 'w') as f:
        json.dump({'attempts': 0, 'net_attempts': 0, 'done': False, 'gave_up': False,
                   'history': [{'at': time.time(), 'rc': 1, 'kind': kind}]}, f)
    _st, sleeps = drive_one_attempt(m)
    return m, started, sleeps


def names(slept, sentinel):
    """`wait - since` is a hair under the sentinel; the sentinels are >= 6 apart."""
    return sentinel - 1.0 < slept <= sentinel


with tempfile.TemporaryDirectory() as tmp:
    m, started, sleeps = resumed_mid_cooldown(tmp, 'busy')
    check('a revived supervisor starts nothing while the last cooldown is still running',
          started == [], str(started))
    check('a revived supervisor waits out the BUSY cadence, not the genuine one',
          names(sleeps[-1], m.BUSY_COOLDOWN_S), f'slept {sleeps}')

with tempfile.TemporaryDirectory() as tmp:
    m, started, sleeps = resumed_mid_cooldown(tmp, 'network')
    check('a revived supervisor waits out the NETWORK cadence after a link failure',
          names(sleeps[-1], m.NET_COOLDOWN_S), f'slept {sleeps}')

with tempfile.TemporaryDirectory() as tmp:
    m, started, sleeps = resumed_mid_cooldown(tmp, 'genuine')
    check('a revived supervisor falls back to COOLDOWN_S for a genuine failure',
          names(sleeps[-1], m.COOLDOWN_S), f'slept {sleeps}')

# ---------------------------------------------------------------------------------------
# (f) a failure nobody can explain is GENUINE
# ---------------------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    m.lane_pids = lambda: []
    m.gate = lambda w: True

    def undiagnosable_lane(args, label):
        # no traceback, no network sign, no REFUSING: — the classifier knows nothing about
        # this failure. Routed to the network budget it would buy 40 retries of it.
        open(m.LOG, 'a').write('  stage aborted with status 3, wrote no diagnosis\n')
        return 3
    m.run = undiagnosable_lane
    st, sleeps = drive_one_attempt(m)

    check('an unexplained failure matches neither heuristic',
          m.looked_like_code_bug() is False and m.looked_like_network() is False,
          f'code={m.looked_like_code_bug()} net={m.looked_like_network()}')
    check('an unexplained failure is charged to the GENUINE budget',
          st['history'][-1].get('kind') == 'genuine' and st['attempts'] == 1,
          str(st['history'][-1]))
    check('an unexplained failure buys NO network retries',
          st.get('net_attempts', 0) == 0, f'net_attempts={st.get("net_attempts")}')
    check('an unexplained failure cools down on COOLDOWN_S',
          sleeps[-1:] == [m.COOLDOWN_S], f'slept {sleeps}')

# ---------------------------------------------------------------------------------------
# (g) the code-bug window must reach back past the teardown chatter
# ---------------------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    m.lane_pids = lambda: []
    m.gate = lambda w: True

    def crash_then_teardown(args, label):
        # the shape every real crash has: the traceback is where it FAILED, and everything
        # after it is the process falling over — here ending in a network line, because a
        # dying worker cannot reach the network either. A window narrow enough to see only
        # the teardown reads this as a link failure and re-creates the 2026-08-24 bug with
        # every sign it needed still sitting in the log.
        lines = ['Traceback (most recent call last):',
                 '  File "data/run_depth90.py", line 12, in <module>',
                 '    import psycopg',
                 "ModuleNotFoundError: No module named 'psycopg'"]
        lines += [f'  teardown {i}/30: flushed queue' for i in range(1, 31)]
        lines.append('  urlopen error [Errno 51] network unreachable — closing')
        open(m.LOG, 'a').write('\n'.join(lines) + '\n')
        return 1
    m.run = crash_then_teardown
    st, sleeps = drive_one_attempt(m)

    check('the teardown really does end in a network sign (else this proves nothing)',
          m.looked_like_network() is True)
    check('a crash 31 teardown lines up is still seen as a CODE BUG',
          st['history'][-1].get('kind') == 'genuine' and st['attempts'] == 1,
          str(st['history'][-1]))
    check('a crash buried above its own teardown spends no network budget',
          st.get('net_attempts', 0) == 0, f'net_attempts={st.get("net_attempts")}')
    check('a buried crash cools down on COOLDOWN_S, not the network cadence',
          sleeps[-1:] == [m.COOLDOWN_S], f'slept {sleeps}')

# ---------------------------------------------------------------------------------------
# (i) the tail windows: judged from the END of the log, at the exact line
# ---------------------------------------------------------------------------------------
# (g) proves the code-bug window is WIDE ENOUGH. This proves neither window is TOO WIDE,
# which is the direction that re-creates (b): a window covering the whole log always finds
# the oldest sign in it, so on a log with hours of history every failure is classified as
# whatever went wrong first. Both directions are asserted at the boundary line itself, so a
# window moved by one in either direction goes red.

CODE_SIGN = "ModuleNotFoundError: No module named 'psycopg'"
NET_SIGN = '  urlopen error [Errno 51] network unreachable — waiting 10s'
# deliberately carries neither a CODE_SIGNS nor a NET_SIGNS substring, so the predicate's
# answer below is a statement about the WINDOW and about nothing else.
FILLER = '  progress {}/999 subreddits swept'


def only_sign_at(m, sign, distance):
    """A log whose ONLY diagnostic line is `sign`, sitting exactly `distance` lines from the
    end — i.e. a window of `distance` lines sees it and one of `distance - 1` does not."""
    lines = [sign] + [FILLER.format(i) for i in range(distance - 1)]
    open(m.LOG, 'w').write('\n'.join(lines) + '\n')


with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    only_sign_at(m, CODE_SIGN, 40)
    check('a crash exactly 40 lines from the end is INSIDE the code-bug window',
          m.looked_like_code_bug() is True)
    check('no NET_SIGN is broad enough to match that filler — one that is (\'error\', '
          '\'reset\') would make every failure look like the link',
          m.looked_like_network() is False)

with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    only_sign_at(m, CODE_SIGN, 41)
    check('the SAME crash one line further back is OUTSIDE it — the code-bug window is a '
          'tail, never the whole log', m.looked_like_code_bug() is False)

with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    only_sign_at(m, NET_SIGN, 80)
    check('a link failure exactly 80 lines from the end is INSIDE the network window',
          m.looked_like_network() is True)
    check('no CODE_SIGN is broad enough to match that filler either',
          m.looked_like_code_bug() is False)

with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    only_sign_at(m, NET_SIGN, 81)
    check('the SAME link failure one line further back is OUTSIDE it — hours-old network '
          'chatter cannot reach forward and claim a fresh failure',
          m.looked_like_network() is False)

# and the same thing where it actually costs money: through main(), on a log that already
# has history in it. This is 2026-08-24 with the roles swapped — the old sign is the one
# that must NOT win.
def with_history(m, old_sign, lane_line, rc):
    """Seed a long log whose only OLD sign is `old_sign`, then fail freshly with `lane_line`."""
    m.lane_pids = lambda: []
    m.gate = lambda w: True
    open(m.LOG, 'w').write('\n'.join(
        [old_sign] + [FILLER.format(i) for i in range(400)]) + '\n')

    def lane(args, label):
        open(m.LOG, 'a').write(lane_line)
        return rc
    m.run = lane
    return drive_one_attempt(m)


with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    st, sleeps = with_history(
        m, NET_SIGN, '  stage aborted with status 3, wrote no diagnosis\n', 3)
    check('a 400-line-old network sign does NOT classify a fresh unexplained failure as '
          'the link', st['history'][-1].get('kind') == 'genuine', str(st['history'][-1]))
    check('...so it buys no network retries', st.get('net_attempts', 0) == 0,
          f'net_attempts={st.get("net_attempts")}')
    check('...and cools down on COOLDOWN_S, not the network cadence',
          sleeps[-1:] == [m.COOLDOWN_S], f'slept {sleeps}')

with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    st, sleeps = with_history(
        m, CODE_SIGN, '  network down > 3600s — giving up on this stage\n', 1)
    check('a 400-line-old traceback does NOT condemn a fresh link failure to the genuine '
          'budget', st['history'][-1].get('kind') == 'network', str(st['history'][-1]))
    check('...the fresh link failure is charged to the network budget',
          st.get('net_attempts') == 1 and st['attempts'] == 0,
          f'genuine={st["attempts"]} net={st.get("net_attempts")}')
    check('...and cools down on NET_COOLDOWN_S',
          sleeps[-1:] == [m.NET_COOLDOWN_S], f'slept {sleeps}')

# ---------------------------------------------------------------------------------------
# (h) LANE_PATTERNS covers every driver the supervisor launches
# ---------------------------------------------------------------------------------------
# (d) proves a non-lane is never counted. This proves a lane is never MISSED. Deleting
# 'run_depth90.py' from LANE_PATTERNS left every other fixture green: the supervisor then
# cannot see the collection lane it started itself, decides nothing is running, and starts a
# second one on the same DB and the same shared rate limit.
#
# The driver set is derived from the supervisor twice over, and the two are unioned:
#   runtime — drive attempt() with run() recorded and gate() open. Every completion marker is
#             false in a fresh temp dir, so it walks all its stages and hands over the exact
#             argv it would have executed.
#   static  — every f'{HERE}/….py' in the module source, which also reaches a driver sitting
#             behind a branch this particular walk does not take.
# Neither is a list typed into this fixture, which is the point: a typed list goes stale the
# same way LANE_PATTERNS did.


def ps_over(table):
    """An offline `pgrep -f` / `ps -o comm=` over a synthetic process table."""
    def run(argv, **kw):
        if argv[0] == 'pgrep':
            pat = argv[2]
            hits = [str(p) for p, (cmd, _) in sorted(table.items()) if pat in cmd]
            return types.SimpleNamespace(stdout='\n'.join(hits), returncode=0 if hits else 1)
        if argv[0] == 'ps':
            return types.SimpleNamespace(stdout=table.get(int(argv[2]), ('', ''))[1] + '\n',
                                         returncode=0)
        raise AssertionError(f'unexpected command in an offline test: {argv}')
    return types.SimpleNamespace(run=run, Popen=None, STDOUT=-2, DEVNULL=-3)


def cmdline_for(rel, tail):
    """What `pgrep -f` would see for that driver on the real box: an absolute interpreter,
    an absolute script path, and the flags the supervisor itself passes."""
    return ' '.join(['/opt/homebrew/bin/python3',
                     f'/Users/x/reddit-index/data/{rel}'] + list(tail))


with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    m.gate = lambda w: True
    launched = []
    m.run = lambda args, label: launched.append((list(args), label)) or 0
    m.attempt()

    runtime = {}
    for args, _label in launched:
        for a in args[1:]:
            if a.startswith(m.HERE + os.sep) and a.endswith('.py'):
                runtime[os.path.relpath(a, m.HERE)] = args[2:]
                break
    src = open(os.path.join(HERE, 'pipeline_supervisor.py')).read()
    static = set(re.findall(r'\{HERE\}/([A-Za-z0-9_./-]+\.py)', src))
    drivers = dict(runtime)
    for rel in sorted(static):
        drivers.setdefault(rel, [])

    # anti-vacuity: with an empty driver set every coverage check below passes by saying
    # nothing, which is precisely the failure mode this whole round exists to kill.
    check('the driver set was actually derived from the supervisor, not assumed empty',
          len(drivers) >= 2, f'drivers={sorted(drivers)}')
    check('every command attempt() builds runs a script out of data/',
          launched and all(a[1].startswith(m.HERE + os.sep) for a, _ in launched),
          str([a[:2] for a, _ in launched]))
    check('the source scan still sees every driver the walk launched (else it has gone '
          'blind to a path built some other way)',
          set(runtime) <= static, f'runtime={sorted(runtime)} static={sorted(static)}')

    # the coverage claim itself, one named check per driver
    for rel in sorted(drivers):
        cmd = cmdline_for(rel, drivers[rel])
        hit = [p for p in m.LANE_PATTERNS if p in cmd]
        check(f'some LANE_PATTERN matches a running {rel}', bool(hit), f'cmdline={cmd}')

    # and the call site, not only the pattern list: lane_pids() is what main() asks.
    pid_of = {rel: 900000 + i for i, rel in enumerate(sorted(drivers))}
    table = {pid: (cmdline_for(rel, drivers[rel]), '/opt/homebrew/bin/python3.13')
             for rel, pid in pid_of.items()}
    m.subprocess = ps_over(table)
    seen = {p for p, _ in m.lane_pids()}
    for rel in sorted(drivers):
        check(f'lane_pids() counts a running {rel} as a live lane', pid_of[rel] in seen,
              f'saw {sorted(seen)}')

    # the inverse, reported as a NOTE rather than a check — deliberately. A pattern matching
    # no DRIVER is not automatically dead: most of these are second-order lanes the drivers
    # spawn (discover_v2, worker/sweep) or scripts run by hand, and pgrep must still see
    # those. Only a pattern resolving to no file at all is dead weight, and failing on it
    # would fail today on 'resume_chain.py', a scratchpad chain this run was started from.
    covered = set()
    for rel in drivers:
        cmd = cmdline_for(rel, drivers[rel])
        covered |= {p for p in m.LANE_PATTERNS if p in cmd}
    idle = [p for p in m.LANE_PATTERNS if p not in covered]
    root = os.path.dirname(HERE)
    print(f'  note   {len(idle)}/{len(m.LANE_PATTERNS)} LANE_PATTERNS match no driver the '
          f'supervisor launches directly:')
    for p in idle:
        where = [c for c in ('', 'data', 'worker') if os.path.exists(os.path.join(root, c, p))]
        print(f'           {p} — ' + (f'file present under {where[0] or "repo root"}/'
                                      if where else 'NAMES NO FILE IN THIS REPO'))

print()
if FAILS:
    print(f'{len(FAILS)} FAILURES')
    sys.exit(1)
print('all supervisor decision checks pass')
