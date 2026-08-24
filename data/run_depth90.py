#!/usr/bin/env python3
"""Stage 3, done the documented way: 90 days, category by category.

This implements `docs/depth-execution-plan.md` Stage 3 (:142-166) for the 51 new categories.
It exists because a previous attempt did NOT implement it — it invented a 30-day wave ladder
across all categories at once, which is neither the depth nor the cadence the plan specifies.

The plan, in its own words (:159-166):

    "process in category order ... After each category's subs finish: 1. targeted classify
     burn for that category's unclassified mentions, 2. worker/score_db.py, 3. publish.
     So categories come online WHOLE, visibly deeper, one after another — never everything
     half-done at once."

THE TREE CAP, and why this file reads it rather than choosing it
---------------------------------------------------------------
The completed 527-subreddit sweep ran at **150 trees per subreddit**, pinned in
`worker/.cache/depth/mode.json` by `worker/collector.py:53`. That number is in no markdown
file in the repo, while `sweep.py`'s own default is 100000 and `run_collection_all.py` passes
no cap at all — so every new-category sweep since has run ~50x the per-subreddit work that
built the index, and nothing would tell you. On 2026-08-24 that cost most of a day.

A cap is not a quality cut here: `sweep.py` orders threads richest-first (:283-289 — a
100+-comment thread yields 9.2 mentions, a 2-comment thread 1.2), so the cap takes the most
valuable threads rather than an arbitrary slice, and `sub_complete` is already cap-aware.

So the cap is READ from the pinned file, never retyped. If the pin is missing this refuses to
run rather than silently falling back to 100000.

  python3 data/run_depth90.py --plan     # category order and cost, run nothing
  python3 data/run_depth90.py            # sweep -> classify -> score -> publish, per category
  python3 data/run_depth90.py --only crm,vpn
"""
import argparse, collections, csv, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RI = os.path.join(HERE, '.roster-import')
MODE_FP = os.path.join(ROOT, 'worker', '.cache', 'depth', 'mode.json')
STATE = os.path.join(HERE, '.pipeline', 'depth90_done.json')
PD = '/Users/vladshvets/Projects/empact-partners/partner-development'

sys.path.insert(0, os.path.join(ROOT, 'worker'))


def pinned_mode():
    """days + tree_cap from the file the production sweep pins. Never guessed."""
    try:
        m = json.load(open(MODE_FP))
        days, cap = int(m['days']), int(m['tree_cap'])
    except Exception as e:
        raise SystemExit(
            f"REFUSING: cannot read the pinned depth mode at {MODE_FP} ({e}).\n"
            f"  That file holds the days/tree_cap the shipped index was actually built with.\n"
            f"  Without it this would fall back to sweep.py's 100000 default — ~50x the work\n"
            f"  per subreddit — which is exactly the mistake this driver exists to prevent.")
    return days, cap


def new_slugs():
    return {p['slug'] for p in json.load(open(f'{RI}/map/clusters.json'))['proposed']}


def core_by_category():
    new = new_slugs()
    out = collections.defaultdict(list)
    for r in csv.DictReader(open(f'{HERE}/category-subreddits.csv')):
        if r['category_slug'] in new and r.get('is_core') == 'True':
            try:
                w = float(r.get('worth') or 0)
            except ValueError:
                w = 0.0
            out[r['category_slug']].append((w, r['subreddit']))
    for k in out:
        out[k].sort(key=lambda x: -x[0])       # best signal first within a category
    return out


def outreach_weight():
    """Companies per category that we hold a contact for — the plan lets Vlad choose the
    order, and for this wave the point is the outreach list, so the categories carrying the
    most contactable companies come online first."""
    new = new_slugs()
    nr = {}
    fp = f'{PD}/data/never-replied/never_replied.csv'
    if os.path.exists(fp):
        nr = {r['domain'].strip().lower() for r in csv.DictReader(open(fp))
              if (r.get('contacts') or '').strip() not in ('', '0', '[]')}
    w = collections.Counter()
    for r in csv.DictReader(open(f'{HERE}/brands.csv')):
        if r['primary_category_slug'] in new:
            d = (r['domains'] or '').split(';')[0].strip().lower()
            w[r['primary_category_slug']] += 1 if d in nr else 0
    return w


def done_subs():
    try:
        return set(json.load(open(STATE)))
    except Exception:
        return set()


def mark(subs):
    d = done_subs() | {s.lower() for s in subs}
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(sorted(d), open(STATE, 'w'), indent=0)


def step(name, args, env=None, fatal=True):
    print(f'\n=== {name} · {time.strftime("%H:%M:%S")} ===', flush=True)
    rc = subprocess.call(args, cwd=ROOT, env=dict(os.environ, **(env or {})))
    print(f'{name} exited {rc} · {time.strftime("%H:%M:%S")}', flush=True)
    if rc != 0 and fatal:
        print(f'ABORT at {name}.', file=sys.stderr)
    return rc


def seeded(subs):
    """sweep_sub SKIPS a sub missing from the subreddits table, SILENTLY."""
    import db
    with db.connect() as cx, cx.cursor() as cur:
        cur.execute('SELECT lower(name) FROM subreddits WHERE lower(name) = ANY(%s)',
                    ([s.lower() for s in subs],))
        return {r[0] for r in cur.fetchall()}


def category_slugs_file(slug):
    fp = os.path.join(HERE, '.pipeline', f'classify_{slug}.txt')
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    rows = {r['slug'] for r in csv.DictReader(open(f'{HERE}/brands.csv'))
            if r['primary_category_slug'] == slug
            or slug in (r.get('also_in_category_slugs') or '').split(';')}
    open(fp, 'w').write('\n'.join(sorted(rows)) + '\n')
    return fp, len(rows)


def ship_category(slug):
    """classify -> score -> publish, for ONE category. The plan's cadence: a category comes
    online whole before the next one starts."""
    fp, n = category_slugs_file(slug)
    step(f'{slug}: classify ({n} brands)',
         [sys.executable, f'{ROOT}/worker/classify_brands.py', '--slugs-file', fp,
          '--allow-metered'], fatal=False)
    step(f'{slug}: score', [sys.executable, f'{ROOT}/worker/score_db.py'], fatal=False)
    # decisions/0002: delete-sync is a legal condition of showing comment text at all.
    step(f'{slug}: delete-sync',
         [sys.executable, f'{ROOT}/worker/delete_sync.py', '--limit', '20000',
          '--publish-follows'], fatal=False)
    step(f'{slug}: publish', [sys.executable, f'{ROOT}/worker/publish.py'], fatal=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--only', default='', help='comma-separated category slugs')
    ap.add_argument('--chunk', type=int, default=10, help='subs per sweep invocation')
    a = ap.parse_args()

    days, cap = pinned_mode()
    by_cat = core_by_category()
    weight = outreach_weight()
    order = sorted(by_cat, key=lambda c: (-weight.get(c, 0), c))
    if a.only:
        keep = {s.strip() for s in a.only.split(',') if s.strip()}
        order = [c for c in order if c in keep]

    total_subs = len({s for v in by_cat.values() for _, s in v})
    print(f'Stage 3 · {days}-day depth · tree cap {cap} (pinned in {MODE_FP})', flush=True)
    print(f'{len(order)} categories · {total_subs} unique core subreddits\n', flush=True)

    if a.plan:
        print(f'  {"#":>3} {"category":38} {"subs":>5} {"contacts":>9}')
        for i, c in enumerate(order, 1):
            print(f'  {i:3} {c:38} {len(by_cat[c]):5} {weight.get(c,0):9}')
        trees = total_subs * cap
        print(f'\n  worst case {trees:,} trees ≈ {trees/60/60:.1f} h at 60 trees/min')
        print(f'  (less whatever the HTTP cache already holds — re-fetches are free)')
        print(f'  already banked: {len(done_subs())} subreddits')
        return 0

    for i, slug in enumerate(order, 1):
        subs = [s for _, s in by_cat[slug]]
        todo = [s for s in subs if s.lower() not in done_subs()]
        print(f'\n{"#"*70}\n# [{i}/{len(order)}] {slug} · {len(todo)}/{len(subs)} subs to sweep '
              f'· {time.strftime("%H:%M:%S")}\n{"#"*70}', flush=True)
        if not todo:
            print('  already swept; shipping what is there', flush=True)
        else:
            have = seeded(todo)
            missing = [s for s in todo if s.lower() not in have]
            if missing:
                print(f'ABORT: {len(missing)} subs not in the subreddits table (e.g. '
                      f'{missing[:4]}). sweep_sub skips these SILENTLY.', file=sys.stderr)
                return 1
            for c0 in range(0, len(todo), a.chunk):
                chunk = todo[c0:c0 + a.chunk]
                rc = step(f'{slug}: sweep {c0+1}-{c0+len(chunk)} of {len(todo)}',
                          [sys.executable, f'{ROOT}/worker/sweep.py',
                           '--days', str(days), '--tree-cap', str(cap),
                           '--only', ','.join(chunk)])
                if rc != 0:
                    print(f'sweep failed in {slug}; {c0} subs banked. Rerun to continue.',
                          file=sys.stderr)
                    return rc
                mark(chunk)
        ship_category(slug)
        print(f'\n>>> {slug} COMPLETE ({i}/{len(order)}) · {time.strftime("%H:%M:%S")}',
              flush=True)

    print(f'\nCOLLECTION COMPLETE {time.strftime("%H:%M:%S")}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
