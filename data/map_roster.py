#!/usr/bin/env python3
"""P1 of the never-replied expansion: map the import roster onto the category taxonomy.

Two fleet passes (the house draft+review pattern), then clustering of the unmapped:
  draft   (gpt-5.6-luna)  batch of companies -> {domain, category_slug|"", confidence}
  review  (gpt-5.6-terra) adversarial re-check; may only DEMOTE to "" or correct a slug
  cluster (gpt-5.6-sol)   the "" remainder -> proposed new categories for Vlad's review

Disk-idempotent under data/.roster-import/map/: a batch whose output parses is never
re-submitted. Serialized nowhere near the Reddit client — this stage is fleet-only.

Run:  python3 data/map_roster.py            # draft + review whatever is missing
      python3 data/map_roster.py --cluster  # cluster after mapping is complete
"""
import json, os, sys, time, glob
sys.path.insert(0, '/Users/vladshvets/.claude/api_helpers')
from codex_fleet import CodexFleet, TERMINAL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RI = os.path.join(ROOT, 'data', '.roster-import')
MAP = os.path.join(RI, 'map')
os.makedirs(MAP, exist_ok=True)
BATCH = 40
WIDTH = int(os.environ.get('FLEET_WIDTH', '10'))

roster = json.load(open(f'{RI}/roster.json'))
cats = json.load(open(f'{RI}/categories_ref.json'))
CATLIST = '\n'.join(f"  {c['slug']:26} {c['category']}  (nouns: {c['nouns']})" for c in cats)
SLUGS = {c['slug'] for c in cats}

batches = [roster[i:i+BATCH] for i in range(0, len(roster), BATCH)]
for i, b in enumerate(batches):
    fp = f'{MAP}/in_{i:03d}.json'
    if not os.path.exists(fp):
        json.dump(b, open(fp, 'w'), indent=0)

def prompt_draft(i):
    return f"""You are mapping SaaS companies onto the Reddit Index category taxonomy.

Read {MAP}/in_{i:03d}.json — up to {BATCH} companies, each with domain, company name,
"sells" (a verified short description of what it sells), niche_hint, and tier2 (a coarse
20-bucket label). Both hints are evidence, not verdicts.

The taxonomy — use the slug EXACTLY as written, these are the only 100 valid values:
{CATLIST}

For EACH company decide: does it belong on one of these category leaderboards? The bar is
whether a Reddit user browsing that category board would expect this product to be ranked
there — the company's PRIMARY product category, its centre of gravity, not a module.

- Map to the single best slug when the fit is real.
- Use "" (empty) when NO category fits without stretching. Do NOT force a fit: an empty
  answer routes the company to a new, more specific category later, which is the better
  outcome for a bad fit. A vertical product (dental software, church management) whose
  vertical has no category here is "" — do not dump it into a vaguely-related horizontal.
- confidence: high / medium / low.

Write a JSON array to exactly {MAP}/out_{i:03d}.json — one object per input company,
same order: {{"domain": "<verbatim>", "category_slug": "<slug or empty>",
"confidence": "high|medium|low"}}
Nothing else in the file. Every input domain exactly once. Do not modify any other file."""

def prompt_review(i):
    return f"""Adversarial review of a category mapping. Read BOTH files:
  {MAP}/in_{i:03d}.json   — the companies (domain, name, sells, hints)
  {MAP}/out_{i:03d}.json  — a cheaper model's mapping onto Reddit Index category slugs

The taxonomy (the only valid slugs):
{CATLIST}

The failure mode you are hunting: FORCED FITS — a company shoved into a vaguely-related
horizontal category when its real category doesn't exist in the list. A Reddit user browsing
that category board must expect this product there; a stretch pollutes a published
leaderboard. Rules:
- You may DEMOTE a mapping to "" (no fit) — this is the common correction.
- You may CORRECT an outright wrong slug to the right one when the right one clearly exists.
- You may not invent slugs. You may not promote "" to a slug unless the draft plainly missed
  an exact fit.

Write the corrected full array to {MAP}/rev_{i:03d}.json — same contract as the input
mapping, every domain exactly once, plus a "changed": true field ONLY on rows you altered.
Do not modify any other file."""

def done(path):
    if not os.path.exists(path): return False
    try:
        d = json.load(open(path)); return isinstance(d, list) and len(d) > 0
    except Exception: return False

def run(jobs, model, label):
    """jobs: list of (task_prompt, output_path). Disk-idempotent, WIDTH-wide."""
    todo = [(p, o) for p, o in jobs if not done(o)]
    print(f'{label}: {len(jobs)} jobs, {len(jobs)-len(todo)} done, {len(todo)} to run', flush=True)
    if not todo: return
    fleet = CodexFleet(); inflight = {}; queue = list(todo); fails = {}
    while queue or inflight:
        while queue and len(inflight) < WIDTH:
            p, o = queue.pop(0)
            try:
                j = fleet.submit(p, model=model, mode='full-auto', timeout=1200, workspace=RI)
                inflight[(j['server'], j['job_id'])] = (p, o)
                time.sleep(1.0)
            except Exception as e:
                print(f'  submit fail {os.path.basename(o)}: {e}', flush=True)
                queue.append((p, o)); time.sleep(15); break
        time.sleep(8)
        for key in list(inflight):
            try: st = fleet.status(*key)
            except Exception: continue
            if st.get('status') not in TERMINAL: continue
            p, o = inflight.pop(key)
            # A job can reach TERMINAL a moment before its file lands, and a naive retry
            # then resubmits a job that is still writing — two Codex sessions writing the
            # same path concurrently, which is how the clustering output rewrote itself
            # three times. Give the write a grace window before calling it a failure.
            for _ in range(6):
                if done(o):
                    break
                time.sleep(5)
            if done(o):
                print(f'  ok {os.path.basename(o)}', flush=True)
            else:
                n = fails[o] = fails.get(o, 0) + 1
                if n <= 2:
                    print(f'  retry {os.path.basename(o)} ({st.get("status")})', flush=True)
                    queue.append((p, o))
                else:
                    print(f'  GAVE UP {os.path.basename(o)}', flush=True)

if '--cluster' not in sys.argv:
    run([(prompt_draft(i), f'{MAP}/out_{i:03d}.json') for i in range(len(batches))],
        'gpt-5.6-luna', 'draft')
    run([(prompt_review(i), f'{MAP}/rev_{i:03d}.json') for i in range(len(batches))],
        'gpt-5.6-terra', 'review')
    # merge: review wins; validate slugs
    final, bad = {}, 0
    for i in range(len(batches)):
        src = f'{MAP}/rev_{i:03d}.json' if done(f'{MAP}/rev_{i:03d}.json') else f'{MAP}/out_{i:03d}.json'
        for r in json.load(open(src)):
            slug = (r.get('category_slug') or '').strip()
            if slug and slug not in SLUGS: slug, bad = '', bad + 1
            final[r['domain']] = {'domain': r['domain'], 'category_slug': slug,
                                  'confidence': r.get('confidence', '')}
    missing = [r['domain'] for r in roster if r['domain'] not in final]
    json.dump(sorted(final.values(), key=lambda x: x['domain']),
              open(f'{RI}/mapping.json', 'w'), indent=0)
    mapped = sum(1 for v in final.values() if v['category_slug'])
    print(f'\nmapping.json: {len(final)} rows · mapped {mapped} · unmapped {len(final)-mapped}'
          f' · invalid-slug-cleared {bad} · missing {len(missing)}', flush=True)
    if missing: json.dump(missing, open(f'{RI}/mapping_missing.json', 'w'), indent=0)
else:
    mapping = {r['domain']: r for r in json.load(open(f'{RI}/mapping.json'))}
    unmapped = [r for r in roster if not mapping.get(r['domain'], {}).get('category_slug')]
    json.dump(unmapped, open(f'{MAP}/unmapped.json', 'w'), indent=0)
    print(f'clustering {len(unmapped)} unmapped companies', flush=True)
    p = f"""Read {MAP}/unmapped.json — SaaS companies that did NOT fit any of the Reddit
Index's 100 existing categories (list: {RI}/categories_ref.json — read it to avoid
proposing a duplicate).

Cluster them into PROPOSED NEW categories for a public software-review index. Rules:
- Granular beats broad: "Contract Lifecycle Management" not "Legal Software". The test is a
  category a practitioner would browse as a leaderboard of competing products.
- Only propose a category with >= 8 member companies from this list. Fewer than 8 = leave
  those companies in a final "unclustered" list instead.
- slug: kebab-case, MUST NOT collide with any existing category slug or read like a generic
  web path (api, search, docs, methodology).
- nouns: 3-6 lowercase search phrases a Redditor would actually write for this category.
- Every input domain appears exactly once: in exactly one proposed category's members, or in
  unclustered.

Write to {MAP}/clusters.json:
{{"proposed": [{{"category": "<Name>", "slug": "<slug>", "nouns": "a;b;c",
                "members": ["domain", ...]}}, ...],
 "unclustered": ["domain", ...]}}
Nothing else in the file. Do not modify any other file."""
    run([(p, f'{MAP}/clusters.json')], 'gpt-5.6-sol', 'cluster')
