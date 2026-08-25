#!/usr/bin/env python3
"""A scoped enumerate run must not delete the categories it was not asked about.

`enumerate_brands.py` rebuilds its seed CSV from `rows`, which comes from `cats`, which
`--only` narrows. So `--expand --only <51 slugs>` would have rewritten
`data/brand-seed-expand.csv` with only those 51 categories and destroyed the other 100
categories' 4,298 rows plus 1,062 imported ones — unattended, in the middle of the night.

Exactly the shape of the is_core wipe in discover_v2: a scoped run rewriting a whole-file
artifact. That one was caught by a fixture, so this one gets a fixture too.

Two levels, because a guard that is TESTED but not WIRED is a guard that is gone. An audit
replaced the two CALL SITES in main() — `carried = carry_forward_rows(...)` with an empty
list, and `assert_no_shrink(...)` with `pass` — and the helper-level checks below all stayed
green while the production write path was defenceless. So the second half of this file drives
the REAL phase-3 write path of enumerate_brands.py, on a copy of the module in a tempdir with
its own inputs, and asserts the behaviour: rows the run does not own survive the write, and a
write that would drop them is refused with a nonzero exit and no promoted temp file.

Third level: the MESSAGE, in the words the guard actually renders. Two checks here used to
assert a bare digit — `'2' in str(e)` and `'3' in str(err.code)`. An auditor stripped the count
out of assert_no_shrink's message ("would drop N rows" -> "would drop some rows") and both
stayed green: str(e) embeds the seed CSV path, and this machine's tempdir
(/var/folders/m1/1tzgpn_n2h54c7v5zs81h07h0000gn/T) already contains a "2". The second was worse
— it passed 1 run in 25, whenever the random 8-character tempdir suffix happened to contain a
"3", and on that run the whole fixture exited 0 and the mutation escaped. Both now assert the
count together with its surrounding words, so no path, filename or timestamp can satisfy them.
Checks that only said "not in" or "all(...)" over a list that could legally be empty were
tightened the same way: an empty result must not read as a pass.

Nothing here touches data/brand-seed-expand.csv — the live pipeline is writing it.

  python3 data/test_seed_csv_preservation.py
"""
import contextlib
import csv
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []


def check(name, ok, detail=''):
    print(('  ok   ' if ok else '  FAIL ') + name + (f'  [{detail}]' if detail and not ok else ''))
    if not ok:
        FAILS.append(name)


def load(src_dir=HERE, tag='enum_brands'):
    """Import without running module-level fleet setup that needs a live worker.

    src_dir is where the module is imported FROM, so a tempdir copy resolves its own
    HERE/REPO and writes its seed CSV inside the tempdir, never over the live one.
    """
    spec = importlib.util.spec_from_file_location(tag,
                                                  os.path.join(src_dir, 'enumerate_brands.py'))
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
    check('does not carry rows for the touched category',
          bool(cats) and 'crm' not in cats, str(cats))
    check('carried rows keep every column',
          bool(carried) and all(len(r) == len(m.SEED_COLS) for r in carried))
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
        check('says how many rows would be lost',
              'would drop 2 rows for categories this run did not touch' in str(e), str(e))
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


# ── the wiring: drive the REAL write path, not the helpers ──────────────────────────
#
# Everything above passes with both call sites in main() deleted. What follows runs
# enumerate_brands.main() itself, in --expand --only mode, over a copy of the module in a
# tempdir. Phase 3 only: no fleet job is ever submitted, and resolve_domain is stubbed, so
# this is offline (no DNS) and touches no live file.

BRANDS_COLS = ['brand', 'slug', 'primary_category_slug', 'also_in_category_slugs', 'aliases',
               'ambiguity_class', 'ambiguity_note', 'domains', 'stop_contexts',
               'bare_disabled_forms', 'source']


def stage(tmp, prior_rows, enumerated):
    """A self-contained data/ dir: the module copy plus every input phase 3 reads.

    prior_rows: (brand, category) pairs already in brand-seed-expand.csv before the run.
    enumerated: {slug: [brand names]} — what the fleet "returned" for the touched categories.
    """
    d = os.path.join(tmp, 'data')
    os.makedirs(d)
    shutil.copy(os.path.join(HERE, 'enumerate_brands.py'),
                os.path.join(d, 'enumerate_brands.py'))

    with open(os.path.join(d, 'taxonomy-100.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['slug', 'category'])
        for slug in ('crm', 'vpn', 'voice-ai'):
            w.writerow([slug, slug.upper()])

    # one pre-existing brand, in a category this run will NOT touch, so it cannot collide
    with open(os.path.join(d, 'brands.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(BRANDS_COLS)
        w.writerow(['Knownbrand', 'knownbrand', 'vpn', '', '', 'low', '',
                    'knownbrand.example', '', '', 'seed'])

    write(os.path.join(d, 'brand-seed-expand.csv'), prior_rows)

    run = os.path.join(d, '.brand-expand')
    os.makedirs(run, exist_ok=True)
    for slug, names in enumerated.items():
        json.dump([{'name': n, 'domains': [f'{n.lower()}.example'], 'aliases': [],
                    'ambiguity': 'low', 'stop_contexts': [], 'note': ''} for n in names],
                  open(os.path.join(run, f'out_{slug}.json'), 'w'))
    return d


def drive(d, only, carry_stub=None):
    """Run phase 3 of the real main() over the staged dir. Returns (exit_object, module)."""
    mod = load(d, tag='enum_copy_' + os.path.basename(os.path.dirname(d)))
    if os.path.abspath(mod.HERE) != os.path.abspath(d):
        raise SystemExit(f'harness unsafe: module HERE is {mod.HERE}, not the tempdir')
    mod.resolve_domain = lambda dom: True          # G4 without DNS
    if carry_stub is not None:
        mod.carry_forward_rows = carry_stub
    argv = sys.argv
    sys.argv = ['enumerate_brands.py', '--expand', '--only', only, '--phase', '3']
    try:
        # main() is chatty; its progress prints would drown the check lines
        with contextlib.redirect_stdout(io.StringIO()):
            return mod.main(), mod
    finally:
        sys.argv = argv


def seed_pairs(fp):
    return sorted((r['brand'], r['primary_category_slug']) for r in csv.DictReader(open(fp)))


prior = [('Alpha', 'crm'), ('Gamma', 'vpn'), ('Delta', 'voice-ai'), ('Eps', 'vpn')]

# 1. the real run: a scoped --only crm rebuild must leave vpn and voice-ai standing
with tempfile.TemporaryDirectory() as tmp:
    d = stage(tmp, prior, {'crm': ['Zorptastic', 'Quibbleflux']})
    out = os.path.join(d, 'brand-seed-expand.csv')
    rc = err = None
    try:
        rc, _ = drive(d, 'crm')
    except SystemExit as e:
        err = e
    check('a scoped --only run completes its write', err is None and rc == 0,
          f'rc={rc} exit={err}')
    after = seed_pairs(out)
    check('untouched categories survive the real write path',
          [p for p in after if p[1] != 'crm']
          == sorted([p for p in prior if p[1] != 'crm']), str(after))
    check('the run still writes the categories it does own',
          ('Zorptastic', 'crm') in after and ('Quibbleflux', 'crm') in after, str(after))
    check('the old rows of the touched category are replaced, not accumulated',
          ('Alpha', 'crm') not in after, str(after))
    check('no temp file is left behind', not os.path.exists(out + '.tmp'))

# 2. the belt: with carry-forward neutralised, the shrink guard must stop the write.
#    This is the mutation the audit made — the call site returning nothing — and the write
#    path has to refuse it rather than promote a file missing 3 rows it does not own.
with tempfile.TemporaryDirectory() as tmp:
    d = stage(tmp, prior, {'crm': ['Zorptastic', 'Quibbleflux']})
    out = os.path.join(d, 'brand-seed-expand.csv')
    before = open(out).read()
    rc = err = None
    try:
        rc, _ = drive(d, 'crm', carry_stub=lambda out_fp, touched: [])
    except SystemExit as e:
        err = e
    check('a write that would drop untouched rows exits nonzero',
          isinstance(err, SystemExit) and err.code not in (0, None)
          and str(err.code).startswith(f'refusing to write {out}:'),
          f'rc={rc} exit={err!r}')
    check('and says how many rows it refused to drop',
          err is not None
          and 'would drop 3 rows for categories this run did not touch' in str(err.code),
          str(err.code if err else None))
    check('the previous seed CSV is left exactly as it was', open(out).read() == before)
    check('the refused temp file is cleaned up', not os.path.exists(out + '.tmp'))

# 3. a full run (no --only) legitimately rewrites everything, and must not be blocked
with tempfile.TemporaryDirectory() as tmp:
    d = stage(tmp, prior, {'crm': ['Zorptastic'], 'vpn': ['Blorbtool'], 'voice-ai': ['Vexovox']})
    out = os.path.join(d, 'brand-seed-expand.csv')
    rc = err = None
    try:
        rc, _ = drive(d, 'crm,vpn,voice-ai')
    except SystemExit as e:
        err = e
    check('a full run is allowed to replace the whole file', err is None and rc == 0,
          f'rc={rc} exit={err}')
    check('a full run keeps only what it enumerated',
          seed_pairs(out) == sorted([('Zorptastic', 'crm'), ('Blorbtool', 'vpn'),
                                     ('Vexovox', 'voice-ai')]), str(seed_pairs(out)))

# the live file: the real invariant, stated in real numbers. Read-only, and never asserted
# against — the pipeline is writing it right now.
live = os.path.join(HERE, 'brand-seed-expand.csv')
if os.path.exists(live):
    try:
        rows = list(csv.DictReader(open(live)))
        cats = {r['primary_category_slug'] for r in rows}
        print(f'\n  live brand-seed-expand.csv: {len(rows)} rows across {len(cats)} categories')
    except Exception as e:
        print(f'\n  live brand-seed-expand.csv unreadable right now ({e}) — not a failure')

print()
if FAILS:
    print(f'{len(FAILS)} FAILURES')
    sys.exit(1)
print('all seed preservation checks pass')
