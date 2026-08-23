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

def resolve_all():
    """Every input domain -> the brand slug the index actually holds it under.

    Two arms, because one is not enough: by domain, then by the slug the roster row would
    generate (abacum.io dedupes onto the existing abacum). Both counts() and split() must use
    THIS, or they disagree — counts() used to cover only source='roster-import-2026-08'
    brands, so a never-replied company that resolved onto a brand the index already held
    under another source read as zero. CapCut, at 1,843 mentions, was filed as
    'zero_mentions'."""
    import sys as _sys
    _sys.path.insert(0, HERE)
    from gen_brands import slugify as _slugify
    bydom = gaz_slug_by_domain()
    all_slugs = {r['slug'] for r in csv.DictReader(open(os.path.join(HERE, 'brands.csv')))}
    roster_by_dom = {r['domain']: r for r in json.load(open(f'{RI}/roster.json'))}
    out = {}
    for dom in list(roster_by_dom) + already_in():
        slug = bydom.get(dom)
        if slug is None:
            r = roster_by_dom.get(dom)
            if r:
                cand = _slugify(r.get('company') or dom.split('.')[0], dom)
                if cand in all_slugs:
                    slug = cand
        out[dom] = slug
    return out


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
    slugs = sorted(set(ours) | {s for s in resolve_all().values() if s})
    with db.connect() as cx, cx.cursor() as cur:
        cur.execute("""
            SELECT b.slug, count(m.doc_id) AS mentions,
                   count(*) FILTER (WHERE ms.label IN (1,2)) AS n_op
            FROM brands b
            LEFT JOIN mentions m ON m.brand_id = b.id
            LEFT JOIN mention_sentiment ms ON ms.brand_id = m.brand_id
                 AND ms.doc_id = m.doc_id
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
    resolved = resolve_all()
    mapping = {m['domain']: m for m in json.load(open(f'{RI}/mapping.json'))}
    dead = set(json.load(open(f'{RI}/g4_dead.json'))) if os.path.exists(f'{RI}/g4_dead.json') else set()
    roster = [r['domain'] for r in json.load(open(f'{RI}/roster.json'))]
    inx = already_in()

    # Resolution lives in resolve_all(), which counts() also uses. A company can be in the
    # gazetteer under a brand slug whose domain list does not carry THIS domain variant —
    # abacum.io deduped onto the existing `abacum` (abacum.ai). One company, one brand row,
    # which is correct. Resolving by slug as well as by domain stops 144 such rows reading as
    # a seeding gap when nothing is missing.
    def bucket(dom):
        slug = resolved.get(dom)
        c = counts_.get(slug or '', {'mentions': 0, 'n_op': 0})
        if dom in dead: return 'g4_dead', c
        if slug is None:
            m = mapping.get(dom, {})
            return ('unmapped_new_category' if not m.get('category_slug')
                    else 'assigned_but_unseeded'), c
        # >=5 mentions AND >=1 opinionated. The opinionated arm is not a refinement, it is
        # the condition for a score EXISTING: the Love Score is computed over opinionated
        # mentions alone, so a company with 40 neutral mentions and no opinion renders a
        # dash. On the first build 41 companies passed the 5-mention bar with zero opinion,
        # and an email promising "your Reddit score" would have linked a page showing a dash
        # to the person it is about.
        if c['mentions'] >= 5 and c['n_op'] >= 1: return 'wave2_emailable', c
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
