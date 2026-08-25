#!/usr/bin/env python3
"""The two files the pipeline depends on that live OUTSIDE this repo — the launchd plist and
`~/.claude/scripts/fleet_preflight.py`. Neither appears in a diff, so no reviewer has ever
seen either one, which is exactly how a Python 3.9 interpreter reached production.

INCIDENT B1 (post-mortem 2026-08-24, ~25 min, listed under "Has none" in the coverage ledger
as "the launchd interpreter"). The plist ran `/usr/bin/python3` — 3.9, no psycopg.
`sys.executable` propagates to every child, so that one string in an unversioned XML file
chose the interpreter for seed, sweep, classify, score and publish. Discovery reported success
the whole time because no stage before the seed touches the database; the first DB stage died,
and `DISCOVERY COMPLETE` had already been printed. The post-mortem's verdict: "No regression
test. Nothing asserts the plist's interpreter can import what the pipeline needs." This is it.

INCIDENT G1 (~9 h, the single most expensive line in the ledger). The Mac slept mid-run, lid
open, on mains power. The entire remedy is `KeepAlive/SuccessfulExit=false` plus `RunAtLoad`
in that same unversioned plist (decisions/0013) — asserted here rather than assumed.

The second subject is the fail-open hole. `pipeline_supervisor.py:70` inserts
`~/.claude/scripts` on sys.path and `gate()` imports the resource guard from it. Rename that
file, break it, or drift a keyword argument, and `gate()`'s `except Exception: return True`
logs one line and starts the wave anyway — while `data/test_resource_guards.py` spends 30
checks certifying a guard that has silently disappeared. That defect is stated out loud here
as an xfail; see the block comment above it.

Nothing here runs the pipeline, connects to a database, reaches the network, or calls
launchctl. The plist is read with plistlib; the only subprocess is `<interpreter> -c
"import psycopg"`, which imports a driver and connects to nothing.

`PIPELINE_PLIST` overrides which plist is read, so a MUTATED COPY can be tested without
touching the live agent. Unset, it is the agent `pipeline_supervisor.uninstall()` would remove.

  python3 data/test_out_of_repo_contract.py
"""
import ast
import importlib
import importlib.util
import inspect
import json
import os
import plistlib
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SUPERVISOR = os.path.join(HERE, 'pipeline_supervisor.py')
FAILS = []
XFAILS = []


def skip(name, why):
    print(f"  skip {name}  [{why}]")


def check(name, ok, detail=''):
    print(('  ok   ' if ok else '  FAIL ') + name + (f'  [{detail}]' if detail and not ok else ''))
    if not ok:
        FAILS.append(name)


# ---------------------------------------------------------------------------------------------
# KNOWN OPEN DEFECT — read this before touching the xfail() rows at the bottom of the file.
#
# pipeline_supervisor.py:233-235 is:
#
#     except Exception as e:
#         say(f'preflight unavailable ({e}) - proceeding without it')
#         return True
#
# so a missing, renamed or signature-drifted fleet_preflight.py removes every RAM and swap
# guard from the run and the supervisor proceeds regardless. The right fix is `return False`:
# a supervisor that cannot check the box must not start a wave on it. That one-line change is
# NOT made here, and not because it is disputed — the supervisor is running a multi-day sweep
# at this moment and editing it would change the code under a live process.
#
# Until then the defect is stated on every run rather than hidden: xfail() prints "  xfail ",
# records nothing in FAILS, and the fixture still exits 0. THE MOMENT the supervisor is
# changed to fail closed, these rows become check() calls — xfail() prints a loud instruction
# to do exactly that if the assertion ever starts passing, so the conversion cannot be missed.
# ---------------------------------------------------------------------------------------------
def xfail(name, ok, detail=''):
    if ok:
        print('  ok   ' + name + '  [DEFECT IS FIXED - convert this xfail() to check() now]')
        return
    print('  xfail ' + name + (f'  [{detail}]' if detail else ''))
    XFAILS.append(name)


TMP = tempfile.TemporaryDirectory()


def load_supervisor():
    """The supervisor module, imported but NEVER run, and bound to a throwaway state dir.

    Module-level code has exactly one side effect — `sys.path.insert(0, '~/.claude/scripts')`
    at line 70 — so sys.path is snapshotted and restored: the import must not be what makes
    the subject-2 checks below pass. Everything that writes is stubbed before any call:
    say/LOG/STATE/PDIR are redirected off the live run, and uninstall() is replaced by a
    raise, because the real one deletes the plist of the agent supervising the live sweep."""
    saved_path = list(sys.path)
    spec = importlib.util.spec_from_file_location('sup_out_of_repo', SUPERVISOR)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sys.path[:] = saved_path

    m.PDIR = TMP.name
    m.LOG = os.path.join(TMP.name, 'pipeline.log')
    m.STATE = os.path.join(TMP.name, 'state.json')
    m.LEGACY = os.path.join(TMP.name, 'nonexistent.log')
    m.SAID = []
    m.say = m.SAID.append

    def _no_uninstall():
        raise AssertionError('uninstall() must never run from a fixture')
    m.uninstall = _no_uninstall
    return m


sup = load_supervisor()

print('Out-of-repo contract\n')
print('subject 1 - the launchd plist')

# --------------------------------------------------------------------------------- the plist
PLIST = os.environ.get('PIPELINE_PLIST') or sup.AGENT_PLIST
d = None
# THE AGENT'S ABSENCE IS CORRECT WHEN THE RUN IS OVER. decisions/0013 grants a
# bounded supervisor for ONE already-started job and requires it to leave nothing
# behind: uninstall() deletes this plist on completion. The first version of this
# fixture asserted the plist EXISTS, which made a clean finish look like a
# failure — it went red the moment the pipeline did exactly what the decision
# demands (2026-08-25 06:18, "pipeline finished cleanly ... removed <plist>").
#
# The real invariant is conditional:
#   run in progress  -> the plist must exist AND be correct
#   run finished     -> the plist must be GONE
# state.json's `done` flag is the supervisor's own record of which it is.
# Read the LIVE state file, not sup.state(). load_supervisor() rebinds the
# module's paths to a tempdir so the fixture cannot touch a running pipeline —
# which also means sup.state() answers about the tempdir, not the machine. The
# first version asked the stub and got {}, concluded a run was outstanding, and
# failed on a plist that was correctly absent.
_live_state = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '.pipeline', 'state.json')
try:
    with open(_live_state) as _f:
        _run_done = bool(json.load(_f).get('done'))
except Exception:
    _run_done = False

if _run_done:
    check('a finished run left no launchd agent behind (decisions/0013)',
          not os.path.isfile(sup.AGENT_PLIST),
          f'{sup.AGENT_PLIST} survived a completed run - that is the automation 0013 bans')
else:
    check('a run in progress has its agent installed where uninstall() looks',
          os.path.isfile(sup.AGENT_PLIST), f'missing {sup.AGENT_PLIST}')

if os.path.isfile(PLIST):
    try:
        with open(PLIST, 'rb') as f:
            d = plistlib.load(f)
    except Exception as e:
        check('the plist parses', False, f'{PLIST}: {e}')
elif not _run_done:
    check('the plist under test exists', False,
          f'{PLIST} is absent while a run is outstanding - the supervisor has no agent, so '
          f'nothing re-arms it after a sleep, a crash or a reboot')
else:
    skip('the plist contract checks', 'run finished and the agent is correctly gone')

if d is not None:
    argv = d.get('ProgramArguments') or []
    argv0 = argv[0] if argv else ''

    # B1: this one string chose the interpreter for every DB stage in the pipeline.
    check('the launchd interpreter is /opt/homebrew/bin/python3, not the system 3.9',
          argv0 == '/opt/homebrew/bin/python3', f'ProgramArguments[0]={argv0!r}')

    if argv0 and os.path.isfile(argv0) and os.access(argv0, os.X_OK):
        r = subprocess.run([argv0, '-c', 'import psycopg'],
                           capture_output=True, text=True, timeout=120)
        why = (r.stderr or '').strip().splitlines()
        check('that interpreter can import psycopg (seed, sweep, classify, score, publish all '
              'die without it)', r.returncode == 0, why[-1] if why else f'rc={r.returncode}')
    else:
        check('that interpreter can import psycopg (seed, sweep, classify, score, publish all '
              'die without it)', False, f'not an executable: {argv0!r}')

    # the agent must run THIS repo's supervisor, not some other checkout's
    prog = argv[1] if len(argv) > 1 else ''
    tail = os.sep + os.path.join(os.path.basename(HERE), os.path.basename(SUPERVISOR))
    check('the agent runs a data/pipeline_supervisor.py that exists',
          bool(prog) and os.path.isfile(prog) and os.path.realpath(prog).endswith(tail),
          f'ProgramArguments[1]={prog!r}')
    wd = d.get('WorkingDirectory') or ''
    check('WorkingDirectory is that supervisor\'s repo root (relative paths in every stage '
          'resolve from it)',
          bool(wd) and bool(prog)
          and os.path.realpath(wd)
          == os.path.realpath(os.path.dirname(os.path.dirname(prog))),
          f'WorkingDirectory={wd!r} vs {prog!r}')

    # uninstall() removes ~/Library/LaunchAgents/<AGENT_LABEL>.plist and boots out
    # gui/<uid>/<AGENT_LABEL>. A label that drifts from the module means the terminal path
    # deletes nothing and the agent survives the run it was installed for (decisions/0013).
    label = d.get('Label')
    check('the plist Label is the label the supervisor uninstalls',
          label == sup.AGENT_LABEL, f'plist={label!r} module={sup.AGENT_LABEL!r}')
    check('that label resolves to the exact path uninstall() deletes',
          bool(label)
          and os.path.expanduser(f'~/Library/LaunchAgents/{label}.plist') == sup.AGENT_PLIST,
          f'{label!r} -> {sup.AGENT_PLIST!r}')

    # G1, the ~9-hour one: the box slept mid-run and nothing brought the supervisor back.
    ka = d.get('KeepAlive')
    check('KeepAlive.SuccessfulExit is false - a crash or a sleep revives supervision, a '
          'clean exit ends it',
          isinstance(ka, dict) and ka.get('SuccessfulExit') is False, f'KeepAlive={ka!r}')
    check('RunAtLoad is true - supervision re-arms at login after a reboot',
          d.get('RunAtLoad') is True, f'RunAtLoad={d.get("RunAtLoad")!r}')

# ------------------------------------------------------- subject 2: the out-of-repo guard
print('\nsubject 2 - ~/.claude/scripts/fleet_preflight.py')

INSERT_RE = re.compile(r"sys\.path\.insert\(\s*0\s*,\s*os\.path\.expanduser\(\s*['\"]([^'\"]+)['\"]")
SKIP_DIRS = {'.git', '__pycache__', '.pipeline', '.cache', 'node_modules', '.venv'}


def repo_py_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS]
        for fn in sorted(filenames):
            if fn.endswith('.py'):
                yield os.path.join(dirpath, fn)


def scan(path):
    """What this repo module asks of fleet_preflight: imported names (local -> real), the
    line it imports on, the sys.path directories it inserts, and every call it makes."""
    src = open(path, errors='replace').read()
    if 'fleet_preflight' not in src:
        return None
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    names, import_line = {}, None
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'fleet_preflight':
            for a in node.names:
                names[a.asname or a.name] = a.name
            import_line = node.lineno if import_line is None else min(import_line, node.lineno)
    if not names:
        return None
    inserts = [(src[:m.start()].count('\n') + 1, m.group(1)) for m in INSERT_RE.finditer(src)]
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in names:
            calls.append((names[node.func.id], len(node.args),
                          [k.arg for k in node.keywords if k.arg], node.lineno))
    return {'path': path, 'names': names, 'import_line': import_line,
            'inserts': inserts, 'calls': calls}


CONSUMERS = [c for c in (scan(p) for p in repo_py_files()) if c]
# the fixture itself never imports fleet_preflight at module scope, so it cannot appear here
CONSUMERS = [c for c in CONSUMERS if os.path.abspath(c['path']) != os.path.abspath(__file__)]
rel = lambda p: os.path.relpath(p, ROOT)

check('repo modules that depend on the out-of-repo guard are found (including the supervisor)',
      bool(CONSUMERS) and any(os.path.abspath(c['path']) == os.path.abspath(SUPERVISOR)
                              for c in CONSUMERS),
      f'found {[rel(c["path"]) for c in CONSUMERS]}')

# one out-of-repo directory, named identically everywhere: five modules reach it, and a
# second spelling means one of them is already importing something else.
dirs = sorted({os.path.expanduser(p) for c in CONSUMERS for _, p in c['inserts']})
check('every consumer inserts the SAME directory on sys.path', len(dirs) == 1, str(dirs))

for c in CONSUMERS:
    first = min((ln for ln, _ in c['inserts']), default=None)
    check(f'{rel(c["path"])} puts that directory on sys.path before importing from it',
          first is not None and c['import_line'] is not None and first < c['import_line'],
          f'insert@{first} import@{c["import_line"]}')

# resolved from the SUPERVISOR's own insert, not from the set: gate() is the fail-open call
# site, so the directory that matters is the one that file puts on the path.
supc = next((c for c in CONSUMERS
             if os.path.abspath(c['path']) == os.path.abspath(SUPERVISOR)), None)
PDIR = os.path.expanduser(supc['inserts'][0][1]) if supc and supc['inserts'] else None
check('the directory the supervisor inserts exists and holds fleet_preflight.py',
      bool(PDIR) and os.path.isfile(os.path.join(PDIR, 'fleet_preflight.py')),
      f'no fleet_preflight.py under {PDIR!r}')

# import it the way the supervisor does: by name, off that directory, nothing else
fp = None
saved_mod = sys.modules.pop('fleet_preflight', None)
saved_path = list(sys.path)
sys.path.insert(0, PDIR or os.path.join(TMP.name, 'no-such-dir'))
try:
    fp = importlib.import_module('fleet_preflight')
except Exception as e:
    check('fleet_preflight imports off exactly that path', False, repr(e))
finally:
    sys.path[:] = saved_path
    sys.modules.pop('fleet_preflight', None)
    if saved_mod is not None:
        sys.modules['fleet_preflight'] = saved_mod

if fp is not None:
    check('fleet_preflight imports off exactly that path',
          bool(PDIR)
          and os.path.realpath(fp.__file__).startswith(os.path.realpath(PDIR) + os.sep),
          str(getattr(fp, '__file__', None)))

    wanted = sorted({real for c in CONSUMERS for real in c['names'].values()})
    check('the guard still exposes every name this repo imports from it',
          bool(wanted) and all(callable(getattr(fp, n, None)) for n in wanted),
          f'wanted {wanted}, missing '
          f'{[n for n in wanted if not callable(getattr(fp, n, None))]}')

    # A keyword the guard no longer accepts is a TypeError inside gate()'s try, which the
    # fail-open branch swallows: the wave then runs with no guard at all and one log line.
    bad, ncalls = [], 0
    for c in CONSUMERS:
        for real, npos, kws, ln in c['calls']:
            fn = getattr(fp, real, None)
            if not callable(fn):
                continue
            ncalls += 1
            try:
                inspect.signature(fn).bind(*([object()] * npos),
                                           **{k: object() for k in kws})
            except TypeError as e:
                bad.append(f'{rel(c["path"])}:{ln} {real}(): {e}')
    check('every call this repo makes into the guard matches its signature',
          ncalls > 0 and not bad, '; '.join(bad) if bad else f'{ncalls} call sites')

# ------------------------------------------------------------------- gate(), the fail-open
print('\nsubject 2 - gate(), the supervisor half')


class _FakePreflight:
    """Stands in for the out-of-repo module inside gate()'s function-level import."""

    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = []

    def preflight(self, **kw):
        self.calls.append(kw)
        return self.behaviour(**kw)


def with_module(mod, fn):
    saved = sys.modules.get('fleet_preflight', '<absent>')
    sys.modules['fleet_preflight'] = mod
    try:
        return fn()
    finally:
        if saved == '<absent>':
            sys.modules.pop('fleet_preflight', None)
        else:
            sys.modules['fleet_preflight'] = saved


def refusing(**kw):
    raise SystemExit('REFUSING: 900 MB free, a 6-wide wave needs 2220 MB.')


sup.SAID.clear()
ok_mod = _FakePreflight(lambda **kw: {'free_mb': 9000})
check('gate() proceeds when the guard passes the box',
      with_module(ok_mod, lambda: sup.gate(6)) is True)
check('gate() asks the guard about the width it is about to run',
      ok_mod.calls == [{'want': 6}], str(ok_mod.calls))

sup.SAID.clear()
check('gate() refuses when the guard refuses (SystemExit is the guard saying no)',
      with_module(_FakePreflight(refusing), lambda: sup.gate(6)) is False)
check('a refusal is reported with the guard\'s own REFUSING line, which the supervisor '
      'later reads back to charge it to no budget',
      any('REFUSING:' in s for s in sup.SAID), str(sup.SAID))

# None in sys.modules makes `from fleet_preflight import preflight` raise ImportError -
# exactly what a renamed, moved or broken out-of-repo file does.
sup.SAID.clear()
gone = with_module(None, lambda: sup.gate(6))
xfail('gate() refuses when preflight is unavailable (KNOWN OPEN: currently fails open)',
      gone is False, f'gate() returned {gone!r} with the guard missing - the wave starts '
      f'with no RAM or swap check at all')
check('the fail-open leaves its one forensic trace in the log (this is what "unguarded" '
      'looks like in pipeline.log)',
      any('preflight unavailable' in s and 'proceeding without it' in s for s in sup.SAID),
      str(sup.SAID))


def drifted(**kw):
    raise TypeError("preflight() got an unexpected keyword argument 'want'")


sup.SAID.clear()
drift = with_module(_FakePreflight(drifted), lambda: sup.gate(6))
xfail('gate() refuses when the guard rejects its arguments (KNOWN OPEN: currently fails open)',
      drift is False, f'gate() returned {drift!r} after a TypeError - a signature drift in an '
      f'unversioned file silently disarms the guard')

print()
if XFAILS:
    print(f'{len(XFAILS)} EXPECTED FAILURES (known open defect, see the block comment):')
    for x in XFAILS:
        print(f'  - {x}')
    print()
if FAILS:
    print(f'{len(FAILS)} FAILURES')
    sys.exit(1)
print('all out-of-repo contract checks pass')
