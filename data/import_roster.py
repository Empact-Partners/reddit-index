#!/usr/bin/env python3
"""P2 of the never-replied expansion: import a fixed company roster into the gazetteer.

enumerate_brands.py enumerates a roster FROM a category; this is its sibling for the case
where the roster is fixed (company + domain + category already decided) and only the
gazetteer craft is missing: aliases, ambiguity, stop-contexts. The fleet drafts those; the
same deterministic gates decide (models draft, gates decide). Two additions the RI-W1
pressure-test demanded:

  * a FLAT-NAMESPACE pre-check — G1 dedupes only against brands.csv, but a company slug that
    collides with a category slug or a reserved route (api, search, methodology...) fails
    `next build` at publish time, the worst possible moment. Collisions get a deterministic
    "-software" disambiguator (decisions/0007's prescription: disambiguate the company,
    never rename a published slug).
  * a G4 RETRY pass — one transient DNS failure must not permanently reject a prospect.
    Domains that fail twice land in g4_dead.json: routed out of the gazetteer AND flagged for
    the wave-2 pool (a dead domain is a dead company — signal, not noise).

Inputs (data/.roster-import/): roster.json + mapping.json (from map_roster.py).
Output: rows appended to brand-seed-expand.csv, source=roster-import-2026-08, then
`python3 data/gen_brands.py` merges them. Disk-idempotent throughout.

Run:  python3 data/import_roster.py          # fleet drafting for missing batches
      python3 data/import_roster.py --merge  # gates + append to the seed CSV
"""
import csv, json, os, re, socket, sys, time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, '/Users/vladshvets/.claude/api_helpers')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from codex_fleet import CodexFleet, TERMINAL
from gen_brands import slugify

HERE = os.path.dirname(os.path.abspath(__file__))
RI = os.path.join(HERE, '.roster-import')
DRAFT = os.path.join(RI, 'gazetteer')
os.makedirs(DRAFT, exist_ok=True)
BATCH = 40
WIDTH = int(os.environ.get('FLEET_WIDTH', '10'))
SOURCE = 'roster-import-2026-08'

def english_words():
    try:
        return {w.strip().lower() for w in open('/usr/share/dict/words') if len(w.strip()) > 2}
    except Exception:
        return set()

def reserved_slugs():
    """Category slugs + framework paths + site routes, read from their sources of truth."""
    res = {r['slug'] for r in csv.DictReader(open(os.path.join(HERE, 'categories.csv')))}
    reg = open(os.path.join(HERE, '..', 'lib', 'routing', 'registry.mjs')).read()
    for m in re.finditer(r'"([a-z0-9._-]+)"', reg.split('SITE_ROUTES')[0].split('FRAMEWORK_PATHS')[1]):
        res.add(m.group(1))
    for m in re.finditer(r'"([a-z0-9._-]+)"', reg.split('SITE_ROUTES')[1].split(']')[0]):
        res.add(m.group(1))
    return res

def load_cohort(which='existing'):
    """Companies mapped to a category, split by whether that category predates this project.

    The split exists because batch files are indexed by position: growing the cohort
    re-slices every batch, so a disk-idempotent skip would pass over companies that were
    never actually drafted and they would silently vanish at merge. Two cohorts, two file
    prefixes, each stable on its own.
    """
    roster = {r['domain']: r for r in json.load(open(f'{RI}/roster.json'))}
    mapping = json.load(open(f'{RI}/mapping.json'))
    pre_existing = {c['slug'] for c in json.load(open(f'{RI}/categories_ref.json'))}
    out = []
    for m in mapping:
        slug = m['category_slug']
        if not slug or m['domain'] not in roster:
            continue
        is_old = slug in pre_existing
        if which == 'existing' and not is_old: continue
        if which == 'new' and is_old: continue
        out.append(dict(roster[m['domain']], category_slug=slug))
    return sorted(out, key=lambda r: r['domain'])

def prompt(i, batch, prefix='g'):
    items = json.dumps([{'company': r['company'], 'domain': r['domain'],
                         'sells': r['sells']} for r in batch], indent=0)
    return f"""You are drafting entity-resolution rows for a Reddit brand-mention gazetteer.
These companies' Reddit mentions will be matched by an automaton built from your output, so
a wrong alias creates FALSE mentions on a published page. Precision beats recall.

Companies:
{items}

For EACH company return:
- "company", "domain": verbatim from the input.
- "aliases": OTHER surface forms Redditors actually write for this company — product names,
  common abbreviations, the domain with the TLD spoken ("acme.io" for Acme). NEVER include
  generic words, the category name, or forms you are guessing at. Empty list is a fine and
  common answer.
- "ambiguity": how dangerous the BARE company name is as a match token in casual English:
    "low"    = distinctive coinage (Klaviyo, Smartlead) — safe to match bare
    "medium" = could appear in other contexts sometimes (Loop, Drip) — needs corroboration
    "high"   = ordinary English word or extremely common token (Close, Front, Motion) —
               bare form must never match
  When unsure, choose the HIGHER class. An earlier audit showed cold-list SaaS names are
  English-word-collision-prone, and one bad SAFE alias pollutes existing leaderboards.
- "stop_contexts": ONLY for medium/high names: 1-3 short phrases where the bare token
  appears in its ORDINARY meaning (for "Close": "close the deal", "close friends"). Each
  phrase MUST contain the bare token. Empty list for low.
- "note": one sentence on the ambiguity call.

Write a JSON array to exactly {DRAFT}/{prefix}_{i:03d}.json — one object per company, same order,
nothing else in the file. Do not modify any other file."""

def done(path):
    if not os.path.exists(path): return False
    try:
        d = json.load(open(path)); return isinstance(d, list) and len(d) > 0
    except Exception: return False

def run_fleet(jobs, model):
    todo = [(p, o) for p, o in jobs if not done(o)]
    print(f'gazetteer drafting: {len(jobs)} batches, {len(jobs)-len(todo)} done, {len(todo)} to run', flush=True)
    if not todo: return
    fleet = CodexFleet(); inflight = {}; queue = list(todo); fails = {}
    while queue or inflight:
        while queue and len(inflight) < WIDTH:
            p, o = queue.pop(0)
            try:
                j = fleet.submit(p, model=model, mode='full-auto', timeout=1200, workspace=RI)
                inflight[(j['server'], j['job_id'])] = (p, o); time.sleep(1.0)
            except Exception as e:
                print(f'  submit fail: {e}', flush=True); queue.append((p, o)); time.sleep(15); break
        time.sleep(8)
        for key in list(inflight):
            try: st = fleet.status(*key)
            except Exception: continue
            if st.get('status') not in TERMINAL: continue
            p, o = inflight.pop(key)
            # A job reaches TERMINAL a moment before its file lands. Without this window the
            # retry resubmits a job that is still writing, and two Codex sessions then write
            # the same path — measured here as 18 redundant in-flight jobs against 37 files
            # already complete, each one able to overwrite a good file mid-write.
            for _ in range(6):
                if done(o): break
                time.sleep(5)
            if done(o): print(f'  ok {os.path.basename(o)}', flush=True)
            else:
                n = fails[o] = fails.get(o, 0) + 1
                if n <= 2: queue.append((p, o))
                else: print(f'  GAVE UP {os.path.basename(o)}', flush=True)

def resolve_domain(d):
    try:
        socket.getaddrinfo(d, 443, proto=socket.IPPROTO_TCP); return True
    except Exception:
        return False

def merge():
    cohort = load_cohort('existing') + load_cohort('new')
    words = english_words()
    reserved = reserved_slugs()

    # existing gazetteer for G1
    existing_slugs, existing_domains = {}, {}
    for r in csv.DictReader(open(os.path.join(HERE, 'brands.csv'))):
        existing_slugs[r['slug']] = r
        for d in (r['domains'] or '').split(';'):
            if d: existing_domains[d.strip().lower()] = r['slug']

    drafts = {}
    for fp in sorted(os.listdir(DRAFT)):
        if (fp.startswith('g_') or fp.startswith('n_')) and fp.endswith('.json'):
            for r in json.load(open(os.path.join(DRAFT, fp))):
                if isinstance(r, dict) and r.get('domain'):
                    drafts[r['domain']] = r

    ORDER = {'low': 0, 'medium': 1, 'high': 2}
    rows, rejects, dead, dedup = [], [], [], 0
    alias_claims = {}
    for c in cohort:
        d = drafts.get(c['domain'])
        if not d:
            rejects.append((c['domain'], 'no draft')); continue
        name = (c['company'] or '').strip() or c['domain'].split('.')[0]
        amb = str(d.get('ambiguity') or 'medium').lower()
        if amb not in ORDER: amb = 'medium'
        # stricter-by-default: an English-word or very short name can never enter as low
        if name.lower() in words or len(name) <= 3:
            amb = max(amb, 'medium', key=lambda a: ORDER[a])
        bslug = slugify(name, c['domain'])
        # flat-namespace pre-check (the publish-time build bomb)
        if bslug in reserved:
            bslug = f'{bslug}-software'
            if bslug in reserved or bslug in existing_slugs:
                rejects.append((c['domain'], f'slug collision unresolvable: {bslug}')); continue
        # G1 dedupe
        if bslug in existing_slugs or c['domain'] in existing_domains:
            dedup += 1; continue
        aliases = [str(a).strip() for a in (d.get('aliases') or [])
                   if str(a).strip() and str(a).strip().lower() != name.lower()]
        stops = [s for s in (d.get('stop_contexts') or [])
                 if name.lower().split()[0] in str(s).lower()]  # G5
        rows.append({'name': name, 'slug': bslug, 'cat': c['category_slug'], 'amb': amb,
                     'aliases': aliases, 'domains': [c['domain']], 'stops': stops,
                     'note': str(d.get('note') or '')[:200]})
        for form in [name] + aliases:
            alias_claims.setdefault(form.lower(), set()).add(bslug)

    # G3 + G2b: bare-form disable on collisions and english-word aliases
    bare_disabled = {}
    for form, claimants in alias_claims.items():
        pool = set(claimants)
        pool.update({s for s in existing_slugs if s == form})  # cheap vs-existing guard
        if len(pool) > 1:
            for b in claimants: bare_disabled.setdefault(b, set()).add(form)
    for r in rows:
        for form in [r['name']] + r['aliases']:
            f = form.lower()
            if ' ' not in f and '.' not in f and f in words:
                bare_disabled.setdefault(r['slug'], set()).add(f)

    # G4 with a retry pass
    all_domains = sorted({d for r in rows for d in r['domains']})
    with ThreadPoolExecutor(max_workers=32) as ex:
        ok = dict(zip(all_domains, ex.map(resolve_domain, all_domains)))
    retry = [d for d, v in ok.items() if not v]
    if retry:
        print(f'G4: {len(retry)} domains failed DNS, retrying once...', flush=True)
        time.sleep(5)
        with ThreadPoolExecutor(max_workers=16) as ex:
            ok.update(dict(zip(retry, ex.map(resolve_domain, retry))))
    kept_rows = []
    for r in rows:
        if all(not ok.get(d) for d in r['domains']):
            dead.append(r['domains'][0]); continue
        r['domains'] = [d for d in r['domains'] if ok.get(d)]
        kept_rows.append(r)

    # append to the seed CSV (append-only contract, matching its columns)
    out_fp = os.path.join(HERE, 'brand-seed-expand.csv')
    seen_seed = {r['brand'].lower() for r in csv.DictReader(open(out_fp))}
    added = 0
    with open(out_fp, 'a', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        for r in kept_rows:
            if r['name'].lower() in seen_seed: continue
            w.writerow([r['name'], r['cat'], '', ';'.join(r['aliases']), r['amb'],
                        r['note'], ';'.join(r['domains']), ';'.join(r['stops']),
                        ';'.join(sorted(bare_disabled.get(r['slug'], set()))), SOURCE])
            added += 1
    json.dump(sorted(dead), open(f'{RI}/g4_dead.json', 'w'), indent=0)
    json.dump(rejects, open(f'{RI}/import_rejects.json', 'w'), indent=0)
    print(f'\ncohort {len(cohort)} · appended {added} · deduped-vs-gazetteer {dedup} · '
          f'G4-dead {len(dead)} · rejects {len(rejects)}', flush=True)
    print(f'next: python3 {HERE}/gen_brands.py && python3 {HERE}/../worker/load.py --seed', flush=True)

if __name__ == '__main__':
    if '--merge' in sys.argv:
        merge()
    else:
        which = 'new' if '--new' in sys.argv else 'existing'
        prefix = 'n' if which == 'new' else 'g'
        cohort = load_cohort(which)
        print(f'cohort ({which} categories): {len(cohort)}', flush=True)
        batches = [cohort[i:i+BATCH] for i in range(0, len(cohort), BATCH)]
        run_fleet([(prompt(i, b, prefix), f'{DRAFT}/{prefix}_{i:03d}.json')
                   for i, b in enumerate(batches)], 'gpt-5.6-terra')
