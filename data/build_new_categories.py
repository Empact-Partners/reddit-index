#!/usr/bin/env python3
"""P4: turn approved cluster proposals into live Reddit Index categories.

Runs the deterministic half of the add-a-category procedure and STOPS at each stage that
costs Reddit API time or needs a human, printing the exact command. decisions/0010 forbids
anything here from auto-firing a long collection.

Order matters and is enforced:
  1. taxonomy rows        data/taxonomy-100.csv  (append; the file may only grow)
  2. colour + icon        node scripts/gen-categories-100.mjs   (existing rows byte-frozen)
  3. TS module            pnpm gen                              (re-stamps the SHA gate)
  4. brand rosters        the cluster members become seed rows; --expand later adds the
                          competitors the fleet knows, which IS the outreach expansion
  5. subreddits           data/discover_v2.py  (six qualification bars)  [manual, API]
  6. core subs            data/select_core_subs.py --add-categories <slugs> --apply
  7. DB seed              worker/load.py --seed   + parity check
  8. history              worker/sweep.py --days 90 --only <core subs>   [manual, API]
  9. publish              worker/update.sh

Icons: gen-categories-100.mjs reads a NEW_ICONS map and throws on a missing slug, so this
writes the mapping first, choosing from lucide names not already taken.

  python3 data/build_new_categories.py --plan          # what would change, nothing written
  python3 data/build_new_categories.py --stage taxonomy
  python3 data/build_new_categories.py --stage brands
  python3 data/build_new_categories.py --next          # print the next manual command
"""
import csv, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RI = os.path.join(HERE, '.roster-import')
SOURCE = 'roster-import-2026-08'

# superseded by .roster-import/icons.json (verified against lucide's real exports)
_UNUSED_ICON_POOL = [
    'binoculars','handshake','bot','presentation','music','landmark','line-chart','megaphone',
    'cloud-cog','trending-up','star','bug-play','file-code','compass','flask-conical','dumbbell',
    'file-signature','leaf','shield-alert','heart-handshake','calculator','smile','package-search',
    'send-horizontal','bitcoin','images','umbrella','stethoscope','lock-keyhole','pie-chart',
    'blocks','tag','route','radar','users','scan-text','sprout','car','trophy','file-check',
    'brain-circuit','mic-vocal','server-cog','hotel','cloud-alert','heart','mail-warning',
    'clipboard-plus','newspaper','banknote-arrow-up','activity-square',
]

def load_clusters():
    d = json.load(open(f'{RI}/map/clusters.json'))
    return sorted(d['proposed'], key=lambda x: -len(x['members']))

def existing_categories():
    return list(csv.DictReader(open(f'{HERE}/categories.csv')))

def assign_icons(proposed, existing):
    """Read the resolved map. Every name was verified against lucide's real export list and
    against the icons the existing 100 already hold — guessing here fails the icons gate at
    build time, and ten of the first guesses collided precisely because they were guesses."""
    icons = json.load(open(f'{RI}/icons.json'))
    taken = {r['icon'] for r in existing}
    missing = [p['slug'] for p in proposed if p['slug'] not in icons]
    clash = sorted({v for v in icons.values() if v in taken})
    dupes = sorted({v for v in icons.values() if list(icons.values()).count(v) > 1})
    if missing: raise SystemExit(f'icons.json missing slugs: {missing[:5]}')
    if clash: raise SystemExit(f'icons.json collides with existing categories: {clash}')
    if dupes: raise SystemExit(f'icons.json has duplicates: {dupes}')
    return {p['slug']: icons[p['slug']] for p in proposed}

def stage_taxonomy(proposed):
    tax = list(csv.DictReader(open(f'{HERE}/taxonomy-100.csv')))
    have = {r['slug'] for r in tax}
    added = 0
    with open(f'{HERE}/taxonomy-100.csv', 'a', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        for p in proposed:
            if p['slug'] in have: continue
            w.writerow([p['category'], p['slug'], p['nouns']]); added += 1
    print(f'taxonomy: +{added} rows (now {len(tax)+added})')
    # the icon map the generator needs
    icons = assign_icons(proposed, existing_categories())
    gen = open(f'{ROOT}/scripts/gen-categories-100.mjs').read()
    block = ',\n'.join(f"  '{s}': '{i}'" for s, i in icons.items())
    if 'ROSTER_ICONS' not in gen:
        gen = gen.replace('const NEW_ICONS = {',
                          f'// added for the never-replied expansion (P4)\nconst ROSTER_ICONS = {{\n{block}\n}};\n\nconst NEW_ICONS = {{\n  ...ROSTER_ICONS,')
        open(f'{ROOT}/scripts/gen-categories-100.mjs', 'w').write(gen)
        print(f'icons: wired {len(icons)} into gen-categories-100.mjs')
    else:
        print('icons: ROSTER_ICONS already present')
    return added

def stage_brands(proposed):
    """Cluster members become gazetteer seed rows for their new category.

    Aliases are NOT drafted here — import_roster.py --merge does that for the whole roster
    once, so a member of a new category gets the same gate treatment as everyone else. This
    only records which category each member belongs to.
    """
    mp = {m['domain']: m for m in json.load(open(f'{RI}/mapping.json'))}
    n = 0
    for p in proposed:
        for dom in p['members']:
            if dom in mp:
                mp[dom]['category_slug'] = p['slug']; n += 1
    json.dump(sorted(mp.values(), key=lambda x: x['domain']),
              open(f'{RI}/mapping.json', 'w'), indent=0)
    print(f'mapping.json: {n} members assigned to their new category slug')
    print('  -> re-run: python3 data/import_roster.py && python3 data/import_roster.py --merge')
    return n

def plan(proposed):
    ex = existing_categories()
    print(f'existing categories : {len(ex)}')
    print(f'proposed            : {len(proposed)}  -> {len(ex)+len(proposed)} total')
    print(f'members to seed     : {sum(len(p["members"]) for p in proposed)}')
    icons = assign_icons(proposed, ex)
    print(f'icons free in pool  : ok ({len(icons)} assigned)')
    print('\ncolour headroom is the real limit: gen-categories throws if it cannot place a')
    print('new colour at maximin dE >= 0.030, and the current 100 already sit at 0.0373.')
    print('\nstages: taxonomy -> gen-categories -> pnpm gen -> brands -> import_roster')
    print('        -> discover_v2 [API] -> select_core_subs --add-categories -> load --seed')
    print('        -> sweep --days 90 [API] -> update.sh')

if __name__ == '__main__':
    proposed = load_clusters()
    if '--plan' in sys.argv: plan(proposed)
    elif '--stage' in sys.argv:
        st = sys.argv[sys.argv.index('--stage') + 1]
        if st == 'taxonomy': stage_taxonomy(proposed)
        elif st == 'brands': stage_brands(proposed)
        else: raise SystemExit(f'unknown stage {st}')
    else: plan(proposed)
