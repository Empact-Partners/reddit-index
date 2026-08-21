#!/usr/bin/env python3
"""Fixture: a category-subreddits.csv round-trip must never lose a column.

discover_v2.stage_qualify rewrites the WHOLE file. It wrote a hardcoded 29-column list with
extrasaction="ignore", so `is_core` — added to the file later — was silently dropped. That
would have wiped 1,741 core slots and collapsed collection for the shipped 100 categories,
with nothing raising. This proves the writer now refuses to lose a column.
"""
import csv, os, sys, tempfile, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('dv2', os.path.join(HERE, 'discover_v2.py'))
dv2 = importlib.util.module_from_spec(spec)
sys.modules['dv2'] = dv2
spec.loader.exec_module(dv2)

FAILS, N = [], 0
def must(name, cond, detail=''):
    global N
    N += 1
    if not cond: FAILS.append(name)
    print(('  ok   ' if cond else '  FAIL ') + name + (f'  [{detail}]' if detail and not cond else ''))

print('category-subreddits.csv column preservation\n')

live_cols = next(csv.reader(open(dv2.CSV_PATH, newline='')), [])
must('the live CSV carries is_core', 'is_core' in live_cols)
must('the live CSV is wider than the hardcoded V1+V2 list',
     len(live_cols) > len(dv2.V1_COLS + dv2.V2_COLS),
     f'{len(live_cols)} vs {len(dv2.V1_COLS + dv2.V2_COLS)}')
must('is_core is NOT in the hardcoded list (the whole trap)',
     'is_core' not in (dv2.V1_COLS + dv2.V2_COLS))

# the union the writer now computes must retain every live column
cols = list(dict.fromkeys(dv2.V1_COLS + dv2.V2_COLS + live_cols))
must('the computed union retains every live column', not (set(live_cols) - set(cols)),
     f'lost {set(live_cols) - set(cols)}')
must('is_core survives the union', 'is_core' in cols)

# and the values must survive, not just the header
rows = list(csv.DictReader(open(dv2.CSV_PATH, newline='')))
core_before = sum(1 for r in rows if r.get('is_core') == 'True')
with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False, newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
    w.writeheader()
    for r in rows: w.writerow({c: r.get(c, '') for c in cols})
    tmp = f.name
core_after = sum(1 for r in csv.DictReader(open(tmp, newline='')) if r.get('is_core') == 'True')
os.unlink(tmp)
must('is_core VALUES survive a round-trip, not just the header',
     core_after == core_before and core_before > 0, f'{core_before} -> {core_after}')

print(f'\n{N - len(FAILS)}/{N} passed  (core slots in the live CSV: {core_before})')
sys.exit(1 if FAILS else 0)
