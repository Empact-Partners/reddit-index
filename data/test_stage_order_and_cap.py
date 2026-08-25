#!/usr/bin/env python3
"""Two ordering/defaults invariants that were each paid for in a full day of wall clock.

(a) EXPANSION RUNS BEFORE COLLECTION — `data/pipeline_supervisor.py:296-316`,
    `data/run_collection_fast.py:69-83`.

    `worker/sweep.py` resolves each comment tree against the brand gazetteer AS IT STORES IT
    (`sweep_sub`, `:229`). A brand seeded after its subreddit was swept is therefore never
    attached to that subreddit's stored threads: the companies the 51 new categories exist to
    surface score zero while every log line reads success. On 2026-08-24 the collection leg was
    started ahead of the expansion leg and every one of those log lines said the sweep had
    worked. The stage sequence and the marker gate are the only two things standing between
    that mistake and a silent re-run of it, so both are asserted here by DRIVING them, never by
    reading the comment that explains them.

(b) NO SWEEP DRIVER MAY INVOKE sweep.py WITHOUT --tree-cap — `decisions/0014-depth-defaults.md:71`
    ("A fixture asserts no sweep driver invokes `sweep.py` without `--tree-cap`"), which until
    this file did not exist.

    The shipped 527-subreddit index was built at 150 trees per subreddit, pinned in
    `worker/.cache/depth/mode.json` by `worker/collector.py:53`. `worker/sweep.py:486` defaults
    to 100000. A driver that passes no cap therefore does ~50x the per-subreddit work that
    built the index, and NOTHING says so: on 2026-08-24 a 51-category sweep queued 4,769 trees
    for r/SideProject against 150 apiece under the shipped method, projecting 33 hours where
    ~12 was correct. Hours were burnt inside that before the two runs were compared.
    `data/run_depth90.py::pinned_mode()` (`:47-59`) is the fix: it READS the pin and refuses to
    run without it, because the silent fallback to 100000 is the whole failure.

    Two drivers still carry the debt — `data/run_collection_all.py:68` and the retired
    `data/run_collection_fast.py:273` (0014 "Consequences" retires the latter and names the
    former in its defaults table). They are frozen as a known set here: the set may SHRINK, and
    any file outside it that invokes sweep.py without a cap fails this fixture. Both are also
    asserted to be off the supervisor's live path, which is what makes the exemption honest.

    HOW (b) IS ESTABLISHED, and why it is no longer a token scan
    -----------------------------------------------------------
    The first version of this fixture proved (b) by looking for the STRING '--tree-cap' in a
    driver's source. An audit on 2026-08-24 ran that scanner against four synthetic drivers and
    it reported "clean" or saw nothing at all for every one of them:

        env_gated.py        cap behind `if os.environ.get('RI_CAP') == '1'`   -> PASSED
        dead_code_cap.py    cap inside `if False:`                            -> PASSED
        name_bound_path.py  SWEEP = f'{ROOT}/worker/sweep.py', then [.., SWEEP]-> INVISIBLE
        shell_string.py     subprocess.call('python3 .../sweep.py', shell=True)-> INVISIBLE

    A cap the scanner can see but the process never passes is exactly the 100000 fallback
    wearing a costume, so the primary evidence is now OBSERVED ARGV: `run_depth90.main()` is
    driven with `step()` stubbed (the same seam `run_collection_fast` is already tested
    through) and the argv it actually hands to sweep.py is asserted to carry --tree-cap at the
    PINNED value. Static scanning stays as the net over drivers this fixture does not execute,
    hardened on all four shapes above: name-bound paths are resolved, shell command strings are
    split and read, and a cap contributed under a branch the invocation itself is not under is
    counted as NO CAP — a cap that only sometimes applies is not a cap. The four synthetic
    drivers are rebuilt in a tempdir and re-run through the scanner on every execution of this
    file, so the net is proven able to fail before anything it says about the repo is believed.

Everything is offline. No DB, no network, no process is spawned except `--plan` runs of a
COPY of run_depth90.py inside a temp dir. The real `worker/.cache/depth/mode.json` pin and the
real `data/.pipeline/` state are never read, written, or deleted.

  python3 data/test_stage_order_and_cap.py
"""
import ast
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FAILS = []


def check(name, ok, detail=''):
    print(('  ok   ' if ok else '  FAIL ') + name + (f'  [{detail}]' if detail and not ok else ''))
    if not ok:
        FAILS.append(name)


def load(path, name):
    """Import a module BY PATH so a temp-dir copy tests THAT copy, never the live tree.

    Compiled from source text rather than through importlib, deliberately: a stale
    `__pycache__` entry is validated on (mtime, size), and an edit that preserves both — a
    reordering of two stage blocks, say — is exactly the mutation this fixture exists to
    catch. Reading the file is the only way to be sure we are testing the file."""
    src = open(path).read()
    m = types.ModuleType(name)
    m.__file__ = path
    exec(compile(src, path, 'exec'), m.__dict__)
    return m


# ---------------------------------------------------------------- (a) stage order

def supervisor(tmp):
    """A supervisor bound to a throwaway state dir with run()/gate() stubbed out, so calling
    attempt() records the sequence instead of starting four multi-hour lanes."""
    m = load(os.path.join(HERE, 'pipeline_supervisor.py'), f'sup_order_{os.path.basename(tmp)}')
    m.PDIR = tmp
    m.LOG = os.path.join(tmp, 'pipeline.log')
    m.STATE = os.path.join(tmp, 'state.json')
    m.LEGACY = os.path.join(tmp, 'nonexistent.log')      # never read the live run's log
    m.AGENT_PLIST = os.path.join(tmp, 'agent.plist')     # never touch the live plist
    m.uninstall = lambda: None
    m.gate = lambda width: True
    m.ran = []
    m.run = lambda args, label: (m.ran.append((os.path.basename(args[1]), label)), 0)[1]
    open(m.LOG, 'a').close()
    return m


print('Stage order and the tree cap\n')

with tempfile.TemporaryDirectory() as tmp:
    m = supervisor(tmp)
    rc = m.attempt()
    seq = [d for d, _ in m.ran]
    check('one attempt() drives discovery -> expansion -> collection -> finish',
          seq == ['run_discovery_all.py', 'run_expansion.py', 'run_depth90.py',
                  'run_finish_all.py'], str(seq))
    check('expansion is strictly before collection in the sequence attempt() executes',
          'run_expansion.py' in seq and 'run_depth90.py' in seq
          and seq.index('run_expansion.py') < seq.index('run_depth90.py'), str(seq))
    check('discovery precedes both expansion and collection',
          'run_discovery_all.py' in seq
          and seq.index('run_discovery_all.py') < seq.index('run_expansion.py')
          and seq.index('run_discovery_all.py') < seq.index('run_depth90.py'), str(seq))
    check('the collection stage is the pinned-cap driver run_depth90.py',
          'run_depth90.py' in seq, str(seq))
    check('a clean pass returns 0', rc == 0, str(rc))

with tempfile.TemporaryDirectory() as tmp:
    # expansion already seeded: it is skipped, and NOTHING else moves
    m = supervisor(tmp)
    open(os.path.join(tmp, 'expansion_seeded'), 'w').write('{}')
    m.attempt()
    seq = [d for d, _ in m.ran]
    check('a seeded expansion marker skips expansion without reordering the rest',
          seq == ['run_discovery_all.py', 'run_depth90.py', 'run_finish_all.py'], str(seq))

with tempfile.TemporaryDirectory() as tmp:
    # the dangerous shape: a COLLECTION COMPLETE from an earlier run, expansion never seeded.
    # Expansion must still run; collection must not be what unblocks it.
    m = supervisor(tmp)
    open(m.LOG, 'w').write('COLLECTION COMPLETE 01:00:00\n')
    m.attempt()
    seq = [d for d, _ in m.ran]
    check('a stale COLLECTION COMPLETE never lets expansion be skipped',
          'run_expansion.py' in seq and 'run_depth90.py' not in seq, str(seq))
    check('expansion is gated on its own marker file, not on the log',
          m.expansion_done() is False, str(m.expansion_done()))

# the second half of the same invariant: the sweep driver refuses to start without the marker
with tempfile.TemporaryDirectory() as tmp:
    fast = load(os.path.join(HERE, 'run_collection_fast.py'), 'rcf_gate')
    fast.EXPANSION_MARKER = os.path.join(tmp, 'expansion_seeded')
    fast.STATE = os.path.join(tmp, 'collected_subs.json')
    fast.waves = lambda: [(['testsub'], 30)]
    fast.depth_done = lambda: {}
    fast.mark = lambda subs, days: None
    fast.ship = lambda days, label: None
    # these open the live Postgres in production; here they only record that they were
    # reached, so the gate failing shows up as a named check rather than a stack trace
    touched = []
    fast.seeded = lambda subs: (touched.append('seeded'), {s.lower() for s in subs})[1]
    fast.boards_live = lambda: (touched.append('boards_live'), (0, 0, {}))[1]
    steps = []
    fast.step = lambda name, args, env=None, fatal=True: (steps.append(args), 0)[1]
    os.environ.pop('RI_SKIP_EXPANSION_GATE', None)
    sys.argv = ['run_collection_fast.py']

    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        rc = fast.main()
    check('run_collection_fast sweeps nothing when the expansion marker is missing',
          steps == [], str(steps))
    check('that refusal is a nonzero exit, not a warning', rc == 1, str(rc))
    check('the refusal says why', 'expansion' in err.getvalue().lower(), err.getvalue()[:80])
    check('nothing reaches Postgres before the expansion gate', touched == [], str(touched))

    # positive control: the gate is a gate, not an unconditional abort
    open(fast.EXPANSION_MARKER, 'w').write('{}')
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        rc = fast.main()
    check('with the marker present it proceeds to the sweep',
          rc == 0 and any('sweep.py' in ' '.join(a) for a in steps), f'rc={rc} {steps}')

    os.remove(fast.EXPANSION_MARKER)
    check('the gate is overridable only by RI_SKIP_EXPANSION_GATE=1',
          fast.expansion_ready() is False)
    os.environ['RI_SKIP_EXPANSION_GATE'] = '1'
    with contextlib.redirect_stdout(io.StringIO()):
        overridden = fast.expansion_ready()
    os.environ.pop('RI_SKIP_EXPANSION_GATE', None)
    check('the documented override still works', overridden is True)


# ---------------------------------------------------------------- (b) the tree cap

def _tok(n):
    """A source token reduced to something comparable. f'{ROOT}/worker/sweep.py' becomes
    '{}/worker/sweep.py', so an f-string path is recognised exactly like a literal one."""
    if isinstance(n, ast.Constant):
        return n.value if isinstance(n.value, str) else f'<{n.value!r}>'
    if isinstance(n, ast.JoinedStr):
        return ''.join(p.value if isinstance(p, ast.Constant) and isinstance(p.value, str)
                       else '{}' for p in n.values)
    if isinstance(n, ast.Name):
        return f'<{n.id}>'
    if isinstance(n, ast.Attribute):
        return f'<{n.attr}>'
    return '<expr>'


def _string_names(tree):
    """name -> its string token, for `SWEEP = f'{ROOT}/worker/sweep.py'`.

    Without this a driver that binds the script path to a name is not merely reported clean,
    it is INVISIBLE: `[sys.executable, SWEEP, ...]` tokenises to '<SWEEP>', nothing in the
    list ends with sweep.py, and the file never enters the scan at all. That was one of the
    four shapes the 2026-08-24 audit slipped past the token scanner."""
    names = {}
    for n in ast.walk(tree):
        if not isinstance(n, ast.Assign) or not isinstance(n.value, (ast.Constant,
                                                                     ast.JoinedStr)):
            continue
        t = _tok(n.value)
        for tgt in n.targets:
            if not isinstance(tgt, ast.Name):
                continue
            prev = names.get(tgt.id)
            # a name rebound to several literals keeps whichever binding could be a sweep
            # path: for this scanner a possible invocation must stay visible
            if prev is None or ('sweep.py' in t and 'sweep.py' not in prev):
                names[tgt.id] = t
    return names


def _tokr(n, names):
    """_tok, plus one level of name resolution."""
    if isinstance(n, ast.Name) and n.id in names:
        return names[n.id]
    return _tok(n)


def _scope_of(node, parents):
    p = parents.get(node)
    while p is not None and not isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef,
                                               ast.Module)):
        p = parents.get(p)
    return p


# every construct that can decide NOT to run the statement inside it. `if False:` needs no
# separate reachability pass — it is an If like any other, and an If the invocation is not
# also under means the flag is conditional.
BRANCHES = (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With,
            ast.AsyncWith, ast.ExceptHandler)


def _branches(node, parents, scope):
    out = set()
    p = parents.get(node)
    while p is not None and p is not scope:
        if isinstance(p, BRANCHES):
            out.add(id(p))
        p = parents.get(p)
    return out


INTERPRETERS = ('<executable>', 'python3', 'python', '/opt/homebrew/bin/python3')
EXEC_CALLS = ('call', 'run', 'Popen', 'check_call', 'check_output', 'system', 'popen',
              'getoutput', 'getstatusoutput')


def _is_invocation(toks):
    """An argv list, not a list that merely NAMES the script.

    pipeline_supervisor.LANE_PATTERNS holds the bare string 'worker/sweep.py' as a pgrep
    pattern; it starts no sweep and has no cap to pass. An argv list either leads with the
    script or carries the interpreter that runs it."""
    i = next(i for i, t in enumerate(toks) if t.endswith('sweep.py'))
    return i == 0 or any(t in INTERPRETERS for t in toks[:i])


def _shell_invocations(tree, names):
    """Sweeps launched through a COMMAND STRING rather than an argv list.

    `subprocess.call(f'python3 {ROOT}/worker/sweep.py --days 90', shell=True)` contains no
    list at all, so a scanner that only walks ast.List sees no invocation anywhere in the
    file. Only the exec-shaped callees are read, so a `print()` of an example command in a
    --plan banner is not mistaken for a launch."""
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        fname = f.attr if isinstance(f, ast.Attribute) else (
            f.id if isinstance(f, ast.Name) else '')
        if fname not in EXEC_CALLS:
            continue
        cand = list(n.args) + [k.value for k in n.keywords if k.arg in ('args', 'cmd')]
        for a in cand:
            if not isinstance(a, (ast.Constant, ast.JoinedStr, ast.Name)):
                continue
            t = _tokr(a, names)
            if 'sweep.py' not in t:
                continue
            toks = t.replace('&&', ' ').replace(';', ' ').replace('|', ' ').split()
            if any(x.endswith('sweep.py') for x in toks) and _is_invocation(toks):
                out.append((n.lineno, toks))
    return out


def sweep_invocations(path):
    """[(lineno, tokens)] for every argument list or command string in `path` that INVOKES
    worker/sweep.py.

    Argument lists are frequently built across several statements (`args = [...]` then
    `args += [...]` / `args.append(...)`), so a list literal that names sweep.py is credited
    with everything appended to the same variable inside the same function. A naive grep of the
    invocation line would call such a driver uncapped, or worse call it capped.

    A contribution only counts when it runs whenever the invocation runs. A flag appended
    under a branch the base list is not itself under — `if os.environ.get('RI_CAP') == '1'`,
    or `if False:` — is dropped, so the driver is reported UNCAPPED. That is the honest
    reading: the process either always passes the cap or the 100000 default is live on some
    path, and a cap on some paths is what the 33-hour projection was made of."""
    tree = ast.parse(open(path).read())
    parents = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            parents[c] = n
    names = _string_names(tree)

    assigned = {}                      # id(List node) -> variable name it was bound to
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name) \
                and isinstance(n.value, (ast.List, ast.Tuple)):
            assigned[id(n.value)] = n.targets[0].id

    out = []
    for n in ast.walk(tree):
        if not isinstance(n, (ast.List, ast.Tuple)):
            continue
        toks = [_tokr(e, names) for e in n.elts]
        if not any(t.endswith('sweep.py') for t in toks) or not _is_invocation(toks):
            continue
        var = assigned.get(id(n))
        if var:
            scope = _scope_of(n, parents) or tree
            base = _branches(n, parents, scope)
            for s in ast.walk(scope):
                if isinstance(s, ast.AugAssign) and isinstance(s.target, ast.Name) \
                        and s.target.id == var and isinstance(s.value, (ast.List, ast.Tuple)):
                    if not _branches(s, parents, scope) <= base:
                        continue
                    toks += [_tokr(e, names) for e in s.value.elts]
                elif isinstance(s, ast.Call) and isinstance(s.func, ast.Attribute) \
                        and isinstance(s.func.value, ast.Name) and s.func.value.id == var \
                        and s.func.attr in ('append', 'extend'):
                    if not _branches(s, parents, scope) <= base:
                        continue
                    for a in s.args:
                        toks += ([_tokr(e, names) for e in a.elts]
                                 if isinstance(a, (ast.List, ast.Tuple)) else [_tokr(a, names)])
        out.append((n.lineno, toks))
    out += _shell_invocations(tree, names)
    return sorted(out)


def uncapped(path):
    return [ln for ln, toks in sweep_invocations(path) if '--tree-cap' not in toks]


# the scanner is the check, so prove the scanner can FAIL before trusting what it says about
# the repo. A scanner that cannot fail advertises coverage that does not exist. The four
# BLIND-SPOT drivers below are the exact shapes the 2026-08-24 audit walked past the token
# scanner; each is paired with a capped twin so "flags everything" cannot pass either.
with tempfile.TemporaryDirectory() as tmp:
    def drv(name, body):
        p = os.path.join(tmp, name)
        open(p, 'w').write(body)
        return p

    good = drv('good_driver.py',
               "import os, subprocess, sys\n"
               "ROOT = '/x'\n"
               "def go(days, cap, chunk):\n"
               "    args = [sys.executable, f'{ROOT}/worker/sweep.py']\n"
               "    args += ['--days', str(days)]\n"
               "    args += ['--tree-cap', str(cap)]\n"
               "    args.append('--only')\n"
               "    args.append(','.join(chunk))\n"
               "    return subprocess.call(args)\n")
    bad = drv('bad_driver.py',
              "import os, subprocess, sys\n"
              "ROOT = '/x'\n"
              "def go(days, chunk):\n"
              "    args = [sys.executable, f'{ROOT}/worker/sweep.py']\n"
              "    args += ['--days', str(days)]\n"
              "    args.extend(['--only', ','.join(chunk)])\n"
              "    return subprocess.call(args)\n")
    flat = drv('flat_driver.py',
               "import subprocess, sys\n"
               "subprocess.call([sys.executable, 'worker/sweep.py', '--days', '90'])\n")
    none = drv('no_sweep.py', "import subprocess\nsubprocess.call(['ls', '--tree-cap'])\n")
    pat = drv('patterns_only.py',
              "LANE_PATTERNS = ['discover_v2.py', 'worker/sweep.py', 'daily.py']\n")
    py3 = drv('py3_driver.py',
              "import subprocess\n"
              "subprocess.call(['python3', 'worker/sweep.py', '--days', '90'])\n")

    # --- the four audited blind spots ---
    env_gated = drv('env_gated.py',
                    "import os, subprocess, sys\n"
                    "ROOT = '/x'\n"
                    "def go(days, cap):\n"
                    "    args = [sys.executable, f'{ROOT}/worker/sweep.py', '--days', str(days)]\n"
                    "    if os.environ.get('RI_CAP') == '1':\n"
                    "        args += ['--tree-cap', str(cap)]\n"
                    "    return subprocess.call(args)\n")
    dead_code = drv('dead_code_cap.py',
                    "import subprocess, sys\n"
                    "ROOT = '/x'\n"
                    "def go(days, cap):\n"
                    "    args = [sys.executable, f'{ROOT}/worker/sweep.py', '--days', str(days)]\n"
                    "    if False:\n"
                    "        args += ['--tree-cap', str(cap)]\n"
                    "    return subprocess.call(args)\n")
    name_bound = drv('name_bound_path.py',
                     "import subprocess, sys\n"
                     "ROOT = '/x'\n"
                     "SWEEP = f'{ROOT}/worker/sweep.py'\n"
                     "def go(days):\n"
                     "    return subprocess.call([sys.executable, SWEEP, '--days', str(days)])\n")
    env_gated_append = drv('env_gated_append.py',
                           "import os, subprocess, sys\n"
                           "ROOT = '/x'\n"
                           "def go(days, cap):\n"
                           "    args = [sys.executable, f'{ROOT}/worker/sweep.py', '--days', str(days)]\n"
                           "    if os.environ.get('RI_CAP') == '1':\n"
                           "        args.append('--tree-cap')\n"
                           "        args.append(str(cap))\n"
                           "    return subprocess.call(args)\n")
    shell = drv('shell_string.py',
                "import subprocess\n"
                "ROOT = '/x'\n"
                "def go(days):\n"
                "    return subprocess.call(f'python3 {ROOT}/worker/sweep.py --days {days}',\n"
                "                           shell=True)\n")
    # capped twins of the two shapes the scanner had to learn to SEE at all
    name_bound_ok = drv('name_bound_capped.py',
                        "import subprocess, sys\n"
                        "ROOT = '/x'\n"
                        "SWEEP = f'{ROOT}/worker/sweep.py'\n"
                        "def go(days, cap):\n"
                        "    return subprocess.call([sys.executable, SWEEP, '--days', str(days),\n"
                        "                            '--tree-cap', str(cap)])\n")
    shell_ok = drv('shell_capped.py',
                   "import subprocess\n"
                   "ROOT = '/x'\n"
                   "def go(days, cap):\n"
                   "    return subprocess.call(\n"
                   "        f'python3 {ROOT}/worker/sweep.py --days {days} --tree-cap {cap}',\n"
                   "        shell=True)\n")
    # and the shape the branch rule must NOT over-report: the whole invocation, cap included,
    # sitting inside one `if`
    branch_ok = drv('capped_inside_branch.py',
                    "import subprocess, sys\n"
                    "def go(days, cap, run):\n"
                    "    if run:\n"
                    "        args = [sys.executable, 'worker/sweep.py']\n"
                    "        args += ['--days', str(days), '--tree-cap', str(cap)]\n"
                    "        return subprocess.call(args)\n")
    printer = drv('prints_the_command.py',
                  "def plan(subs):\n"
                  "    print(f'  next: python3 worker/sweep.py --days 90 --only {subs}')\n")

    check('the scanner sees a multi-line arg list as one invocation',
          len(sweep_invocations(good)) == 1 and len(sweep_invocations(bad)) == 1,
          f'{sweep_invocations(good)} / {sweep_invocations(bad)}')
    check('the scanner FLAGS a new driver that omits --tree-cap across lines',
          uncapped(bad) != [], 'a driver built across lines slipped through')
    check('the scanner FLAGS a flat uncapped invocation', uncapped(flat) != [])
    check('the scanner does not flag a capped multi-line driver', uncapped(good) == [],
          str(sweep_invocations(good)))
    check('the scanner does not invent invocations', sweep_invocations(none) == [])
    check('a pgrep pattern list is not mistaken for an invocation',
          sweep_invocations(pat) == [], str(sweep_invocations(pat)))
    check('an uncapped python3-prefixed invocation is still FLAGGED',
          uncapped(py3) != [], str(sweep_invocations(py3)))

    check('blind spot 1: an env-gated cap is UNCAPPED, not clean',
          len(sweep_invocations(env_gated)) == 1 and uncapped(env_gated) != [],
          str(sweep_invocations(env_gated)))
    check('blind spot 1b: the same env gate via append() is UNCAPPED too',
          len(sweep_invocations(env_gated_append)) == 1 and uncapped(env_gated_append) != [],
          str(sweep_invocations(env_gated_append)))
    check('blind spot 2: a cap inside `if False:` is UNCAPPED, not clean',
          len(sweep_invocations(dead_code)) == 1 and uncapped(dead_code) != [],
          str(sweep_invocations(dead_code)))
    check('blind spot 3: a name-bound sweep path is VISIBLE and flagged',
          len(sweep_invocations(name_bound)) == 1 and uncapped(name_bound) != [],
          str(sweep_invocations(name_bound)))
    check('blind spot 4: a shell command string is VISIBLE and flagged',
          len(sweep_invocations(shell)) == 1 and uncapped(shell) != [],
          str(sweep_invocations(shell)))
    check('a name-bound path WITH a cap is seen and passes',
          len(sweep_invocations(name_bound_ok)) == 1 and uncapped(name_bound_ok) == [],
          str(sweep_invocations(name_bound_ok)))
    check('a shell string WITH a cap is seen and passes',
          len(sweep_invocations(shell_ok)) == 1 and uncapped(shell_ok) == [],
          str(sweep_invocations(shell_ok)))
    check('a cap under the SAME branch as the invocation still counts',
          len(sweep_invocations(branch_ok)) == 1 and uncapped(branch_ok) == [],
          str(sweep_invocations(branch_ok)))
    check('printing an example command is not an invocation',
          sweep_invocations(printer) == [], str(sweep_invocations(printer)))

# sweep.py must still offer the flag every driver is required to pass
sweep_src = ast.parse(open(os.path.join(ROOT, 'worker', 'sweep.py')).read())
flags = [_tok(a) for n in ast.walk(sweep_src) if isinstance(n, ast.Call)
         and isinstance(n.func, ast.Attribute) and n.func.attr == 'add_argument'
         for a in n.args]
check('worker/sweep.py still declares --tree-cap', '--tree-cap' in flags, str(flags))

# the whole repo, not just the driver we happen to remember
KNOWN_UNCAPPED_DEBT = {
    # 0014 Consequences: retired in favour of run_depth90.py (wrong depth, wrong cadence)
    'data/run_collection_fast.py',
    # 0014 defaults table: "passes no cap at all" — the invocation the post-mortem indicts
    'data/run_collection_all.py',
}
scanned, offenders, capped = 0, {}, {}
for d in ('data', 'worker'):
    base = os.path.join(ROOT, d)
    for fn in sorted(os.listdir(base)):
        if not fn.endswith('.py') or fn.startswith('test_'):
            continue
        p = os.path.join(base, fn)
        inv = sweep_invocations(p)
        if not inv:
            continue
        scanned += 1
        rel = f'{d}/{fn}'
        bad = uncapped(p)
        (offenders if bad else capped)[rel] = bad or [ln for ln, _ in inv]

check('the repo scan actually found sweep drivers', scanned >= 3, f'scanned {scanned}')
check('data/run_depth90.py passes --tree-cap on every sweep invocation',
      'data/run_depth90.py' in capped, f'capped={sorted(capped)} uncapped={sorted(offenders)}')
check('no sweep driver outside the frozen 0014 debt set omits --tree-cap',
      set(offenders) <= KNOWN_UNCAPPED_DEBT,
      f'uncapped and undocumented: {sorted(set(offenders) - KNOWN_UNCAPPED_DEBT)}')

# which drivers the supervisor actually launches: the f'{HERE}/x.py' args it hands to run().
# LANE_PATTERNS holds bare 'run_collection_all.py' strings, which are patterns, not launches —
# requiring the '{}/' prefix is what separates the two.
sup_src = ast.parse(open(os.path.join(HERE, 'pipeline_supervisor.py')).read())
launched = sorted({t.split('/')[-1] for n in ast.walk(sup_src)
                   if isinstance(n, (ast.List, ast.Tuple)) for t in (_tok(e) for e in n.elts)
                   if t.startswith('{}/') and t.endswith('.py')})
check('the supervisor launch set was extracted, not silently empty',
      'run_depth90.py' in launched and len(launched) >= 4, str(launched))
live_offenders = [f for f in offenders if os.path.basename(f) in launched]
check('no driver the supervisor launches omits --tree-cap', live_offenders == [],
      str(live_offenders))
check('the frozen uncapped drivers are off the supervisor path',
      not (KNOWN_UNCAPPED_DEBT & {f'data/{b}' for b in launched}),
      str(KNOWN_UNCAPPED_DEBT & {f'data/{b}' for b in launched}))


# ---------------------------------------------------- (b) again, from OBSERVED argv

def depth90_sandbox(tmp, pin=True):
    """A COPY of run_depth90.py with the whole set of files it reads beside it.

    Two things depend on this being complete. The observed-argv run below needs main() to
    reach a sweep at all, and the `--plan` return code below means nothing unless every input
    except the pin is present — with clusters.json missing, --plan exits 1 for every possible
    pinned_mode, including a deleted one."""
    os.makedirs(os.path.join(tmp, 'data', '.roster-import', 'map'), exist_ok=True)
    os.makedirs(os.path.join(tmp, 'worker', '.cache', 'depth'), exist_ok=True)
    copy = os.path.join(tmp, 'data', 'run_depth90.py')
    shutil.copy(os.path.join(HERE, 'run_depth90.py'), copy)
    d = os.path.join(tmp, 'data')
    json.dump({'proposed': [{'slug': 'crm'}, {'slug': 'vpn'}]},
              open(os.path.join(d, '.roster-import', 'map', 'clusters.json'), 'w'))
    open(os.path.join(d, 'category-subreddits.csv'), 'w').write(
        'category_slug,subreddit,is_core,worth\n'
        'crm,salesforce,True,9.0\n'
        'crm,CRM,True,4.0\n'
        'vpn,VPN,True,7.0\n'
        'other,ignored,True,9.9\n'
        'crm,notcore,False,9.9\n')
    open(os.path.join(d, 'brands.csv'), 'w').write(
        'brand,slug,primary_category_slug,also_in_category_slugs,domains\n'
        'Salesforce,salesforce,crm,,salesforce.com\n'
        'Mullvad,mullvad,vpn,,mullvad.net\n')
    fp = os.path.join(tmp, 'worker', '.cache', 'depth', 'mode.json')
    if pin:
        open(fp, 'w').write('{"days": 90, "tree_cap": 150}')
    return copy, fp


# pinned_mode(): refuse, never fall back. Tested on a COPY — the live pin is never touched.
with tempfile.TemporaryDirectory() as tmp:
    copy, pin = depth90_sandbox(tmp, pin=False)

    d90 = load(copy, 'd90_missing')
    check('pinned_mode reads the copy, not the live pin', d90.MODE_FP == pin, d90.MODE_FP)
    try:
        got = d90.pinned_mode()
        check('pinned_mode refuses when the pin is missing', False, f'returned {got}')
    except SystemExit as e:
        check('pinned_mode refuses when the pin is missing', 'REFUSING' in str(e), str(e)[:60])

    open(pin, 'w').write('{"days": 90}')            # malformed: no tree_cap
    try:
        got = load(copy, 'd90_bad').pinned_mode()
        check('pinned_mode refuses when the pin is malformed', False, f'returned {got}')
    except SystemExit as e:
        check('pinned_mode refuses when the pin is malformed', 'REFUSING' in str(e), str(e)[:60])

    open(pin, 'w').write('{"days": 90, "tree_cap": 150}')
    check('pinned_mode returns the pinned days/tree-cap when it can read them',
          load(copy, 'd90_ok').pinned_mode() == (90, 150),
          str(load(copy, 'd90_ok2').pinned_mode()))

    # THE ARGV THE PROCESS WOULD ACTUALLY PASS. step() is the seam: stubbed, main() plans and
    # dispatches exactly as it does in production, and every command it would have spawned is
    # recorded instead. A cap that is present in the source but absent here is the failure the
    # static scan was blind to.
    d90 = load(copy, 'd90_observed')
    d90.PD = tmp                                   # never read partner-development from a test
    d90.seeded = lambda subs: {s.lower() for s in subs}     # would open live Postgres
    argvs = []
    d90.step = lambda name, args, env=None, fatal=True: (argvs.append(list(args)), 0)[1]
    sys.argv = ['run_depth90.py']
    with contextlib.redirect_stdout(io.StringIO()):
        rc = d90.main()
    sweeps = [a for a in argvs if any(str(t).endswith('sweep.py') for t in a)]
    check('driving run_depth90.main() reached a sweep at all', rc == 0 and len(sweeps) >= 2,
          f'rc={rc} argvs={len(argvs)} sweeps={len(sweeps)}')
    check('every observed sweep argv carries --tree-cap',
          sweeps and all('--tree-cap' in a for a in sweeps), str(sweeps))
    check('the observed cap is the PINNED 150, not sweep.py\'s 100000 default',
          sweeps and all(a[a.index('--tree-cap') + 1] == '150'
                         for a in sweeps if '--tree-cap' in a), str(sweeps))
    check('the observed depth is the pinned 90 days',
          sweeps and all('--days' in a and a[a.index('--days') + 1] == '90' for a in sweeps),
          str(sweeps))

    # and the same driver as a real process. WITH the pin (and the inputs beside it) --plan
    # exits 0; the nonzero below is therefore attributable to the pin and nothing else.
    r = subprocess.run([sys.executable, copy, '--plan'], capture_output=True, text=True,
                       cwd=tmp, timeout=60)
    check('run_depth90.py --plan exits 0 when the pin and its inputs are all present',
          r.returncode == 0, f'rc={r.returncode} {(r.stderr or r.stdout)[:160]}')
    check('--plan reports the pinned cap rather than a default',
          'tree cap 150' in r.stdout, r.stdout[:120])

    os.remove(pin)
    r = subprocess.run([sys.executable, copy, '--plan'], capture_output=True, text=True,
                       cwd=tmp, timeout=60)
    check('removing ONLY the pin makes run_depth90.py --plan exit nonzero',
          r.returncode != 0, f'rc={r.returncode}')
    check('and says REFUSING rather than falling back to 100000',
          'REFUSING' in (r.stderr + r.stdout) and '100000' in (r.stderr + r.stdout),
          (r.stderr or r.stdout)[:120])

print()
if FAILS:
    print(f'{len(FAILS)} FAILURES')
    sys.exit(1)
print('stage order holds and every live sweep driver passes --tree-cap')
