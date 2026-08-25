#!/usr/bin/env python3
"""One command that runs the whole fixture gate, because a gate whose worst case is
"it hangs forever" is a gate people stop running.

2026-08-24 audit: the suite had a dozen fixtures, no runner and no timeout. Reverting the
attempt cap in pipeline_supervisor.py put test_pipeline_supervisor.py into an unbounded
restart loop — 1,696 attempts in 15 s, no output, no exit, and nothing to do but ^C and
guess. Three other reverts died in a traceback partway through instead of printing a FAIL
line, leaving ~40 checks unevaluated. The exit codes were still nonzero so nothing read as
green, but "run these twelve files by hand and read the tracebacks" is not a gate.

So this runner owes four things the bare `python3 data/test_x.py` loop did not:

  1. a per-file timeout, and a TIMEOUT verdict that is not a FAIL   (--timeout, default 30 s)
  2. the killed child's whole PROCESS GROUP dies with it, so a hung fixture's own children
     cannot outlive the runner
  3. a CRASH verdict that is not a FAIL, printed with the tail of that fixture's output, so
     the cause is visible without re-running it by hand
  4. checks EVALUATED against checks the file DECLARES, so a partial run cannot read as a
     small clean run

It runs fixtures and nothing else: only files named test_*.py, one at a time (a suite that
guards a live pipeline must not become load on it), no pipeline, no database, no network of
its own.

  python3 data/run_all_fixtures.py                     # data/ + worker/
  python3 data/run_all_fixtures.py --timeout 60
  python3 data/run_all_fixtures.py /some/other/scripts  # extra directories
  python3 data/run_all_fixtures.py --json
  python3 data/run_all_fixtures.py --self-test-only     # prove the runner, run no suite

The runner SELF-TESTS before every run (--no-self-test to skip). It builds synthetic
fixtures that pass, fail, crash, hang, spawn a child, and under-report, and asserts it
classifies each one correctly. That is this file's regression surface: a runner that cannot
tell a hang from a pass is worse than no runner, because it advertises a gate that is not
there.
"""
import argparse
import glob
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PY = '/opt/homebrew/bin/python3'
if not os.path.exists(PY):
    PY = sys.executable

FAILS = []

# The fixtures all print their results with a two-space prefix (see data/test_*.py:check).
MARK_RE = re.compile(r'^  (ok|FAIL|skip|xfail)(?:\s|$)')
# ...and several close with "9/9 passed" / "12/13 fixtures passed", which is the only place
# a fixture DECLARES how many checks it meant to run.
DECL_RE = re.compile(r'(\d+)\s*/\s*(\d+)\s+(?:\w+\s+)?passed')
TRACEBACK = 'Traceback (most recent call last):'
VERDICTS = ('ok', 'FAIL', 'TIMEOUT', 'CRASH')
TAIL_LINES = 8


def check(name, ok, detail='', stream=None):
    s = stream or sys.stdout
    print(('  ok   ' if ok else '  FAIL ') + name + (f'  [{detail}]' if detail and not ok else ''),
          file=s)
    if not ok:
        FAILS.append(name)


# ------------------------------------------------------------------------------------------
# discovery — fixtures only, never anything else
# ------------------------------------------------------------------------------------------
def discover(dirs):
    """Every test_*.py under the given directories. Nothing else is ever executed: this
    runner is a gate, not a launcher, and the pipeline it guards is running right now."""
    found = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for p in sorted(glob.glob(os.path.join(d, 'test_*.py'))):
            if os.path.isfile(p):
                found.append(os.path.abspath(p))
    return found


def default_dirs():
    return [HERE, os.path.join(ROOT, 'worker')]


# ------------------------------------------------------------------------------------------
# running one fixture
# ------------------------------------------------------------------------------------------
def kill_group(proc, pgid):
    """Kill the child AND everything it spawned. A hung fixture that leaves a sweep or an
    lsof loop behind has not been stopped, it has been orphaned."""
    mine = os.getpgrp()
    if isinstance(pgid, int) and pgid > 0 and pgid != mine:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    else:
        # Refuse to signal our own group: that would kill the runner. We only land here if
        # the child was not started in its own session, which is itself a bug — the
        # self-test asserts the pgid is separate, so it will be reported, not swallowed.
        try:
            proc.kill()
        except ProcessLookupError:
            pass


def parse_counts(text):
    ok = fail = skip = xfail = 0
    for line in text.splitlines():
        m = MARK_RE.match(line)
        if not m:
            continue
        kind = m.group(1)
        if kind == 'ok':
            ok += 1
        elif kind == 'FAIL':
            fail += 1
        elif kind == 'skip':
            skip += 1
        else:
            xfail += 1
    declared = None
    for m in DECL_RE.finditer(text):
        declared = int(m.group(2))
    return ok, fail, skip, xfail, declared


def classify(rc, out, err, timed_out, evaluated, fail_n, declared):
    """A TIMEOUT is not a FAIL, and a CRASH is not a FAIL. Collapsing them is how a hang
    became something people stopped running."""
    if timed_out:
        return 'TIMEOUT', 'killed at the timeout'
    crashed = TRACEBACK in err
    summarised = re.search(r'^\d+ (?:FAILURES|EXPECTED FAILURES)', out, re.M) is not None
    if rc != 0:
        if crashed and not summarised:
            return 'CRASH', 'traceback, partial run'
        if rc < 0:
            return 'CRASH', f'killed by signal {-rc}'
        if fail_n or summarised:
            return 'FAIL', f'{fail_n} failed check(s)'
        return 'CRASH', f'exit {rc} with no FAIL line'
    if fail_n:
        return 'FAIL', f'{fail_n} failed check(s) but exit 0'
    if declared is not None and evaluated != declared:
        # A file that meant to run 9 checks and printed 2 is a partial run wearing the
        # costume of a small clean one.
        return 'FAIL', f'evaluated {evaluated} of {declared} declared'
    return 'ok', ''


def run_one(path, timeout):
    out_f = tempfile.TemporaryFile('w+b')
    err_f = tempfile.TemporaryFile('w+b')
    t0 = time.time()
    proc = subprocess.Popen([PY, path], stdout=out_f, stderr=err_f,
                            stdin=subprocess.DEVNULL,
                            cwd=os.path.dirname(path),
                            start_new_session=True)
    try:
        pgid = os.getpgid(proc.pid)
    except (ProcessLookupError, OSError):
        pgid = None
    timed_out = False
    try:
        rc = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_group(proc, pgid)
        try:
            rc = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            rc = -signal.SIGKILL
    secs = time.time() - t0
    out_f.seek(0)
    err_f.seek(0)
    out = out_f.read().decode('utf-8', 'replace')
    err = err_f.read().decode('utf-8', 'replace')
    out_f.close()
    err_f.close()

    ok_n, fail_n, skip_n, xfail_n, declared = parse_counts(out + err)
    evaluated = ok_n + fail_n + skip_n + xfail_n
    verdict, note = classify(rc, out, err, timed_out, evaluated, fail_n, declared)
    return {
        'path': path,
        'verdict': verdict,
        'note': note,
        'rc': rc,
        'timed_out': timed_out,
        'pgid': pgid,
        'ok': ok_n,
        'fail': fail_n,
        'skip': skip_n,
        'xfail': xfail_n,
        'evaluated': evaluated,
        'declared': declared,
        'secs': round(secs, 2),
        'tail': tail_of(out, err),
    }


def tail_of(out, err):
    lines = [ln.rstrip() for ln in (out + ('\n' if out and err else '') + err).splitlines()
             if ln.strip()]
    return lines[-TAIL_LINES:]


def run_suite(dirs, timeout, progress=None):
    """Serial by design. These fixtures copy 60 MB CSVs and grep the repo while a live
    pipeline is mid-write; a parallel gate would be measuring contention, not correctness."""
    results = []
    for p in discover(dirs):
        if progress:
            print(f'  .. {disp(p)}', file=progress, flush=True)
        results.append(run_one(p, timeout))
    return results


# ------------------------------------------------------------------------------------------
# reporting
# ------------------------------------------------------------------------------------------
def disp(path):
    rel = os.path.relpath(path, ROOT)
    if rel.startswith('..'):
        return os.path.join(os.path.basename(os.path.dirname(path)), os.path.basename(path))
    return rel


def overall_exit(results):
    """Nonzero if ANY file fails, times out or crashes — and if nothing ran at all, which
    is the silent way a gate stops guarding."""
    if not results:
        return 1
    return 1 if any(r['verdict'] != 'ok' for r in results) else 0


def render(results):
    if not results:
        return 'no test_*.py fixtures found — nothing was checked\n'
    w = max(len(disp(r['path'])) for r in results)
    w = max(w, len('FILE'))
    lines = []
    lines.append(f'{"FILE".ljust(w)}  {"VERDICT".ljust(7)}  {"OK":>4} {"FAIL":>4} {"SKIP":>4}'
                 f'  {"EVAL/DECL":>10}  {"SECS":>6}')
    lines.append('-' * (w + 44))
    for r in results:
        decl = f'{r["evaluated"]}/{r["declared"]}' if r['declared'] is not None \
            else str(r['evaluated'])
        skip = r['skip'] + r['xfail']
        lines.append(f'{disp(r["path"]).ljust(w)}  {r["verdict"].ljust(7)}  '
                     f'{r["ok"]:>4} {r["fail"]:>4} {skip:>4}  {decl:>10}  {r["secs"]:>6.1f}')
    lines.append('')
    for r in results:
        if r['verdict'] in ('CRASH', 'TIMEOUT'):
            lines.append(f'{r["verdict"]}  {disp(r["path"])}  ({r["note"]}) — last '
                         f'{len(r["tail"])} lines of its output:')
            for ln in r['tail']:
                lines.append(f'    | {ln}')
            lines.append('')
    tally = {v: sum(1 for r in results if r['verdict'] == v) for v in VERDICTS}
    checks = sum(r['evaluated'] for r in results)
    failed = sum(r['fail'] for r in results)
    skipped = sum(r['skip'] + r['xfail'] for r in results)
    code = overall_exit(results)
    lines.append(f'{len(results)} files: {tally["ok"]} ok, {tally["FAIL"]} FAIL, '
                 f'{tally["TIMEOUT"]} TIMEOUT, {tally["CRASH"]} CRASH  |  '
                 f'{checks} checks evaluated, {failed} failed, {skipped} not evaluated  |  '
                 f'exit {code}')
    return '\n'.join(lines) + '\n'


# ------------------------------------------------------------------------------------------
# self-test — the runner's own regression surface
# ------------------------------------------------------------------------------------------
CRASH_MARKER = 'SYNTHCRASH_MARKER_7Q'

SYNTH = {
    'test_synth_pass.py':
        "print('  ok   alpha')\n"
        "print('  ok   beta')\n"
        "print('  ok   gamma')\n"
        "print('\\n3/3 passed')\n",
    'test_synth_fail.py':
        "import sys\n"
        "print('  ok   alpha')\n"
        "print('  FAIL beta  [expected 1 got 2]')\n"
        "print('\\n1 FAILURES')\n"
        "sys.exit(1)\n",
    'test_synth_crash.py':
        "print('  ok   alpha')\n"
        f"raise RuntimeError('{CRASH_MARKER}')\n",
    'test_synth_short.py':
        "print('  ok   alpha')\n"
        "print('  ok   beta')\n"
        "print('\\n2/9 passed')\n",
    'test_synth_silent.py':
        "import sys\nsys.exit(3)\n",
    'test_synth_hang.py':
        "import os, subprocess, sys, time\n"
        "here = os.path.dirname(os.path.abspath(__file__))\n"
        "g = subprocess.Popen(['sleep', '300'])\n"
        "open(os.path.join(here, 'grandchild.pid'), 'w').write(str(g.pid))\n"
        "print('  ok   spawned a child', flush=True)\n"
        "while True:\n"
        "    time.sleep(0.05)\n",
    # NOT a test_*.py: if this ever runs, the runner is a launcher, not a gate.
    'notatest_synth.py':
        "import os\n"
        "print('  ok   this file must never be run')\n"
        "open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'RAN'), 'w').write('x')\n",
}

SELF_TIMEOUT = 2.0


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def self_test(stream=None):
    """Build fixtures that pass, fail, crash, hang and under-report; assert the runner tells
    them apart. Every check here has been broken on purpose — see the mutation list."""
    s = stream or sys.stdout
    before = len(FAILS)
    print('Runner self-test\n', file=s)
    grandchild = None
    with tempfile.TemporaryDirectory() as tmp:
        for name, src in SYNTH.items():
            with open(os.path.join(tmp, name), 'w') as f:
                f.write(src)

        names = [os.path.basename(p) for p in discover([tmp])]
        check('discovery runs only test_*.py files',
              'notatest_synth.py' not in names, str(names), stream=s)

        # the same entry point main() uses, so the wiring is under test, not just the helpers
        results = run_suite([tmp], SELF_TIMEOUT)
        table = render(results)
        r = {os.path.basename(x['path']): x for x in results}
        try:
            pidf = os.path.join(tmp, 'grandchild.pid')
            if os.path.exists(pidf):
                grandchild = int(open(pidf).read().strip())

            check('and the non-test file was never executed',
                  not os.path.exists(os.path.join(tmp, 'RAN')), stream=s)
            check('every discovered fixture appears in the table',
                  all(n in table for n in r), stream=s)

            p = r.get('test_synth_pass.py', {})
            check('a passing fixture is ok', p.get('verdict') == 'ok',
                  f'{p.get("verdict")} {p.get("note")}', stream=s)
            check('its check counts are parsed from its own output',
                  (p.get('ok'), p.get('fail'), p.get('declared')) == (3, 0, 3),
                  f'ok={p.get("ok")} declared={p.get("declared")}', stream=s)

            f_ = r.get('test_synth_fail.py', {})
            check('a failing fixture is FAIL, not CRASH', f_.get('verdict') == 'FAIL',
                  f'{f_.get("verdict")} {f_.get("note")}', stream=s)
            check('and its failed check is counted', f_.get('fail') == 1,
                  str(f_.get('fail')), stream=s)

            c = r.get('test_synth_crash.py', {})
            check('a crashing fixture is CRASH, not FAIL', c.get('verdict') == 'CRASH',
                  f'{c.get("verdict")} {c.get("note")}', stream=s)
            check('a crash report prints the tail of that fixture output',
                  CRASH_MARKER in table, 'cause is invisible without re-running it', stream=s)

            sh = r.get('test_synth_short.py', {})
            check('a partial run is not reported as a small clean run',
                  sh.get('verdict') == 'FAIL' and sh.get('evaluated') == 2
                  and sh.get('declared') == 9,
                  f'{sh.get("verdict")} {sh.get("evaluated")}/{sh.get("declared")}', stream=s)

            si = r.get('test_synth_silent.py', {})
            check('a nonzero exit with no FAIL line is CRASH, not a pass',
                  si.get('verdict') == 'CRASH', f'{si.get("verdict")} rc={si.get("rc")}',
                  stream=s)

            h = r.get('test_synth_hang.py', {})
            check('a hanging fixture is TIMEOUT, not ok and not FAIL',
                  h.get('verdict') == 'TIMEOUT', f'{h.get("verdict")} {h.get("note")}', stream=s)
            check('the hang is cut off at the timeout, not left running',
                  isinstance(h.get('secs'), float) and h['secs'] < SELF_TIMEOUT + 5,
                  f'{h.get("secs")}s', stream=s)
            check('the hung fixture ran in its OWN process group',
                  isinstance(h.get('pgid'), int) and h['pgid'] > 0
                  and h['pgid'] != os.getpgrp(),
                  f'pgid={h.get("pgid")} runner={os.getpgrp()}', stream=s)
            if grandchild is None:
                check("a hung fixture's children do not outlive the runner", False,
                      'the hang fixture never recorded a child pid', stream=s)
            else:
                deadline = time.time() + 3
                while alive(grandchild) and time.time() < deadline:
                    time.sleep(0.05)
                check("a hung fixture's children do not outlive the runner",
                      not alive(grandchild), f'pid {grandchild} survived the kill', stream=s)

            check('the runner exits nonzero when anything fails, times out or crashes',
                  overall_exit(results) != 0, stream=s)
            check('the runner exits zero when every fixture passes',
                  overall_exit([x for x in results if x['verdict'] == 'ok']) == 0, stream=s)
            check('an empty run is a failure, not a silent pass',
                  overall_exit([]) != 0, stream=s)
        finally:
            if grandchild is not None and alive(grandchild):
                try:
                    os.kill(grandchild, signal.SIGKILL)
                except OSError:
                    pass
    return len(FAILS) == before


# ------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description='Run every test_*.py fixture with a timeout.')
    ap.add_argument('dirs', nargs='*', help='extra directories to search for test_*.py')
    ap.add_argument('--timeout', type=float, default=30.0, help='per-file seconds (default 30)')
    ap.add_argument('--json', action='store_true', help='machine-readable output on stdout')
    ap.add_argument('--no-self-test', action='store_true', help='skip the runner self-test')
    ap.add_argument('--self-test-only', action='store_true', help='prove the runner, run no suite')
    a = ap.parse_args()

    # In --json mode stdout belongs to the JSON, so the human lines go to stderr.
    s = sys.stderr if a.json else sys.stdout

    if not a.no_self_test:
        if not self_test(stream=s):
            print(f'\n{len(FAILS)} FAILURES in the runner itself — the gate is not trustworthy, '
                  f'suite NOT run', file=s)
            sys.exit(1)
        print('  runner self-test passes\n', file=s)
    if a.self_test_only:
        print('self-test only: no fixtures were run', file=s)
        sys.exit(0)

    dirs = default_dirs() + [os.path.abspath(d) for d in a.dirs]
    for d in a.dirs:
        if not os.path.isdir(d):
            print(f'  note: {d} is not a directory, skipped', file=s)
    print(f'Fixture suite  (timeout {a.timeout:g}s per file, {PY})\n', file=s)
    results = run_suite(dirs, a.timeout, progress=s)
    print('', file=s)
    if a.json:
        print(json.dumps({'python': PY, 'timeout': a.timeout,
                          'exit': overall_exit(results), 'results': results}, indent=2))
        print(render(results), file=s)
    else:
        print(render(results), file=s)
    sys.exit(overall_exit(results))


if __name__ == '__main__':
    main()
