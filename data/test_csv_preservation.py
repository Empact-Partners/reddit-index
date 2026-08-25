#!/usr/bin/env python3
"""Incident A1: `qualify` rewrites the WHOLE category-subreddits.csv and dropped a column.

`discover_v2.stage_qualify` rebuilds the file from scratch. It wrote a hardcoded
`V1_COLS + V2_COLS` header with `extrasaction="ignore"`, which SILENTLY DROPS any column
added to the file after that function was written — and `is_core` was added later (8628130).
A single qualify run would have wiped 1,741 core slots across 527 subs, collapsed
`daily.py --core-only` for the shipped 100 categories, and then crashed select_core_subs on
a fieldname mismatch. Nothing would have raised. Fix: `data/discover_v2.py:1090`,
`cols = list(dict.fromkeys(V1_COLS + V2_COLS + existing_cols))`.

This fixture was rewritten on 2026-08-24 because the version it replaces did not test that.
Three of its six checks recomputed the union INSIDE the fixture and asserted properties of
that local variable (a superset of `live_cols` by construction, unfalsifiable as arithmetic),
and the round-trip check exercised the fixture's own csv.DictWriter. An audit reverted
:1090 to the incident line and watched it print 6/6 passed, rc 0. It also read the live
56 MB CSV, which the running pipeline rewrites — 4.24 s and a torn read away from a
spurious FAIL.

So the REAL writer is driven here: stage_qualify, everything else stubbed, over a small
synthetic CSV carrying two columns the writer knows nothing about. Every check below fails
when the line it guards is reverted; the mutations are listed in the round's report.

  python3 data/test_csv_preservation.py
"""
import csv
import importlib.util
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(HERE, 'category-subreddits.csv')
FAILS = []

# columns the writer's hardcoded lists do not contain. `is_core` is the real one from the
# incident; `zz_unknown_col` is here so the fixture stays non-vacuous even if someone later
# adds is_core to V1_COLS/V2_COLS.
EXTRA = ['is_core', 'zz_unknown_col']


def check(name, ok, detail=''):
    print(('  ok   ' if ok else '  FAIL ') + name + (f'  [{detail}]' if detail and not ok else ''))
    if not ok:
        FAILS.append(name)


def skip(name, detail=''):
    print('  skip ' + name + (f'  [{detail}]' if detail else ''))


# ─────────────────────────────────────────────────────────────────────── harness
# discover_v2's module top imports the real Reddit client (credentials + a live socket),
# instantiates a CodexFleet, and mkdirs state dirs under data/. None of that may happen in a
# fixture that runs offline beside a live pipeline, so the three imports are pre-empted in
# sys.modules and os.makedirs is neutered for the exec. Same shape as test_refetch_cache.py.

def _stub_modules():
    rc = types.ModuleType('reddit_client')

    def _forbidden(*a, **k):
        raise AssertionError('reddit_client.get called in an offline fixture')
    rc.get = _forbidden
    rc.CACHE = '/dev/null'

    cf = types.ModuleType('codex_fleet')

    class _Fleet:
        def health(self):
            raise AssertionError('fleet contacted in an offline fixture')
    cf.CodexFleet = _Fleet

    dv = types.ModuleType('discover')
    dv.VENDOR_TOKENS = set()
    dv.SHIPPED = {}
    return {'reddit_client': rc, 'codex_fleet': cf, 'discover': dv}


def fresh(tmp, name):
    """A discover_v2 bound to a throwaway dir. Never reads or writes the live CSV."""
    saved = {k: sys.modules.get(k) for k in ('reddit_client', 'codex_fleet', 'discover')}
    real_makedirs = os.makedirs
    sys.modules.update(_stub_modules())
    os.makedirs = lambda *a, **k: None
    try:
        spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, 'discover_v2.py'))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    finally:
        os.makedirs = real_makedirs
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    for attr in ('V2', 'ENUM', 'EVID', 'RULES', 'POSTURE', 'QUAL', 'CACHE', 'BODIES', 'TOPIC'):
        d = os.path.join(tmp, attr.lower())
        real_makedirs(d, exist_ok=True)
        setattr(m, attr, d)
    m.CSV_PATH = os.path.join(tmp, 'category-subreddits.csv')
    return m


def wire(m):
    """Every input stage_qualify pulls from disk or the network, stubbed to a fixed verdict.

    Only the CSV read (csv_rows) and the CSV write stay real — they are what is under test.
    """
    m.build_candidates = lambda: {}
    m.categories_meta = lambda: {}
    m.taxonomy = lambda: []
    m.probe_terms = lambda: {}
    m.evidence_tally = lambda slug: {}
    m.matcher = lambda *a, **k: None
    m.bodies_of = lambda name: []
    m.measure_v2 = lambda name: {'status': 'ok', 'subreddit_type': 'public',
                                 'subscribers': 1000, 'comments_per_hour': 2.0,
                                 'distinct_threads_in_page': 5,
                                 'measured_at': '2026-08-24T00:00:00Z'}
    m.qual_rec = lambda name: {'alive_n14': 9, 'alive_ppw': 4.5, 'titles': []}
    m.posture_verdict = lambda name: {'posture_v2': 'allow', 'vendor_v2': False}
    m.vendor_of = lambda name, verdict: False
    m.topicality_of = lambda slug, name: 0.9
    m.topicality_fill = lambda pairs, names: None

    def _no_rescue(cands=None):
        raise AssertionError('stage_rescue reached: a stub returned a null posture')
    m.stage_rescue = _no_rescue
    return m


SPEC = [('crm', 'salesforce', 'True', 'True', 'keep-a'),
        ('crm', 'CRMSoftware', 'True', 'False', 'keep-b'),
        ('vpn', 'VPNTorrents', 'False', 'True', 'keep-c')]


def seed(m):
    """A small CSV shaped like the live one BEFORE v2: the v1 columns, plus the extras.

    Deliberately missing V2_COLS. The live file grew that way (v1 columns, then `is_core`,
    then the v2 columns qualify adds), so the writer has to both ADD what it knows and KEEP
    what it does not.
    """
    cols = list(m.V1_COLS) + EXTRA
    with open(m.CSV_PATH, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for slug, sub, scoring, core, zz in SPEC:
            r = {c: '' for c in cols}
            r.update(category='Cat ' + slug, category_slug=slug, subreddit=sub, status='ok',
                     subscribers='1000', rule_posture='permissive', posture_source='v1',
                     is_vendor_sub='False', scorable='True', is_scoring=scoring,
                     is_core=core, zz_unknown_col=zz)
            w.writerow(r)
    return {sub: {'is_core': core, 'zz_unknown_col': zz} for _, sub, _, core, zz in SPEC}


def quiet(fn, *a, **k):
    """Run with stdout swallowed — stage_qualify prints a summary we do not want here."""
    out, sys.stdout = sys.stdout, open(os.devnull, 'w')
    try:
        return fn(*a, **k)
    finally:
        sys.stdout.close()
        sys.stdout = out


print('category-subreddits.csv column preservation\n')

# ── 1. the REAL writer, over a CSV carrying columns it has never heard of ───────────
with tempfile.TemporaryDirectory() as tmp:
    m = wire(fresh(tmp, 'dv2_write'))
    want = seed(m)
    before = open(m.CSV_PATH, 'rb').read()

    raised = None
    try:
        quiet(m.stage_qualify)
    except SystemExit as e:                 # the writer's own refuse-to-drop guard
        raised = str(e) or 'SystemExit'

    header = next(csv.reader(open(m.CSV_PATH, newline='')), [])
    rows = list(csv.DictReader(open(m.CSV_PATH, newline='')))
    # the writer stamps run_id_v2 on every row; the seeded file has it empty. This is how we
    # know the file on disk is the writer's output and not the untouched input — without it
    # a writer that refuses to write leaves a file that still passes the checks below.
    rewrote = bool(rows) and all(r.get('run_id_v2') == m.RUN_ID_V2 for r in rows)

    check('stage_qualify rewrote the CSV', rewrote,
          f'raised={raised}' if raised else 'run_id_v2 not stamped')
    check('the writer keeps columns it does not know about',
          rewrote and not (set(EXTRA) - set(header)),
          'no write happened' if not rewrote
          else f'header missing {sorted(set(EXTRA) - set(header))}')
    got = {r['subreddit']: {c: r.get(c) for c in EXTRA} for r in rows}
    check('and their VALUES, not just the header', rewrote and got == want,
          'no write happened' if not rewrote else f'{got} != {want}')
    check('no column is duplicated in the header', len(header) == len(set(header)),
          f'{[c for c in header if header.count(c) > 1]}')
    check('every writer-known column is still there',
          not (set(m.V1_COLS) | set(m.V2_COLS)) - set(header),
          f'missing {sorted((set(m.V1_COLS) | set(m.V2_COLS)) - set(header))}')

    bak = os.path.join(m.V2, 'category-subreddits.v1.bak.csv')
    check('the pre-write file is backed up before it is replaced',
          os.path.exists(bak) and open(bak, 'rb').read() == before,
          'no backup' if not os.path.exists(bak) else 'backup does not match the input')

# ── 2. --dry-run must not touch the file an operator is inspecting ────────────────
with tempfile.TemporaryDirectory() as tmp:
    m = wire(fresh(tmp, 'dv2_dry'))
    seed(m)
    before = open(m.CSV_PATH, 'rb').read()
    quiet(m.stage_qualify, True)
    check('a dry run writes nothing at all', open(m.CSV_PATH, 'rb').read() == before)

# ── 3. the call site: the stage the pipeline actually invokes ─────────────────────
# A tested writer nobody calls is not a guard. run_discovery_all.py / run_discovery_safe.py
# shell out to `discover_v2.py --stage qualify`, so the dispatch is part of the contract.
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp, 'dv2_cli')
    calls = []
    m.stage_qualify = lambda dry_run=False: calls.append(dry_run)
    argv = sys.argv
    try:
        sys.argv = ['discover_v2.py', '--stage', 'qualify']
        m.main()
        sys.argv = ['discover_v2.py', '--stage', 'qualify', '--dry-run']
        m.main()
    finally:
        sys.argv = argv
    check('--stage qualify runs the writer under test', len(calls) == 2, str(calls))
    check('--dry-run reaches it, and a plain run does not', calls == [False, True], str(calls))

# ── 4. the live file, read defensively: one line, and never a green check we could not
#      evaluate. The pipeline rewrites this file; a torn or absent read is a skip.
try:
    with open(LIVE, newline='') as f:
        live_header = next(csv.reader(f), [])
except OSError as e:
    live_header = None
    skip('the live CSV still carries is_core', f'unreadable: {e}')
if live_header is not None:
    if len(live_header) < len(m.V1_COLS):
        skip('the live CSV still carries is_core',
             f'{os.path.basename(LIVE)} header looks torn: {len(live_header)} columns')
    else:
        check('the live CSV still carries is_core', 'is_core' in live_header,
              f'{len(live_header)} columns, no is_core')

print()
if FAILS:
    print(f'{len(FAILS)} FAILURES')
    sys.exit(1)
print('all column-preservation checks pass')
