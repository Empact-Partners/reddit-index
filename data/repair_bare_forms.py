#!/usr/bin/env python3
"""Repair the bare-form pollution found 2026-08-21.

13 imported brands entered with a live bare form that should never have matched: 11 whose
name is a plural English word (/usr/share/dict/words ships singulars, so the guard passed
"things" and "cats" through) and 2 whose name IS one of their own category's nouns, which
lets resolve.py's HOSTILE corroboration rule fire on itself.

Both gaps are fixed in import_roster.py with fixtures. This repairs what already landed:
  1. bare_disabled=True on the offending surface form in brand-aliases.csv
  2. DELETE the mentions whose matched_form is that bare token

Only bare-token mentions are removed. A mention matched via a qualified form ("Things 3",
"culturedcode.com") is real evidence and stays.

  python3 data/repair_bare_forms.py --dry-run
  python3 data/repair_bare_forms.py --apply
"""
import csv, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'worker'))
import db  # noqa: E402

risk = json.load(open(f'{HERE}/.roster-import/bare_risk.json'))
SLUGS = risk['word'] + risk['noun']
names = {r['slug']: r['brand'].lower()
         for r in csv.DictReader(open(f'{HERE}/brands.csv')) if r['slug'] in set(SLUGS)}
APPLY = '--apply' in sys.argv

# ---- 1. the alias file
rows = list(csv.DictReader(open(f'{HERE}/brand-aliases.csv')))
cols = list(rows[0].keys())
flipped = 0
for r in rows:
    if r['brand_slug'] in names and r['alias'].lower() == names[r['brand_slug']]:
        if r['bare_disabled'] != 'True':
            r['bare_disabled'] = 'True'; flipped += 1
print(f'brand-aliases.csv: {flipped} bare forms to disable')
if APPLY and flipped:
    with open(f'{HERE}/brand-aliases.csv.tmp', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator='\n')
        w.writeheader(); w.writerows(rows)
    os.replace(f'{HERE}/brand-aliases.csv.tmp', f'{HERE}/brand-aliases.csv')
    print('  written')

# ---- 2. the false mentions
with db.connect() as cx, cx.cursor() as cur:
    total = 0
    for s in SLUGS:
        cur.execute("""SELECT count(*) FROM mentions m JOIN brands b ON b.id = m.brand_id
                       WHERE b.slug = %s AND lower(m.matched_form) = %s""", (s, names[s]))
        n = cur.fetchone()[0]
        if not n: continue
        total += n
        print(f'  {s:14} bare {names[s]!r:14} {n:5} false mentions')
        if APPLY:
            cur.execute("""DELETE FROM mention_sentiment ms USING mentions m, brands b
                           WHERE ms.brand_id = m.brand_id AND ms.doc_id = m.doc_id
                             AND b.id = m.brand_id AND b.slug = %s
                             AND lower(m.matched_form) = %s""", (s, names[s]))
            cur.execute("""DELETE FROM mentions m USING brands b
                           WHERE b.id = m.brand_id AND b.slug = %s
                             AND lower(m.matched_form) = %s""", (s, names[s]))
    if APPLY:
        cx.commit(); print(f'\nDELETED {total} false mentions (+ their sentiment rows)')
    else:
        print(f'\n{total} false mentions would be deleted (dry run)')
        cx.rollback()
