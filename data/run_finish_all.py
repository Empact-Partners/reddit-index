#!/usr/bin/env python3
"""The last leg: outreach-pool expansion, then the wave-2 artifacts and the docs.

Runs AFTER data/run_collection_all.py. Same shape as the two runners before it — a finite
sequence where a failure ABORTS rather than retries — because that shape, not a smaller
concurrency number, is what stops a runaway.

  QA         the collection actually produced mentions, before anything is built on it
  QUALIFY    suppression (Monday board by domain AND folded name, CompanyOS, everyone
             already emailed) turns the expansion's candidates into approachable companies.
             The enumeration itself now lives in data/run_expansion.py and runs BEFORE
             collection — a brand seeded after its subreddit is swept is never attached to
             that subreddit's stored threads.
  MEASURE    parity, live counts, and the stamped split artifact
  QUEUES     rebuild wave 2 in partner-development, verifying every tier-A page renders a
             score rather than trusting the database
  GATES      both repos' validators, then commit

Fleet note: EXPAND is the only fleet stage here and it runs alone. Discovery and a
brand-expansion run submitting into the same slots deadlocked each other on 2026-08-22 —
each driver's no-progress timer resubmitting for progress the other could not make. This
sequence starts only after discovery is done, so there is one fleet lane, ever.

  python3 data/run_finish_all.py                # the whole leg
  python3 data/run_finish_all.py --skip-expand  # measure + queues only
"""
import argparse, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RI = os.path.join(HERE, '.roster-import')
PD = '/Users/vladshvets/Projects/empact-partners/partner-development'

sys.path.insert(0, os.path.expanduser('~/.claude/scripts'))


def slugs():
    return sorted(p['slug'] for p in json.load(open(f'{RI}/map/clusters.json'))['proposed'])


def step(name, args, cwd=ROOT, fatal=True):
    print(f'\n=== {name} · {time.strftime("%H:%M:%S")} ===', flush=True)
    rc = subprocess.call(args, cwd=cwd)
    print(f'{name} exited {rc} · {time.strftime("%H:%M:%S")}', flush=True)
    if rc != 0 and fatal:
        print(f'ABORT at {name}. Nothing retried by design; fix, then rerun.', file=sys.stderr)
    return rc


def gate_fleet(width):
    try:
        from fleet_preflight import preflight, reconcile
        preflight(want=width)
        # scoped: the fleet is shared between Claude Code sessions, and an unscoped cancel
        # killed seven of another session's jobs on 2026-08-22
        reconcile(match='brand')
        return True
    except SystemExit as e:
        print(f'preflight refused: {e}', file=sys.stderr)
        return False
    except Exception as e:
        print(f'preflight unavailable ({e}) — proceeding without it')
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-expand', action='store_true')
    ap.add_argument('--width', type=int, default=6)
    a = ap.parse_args()

    new = slugs()
    print(f'finishing leg over {len(new)} new categories', flush=True)

    # QA first. Everything downstream describes the collection, so if the collection is
    # empty the honest outcome is to stop, not to publish confident artifacts about nothing.
    if step('QA the expansion', [sys.executable, f'{HERE}/qa_expansion.py']) != 0:
        return 1

    if not a.skip_expand:
        # Enumeration already happened in run_expansion.py before collection. What is left
        # is turning those brands into approachable companies.
        if step('qualify the expansion roster (suppression)',
                [sys.executable, f'{HERE}/qualify_expansion_roster.py']) != 0:
            return 1

    if step('parity + counts + split',
            [sys.executable, f'{HERE}/expansion_status.py', '--parity', '--count', '--split']) != 0:
        return 1

    if step('rebuild wave-2 send queues',
            [sys.executable, f'{PD}/scripts/build_wave2_tiers.py', '--verify-urls'],
            cwd=PD) != 0:
        return 1

    if step('partner-development validator', [sys.executable, f'{PD}/scripts/validate.py'],
            cwd=PD) != 0:
        return 1

    # Messages state what this run did, not what it hopes happened. An earlier version
    # committed "Expansion collection complete" from a rehearsal in which collection had not
    # run at all, which is the kind of claim a git log is later trusted for.
    stamp = time.strftime('%Y-%m-%d %H:%M')
    for repo, msg in ((ROOT, f'Expansion measured and split after collection ({stamp})'),
                      (PD, f'Wave 2 rebuilt from the live index ({stamp})')):
        subprocess.call(['git', 'add', '-A'], cwd=repo)
        rc = subprocess.call(['git', 'diff', '--cached', '--quiet'], cwd=repo)
        if rc == 0:
            print(f'{os.path.basename(repo)}: nothing to commit', flush=True)
            continue
        step(f'commit {os.path.basename(repo)}', ['git', 'commit', '-q', '-m', msg],
             cwd=repo, fatal=False)

    print(f'\nFINISH COMPLETE {time.strftime("%H:%M:%S")}', flush=True)
    print('Not pushed. Review the diffs, then push — these are the artifacts an email is '
          'built from.', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
