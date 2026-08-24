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
    m.NET_COOLDOWN_S = 0
    m.POLL_S = 0
    # NEVER let a test touch the real launchd agent: uninstall() deletes a plist, and the
    # live supervisor for the current run is behind that exact label.
    m.AGENT_PLIST = os.path.join(tmp, 'agent.plist')
    m.uninstalls = []
    m.uninstall = lambda: m.uninstalls.append(True)
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
    check('uninstalls itself after giving up', m.uninstalls == [True], str(m.uninstalls))

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
        if label.split()[0] == 'expansion':
            # the real leg signals completion with a marker file, not a log line
            open(os.path.join(m.PDIR, 'expansion_seeded'), 'w').write('{}')
            return 0
        marker = {'collection': 'COLLECTION COMPLETE', 'finish': 'FINISH COMPLETE'}
        text = marker.get(label.split()[0], 'DISCOVERY COMPLETE')
        open(m.LOG, 'a').write(text + '\n')
        return 0
    m.run = stepping
    m.time.sleep = lambda s: None
    sys.argv = ['x']
    rc = m.main()
    check('runs discovery, expansion, collection, finish in order',
          [r.split()[0] for r in ran] == ['discovery', 'expansion', 'collection', 'finish'],
          str(ran))
    check('expansion runs BEFORE collection (brands must exist before a sweep stores)',
          [r.split()[0] for r in ran].index('expansion')
          < [r.split()[0] for r in ran].index('collection'))
    check('exits 0 when finished', rc == 0, str(rc))
    check('a successful run spends no budget at all',
          json.load(open(m.STATE))['attempts'] == 0
          and json.load(open(m.STATE)).get('net_attempts', 0) == 0)
    check('uninstalls itself when the run completes', m.uninstalls == [True],
          str(m.uninstalls))

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

# 5. uninstall really removes the plist (the property decisions/0010 depends on)
with tempfile.TemporaryDirectory() as tmp:
    # a module WITHOUT the stub, so the real uninstall runs — pointed at a throwaway plist
    # and a label that does not exist, so launchctl bootout is a harmless no-op
    spec = importlib.util.spec_from_file_location(
        'sup_real', os.path.join(HERE, 'pipeline_supervisor.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.PDIR = tmp
    m.LOG = os.path.join(tmp, 'pipeline.log')
    m.AGENT_PLIST = os.path.join(tmp, 'agent.plist')
    m.AGENT_LABEL = 'com.vladshvets.test-does-not-exist'
    open(m.AGENT_PLIST, 'w').write('<plist/>')
    m.uninstall()
    check('uninstall removes the plist', not os.path.exists(m.AGENT_PLIST))
    m.uninstall()                        # idempotent: a missing plist is not an error
    check('uninstall is idempotent', True)


# 6. a flaky link must not spend the runaway budget
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    m.lane_pids = lambda: []
    m.gate = lambda w: True
    m.time.sleep = lambda s: None

    def net_fail(args, label):
        open(m.LOG, 'a').write('  network unreachable (URLError) — waiting 10s, attempt 1\n')
        return 1
    m.run = net_fail
    sys.argv = ['x']
    m.main()
    st = json.load(open(m.STATE))
    check('a network failure spends the NETWORK budget',
          st.get('net_attempts') == m.MAX_NET_ATTEMPTS, str(st.get('net_attempts')))
    check('a network failure spends NO genuine budget', st['attempts'] == 0,
          f'genuine={st["attempts"]}')
    check('it still stops at the network cap', st.get('gave_up') is True)

with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    m.lane_pids = lambda: []
    m.gate = lambda w: True
    m.time.sleep = lambda s: None

    def real_fail(args, label):
        open(m.LOG, 'a').write('Traceback (most recent call last):\nKeyError: slug\n')
        return 1
    m.run = real_fail
    sys.argv = ['x']
    m.main()
    st = json.load(open(m.STATE))
    check('a genuine failure spends the genuine budget',
          st['attempts'] == m.MAX_ATTEMPTS, str(st['attempts']))
    check('a genuine failure spends no network budget',
          st.get('net_attempts', 0) == 0, str(st.get('net_attempts')))

# a network sign from HOURS ago must not excuse a genuine failure now
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp)
    open(m.LOG, 'w').write('  network unreachable (URLError)\n' + ('filler line\n' * 200)
                           + 'Traceback (most recent call last):\nKeyError: slug\n')
    check('an old network sign does not excuse a fresh genuine failure',
          m.looked_like_network() is False)
    open(m.LOG, 'a').write('  network unreachable (URLError) — waiting 40s\n')
    check('a fresh network sign is detected', m.looked_like_network() is True)

print()
if FAILS:
    print(f'{len(FAILS)} FAILURES')
    sys.exit(1)
print('all supervisor safety checks pass')
