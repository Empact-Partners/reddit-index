#!/usr/bin/env python3
"""P1 checkpoint: render the proposed-category review page for Vlad.

Inputs: .roster-import/mapping.json + map/clusters.json + roster.json.
Output: .roster-import/checkpoint.html — proposed NEW categories (name, slug, nouns,
members) + a 100-row random sample of the existing-category mapping + the numbers.
Slugs freeze forever at publish (decisions/0007), so this page is the one moment to veto
a name. Read-only; writes only the HTML.
"""
import csv, json, os, random, html

HERE = os.path.dirname(os.path.abspath(__file__))
RI = os.path.join(HERE, '.roster-import')

roster = {r['domain']: r for r in json.load(open(f'{RI}/roster.json'))}
mapping = json.load(open(f'{RI}/mapping.json'))
clusters = json.load(open(f'{RI}/map/clusters.json'))
cats = {c['slug']: c['category'] for c in json.load(open(f'{RI}/categories_ref.json'))}

mapped = [m for m in mapping if m['category_slug']]
unmapped = [m for m in mapping if not m['category_slug']]
proposed = clusters.get('proposed', [])
unclustered = clusters.get('unclustered', [])

# hygiene: slug collisions with existing categories, members not in roster, dupes
existing = set(cats)
problems = []
seen_members = set()
for p in proposed:
    if p['slug'] in existing:
        problems.append(f"slug collision with existing category: {p['slug']}")
    for m in p['members']:
        if m in seen_members: problems.append(f"{m} in two clusters")
        seen_members.add(m)
        if m not in roster: problems.append(f"{p['slug']}: unknown member {m}")

# adjacency to existing categories, on DISTINCTIVE tokens only (a check on generic words
# like "Management" flags 41 of 51 and is worthless). These are the calls worth a human eye.
GENERIC = {'management','software','platform','platforms','tools','tool','and','systems',
           'system','services','service','automation','marketing','business','data','cloud',
           'ai','the','of','for','intelligence','security','processing','analytics','testing',
           'hosting','reporting'}
def dtoks(x):
    import re as _re
    return {w for w in _re.findall(r'[a-z]+', x.lower()) if w not in GENERIC and len(w) > 3}
adjacent = []
for p_ in proposed:
    pt = dtoks(p_['category'])
    for es, ec in cats.items():
        sh = pt & dtoks(ec)
        if sh:
            adjacent.append((p_['category'], ec, sorted(sh))); break

random.seed(11)
sample = random.sample(mapped, min(100, len(mapped)))

E = html.escape
L = []
w = L.append
w('<title>Reddit Index Expansion Review</title>')
w('<style>:root{--bg:#EEF1ED;--panel:#fff;--ink:#08272C;--ink2:#3D5A5F;--rule:#D3DCD8;'
  '--acc:#02454F;--go:#40C890;}'
  '@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0D1416;'
  '--panel:#141E20;--ink:#E8EFEB;--ink2:#A8BCBB;--rule:#25373A;--acc:#7FD8D0;}}'
  ':root[data-theme="dark"]{--bg:#0D1416;--panel:#141E20;--ink:#E8EFEB;--ink2:#A8BCBB;'
  '--rule:#25373A;--acc:#7FD8D0;}'
  'body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 ui-sans-serif,system-ui;}'
  '.wrap{max-width:960px;margin:0 auto;padding:40px 20px;}'
  'h1{font-size:28px;margin:0 0 6px;} h2{font-size:19px;margin:36px 0 10px;color:var(--acc);}'
  'p{color:var(--ink2);max-width:70ch;margin:6px 0;}'
  'table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--rule);'
  'border-radius:10px;overflow:hidden;font-size:13.5px;}'
  'th{ text-align:left;padding:9px 12px;border-bottom:1px solid var(--rule);font-size:11px;'
  'text-transform:uppercase;letter-spacing:.08em;color:var(--ink2);}'
  'td{padding:8px 12px;border-bottom:1px solid var(--rule);vertical-align:top;color:var(--ink2);}'
  'td b{color:var(--ink);} tr:last-child td{border-bottom:0;}'
  'code{background:var(--bg);padding:1px 5px;border-radius:4px;font-size:.9em;}'
  '.n{text-align:right;font-variant-numeric:tabular-nums;}'
  '.warn{background:var(--panel);border:1px solid var(--go);border-radius:10px;padding:12px 16px;}'
  '.scroll{overflow-x:auto;}</style>')
w('<div class="wrap">')
w('<h1>Reddit Index Expansion — Review</h1>')
w(f'<p>{len(mapping):,} companies mapped by the fleet: <b>{len(mapped):,}</b> fit an existing '
  f'category, <b>{len(unmapped):,}</b> did not. Clustering proposes <b>{len(proposed)}</b> new '
  f'categories covering <b>{sum(len(p["members"]) for p in proposed):,}</b> companies; '
  f'{len(unclustered):,} remain unclustered (too few peers). Category names and slugs freeze '
  f'forever at publish — this page is the veto moment.</p>')
if problems:
    w(f'<div class="warn"><b>{len(problems)} hygiene problems</b> (fix before build):<br>'
      + '<br>'.join(E(p) for p in problems[:20]) + '</div>')
w('<h2>Proposed new categories</h2>')
w('<div class="scroll"><table><tr><th>Category</th><th>Slug</th><th class="n">Members</th>'
  '<th>Nouns</th><th>Sample members</th></tr>')
for p in sorted(proposed, key=lambda x: -len(x['members'])):
    samp = ', '.join(p['members'][:5])
    w(f'<tr><td><b>{E(p["category"])}</b></td><td><code>{E(p["slug"])}</code></td>'
      f'<td class="n">{len(p["members"])}</td><td>{E(p.get("nouns",""))}</td>'
      f'<td>{E(samp)}</td></tr>')
w('</table></div>')
if adjacent:
    w('<h2>Sits near an existing category</h2>')
    w('<p>Checked on distinctive words only — a naive check that counts words like '
      '&ldquo;Management&rdquo; flags 41 of 51 and tells you nothing. Each of these reads as '
      'genuinely separate to me, but they are the calls worth your eye.</p>')
    w('<div class="scroll"><table><tr><th>Proposed</th><th>Existing</th><th>Shared word</th></tr>')
    for a, b, sh in adjacent:
        w(f'<tr><td><b>{E(a)}</b></td><td>{E(b)}</td><td>{E(", ".join(sh))}</td></tr>')
    w('</table></div>')

w('<h2>Existing-category mapping — 100-row random sample</h2>')
w('<div class="scroll"><table><tr><th>Company</th><th>Sells</th><th>Mapped to</th></tr>')
for m in sample:
    r = roster[m['domain']]
    w(f'<tr><td><b>{E(m["domain"])}</b></td><td>{E(r["sells"])}</td>'
      f'<td><code>{E(m["category_slug"])}</code> {E(cats.get(m["category_slug"],""))}</td></tr>')
w('</table></div>')
w('</div>')
open(f'{RI}/checkpoint.html', 'w').write('\n'.join(L))
print(f'wrote {RI}/checkpoint.html · proposed {len(proposed)} · problems {len(problems)}')
