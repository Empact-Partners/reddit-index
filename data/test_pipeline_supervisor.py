#!/usr/bin/env python3
"""Prove the supervisor's safety properties, since the whole point of it is the case where
nobody is watching.

The 2026-08-21 OOM came from a restart loop with no cap. A supervisor is the same shape as
that runaway unless four things hold, so each is asserted here rather than assumed:

  1. it never starts work while a lane is alive
  2. the restart cap is enforced, and survives the process dying (state is on disk)
  3. it resumes at the right stage, from the log rather than from a guess
  4. it stops when the work is done

  python3 data/test_pipeline_supervisor.py
"""
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []


def check(name, ok, detail=''):
    print(('  ok   ' if ok else '  FAIL ') + name + (f'  [{detail}]' if detail and not ok else ''))
    if not ok:
        FAILS.append(name)


def fresh(tmp):
    """A supervisor module bound to a throwaway state dir, so tests cannot touch the real run."""
    spec = importlib.util.spec_from_file_location(f'sup_{os.path.basename(tmp)}',
                                                  os.path.join(HERE, 'pipeline_supervisor.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.PDIR = tmp
    m.LOG = os.path.join(tmp, 'pipeline.log')
    m.STATE = os.path.join(tmp, 'state.json')
    m.LEGACY = os.path.join(tmp, 'nonexistent.log')
    m.COOLDOWN_S = 0
    m.POLL_S = 0
    # append, never truncate: reusing a dir is how "a revived supervisor" is simulated, and
    # wiping the log there would be testing a different thing entirely
    open(m.LOG, 'a').close()
    return m


print('Supervisor safety\n')

# 1. a live lane means hands off
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    started = []
    m.lane_pids = lambda: [(999, 'run_discovery_all.py')]
    m.run = lambda args, label: started.append(label) or 0
    # with a lane alive the loop must fall through to its poll sleep rather than start
    # anything. Raising out of sleep is how we observe that it got there.
    reached_sleep = []

    def trip(_):
        reached_sleep.append(True)
        raise SystemExit('slept')
    m.time.sleep = trip
    sys.argv = ['x']
    try:
        m.main()
    except SystemExit:
        pass
    check('starts nothing while a lane is alive', started == [], f'started {started}')
    check('waits on the live lane instead', reached_sleep == [True])

# 2. the cap is enforced and lives on disk
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    m.lane_pids = lambda: []
    m.gate = lambda w: True
    calls = []

    def failing(args, label):
        calls.append(label)
        return 1                      # every attempt fails, the runaway condition
    m.run = failing
    m.time.sleep = lambda s: None
    sys.argv = ['x']
    m.main()
    st = json.load(open(m.STATE))
    check('stops at the cap', st['attempts'] == m.MAX_ATTEMPTS,
          f'attempts={st["attempts"]}')
    check('records giving up', st.get('gave_up') is True)

    # the counter is on disk: a "revived" supervisor must not get a fresh budget
    m2 = fresh(tmp)          # same tmp -> same state.json
    m2.STATE = os.path.join(tmp, 'state.json')
    m2.LOG = os.path.join(tmp, 'pipeline.log')
    m2.LEGACY = os.path.join(tmp, 'nonexistent.log')
    m2.lane_pids = lambda: []
    m2.gate = lambda w: True
    after = []
    m2.run = lambda a, l: after.append(l) or 1
    m2.time.sleep = lambda s: None
    sys.argv = ['x']
    m2.main()
    check('a revived supervisor does not get a fresh budget', after == [],
          f'ran {after}')

# 3. resume stage is read from the log
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    open(m.LOG, 'w').write('=== evidence · 01:00:00 ===\n'
                           '=== candidates · 02:00:00 ===\n'
                           '=== qualify · 03:00:00 ===\n'
                           '  probe/alive 100/29658\n')
    check('resumes at the interrupted stage', m.resume_stage() == 'qualify',
          str(m.resume_stage()))
    open(m.LOG, 'a').write('=== core selection (additive) · 04:00:00 ===\n')
    check('a non-stage heading does not become a resume point',
          m.resume_stage() == 'qualify', str(m.resume_stage()))

# 4. it stops when the work is done, and skips parts already complete
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    m.lane_pids = lambda: []
    m.gate = lambda w: True
    ran = []

    def stepping(args, label):
        ran.append(label)
        marker = {'collection': 'COLLECTION COMPLETE', 'finish': 'FINISH COMPLETE'}
        text = marker.get(label.split()[0], 'DISCOVERY COMPLETE')
        open(m.LOG, 'a').write(text + '\n')
        return 0
    m.run = stepping
    m.time.sleep = lambda s: None
    sys.argv = ['x']
    rc = m.main()
    check('runs discovery, collection and finish in order',
          [r.split()[0] for r in ran] == ['discovery', 'collection', 'finish'], str(ran))
    check('exits 0 when finished', rc == 0, str(rc))
    check('only one attempt was spent', json.load(open(m.STATE))['attempts'] == 1)

    # a second supervisor over a finished run must do nothing at all
    m3 = fresh(tmp)
    m3.LOG = os.path.join(tmp, 'pipeline.log')
    m3.STATE = os.path.join(tmp, 'state.json')
    m3.LEGACY = os.path.join(tmp, 'nonexistent.log')
    m3.lane_pids = lambda: []
    again = []
    m3.run = lambda a, l: again.append(l) or 0
    m3.time.sleep = lambda s: None
    sys.argv = ['x']
    m3.main()
    check('a finished pipeline is never restarted', again == [], str(again))

    # and it stays stopped even if the log is lost, because done is also in state.json
    open(m3.LOG, 'w').close()
    m4 = fresh(tmp)
    m4.LOG = os.path.join(tmp, 'pipeline.log')
    m4.STATE = os.path.join(tmp, 'state.json')
    m4.LEGACY = os.path.join(tmp, 'nonexistent.log')
    m4.lane_pids = lambda: []
    lost = []
    m4.run = lambda a, l: lost.append(l) or 0
    m4.time.sleep = lambda s: None
    sys.argv = ['x']
    m4.main()
    check('a lost log does not restart a finished run', lost == [], str(lost))

print()
if FAILS:
    print(f'{len(FAILS)} FAILURES')
    sys.exit(1)
print('all supervisor safety checks pass')
