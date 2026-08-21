#!/usr/bin/env python3
"""Turn the new categories' expansion roster into qualified outreach candidates.

enumerate_brands --expand drafts, for each of the 51 new categories, the brands we do NOT
already hold (brands.csv is its exclusion set). Those are companies the index surfaced that
were never on any Empact list — the outreach-pool expansion.

They are candidates, not targets, until suppressed. This applies the same two-arm check the
RI-W1 campaign uses (lib_ri.is_suppressed: registrable domain AND exact folded name against
the Monday master board and the CompanyOS billing names), plus a check against every domain
Empact has already emailed, so wave 2 does not re-approach someone mid-thread.

  python3 data/qualify_expansion_roster.py
"""
import csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RI = os.path.join(HERE, '.roster-import')
OUTREACH = '/Users/vladshvets/Projects/reddit-index-outreach/scripts'
PD = '/Users/vladshvets/Projects/empact-partners/partner-development'
sys.path.insert(0, OUTREACH)

SEED = os.path.join(HERE, 'brand-seed-expand.csv')
NEW = {p['slug'] for p in json.load(open(f'{RI}/map/clusters.json'))['proposed']}

def main():
    try:
        from lib_ri import is_suppressed, registrable
    except Exception as e:
        raise SystemExit(f'cannot import lib_ri ({e}). Run the suppression build first:\n'
                         '  python3 ~/Projects/qvery/outreach/_shared/suppression/build.py --refresh all')

    # rows this expansion added, for the 51 new categories only
    rows = [r for r in csv.DictReader(open(SEED))
            if r['primary_category_slug'] in NEW and r['source'] == 'fleet-expand-2026-08']
    print(f'expansion rows in the 51 new categories: {len(rows)}')

    # everything Empact has already emailed (the acquisition universe)
    universe = set(json.load(open(f'{PD}/data/_work/never-replied/universe.json')).keys())
    # everything already in our own roster for this project
    ours = {r['domain'] for r in json.load(open(f'{RI}/roster.json'))}
    already_gaz = set(json.load(open(f'{RI}/already_in_gazetteer.json')))

    out, drops = [], {'suppressed': 0, 'already_emailed': 0, 'already_ours': 0, 'no_domain': 0}
    for r in rows:
        dom = (r['domains'] or '').split(';')[0].strip().lower()
        if not dom:
            drops['no_domain'] += 1; continue
        d = registrable(dom) or dom
        if d in ours or d in already_gaz:
            drops['already_ours'] += 1; continue
        if d in universe:
            drops['already_emailed'] += 1; continue
        why = is_suppressed(d, r['brand'])
        if why:
            drops['suppressed'] += 1; continue
        out.append({'domain': d, 'company': r['brand'],
                    'category_slug': r['primary_category_slug'],
                    'source': 'reddit-index-expansion-2026-08'})

    out.sort(key=lambda x: (x['category_slug'], x['domain']))
    fp = f'{RI}/outreach_expansion.csv'
    with open(fp, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['domain', 'company', 'category_slug', 'source'],
                           lineterminator='\n')
        w.writeheader(); w.writerows(out)
    print(f'drops: {drops}')
    print(f'NEW outreach candidates: {len(out)}  -> {fp}')
    import collections
    for c, n in collections.Counter(x['category_slug'] for x in out).most_common(12):
        print(f'   {n:4}  {c}')

if __name__ == '__main__':
    main()
