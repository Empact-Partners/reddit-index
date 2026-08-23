#!/usr/bin/env python3
"""A dead link must never end a multi-day run.

The whole design says so — every byte of progress is on disk, so waiting always beats
failing. Twice now that promise has been broken by the same gap: the ONE call that
authorises all the others sat outside the loop that waits for the network. It cost a
14-hour qualify run on 2026-08-23.

  python3 worker/test_reddit_client_resilience.py
"""
import os
import sys
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reddit_client as rc  # noqa: E402

FAILS = []


def check(name, ok, detail=''):
    print(('  ok   ' if ok else '  FAIL ') + name + (f'  [{detail}]' if detail and not ok else ''))
    if not ok:
        FAILS.append(name)


print('Reddit client resilience\n')

check('a token failure counts as network loss',
      rc._is_network_error(rc.TokenUnavailable('link down')))
check('TokenUnavailable is what token exhaustion raises',
      issubclass(rc.TokenUnavailable, RuntimeError))
check('a plain RuntimeError is still NOT network loss',
      not rc._is_network_error(RuntimeError('bug')))
check('an HTTP answer is not network loss',
      not rc._is_network_error(urllib.error.HTTPError('u', 401, 'Unauthorized', {}, None)))
check('DNS failure is network loss',
      rc._is_network_error(urllib.error.URLError(
          __import__('socket').gaierror(8, 'nodename nor servname provided'))))

# the structural property: the token call must be INSIDE get()'s try, or its failure
# bypasses the network-wait entirely
import inspect  # noqa: E402
src = inspect.getsource(rc.get)
try_at = src.index('\n        try:')
tok_at = src.index('_access_token()')
check('the token call sits inside get()\'s try block', tok_at > try_at,
      'it is above the try — a token failure will kill the caller')

# a token failure must be waited out, not counted against the HTTP attempt budget
calls = {'n': 0}


def boom():
    calls['n'] += 1
    raise rc.TokenUnavailable('link down')


slept = []
orig_tok, orig_sleep = rc._access_token, rc.time.sleep
rc._access_token = boom
rc.time.sleep = lambda s: slept.append(s)
try:
    rc.NET_MAX_WAIT, keep = 0.0, rc.NET_MAX_WAIT      # deadline immediately past
    out = rc.get('/r/test/about', {'raw_json': 1}, bucket='unit-test', use_cache=False)
    rc.NET_MAX_WAIT = keep
    check('a token failure returns the network sentinel, never raises',
          out == {'_err': 'network'}, str(out))
    check('it did not spend an HTTP attempt', calls['n'] >= 1)
finally:
    rc._access_token, rc.time.sleep = orig_tok, orig_sleep

print()
if FAILS:
    print(f'{len(FAILS)} FAILURES')
    sys.exit(1)
print('all resilience checks pass')
