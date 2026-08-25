#!/usr/bin/env python3
"""A dead link must never end a multi-day run.

The whole design says so — every byte of progress is on disk, so waiting always beats
failing. Twice now that promise has been broken by the same gap: the ONE call that
authorises all the others sat outside the loop that waits for the network. It cost a
14-hour qualify run on 2026-08-23, fourteen categories in, on a phone hotspot whose DNS
dropped: "could not obtain a Reddit token after 7 attempts".

A third time it was the GUARD that lied. The structural check here took the FIRST
eight-space `try:` in get() — the cache read at ~offset 558 — and only proved
`_access_token()` appeared after it, 1,574 characters before the try it meant. Incident G2
replayed verbatim (the Request, and with it the token call, hoisted out of the network try)
printed "ok". The fixture went red four checks later only because the escaping
TokenUnavailable crashed it, and a crash is not a diagnosis.

So the invariant is now driven, not read: get() is run against a token function that always
raises, on a fake clock, and the fixture asserts what the caller actually sees — the network
sentinel, the network retry cadence, and an untouched HTTP attempt budget. The source-offset
check survives only as a supplement, anchored to the try that encloses the network call.

  python3 worker/test_reddit_client_resilience.py
"""
import contextlib
import inspect
import io
import os
import shutil
import socket
import sys
import tempfile
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reddit_client as rc  # noqa: E402

FAILS = []


def check(name, ok, detail=''):
    print(('  ok   ' if ok else '  FAIL ') + name + (f'  [{detail}]' if detail and not ok else ''))
    if not ok:
        FAILS.append(name)


class FakeClock:
    """Stands in for the `time` module inside reddit_client.

    Sleeping advances the clock instead of burning wall-time, so a 300s network
    deadline is reached in microseconds and every wait the code took is recorded.
    """

    def __init__(self, start=1_000_000.0):
        self.now = start
        self.slept = []

    def time(self):
        return self.now

    def sleep(self, s):
        self.slept.append(s)
        self.now += s


def drive_token_outage(net_max_wait, tries=3):
    """Run the REAL get() with a token function that always fails.

    Returns (outcome, token_calls, waits, log). `outcome` is get()'s return value —
    or the exception object, if one escaped get() instead of being handled, which is
    itself the incident this file exists for.
    """
    clock = FakeClock()
    calls = {'n': 0}

    def boom():
        calls['n'] += 1
        raise rc.TokenUnavailable('link down')

    saved = (rc._access_token, rc.time, rc.NET_MAX_WAIT, rc.CACHE, rc._last_call[0])
    scratch = tempfile.mkdtemp(prefix='ri-resilience-')   # never touch the live cache
    rc._access_token = boom
    rc.time = clock
    rc.NET_MAX_WAIT = net_max_wait
    rc.CACHE = scratch
    rc._last_call[0] = 0.0
    log = io.StringIO()
    try:
        with contextlib.redirect_stdout(log):
            outcome = rc.get('/r/test/about', {'raw_json': 1}, bucket='unit-test',
                             tries=tries, use_cache=False)
    except BaseException as e:                       # noqa: BLE001 — the escape IS the finding
        outcome = e
    finally:
        rc._access_token, rc.time, rc.NET_MAX_WAIT, rc.CACHE = saved[:4]
        rc._last_call[0] = saved[4]
        shutil.rmtree(scratch, ignore_errors=True)
    return outcome, calls['n'], clock.slept, log.getvalue()


def drive_dead_link_token(net_max_wait=1.0):
    """Run the REAL _access_token() with the socket layer refusing to resolve.

    Returns whatever it raised (or None if it somehow returned). Offline: urlopen is
    replaced before it is ever reached.
    """
    clock = FakeClock()

    def dead(*a, **k):
        raise socket.gaierror(8, 'nodename nor servname provided')

    saved = (rc.urllib.request.urlopen, rc.time, rc.NET_MAX_WAIT, dict(rc._token))
    rc.urllib.request.urlopen = dead
    rc.time = clock
    rc.NET_MAX_WAIT = net_max_wait
    rc._token['v'] = None
    try:
        rc._access_token()
        return None
    except BaseException as e:                       # noqa: BLE001
        return e
    finally:
        rc.urllib.request.urlopen, rc.time, rc.NET_MAX_WAIT = saved[:3]
        rc._token.clear()
        rc._token.update(saved[3])


print('Reddit client resilience\n')

# ── the classifier ──────────────────────────────────────────────────────────
check('a token failure counts as network loss',
      rc._is_network_error(rc.TokenUnavailable('link down')))
check('a plain RuntimeError is still NOT network loss',
      not rc._is_network_error(RuntimeError('bug')))
check('an HTTP answer is not network loss',
      not rc._is_network_error(urllib.error.HTTPError('u', 401, 'Unauthorized', {}, None)))
check('DNS failure is network loss',
      rc._is_network_error(urllib.error.URLError(socket.gaierror(8, 'nodename nor servname'))))

# ── what token exhaustion actually raises (driven, not asserted about a base class) ──
raised = drive_dead_link_token()
check('token exhaustion on a dead link raises TokenUnavailable',
      isinstance(raised, rc.TokenUnavailable), f'it raised {raised!r}')
check('and the classifier accepts THAT object as network loss',
      raised is not None and rc._is_network_error(raised), repr(raised))

# ── the invariant, driven through get() ─────────────────────────────────────
# A token failure must be counted as network loss and retried on the network cadence.
# NET_MAX_WAIT=300 on the fake clock lets the capped-exponential backoff run to the
# deadline; tries=3 is get()'s own default HTTP budget.
outcome, token_calls, waits, log = drive_token_outage(300.0, tries=3)

check('a token failure never escapes get()',
      not isinstance(outcome, BaseException),
      f'{type(outcome).__name__} escaped the network try: {outcome}')
check('a token failure returns the network sentinel',
      outcome == {'_err': 'network'}, repr(outcome))
check('a token failure is not charged to the HTTP attempt budget',
      outcome == {'_err': 'network'} and token_calls > 3,
      f'{token_calls} token calls against tries=3, returned {outcome!r} '
      f'({{"_err": "fail"}} means the budget was spent)')
check('a token failure waits on the network cadence, not the 2s non-network penalty',
      len(waits) > 3 and all(w >= 5 for w in waits), f'waits={waits}')
check('giving up says the link died and names the path it abandoned',
      'network down >' in log and '/r/test/about' in log and 'state is on disk' in log,
      repr(log))

# ── structural supplement ───────────────────────────────────────────────────
# Anchored to the try that ENCLOSES the network call — not the first try in get(),
# which is the cache read and is satisfied by a token call hoisted out of the network try.
src = inspect.getsource(rc.get)
net_at = src.index('urlopen(req')
net_try_at = src.rfind('\n        try:', 0, net_at)
tok_at = src.rfind('_access_token()', 0, net_at)
check("the token call sits inside the try that wraps get()'s network call",
      net_try_at != -1 and tok_at > net_try_at,
      f'network try at {net_try_at}, token call at {tok_at} — the token call is '
      f'above the network try, so its failure bypasses the network wait')

print()
if FAILS:
    print(f'{len(FAILS)} FAILURES')
    sys.exit(1)
print('all resilience checks pass')
