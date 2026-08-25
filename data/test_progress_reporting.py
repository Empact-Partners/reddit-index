#!/usr/bin/env python3
"""Guard the observability layer: the completion MARKER other stages trust, and the probe
that is supposed to say where a silent stage actually is.

Two incidents, both of which made the pipeline lie about itself rather than break loudly.

  1. THE MARKER — data/run_discovery_all.py:94-102
     'DISCOVERY COMPLETE' is not a log flourish, it is a control signal. The supervisor skips
     the whole discovery leg on it: pipeline_supervisor.py:177 is literally
         return 'DISCOVERY COMPLETE' in log_text()
     It was once printed even when `worker/load.py --seed` had FAILED, so the marker said the
     new subreddits were registered in Postgres when they were not. The next leg would have
     swept an empty seed and reported success the whole way down. The invariant: the marker is
     printed ONLY after a seed that exited 0, and a failed seed prints the explicit
     NOT-writing line and returns the failure instead. A completion marker must never outrun
     the work.

  2. THE PROBE — data/progress_probe.py
     Two incidents stacked in one file. First, progress was inferred from a SIDE EFFECT: lsof
     on the lane's open files named the evidence/<category>.json it had open. Memoising the
     cache readers deleted those opens, the signal vanished, and the probe went blind while
     still printing confidently. Then the fix sampled hard enough to catch a fast loop —
     ~900 lsof passes at ~72 ms — which stole ~65 s of CPU from the very process it was
     measuring and raised a false 'cpu IDLE — investigate now' about a lane running at 67%
     CPU. The rule that came out of it: PROGRESS IS A COUNTER THE CODE ITSELF PRINTS, never a
     side effect observed from outside. discover_v2 now emits 'cheap bars i/N' / 'verdicts
     i/N' every 10,000 pairs and the probe parses those.
     progress_probe.py:38 still shells out to pgrep, which is fine and is asserted here to be
     LIVENESS ONLY: a live pid with burning CPU and a frozen counter is a STALL, not progress.

  python3 data/test_progress_reporting.py
"""
import ast
import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import time as _real_time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []


def check(name, ok, detail=''):
    print(('  ok   ' if ok else '  FAIL ') + name + (f'  [{detail}]' if detail and not ok else ''))
    if not ok:
        FAILS.append(name)


def load(fname, modname):
    """Import a module from THIS tree by path, so a copy in a tempdir tests that copy."""
    spec = importlib.util.spec_from_file_location(modname, os.path.join(HERE, fname))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def announces_complete(text):
    """Does this output claim discovery finished?

    Line-anchored on purpose: the marker is a whole line the stage prints, and only that
    counts as an announcement here."""
    return any(ln.strip().startswith('DISCOVERY COMPLETE') for ln in text.splitlines())


# run_discovery_all imports fleet_preflight from ~/.claude/scripts at module scope. Stub it in
# sys.modules first so this fixture is hermetic and cannot preflight anything for real.
_fp = types.ModuleType('fleet_preflight')
_fp.preflight = lambda want=None, **k: True
_fp.reconcile = lambda **k: None
_fp.swap_growth_mb = lambda: 0.0
sys.modules['fleet_preflight'] = _fp


class FakeSub:
    """Stands in for the subprocess module. Nothing real is ever spawned."""

    def __init__(self, rc_for=None, outputs=None):
        self.calls = []            # full argv of every subprocess.call
        self.runs = []             # full argv of every subprocess.run
        self._rc_for = rc_for or (lambda args: 0)
        self._outputs = outputs or (lambda args: '')

    def call(self, args, **kw):
        self.calls.append(list(args))
        return self._rc_for(list(args))

    def run(self, args, **kw):
        self.runs.append(list(args))
        out = self._outputs(list(args))
        return types.SimpleNamespace(stdout=out, stderr='', returncode=0)


def is_seed(args):
    return any(str(a).endswith('load.py') for a in args) and '--seed' in [str(a) for a in args]


def drive_discovery(seed_rc):
    """Run the real main() tail with a stubbed seed. Returns (rc, stdout, fake_subprocess)."""
    m = load('run_discovery_all.py', f'rda_{seed_rc}')
    m.slugs = lambda: ['alpha', 'beta']
    m.core_count = lambda: 1234
    m.enum_done = lambda: 2
    m.preflight = lambda want=None, **k: True
    m.reconcile = lambda **k: None
    m.swap_growth_mb = lambda: 0.0
    fake = FakeSub(rc_for=lambda args: seed_rc if is_seed(args) else 0)
    m.subprocess = fake
    buf = io.StringIO()
    argv = sys.argv
    sys.argv = ['run_discovery_all.py', '--from', 'qualify']   # one stage, then the tail
    try:
        with contextlib.redirect_stdout(buf):
            rc = m.main()
    finally:
        sys.argv = argv
    return rc, buf.getvalue(), fake


print('Progress reporting\n')

# ---------------------------------------------------------------- 1. the marker
# 1a. a FAILED seed must not announce completion
rc, out, fake = drive_discovery(seed_rc=7)
check('a failed seed does NOT print the DISCOVERY COMPLETE marker',
      not announces_complete(out), repr(out[-220:]))
check('a failed seed says explicitly that it is not writing the marker',
      'NOT writing DISCOVERY COMPLETE' in out, repr(out[-220:]))
check('a failed seed returns the seed failure code', rc == 7, str(rc))
check('nothing runs after a failed seed', fake.calls and is_seed(fake.calls[-1]),
      str([c[-2:] for c in fake.calls]))

# 1b. a SUCCESSFUL seed must announce it, exactly once
rc0, out0, fake0 = drive_discovery(seed_rc=0)
check('a successful seed prints the DISCOVERY COMPLETE marker', announces_complete(out0),
      repr(out0[-220:]))
check('the marker is printed once, not per stage',
      sum(1 for ln in out0.splitlines() if ln.strip().startswith('DISCOVERY COMPLETE')) == 1)
check('a successful run exits 0', rc0 == 0, str(rc0))
check('the seed actually ran (the marker is not printed without one)',
      any(is_seed(c) for c in fake0.calls), str(fake0.calls))

# 1c. the supervisor's own reader agrees on the success case: this is the consumer whose
# behaviour the marker exists for, so it is checked against the real function.
sup = load('pipeline_supervisor.py', 'sup_marker')
with tempfile.TemporaryDirectory() as tmp:
    sup.PDIR, sup.LEGACY = tmp, os.path.join(tmp, 'nonexistent.log')
    sup.LOG = os.path.join(tmp, 'pipeline.log')
    open(sup.LOG, 'w').write(out0)          # exactly what a good run pipes into the log
    check('the supervisor sees discovery done after a successful seed', sup.discovery_done())

# 1d. structural backstop: the statement immediately before the marker print is an
# `if rc != 0: ... return` guard. Behaviour above is the real test; this fails loudly if the
# guard is ever moved away from the print it protects.
tree = ast.parse(open(os.path.join(HERE, 'run_discovery_all.py')).read())
main_fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
marker_at = [i for i, n in enumerate(main_fn.body)
             if isinstance(n, ast.Expr) and 'DISCOVERY COMPLETE' in ast.dump(n)
             and 'NOT writing' not in ast.dump(n)]
prev = main_fn.body[marker_at[0] - 1] if marker_at else None
guarded = (isinstance(prev, ast.If) and 'NotEq' in ast.dump(prev.test)
           and any(isinstance(b, ast.Return) for b in prev.body))
check('(structural) the marker print sits directly behind an rc != 0 return',
      bool(marker_at) and guarded,
      f'marker at {marker_at}, preceded by {type(prev).__name__}')

# ---------------------------------------------------------------- 2. the probe
print()
probe_src = open(os.path.join(HERE, 'progress_probe.py')).read()
ptree = ast.parse(probe_src)

# 2a. no lsof ANYWHERE in executable code.
#
# This used to be TWO checks, and the one that was supposed to guard the incident could not
# see it. The incident shape is subprocess.run(['lsof', '-p', pid]): the word lives in a
# STRING — an ast.Constant — never in an identifier. A scan over ast.Name/ast.Attribute only
# fires if somebody names a *function* lsof_something, which is not how the bug was written
# or how it would come back. The two scans are merged into one that reads call arguments and
# identifiers alike, and it is proved against a synthetic probe below rather than assumed.
#
# Docstrings are excluded because the probe explains the incident in prose; comments never
# reach the AST at all.
def lsof_mentions(tree):
    """Every place a parsed module could reach lsof: string literals (incl. call args) and
    identifiers. Docstring prose is not a mention. Returns the offending values."""
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            d = ast.get_docstring(node, clean=False)
            if d is not None:
                docstrings.add(d)
    hits = [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and n.value not in docstrings and 'lsof' in n.value.lower()]
    hits += [n.id for n in ast.walk(tree)
             if isinstance(n, ast.Name) and 'lsof' in n.id.lower()]
    hits += [n.attr for n in ast.walk(tree)
             if isinstance(n, ast.Attribute) and 'lsof' in n.attr.lower()]
    return hits


# the regression, written the way it was actually written: a string in a call argument
SYNTHETIC_LSOF = (
    '"""A probe that samples open files."""\n'
    'import subprocess\n'
    'def position(pid):\n'
    '    out = subprocess.run(["lsof", "-p", str(pid)], capture_output=True).stdout\n'
    '    return out\n'
)
# the same file explaining the incident instead of committing it
SYNTHETIC_PROSE = (
    '"""There is deliberately no lsof sampling here any more."""\n'
    'import subprocess\n'
    'def position(pid):\n'
    '    """lsof was the original signal and sampling it starved the process."""\n'
    '    return subprocess.run(["pgrep", "-f", "discover_v2.py"], capture_output=True).stdout\n'
)
check('(fixture) the scan catches a probe that shells out to lsof in a call argument',
      lsof_mentions(ast.parse(SYNTHETIC_LSOF)) == ['lsof'],
      str(lsof_mentions(ast.parse(SYNTHETIC_LSOF))))
check('(fixture) prose about the lsof incident is not a false positive',
      lsof_mentions(ast.parse(SYNTHETIC_PROSE)) == [],
      str(lsof_mentions(ast.parse(SYNTHETIC_PROSE))))
check('no lsof anywhere in probe code — call arguments, strings or identifiers',
      lsof_mentions(ptree) == [], str(lsof_mentions(ptree))[:160])

# 2b. position() is parsed out of the log the stage writes, not observed from outside
probe = load('progress_probe.py', 'probe_pos')
with tempfile.TemporaryDirectory() as tmp:
    probe.PIPELINE_LOG = os.path.join(tmp, 'pipeline.log')
    open(probe.PIPELINE_LOG, 'w').write(
        'noise\n  cheap bars 40000/283113 ok\nmore noise\n')
    check('position() reads the counter the stage printed',
          probe.position() == ('cheap bars', 40000, 283113), str(probe.position()))
    open(probe.PIPELINE_LOG, 'a').write('  verdicts 12000/283113\n')
    check('position() takes the LATEST counter line',
          probe.position() == ('verdicts', 12000, 283113), str(probe.position()))
    open(probe.PIPELINE_LOG, 'w').write('no counters here at all\n')
    check('position() reports nothing rather than guessing', probe.position() is None,
          str(probe.position()))


class Clock:
    """Fake time, so a 900-second stall costs no wall clock. sleep() is the scripted world."""

    def __init__(self, script):
        self.t = 10_000.0
        self.script = list(script)
        self.slept = 0

    def time(self):
        return self.t

    def strftime(self, fmt, *a):
        return _real_time.strftime(fmt, *a)

    def sleep(self, _s):
        self.slept += 1
        if not self.script:
            raise SystemExit('scripted polls exhausted')
        self.script.pop(0)()


def run_probe(script, ps_times, pid_out='4242\n'):
    """Drive the real probe loop over scripted polls. Returns (stdout, commands run)."""
    tmp = tempfile.mkdtemp()
    p = load('progress_probe.py', f'probe_{len(script)}_{ps_times[0]}_{len(pid_out)}')
    p.PIPELINE_LOG = os.path.join(tmp, 'pipeline.log')
    p.LOG = os.path.join(tmp, 'progress.log')
    p.EVERY, p.STALL_AFTER = 0, 60
    p.FLEET_OUT = {}                      # no fleet lane: progress must come from counters
    seen_ps = iter(ps_times)

    def outputs(args):
        if args[0] == 'pgrep':
            return pid_out
        if args[0] == 'ps':
            return next(seen_ps, ps_times[-1])
        return ''

    fake = FakeSub(outputs=outputs)
    p.subprocess = fake
    p.time = Clock(script)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            p.main()
        except SystemExit:
            pass
    return buf.getvalue(), [c[0] for c in fake.runs], p


# 2c/2d. two scenarios differing ONLY in whether the printed counter moved.
def scenario(append_text, ps_times):
    holder = {}

    def first_sleep():
        open(holder['log'], 'a').write(append_text)
        holder['clock'].t += 1000          # far past STALL_AFTER

    out, cmds, mod = None, None, None
    tmp = tempfile.mkdtemp()
    log = os.path.join(tmp, 'pipeline.log')
    open(log, 'w').write('  cheap bars 100000/283113\n')
    holder['log'] = log
    p = load('progress_probe.py', f'probe_sc_{abs(hash(append_text)) % 10 ** 6}')
    p.PIPELINE_LOG = log
    p.LOG = os.path.join(tmp, 'progress.log')
    p.EVERY, p.STALL_AFTER = 0, 60
    p.FLEET_OUT = {}
    times = iter(ps_times)

    def outputs(args):
        if args[0] == 'pgrep':
            return '4242\n'
        if args[0] == 'ps':
            return next(times, ps_times[-1])
        return ''

    fake = FakeSub(outputs=outputs)
    p.subprocess = fake
    clock = Clock([first_sleep])
    holder['clock'] = clock
    p.time = clock
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            p.main()
        except SystemExit:
            pass
    return buf.getvalue(), [c[0] for c in fake.runs], log


CPU = ['10:00.00', '20:00.00', '30:00.00']       # CPU climbing: the lane is alive and busy

adv_out, adv_cmds, _ = scenario('  cheap bars 150000/283113\n', CPU)
check('an advancing counter is reported as progress', '150,000/283,113' in adv_out,
      repr(adv_out))
check('an advancing counter never raises STALL',
      not any(ln.split(' ', 1)[-1].startswith('STALL') for ln in adv_out.splitlines()),
      repr(adv_out))

# 2d. stalled: the log GROWS (bytes appended) but the counter does not move.
FILLER = ''.join(f'  fetching r/sub{i} ...\n' for i in range(50))
stall_out, stall_cmds, stall_log = scenario(FILLER, CPU)
stall_lines = [ln for ln in stall_out.splitlines() if ln.split(' ', 1)[-1].startswith('STALL')]
check('a growing log with a frozen counter is a STALL', bool(stall_lines), repr(stall_out))
# on the STALL LINE, not merely somewhere in the output: the ordinary progress line printed
# the identical position one poll earlier, so a substring test over the whole output passes
# even when no STALL is emitted at all. An alarm that does not say where it is stuck sends
# you back to the log to find out, which is the three hours this probe exists to prevent.
check('the STALL line itself names the position it is stuck at',
      any('100,000/283,113' in ln for ln in stall_lines), repr(stall_lines))
# and the bytes appended are NOT the signal: 50 non-counter lines are now the newest thing
# in the log, and the probe must still report the frozen counter from further back rather
# than losing the position (returning None here would downgrade the STALL to the vaguer
# 'no counter for Nm' branch, which names nothing).
grown = load('progress_probe.py', 'probe_grown')
grown.PIPELINE_LOG = stall_log
check('50 appended non-counter lines do not move or erase the reported position',
      grown.position() == ('cheap bars', 100000, 283113), str(grown.position()))
check('a live pid burning CPU does not count as progress (liveness != progress)',
      'BURNING' in stall_out, repr(stall_out))

# 2e. the only things the probe shells out to are liveness probes, never a file-handle sample
check('the probe shells out to pgrep/ps only, never lsof',
      set(adv_cmds + stall_cmds) <= {'pgrep', 'ps'}, str(sorted(set(adv_cmds + stall_cmds))))
check('it does check liveness with pgrep', 'pgrep' in adv_cmds, str(adv_cmds))

# 2f. no lane, no probe: it exits instead of reporting on nothing
gone_out, gone_cmds, _ = run_probe([], CPU, pid_out='')
check('the probe exits when the lane is gone', 'not running' in gone_out, repr(gone_out))
check('the probe never sampled a dead lane', gone_cmds == ['pgrep'], str(gone_cmds))

print()
if FAILS:
    print(f'{len(FAILS)} FAILURES')
    sys.exit(1)
print('progress reporting holds: the marker follows the work, progress is a printed counter')
