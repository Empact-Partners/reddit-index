#!/usr/bin/env python3
"""QA the expansion after publish. Every check is a claim the live site now makes.

  python3 data/qa_expansion.py            # all checks, exit 1 on any failure
"""
import csv, json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
RI = os.path.join(HERE, '.roster-import')
sys.path.insert(0, os.path.join(HERE, '..', 'worker'))
import db  # noqa: E402

SOURCE = 'roster-import-2026-08'
FAILS, WARNS = [], []
def check(name, ok, detail=''):
    print(('  ok   ' if ok else '  FAIL ') + name + (f'  [{detail}]' if detail and not ok else ''))
    if not ok: FAILS.append(name)
def warn(name, ok, detail=''):
    if not ok:
        print(f'  warn  {name}  [{detail}]'); WARNS.append(name)

print('Expansion QA\n')
csv_brands = {r['slug']: r for r in csv.DictReader(open(f'{HERE}/brands.csv'))}
ours = {s: r for s, r in csv_brands.items() if r['source'] == SOURCE}
cats_csv = {r['slug'] for r in csv.DictReader(open(f'{HERE}/categories.csv'))}
new_cats = {p['slug'] for p in json.load(open(f'{RI}/map/clusters.json'))['proposed']}

with db.connect() as cx, cx.cursor() as cur:
    cur.execute('SELECT slug FROM categories'); db_cats = {r[0] for r in cur.fetchall()}
    cur.execute('SELECT slug FROM brands'); db_brands = {r[0] for r in cur.fetchall()}
    cur.execute("""SELECT b.slug, count(m.doc_id) FROM brands b
                   LEFT JOIN mentions m ON m.brand_id=b.id
                   WHERE b.slug = ANY(%s) GROUP BY b.slug""", (list(ours),))
    ment = {r[0]: r[1] for r in cur.fetchall()}
    # The invariant is that a vendor sub never SCORES, not that no row exists: a sub can be
    # flagged vendor after its mentions landed (r/ios, r/vscode, r/Anthropic all carry rows
    # that predate the flag). Measured 2026-08-20: 850 such rows exist, 0 in a scoring slot.
    cur.execute("""SELECT count(*) FROM mentions m
                   JOIN subreddits s ON s.id = m.subreddit_id
                   JOIN category_subreddits cs ON cs.subreddit_id = s.id
                   WHERE s.is_vendor_sub AND cs.is_scoring""")
    vendor_scoring = cur.fetchone()[0]
    cur.execute("""SELECT count(*) FROM mentions m
                   JOIN subreddits s ON s.id = m.subreddit_id WHERE s.is_vendor_sub""")
    vendor_any = cur.fetchone()[0]
    cur.execute("""SELECT c.slug, count(DISTINCT b.slug) FROM categories c
                   JOIN brands b ON b.primary_category_id=c.id
                   WHERE c.slug = ANY(%s) GROUP BY c.slug""", (list(new_cats),))
    per_new = {r[0]: r[1] for r in cur.fetchall()}

# 1. seeding parity — the silent JOIN drop
check('every new category reached the DB', new_cats <= db_cats,
      f'missing {sorted(new_cats - db_cats)[:5]}')
check('every imported brand reached the DB', set(ours) <= db_brands,
      f'{len(set(ours) - db_brands)} missing')
check('categories.csv and DB agree on category count', cats_csv == db_cats,
      f'csv-only {len(cats_csv-db_cats)}, db-only {len(db_cats-cats_csv)}')

# 2. every new category actually has brands (an empty board is a claim of coverage)
empty = sorted(new_cats - set(per_new))
check('no new category is empty of brands', not empty, f'{len(empty)}: {empty[:5]}')
thin = sorted(s for s, n in per_new.items() if n < 4)
warn('new categories with under 4 brands (prior cannot fit)', not thin, f'{thin[:6]}')

# 3. the legal invariant — vendor subs contribute nothing, ever
check('no vendor-subreddit mention sits in a scoring slot', vendor_scoring == 0,
      f'{vendor_scoring} rows would contaminate a board')
warn('vendor-sub mentions exist in non-scoring slots (harmless, pre-flag)',
     vendor_any == 0, f'{vendor_any} rows — they score nothing')

# 4. mention coverage — how much of the import actually has Reddit presence
have = sum(1 for v in ment.values() if v > 0)
five = sum(1 for v in ment.values() if v >= 5)
print(f'\n  imported brands: {len(ours)} · with >=1 mention: {have} · with >=5: {five}')
check('the import produced some mentions at all', have > 0)

# 5. slug namespace still clean against the live route registry
overlap = cats_csv & set(csv_brands)
check('no company slug collides with a category slug', not overlap, f'{sorted(overlap)[:5]}')

print(f'\n{len(FAILS)} failures, {len(WARNS)} warnings')
sys.exit(1 if FAILS else 0)
