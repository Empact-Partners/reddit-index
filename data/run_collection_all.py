#!/usr/bin/env python3
"""After discovery: 90-day sweep of the new core subs, then classify, score, publish.

Runs AFTER data/run_discovery_all.py. Preconditions it enforces rather than assumes:
  * the new categories have core subs (discovery + additive selection ran)
  * those subs exist in the Postgres subreddits table — sweep_sub SKIPS SILENTLY otherwise,
    so a premature start collects nothing and reports success

None of this touches the Codex fleet: sweep is pure Reddit (one client, 0.75s floor) and
classify is DeepSeek HTTP. The memory profile is nothing like a fleet wave. It is still
serialized against every other Reddit consumer.

  python3 data/run_collection_all.py            # sweep -> classify -> score -> publish
  python3 data/run_collection_all.py --skip-sweep
"""
import argparse, csv, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RI = os.path.join(HERE, '.roster-import')
sys.path.insert(0, os.path.join(ROOT, 'worker'))

def slugs():
    return {p['slug'] for p in json.load(open(f'{RI}/map/clusters.json'))['proposed']}

def new_core_subs():
    new = slugs()
    return sorted({r['subreddit'] for r in csv.DictReader(open(f'{HERE}/category-subreddits.csv'))
                   if r['category_slug'] in new and r.get('is_core') == 'True'})

def seeded_subs(subs):
    import db
    with db.connect() as cx, cx.cursor() as cur:
        cur.execute('SELECT lower(name) FROM subreddits WHERE lower(name) = ANY(%s)',
                    ([s.lower() for s in subs],))
        return {r[0] for r in cur.fetchall()}

def step(name, args, cwd=ROOT):
    print(f'\n=== {name} · {time.strftime("%H:%M:%S")} ===', flush=True)
    rc = subprocess.call(args, cwd=cwd)
    print(f'{name} exited {rc} · {time.strftime("%H:%M:%S")}', flush=True)
    return rc

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-sweep', action='store_true')
    ap.add_argument('--days', type=int, default=90)
    a = ap.parse_args()

    subs = new_core_subs()
    print(f'new-category core subreddits: {len(subs)}', flush=True)
    if len(subs) < 10:
        print('ABORT: fewer than 10 core subs. Discovery and additive core selection must '
              'run first (data/run_discovery_all.py).', file=sys.stderr)
        return 1

    have = seeded_subs(subs)
    missing = [s for s in subs if s.lower() not in have]
    print(f'seeded in Postgres: {len(have)}/{len(subs)}', flush=True)
    if missing:
        print(f'ABORT: {len(missing)} core subs are not in the subreddits table, e.g. '
              f'{missing[:5]}. sweep_sub SKIPS these SILENTLY — it would report success and '
              f'collect nothing. Run: python3 worker/load.py --seed', file=sys.stderr)
        return 1

    if not a.skip_sweep:
        rc = step(f'sweep --days {a.days} over {len(subs)} subs',
                  [sys.executable, f'{ROOT}/worker/sweep.py', '--days', str(a.days),
                   '--only', ','.join(subs)])
        if rc != 0:
            print('sweep failed — not proceeding to classify', file=sys.stderr); return rc

    # classify only what the sweep just added, for the brands we care about
    slugs_fp = '/tmp/roster_slugs_all.txt'
    with open(slugs_fp, 'w') as f:
        rows = [r['slug'] for r in csv.DictReader(open(f'{HERE}/brands.csv'))
                if r['source'] == 'roster-import-2026-08'
                or r['primary_category_slug'] in slugs()]
        f.write('\n'.join(sorted(set(rows))) + '\n')
    print(f'classify targets: {len(set(rows))} brand slugs', flush=True)
    step('classify', [sys.executable, f'{ROOT}/worker/classify_brands.py',
                      '--slugs-file', slugs_fp, '--allow-metered'])

    step('score', [sys.executable, f'{ROOT}/worker/score_db.py'])
    step('delete-sync (legal condition, never skipped)',
         [sys.executable, f'{ROOT}/worker/delete_sync.py', '--limit', '60000',
          '--publish-follows'])
    step('publish', [sys.executable, f'{ROOT}/worker/publish.py'])
    step('verify', [sys.executable, f'{ROOT}/worker/healthcheck.py', '--json'])
    print(f'\nCOLLECTION COMPLETE {time.strftime("%H:%M:%S")}', flush=True)
    return 0

if __name__ == '__main__':
    sys.exit(main())
