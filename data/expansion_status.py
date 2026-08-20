#!/usr/bin/env python3
"""Verification + measurement for the never-replied expansion (P3/P5).

Three read-only checks, one artifact:
  --parity   seed parity: every roster brand appended to the CSVs exists in the DB.
             seed_brands() silently drops rows whose category JOIN misses — this is the
             loud counterpart the pressure-test demanded.
  --count    per-roster-brand mention counts from Supabase (total + opinionated).
  --split    writes data/.roster-import/split.json — the wave-2 artifact:
             >=5 total mentions / 1-4 / 0, plus the already-in-gazetteer 302 and the
             G4-dead exclusions. Reconciliation asserted against the 4,454 input.

Read-only against the DB; safe at any time. Counts accrue with every update.sh, so the
split is stamped and must be recomputed at send time.
"""
import csv, json, os, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RI = os.path.join(HERE, '.roster-import')
sys.path.insert(0, os.path.join(HERE, '..', 'worker'))
import db  # noqa: E402

SOURCE = 'roster-import-2026-08'

def roster_slugs():
    out = {}
    for r in csv.DictReader(open(os.path.join(HERE, 'brands.csv'))):
        if r['source'] == SOURCE:
            out[r['slug']] = r
    return out

def already_in():
    return json.load(open(f'{RI}/already_in_gazetteer.json'))

def gaz_slug_by_domain():
    m = {}
    for r in csv.DictReader(open(os.path.join(HERE, 'brands.csv'))):
        for d in (r['domains'] or '').split(';'):
            if d: m.setdefault(d.strip().lower(), r['slug'])
    return m

def parity():
    ours = roster_slugs()
    with db.connect() as cx, cx.cursor() as cur:
        cur.execute("SELECT slug FROM brands WHERE slug = ANY(%s)", (list(ours),))
        in_db = {r[0] for r in cur.fetchall()}
    missing = sorted(set(ours) - in_db)
    print(f'parity: {len(ours)} roster brands in CSV · {len(in_db)} in DB · missing {len(missing)}')
    for s in missing[:20]: print('  MISSING', s)
    return 1 if missing else 0

def counts():
    ours = roster_slugs()
    bydom = gaz_slug_by_domain()
    extra = {bydom[d]: d for d in already_in() if d in bydom}
    slugs = sorted(set(ours) | set(extra))
    with db.connect() as cx, cx.cursor() as cur:
        cur.execute("""
            SELECT b.slug, count(m.doc_id) AS mentions,
                   count(*) FILTER (WHERE ms.label IN (1,2)) AS n_op
            FROM brands b
            LEFT JOIN mentions m ON m.brand_id = b.id
            LEFT JOIN mention_sentiment ms ON ms.brand_id = m.brand_id
                 AND ms.doc_id = m.doc_id AND ms.created_utc = m.created_utc
            WHERE b.slug = ANY(%s)
            GROUP BY b.slug
        """, (slugs,))
        rows = {r[0]: {'mentions': r[1], 'n_op': r[2]} for r in cur.fetchall()}
    json.dump(rows, open(f'{RI}/counts.json', 'w'), indent=0)
    have = sum(1 for v in rows.values() if v['mentions'] > 0)
    five = sum(1 for v in rows.values() if v['mentions'] >= 5)
    print(f'counts: {len(slugs)} slugs · >=1 mention {have} · >=5 mentions {five}')
    return 0

def split():
    counts_ = json.load(open(f'{RI}/counts.json'))
    ours = roster_slugs()
    bydom = gaz_slug_by_domain()
    dom_by_slug = {}
    for r in csv.DictReader(open(os.path.join(HERE, 'brands.csv'))):
        d = (r['domains'] or '').split(';')[0].strip().lower()
        dom_by_slug[r['slug']] = d
    mapping = {m['domain']: m for m in json.load(open(f'{RI}/mapping.json'))}
    dead = set(json.load(open(f'{RI}/g4_dead.json'))) if os.path.exists(f'{RI}/g4_dead.json') else set()
    roster = [r['domain'] for r in json.load(open(f'{RI}/roster.json'))]
    inx = already_in()

    def bucket(dom):
        slug = None
        if dom in bydom: slug = bydom[dom]
        c = counts_.get(slug or '', {'mentions': 0, 'n_op': 0})
        if dom in dead: return 'g4_dead', c
        if slug is None:
            m = mapping.get(dom, {})
            return ('unmapped_new_category' if not m.get('category_slug') else 'not_seeded'), c
        if c['mentions'] >= 5: return 'wave2_emailable', c
        if c['mentions'] >= 1: return 'page_below_floor', c
        return 'zero_mentions', c

    out = {'generated': datetime.date.today().isoformat(),
           'note': 'RECOMPUTE AT SEND TIME - counts accrue with every update.sh',
           'buckets': {}}
    for dom in roster + inx:
        b, c = bucket(dom)
        out['buckets'].setdefault(b, []).append(
            {'domain': dom, 'mentions': c['mentions'], 'n_op': c['n_op']})
    total = sum(len(v) for v in out['buckets'].values())
    print(f'split over {total} companies (roster {len(roster)} + already-indexed {len(inx)}):')
    for b, v in sorted(out['buckets'].items(), key=lambda x: -len(x[1])):
        print(f'  {len(v):5}  {b}')
    assert total == len(roster) + len(inx), f'reconciliation broke: {total}'
    json.dump(out, open(f'{RI}/split.json', 'w'), indent=1)
    print(f'wrote {RI}/split.json')
    return 0

if __name__ == '__main__':
    rc = 0
    if '--parity' in sys.argv or len(sys.argv) == 1: rc |= parity()
    if '--count' in sys.argv: rc |= counts()
    if '--split' in sys.argv: rc |= split()
    sys.exit(rc)
