#!/usr/bin/env python3
"""Subreddit discovery for the new categories — one stage per invocation, guarded.

This replaces /tmp/discovery_chain.sh, which caused the 2026-08-21 OOM: it looped for hours,
resubmitting 25-minute-timeout jobs on top of in-flight ones with no ceiling, on a box
already carrying 8 Claude sessions. The lesson is not "use a smaller number", it is that a
long unattended loop around a fleet is the wrong shape. This does ONE stage and exits.

Every invocation:
  1. PREFLIGHT — refuses if swap >=70%, load >=40, the wave exceeds the fleet cap, or codex
     processes are already running (~/.claude/scripts/fleet-preflight.py)
  2. RECONCILE — cancels server-side leftovers first, because a killed Bash call does not
     kill fleet jobs and resubmitting on top of them is how the loop became a memory bomb
  3. runs the named stage, then EXITS. Progress is on disk; the next stage is another call.

  python3 data/run_discovery_safe.py --status
  python3 data/run_discovery_safe.py --stage enumerate [--width 6]

Stages, in order: enumerate evidence rescue siblings candidates qualify
Then: python3 data/select_core_subs.py --add-categories <slugs> --apply
      python3 worker/load.py --seed
"""
import argparse, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RI = os.path.join(HERE, '.roster-import')
sys.path.insert(0, os.path.expanduser('~/.claude/scripts'))

STAGES = ['enumerate', 'evidence', 'rescue', 'siblings', 'candidates', 'qualify']

def slugs():
    return [p['slug'] for p in json.load(open(f'{RI}/map/clusters.json'))['proposed']]

def enum_done():
    d = os.path.join(HERE, '.discover-v2', 'enum')
    have = {f[4:-5] for f in os.listdir(d)} if os.path.isdir(d) else set()
    return set(slugs()) & have

def core_count(path=None):
    import csv
    p = path or os.path.join(HERE, 'category-subreddits.csv')
    return sum(1 for r in csv.DictReader(open(p)) if r.get('is_core') == 'True')

def status():
    sl = slugs()
    print(f'new categories        : {len(sl)}')
    print(f'enumerate outputs     : {len(enum_done())}/{len(sl)}')
    import csv
    rows = list(csv.DictReader(open(os.path.join(HERE, 'category-subreddits.csv'))))
    mapped = {r['category_slug'] for r in rows} & set(sl)
    print(f'categories with subreddit rows : {len(mapped)}/{len(sl)}')
    print(f'core slots (must stay 1741 until additive selection) : {core_count()}')
    try:
        from fleet_preflight import status as fs
        s = fs()
        print(f"machine               : swap {s['swap_pct']}% · load {s['load1']:.1f} · "
              f"codex {s['codex_procs']} · fleet {s['fleet']}")
    except Exception as e:
        print(f'machine               : preflight unavailable ({e})')

def run(stage, width):
    from fleet_preflight import preflight, reconcile
    preflight(want=width)              # raises SystemExit if the box cannot take it
    reconcile()                        # never resubmit on top of in-flight jobs

    before = core_count()
    args = [sys.executable, os.path.join(HERE, 'discover_v2.py'), '--stage', stage]
    for s in slugs():
        args += ['--category', s]
    env = dict(os.environ, RI_FLEET_WIDTH=str(width))
    print(f'running stage {stage} at width {width} over {len(slugs())} categories', flush=True)
    rc = subprocess.call(args, cwd=ROOT, env=env)
    print(f'stage {stage} exited {rc}', flush=True)

    after = core_count()
    if after != before:
        print(f'!! core slots changed {before} -> {after}. qualify must preserve is_core; '
              f'check data/test_csv_preservation.py', file=sys.stderr)
        return 2
    return rc

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', choices=STAGES)
    ap.add_argument('--width', type=int, default=6)
    ap.add_argument('--status', action='store_true')
    a = ap.parse_args()
    if a.status or not a.stage:
        status()
    else:
        sys.exit(run(a.stage, a.width))
