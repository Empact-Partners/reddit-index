#!/usr/bin/env python3
"""Grow the gazetteer with the companies the new categories surface — BEFORE any collection.

The 51 new categories exist to find companies Empact does not already hold: the competitors
and neighbours a category's own subreddits talk about. `enumerate_brands --expand` drafts
them (brands.csv is its exclusion set), gates them, and this leg merges and seeds them.

**Ordering is the whole point of this being a separate leg.** A sweep resolves each comment
tree against the gazetteer AS IT STORES IT. A brand seeded after its subreddit was swept is
never attached to that subreddit's stored threads — it would score zero while every log line
reported success, and the companies the expansion was built to surface would be invisible in
the outreach list. So this runs after discovery (which needs the fleet) and before collection
(which needs the gazetteer complete), and it writes the marker `run_collection_fast.py`
refuses to start without.

Fleet-only: zero Reddit calls. It is the one fleet lane running at the time, because
discovery has finished and two fleet lanes deadlock each other (2026-08-22).

  python3 data/run_expansion.py              # enumerate -> merge -> seed -> marker
  python3 data/run_expansion.py --skip-enum  # merge + seed only (enumeration already done)
"""
import argparse, csv, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RI = os.path.join(HERE, '.roster-import')
MARKER = os.path.join(HERE, '.pipeline', 'expansion_seeded')
SEED = os.path.join(HERE, 'brand-seed-expand.csv')

sys.path.insert(0, os.path.expanduser('~/.claude/scripts'))


def slugs():
    return sorted(p['slug'] for p in json.load(open(f'{RI}/map/clusters.json'))['proposed'])


def expand_rows(new):
    """Rows the expansion added for the new categories, by source tag."""
    if not os.path.exists(SEED):
        return 0
    return sum(1 for r in csv.DictReader(open(SEED))
               if r['primary_category_slug'] in new
               and r['source'].startswith('fleet-expand'))


def brands_in(new):
    return sum(1 for r in csv.DictReader(open(f'{HERE}/brands.csv'))
               if r['primary_category_slug'] in new)


def step(name, args, cwd=ROOT, env=None):
    print(f'\n=== {name} · {time.strftime("%H:%M:%S")} ===', flush=True)
    rc = subprocess.call(args, cwd=cwd, env=dict(os.environ, **(env or {})))
    print(f'{name} exited {rc} · {time.strftime("%H:%M:%S")}', flush=True)
    return rc


def gate_fleet(width):
    try:
        from fleet_preflight import preflight, reconcile
        preflight(want=width)
        reconcile(match='brand')     # scoped: the fleet is shared between sessions
        return True
    except SystemExit as e:
        print(f'preflight refused: {e}', file=sys.stderr)
        return False
    except Exception as e:
        print(f'preflight unavailable ({e}) — proceeding without it')
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-enum', action='store_true')
    ap.add_argument('--width', type=int, default=6)
    a = ap.parse_args()

    new = set(slugs())
    before_seed, before_brands = expand_rows(new), brands_in(new)
    print(f'expansion leg over {len(new)} new categories · '
          f'seed rows now {before_seed} · brands in those categories {before_brands}',
          flush=True)

    if not a.skip_enum:
        if not gate_fleet(a.width):
            return 90
        rc = step(f'enumerate (fleet, {len(new)} categories)',
                  [sys.executable, f'{HERE}/enumerate_brands.py', '--expand',
                   '--only', ','.join(sorted(new))],
                  env={'RI_FLEET_WIDTH': str(a.width)})
        if rc != 0:
            print('ABORT: enumeration failed; nothing merged, nothing seeded.',
                  file=sys.stderr)
            return rc

    after_seed = expand_rows(new)
    print(f'\nseed rows for the new categories: {before_seed} -> {after_seed}', flush=True)
    if after_seed == 0:
        print('ABORT: the expansion produced no rows for the new categories. Seeding and '
              'collecting now would ship a wave that surfaces nobody, and the marker would '
              'claim otherwise.', file=sys.stderr)
        return 1

    # merge into the gazetteer, then seed to Postgres
    if step('merge into brands.csv', [sys.executable, f'{HERE}/gen_brands.py']) != 0:
        return 1
    after_brands = brands_in(new)
    print(f'brands in the new categories: {before_brands} -> {after_brands}', flush=True)
    if after_brands < before_brands:
        print(f'ABORT: the merge LOST {before_brands - after_brands} brands.',
              file=sys.stderr)
        return 1

    if step('seed to Postgres', [sys.executable, f'{ROOT}/worker/load.py', '--seed']) != 0:
        return 1

    # parity: every brand in the CSV must exist in the DB, or the sweep silently under-resolves
    if step('parity', [sys.executable, f'{HERE}/expansion_status.py', '--parity']) != 0:
        print('ABORT: seed parity failed — some brands are in the CSV but not the DB.',
              file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(MARKER), exist_ok=True)
    with open(MARKER, 'w') as f:
        json.dump({'at': time.strftime('%Y-%m-%dT%H:%M:%S'),
                   'categories': len(new),
                   'seed_rows': after_seed,
                   'brands_in_new_categories': after_brands}, f, indent=1)
    print(f'\nwrote {MARKER}', flush=True)
    print(f'EXPANSION COMPLETE {time.strftime("%H:%M:%S")}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
