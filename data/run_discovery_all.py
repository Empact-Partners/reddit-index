#!/usr/bin/env python3
"""Run the remaining discovery stages in order, then core selection and seed.

This is NOT the runaway that caused the 2026-08-21 OOM, and the difference is the point:

  the runaway          an uncapped RETRY loop that resubmitted 25-minute-timeout jobs on
                       top of in-flight ones, forever, deciding for itself to keep going
  this                 a fixed, finite sequence. Each stage preflights independently. A
                       stage that fails ABORTS the sequence — there is no retry, ever.
                       Between stages it re-checks that swap is not climbing.

Stages are individually resumable (discover_v2 keys its caches by subreddit, never by run),
so an abort costs nothing but the current stage.

  python3 data/run_discovery_all.py            # from wherever it left off
  python3 data/run_discovery_all.py --from qualify
"""
import argparse, csv, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RI = os.path.join(HERE, '.roster-import')
sys.path.insert(0, os.path.expanduser('~/.claude/scripts'))
from fleet_preflight import preflight, reconcile, swap_growth_mb   # noqa: E402

STAGES = ['enumerate', 'evidence', 'rescue', 'siblings', 'candidates', 'qualify']

def slugs():
    return [p['slug'] for p in json.load(open(f'{RI}/map/clusters.json'))['proposed']]

def core_count():
    return sum(1 for r in csv.DictReader(open(f'{HERE}/category-subreddits.csv'))
               if r.get('is_core') == 'True')

def enum_done():
    d = f'{HERE}/.discover-v2/enum'
    have = {f[4:-5] for f in os.listdir(d)} if os.path.isdir(d) else set()
    return len(set(slugs()) & have)

def run_stage(stage, width):
    print(f'\n=== {stage} · {time.strftime("%H:%M:%S")} ===', flush=True)
    preflight(want=width)
    # scoped to OUR jobs only. The fleet is shared between Claude Code sessions and a blanket
    # cancel killed seven of another session's long synthesis jobs on 2026-08-22.
    reconcile(match='subreddit')
    before = core_count()
    args = [sys.executable, f'{HERE}/discover_v2.py', '--stage', stage]
    for s in slugs():
        args += ['--category', s]
    rc = subprocess.call(args, cwd=ROOT, env=dict(os.environ, RI_FLEET_WIDTH=str(width)))
    after = core_count()
    print(f'{stage} exited {rc} · core slots {before} -> {after}', flush=True)
    if after != before:
        print('ABORT: qualify must preserve is_core — see data/test_csv_preservation.py',
              file=sys.stderr)
        return 2
    return rc

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='start', choices=STAGES, default=None)
    ap.add_argument('--width', type=int, default=6)
    a = ap.parse_args()
    todo = STAGES[STAGES.index(a.start):] if a.start else STAGES
    print(f'sequence: {" -> ".join(todo)} (width {a.width})', flush=True)

    for stage in todo:
        if stage == 'enumerate' and enum_done() >= len(slugs()):
            print('enumerate already complete, skipping', flush=True); continue
        rc = run_stage(stage, a.width)
        if rc != 0:
            print(f'STOPPED at {stage} (rc {rc}). Nothing retried by design; '
                  f'fix, then rerun with --from {stage}', flush=True)
            return rc
        g = swap_growth_mb()
        print(f'  swap growth between stages: {g:+.0f} MB', flush=True)
        if g > 400:
            print('STOPPING: swap is climbing between stages. The box needs headroom '
                  'before the next wave.', flush=True)
            return 3

    print(f'\n=== core selection (additive) · {time.strftime("%H:%M:%S")} ===', flush=True)
    before = core_count()
    rc = subprocess.call([sys.executable, f'{HERE}/select_core_subs.py',
                          '--add-categories', ','.join(slugs()),
                          '--budget', '20000', '--min', '8', '--max', '22', '--apply'],
                         cwd=ROOT)
    print(f'select_core_subs exited {rc} · core slots {before} -> {core_count()}', flush=True)
    if rc != 0: return rc

    print(f'\n=== seed · {time.strftime("%H:%M:%S")} ===', flush=True)
    rc = subprocess.call([sys.executable, f'{ROOT}/worker/load.py', '--seed'], cwd=ROOT)
    print(f'load --seed exited {rc}', flush=True)
    print(f'\nDISCOVERY COMPLETE {time.strftime("%H:%M:%S")}', flush=True)
    return rc

if __name__ == '__main__':
    sys.exit(main())
