#!/usr/bin/env python3
"""A scoped enumerate run must not delete the categories it was not asked about.

`enumerate_brands.py` rebuilds its seed CSV from `rows`, which comes from `cats`, which
`--only` narrows. So `--expand --only <51 slugs>` would have rewritten
`data/brand-seed-expand.csv` with only those 51 categories and destroyed the other 100
categories' 4,298 rows plus 1,062 imported ones — unattended, in the middle of the night.

Exactly the shape of the is_core wipe in discover_v2: a scoped run rewriting a whole-file
artifact. That one was caught by a fixture, so this one gets a fixture too.

  python3 data/test_seed_csv_preservation.py
"""
import csv
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []


def check(name, ok, detail=''):
    print(('  ok   ' if ok else '  FAIL ') + name + (f'  [{detail}]' if detail and not ok else ''))
    if not ok:
        FAILS.append(name)


def load():
    """Import without running module-level fleet setup that needs a live worker."""
    spec = importlib.util.spec_from_file_location('enum_brands',
                                                  os.path.join(HERE, 'enumerate_brands.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def write(fp, rows):
    with open(fp, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['brand', 'primary_category_slug', 'also_in_category_slugs', 'aliases',
                    'ambiguity_class', 'ambiguity_note', 'domains', 'stop_contexts',
                    'bare_disabled_forms', 'source'])
        for brand, cat in rows:
            w.writerow([brand, cat, '', '', 'low', '', f'{brand.lower()}.com', '', '', 'test'])


print('Seed CSV preservation\n')
m = load()

with tempfile.TemporaryDirectory() as tmp:
    fp = os.path.join(tmp, 'seed.csv')
    write(fp, [('Alpha', 'crm'), ('Beta', 'crm'), ('Gamma', 'vpn'), ('Delta', 'voice-ai')])

    carried = m.carry_forward_rows(fp, touched={'crm'})
    cats = sorted(r[1] for r in carried)
    check('carries rows for categories the run did not touch', cats == ['voice-ai', 'vpn'],
          str(cats))
    check('does not carry rows for the touched category', 'crm' not in cats, str(cats))
    check('carried rows keep every column',
          all(len(r) == len(m.SEED_COLS) for r in carried))
    check('carried rows keep their values',
          any(r[0] == 'Gamma' and r[6] == 'gamma.com' for r in carried), str(carried))

    check('a missing file carries nothing rather than raising',
          m.carry_forward_rows(os.path.join(tmp, 'nope.csv'), {'crm'}) == [])

    # touching everything means nothing to carry — the whole-file rewrite case, still legal
    check('a full run carries nothing',
          m.carry_forward_rows(fp, {'crm', 'vpn', 'voice-ai'}) == [])

with tempfile.TemporaryDirectory() as tmp:
    fp = os.path.join(tmp, 'seed.csv')
    tmpf = fp + '.tmp'
    write(fp, [('Alpha', 'crm'), ('Gamma', 'vpn'), ('Delta', 'voice-ai')])

    # the bug: a scoped run writing only its own category
    write(tmpf, [('Alpha2', 'crm')])
    try:
        m.assert_no_shrink(fp, tmpf, touched={'crm'})
        check('refuses a write that drops untouched categories', False, 'it allowed it')
    except SystemExit as e:
        check('refuses a write that drops untouched categories', True)
        check('says how many rows would be lost', '2' in str(e), str(e))
        check('removes the bad temp file so it cannot be promoted', not os.path.exists(tmpf))

    # the fixed behaviour: carried forward, so nothing is lost
    write(tmpf, [('Alpha2', 'crm'), ('Gamma', 'vpn'), ('Delta', 'voice-ai')])
    try:
        m.assert_no_shrink(fp, tmpf, touched={'crm'})
        check('allows a write that preserves them', True)
    except SystemExit as e:
        check('allows a write that preserves them', False, str(e))

    # growth in untouched categories is fine (a widen row, say)
    write(tmpf, [('Alpha2', 'crm'), ('Gamma', 'vpn'), ('Delta', 'voice-ai'), ('Eps', 'vpn')])
    try:
        m.assert_no_shrink(fp, tmpf, touched={'crm'})
        check('allows growth in untouched categories', True)
    except SystemExit as e:
        check('allows growth in untouched categories', False, str(e))

# the live file: the real invariant, stated in real numbers
live = os.path.join(HERE, 'brand-seed-expand.csv')
if os.path.exists(live):
    rows = list(csv.DictReader(open(live)))
    cats = {r['primary_category_slug'] for r in rows}
    print(f'\n  live brand-seed-expand.csv: {len(rows)} rows across {len(cats)} categories')

print()
if FAILS:
    print(f'{len(FAILS)} FAILURES')
    sys.exit(1)
print('all seed preservation checks pass')
