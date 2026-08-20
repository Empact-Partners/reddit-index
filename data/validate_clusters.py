#!/usr/bin/env python3
"""Validate a proposed-category set BEFORE it reaches Vlad or the build.

Every check here is something that fails later and more expensively: a slug collision fails
next build at publish, a member appearing twice double-counts a leaderboard, a lost member
silently drops a prospect from wave 2. Exit 1 blocks the checkpoint.
"""
import csv, json, os, re, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
RI = os.path.join(HERE, '.roster-import')
sys.path.insert(0, HERE)
from import_roster import reserved_slugs

d = json.load(open(f'{RI}/map/clusters.json'))
proposed, unclustered = d.get('proposed', []), d.get('unclustered', [])
mapping = json.load(open(f'{RI}/mapping.json'))
unmapped = {m['domain'] for m in mapping if not m['category_slug']}
reserved = reserved_slugs()

FAILS, WARNS = [], []
def fail(m): FAILS.append(m)
def warn(m): WARNS.append(m)

# 1. slug hygiene — the publish-time build bomb
for p in proposed:
    s = p.get('slug', '')
    if not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', s):
        fail(f'slug not kebab-case: {s!r} ({p.get("category")})')
    if s in reserved:
        fail(f'slug collides with an existing category or reserved route: {s}')
dupes = [s for s, n in collections.Counter(p.get('slug') for p in proposed).items() if n > 1]
for s in dupes: fail(f'duplicate proposed slug: {s}')

# 2. membership conservation — nobody invented, nobody lost, nobody twice
seen = collections.Counter()
for p in proposed:
    for m in p.get('members', []): seen[m] += 1
for m in unclustered: seen[m] += 1
twice = [m for m, n in seen.items() if n > 1]
for m in twice[:10]: fail(f'company in two buckets: {m}')
invented = set(seen) - unmapped
lost = unmapped - set(seen)
if invented: fail(f'{len(invented)} companies not in the unmapped set: {sorted(invented)[:5]}')
if lost: fail(f'{len(lost)} unmapped companies missing from the output: {sorted(lost)[:5]}')

# 3. the >=8 member rule the prompt set
thin = [(p['slug'], len(p.get('members', []))) for p in proposed if len(p.get('members', [])) < 8]
for s, n in thin: warn(f'proposed category under the 8-member bar: {s} ({n})')

# 4. nouns present and plausible
for p in proposed:
    ns = [x for x in (p.get('nouns') or '').split(';') if x.strip()]
    if len(ns) < 3: warn(f'{p.get("slug")}: only {len(ns)} nouns (3-6 expected)')

print(f'proposed categories : {len(proposed)}')
print(f'clustered companies : {sum(len(p.get("members", [])) for p in proposed)}')
print(f'unclustered         : {len(unclustered)}')
print(f'unmapped input      : {len(unmapped)}')
print(f'conservation        : {"OK" if not invented and not lost and not twice else "BROKEN"}')
for w in WARNS[:15]: print(f'  warn  {w}')
if len(WARNS) > 15: print(f'  ... and {len(WARNS)-15} more warnings')
for f_ in FAILS[:20]: print(f'  FAIL  {f_}')
print(f'\n{len(FAILS)} failures, {len(WARNS)} warnings')
sys.exit(1 if FAILS else 0)
