#!/usr/bin/env python3
"""Snapshot each category's publication bar BEFORE new brands land, so drift is measured.

snapshot.ts sets a category's display floor to the median opinionated-mention count across
its scored brands, clamped [3,30]. Mass-injecting thin brands drags that median DOWN, so
boards start publishing noisier rows. Not fatal (floor of 3) but it must be observed rather
than assumed — this writes the before, and --compare reads the after.
"""
import json, os, sys, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
RI = os.path.join(HERE, '.roster-import')
sys.path.insert(0, os.path.join(HERE, '..', 'worker'))
import db  # noqa: E402

OUT = os.path.join(RI, 'threshold_baseline.json')

def measure():
    with db.connect() as cx, cx.cursor() as cur:
        cur.execute("""
            SELECT c.slug, b.slug AS brand,
                   count(*) FILTER (WHERE ms.label IN (1,2)) AS n_op
            FROM categories c
            JOIN brands b ON b.primary_category_id = c.id
            LEFT JOIN mentions m ON m.brand_id = b.id
            LEFT JOIN mention_sentiment ms ON ms.brand_id = m.brand_id
                 AND ms.doc_id = m.doc_id
            GROUP BY c.slug, b.slug
        """)
        rows = cur.fetchall()
    by = {}
    for cat, brand, n_op in rows:
        if n_op and n_op > 0:
            by.setdefault(cat, []).append(n_op)
    out = {}
    for cat, ns in by.items():
        med = statistics.median(ns)
        out[cat] = {'scored_brands': len(ns), 'median_n_op': med,
                    'display_floor': max(3, min(30, int(med)))}
    return out

if '--compare' in sys.argv:
    before = json.load(open(OUT))
    after = measure()
    moved = []
    for cat, a in sorted(after.items()):
        b = before.get(cat)
        if b and b['display_floor'] != a['display_floor']:
            moved.append((cat, b['display_floor'], a['display_floor'],
                          b['scored_brands'], a['scored_brands']))
    print(f'categories whose display floor moved: {len(moved)}')
    for cat, x, y, bb, ab in moved:
        print(f'  {cat:26} floor {x:2} -> {y:2}   scored brands {bb} -> {ab}')
    if not moved:
        print('  none — no board changed its publication bar')
else:
    out = measure()
    json.dump(out, open(OUT, 'w'), indent=1)
    f = [v['display_floor'] for v in out.values()]
    print(f'baseline: {len(out)} categories with scored brands · '
          f'display floor min {min(f)} median {statistics.median(f):.0f} max {max(f)}')
    print(f'wrote {OUT}')
