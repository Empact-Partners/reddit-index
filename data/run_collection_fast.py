#!/usr/bin/env python3
"""Collect in waves that each ship, instead of one 22-hour sweep that ships at the end.

`run_collection_all.py` sweeps every new core subreddit, then classifies, then publishes. That
is one atomic 15-22 hour block during which the 51 new boards show nothing, and it is why this
has felt like it takes days.

Nothing about that ordering is required. The sweep is per-subreddit and the site rebuilds from
whatever is in the database, so the work can be cut into waves that each end in a publish:

  wave 1   the 2 highest-signal core subs per category   -> every board has rows, in hours
  wave 2   the next 3 per category                       -> boards deepen
  wave 3   everything remaining                          -> full 90-day depth

Ordering is by `worth` (brand-bearing comments per hour, measured during discovery), so the
subs most likely to yield mentions run first. Waves are round-robin across categories rather
than a global sort, or the loudest three categories would take the whole first wave.

Same stages, same legal conditions: delete-sync runs before every publish, never skipped.
Resumable — completed subreddits are recorded on disk, so an interruption costs one sub.

  python3 data/run_collection_fast.py                 # all waves
  python3 data/run_collection_fast.py --wave 1        # just the first
  python3 data/run_collection_fast.py --plan          # show the waves, run nothing
"""
import argparse, collections, csv, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RI = os.path.join(HERE, '.roster-import')
STATE = os.path.join(HERE, '.pipeline', 'collected_subs.json')
# Written by the expansion leg once its brands are in the gazetteer AND seeded to Postgres.
EXPANSION_MARKER = os.path.join(HERE, '.pipeline', 'expansion_seeded')
sys.path.insert(0, os.path.join(ROOT, 'worker'))

# (subs per category, sweep depth in days). None = "everything remaining".
#
# Wave 1 is deliberately SHALLOW. Thread trees are cached on disk, so deepening a sub from 30
# to 90 days later pays only for the extra listings and the trees it has not already fetched —
# a 30-day first pass is very nearly free to re-deepen. That buys a populated board in under
# an hour instead of after the whole 90-day sweep, and the end state is still uniform 90-day
# depth, so nothing about score comparability changes once the last wave lands.
WAVES = [(2, 30), (2, 90), (3, 90), (None, 90)]

# subreddits swept before progress is written to disk. Small enough that a dropped link costs
# minutes, large enough that process startup is not the dominant cost.
CHUNK = 20

# Reddit's app-only budget is ~100 QPM and the client paces start-to-start, so 0.75s spends
# only 80 of it. The client also reads x-ratelimit-remaining and widens itself when the
# budget runs low, so this is bounded by the server's own signal rather than by hope.
FLOOR = os.environ.get('RI_SLEEP', '0.62')


def expansion_ready():
    """Has the outreach-pool expansion been seeded yet?

    A sweep resolves each comment tree against the gazetteer AS IT STORES IT. A brand seeded
    after its subreddit was swept is therefore not attached to that subreddit's stored
    threads, and the companies the 51 new categories were supposed to surface would score
    zero while every log line said success. Waiting costs hours; discovering it later costs
    the wave.

    Override with RI_SKIP_EXPANSION_GATE=1 only when the expansion is deliberately not part
    of this run."""
    if os.environ.get('RI_SKIP_EXPANSION_GATE') == '1':
        print('expansion gate: SKIPPED by RI_SKIP_EXPANSION_GATE=1', flush=True)
        return True
    return os.path.exists(EXPANSION_MARKER)


def new_slugs():
    return {p['slug'] for p in json.load(open(f'{RI}/map/clusters.json'))['proposed']}


def core_by_category():
    """New-category core subs, best signal first. `worth` = brand-bearing comments/hour."""
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
        out[k].sort(key=lambda x: -x[0])
    return out


def waves():
    """[(subs, days)] per wave. A wave may revisit earlier subs at greater depth."""
    by_cat = core_by_category()
    taken = collections.defaultdict(int)
    result = []
    prev_depth = 0
    for n, days in WAVES:
        batch = []
        for cat, subs in sorted(by_cat.items()):
            start = 0 if days > prev_depth and n is not None and taken[cat] else taken[cat]
            end = len(subs) if n is None else min(taken[cat] + n, len(subs))
            batch += [s for _, s in subs[start:end]]
            taken[cat] = end
        seen, uniq = set(), []          # one subreddit can be core for two categories
        for s in batch:
            if s.lower() not in seen:
                seen.add(s.lower()); uniq.append(s)
        result.append((uniq, days))
        prev_depth = max(prev_depth, days)
    return result


def depth_done():
    """subreddit -> deepest window already swept. Depth-aware, because a sub collected at 30
    days is not finished at 90."""
    try:
        d = json.load(open(STATE))
        return d if isinstance(d, dict) else {s: 90 for s in d}
    except Exception:
        return {}


def mark(subs, days):
    d = depth_done()
    for s in subs:
        d[s.lower()] = max(d.get(s.lower(), 0), days)
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(d, open(STATE, 'w'), indent=0, sort_keys=True)


def _db(fn, label):
    """Run a query with reconnect-on-drop. db.connect() retries the CONNECT, but a link that
    dies mid-query still raises, and on a flaky connection that would kill a multi-hour
    collection over a status read. db.run rolls back, reconnects and retries a transient
    failure while still surfacing a genuine query error immediately."""
    import db
    state = {"conn": db.connect()}
    try:
        return db.run(state, fn, label=label)
    finally:
        try:
            state["conn"].close()
        except Exception:
            pass


def seeded(subs):
    """sweep_sub SKIPS a sub that is not in the Postgres subreddits table, SILENTLY — it
    would report success having collected nothing."""
    def q(cx):
        with cx.cursor() as cur:
            cur.execute('SELECT lower(name) FROM subreddits WHERE lower(name) = ANY(%s)',
                        ([s.lower() for s in subs],))
            return {r[0] for r in cur.fetchall()}
    return _db(q, 'seeded')


def boards_live():
    """How many of the 51 new boards currently have at least one scored company."""
    new = new_slugs()

    def q(cx):
        with cx.cursor() as cur:
            cur.execute("""
                SELECT c.slug, count(DISTINCT m.brand_id)
                FROM categories c
                JOIN brands b ON b.primary_category_id = c.id
                JOIN mentions m ON m.brand_id = b.id
                JOIN mention_sentiment ms ON ms.brand_id = m.brand_id
                     AND ms.doc_id = m.doc_id
                WHERE c.slug = ANY(%s) AND ms.label IN (1,2)
                GROUP BY c.slug
            """, (sorted(new),))
            return dict(cur.fetchall())
    rows = _db(q, 'boards_live')
    return len(rows), len(new), rows


def step(name, args, env=None, fatal=True):
    print(f'\n=== {name} · {time.strftime("%H:%M:%S")} ===', flush=True)
    e = dict(os.environ, **(env or {}))
    rc = subprocess.call(args, cwd=ROOT, env=e)
    print(f'{name} exited {rc} · {time.strftime("%H:%M:%S")}', flush=True)
    if rc != 0 and fatal:
        print(f'ABORT at {name}.', file=sys.stderr)
    return rc


def classify_targets():
    new = new_slugs()
    fp = os.path.join(HERE, '.pipeline', 'classify_slugs.txt')
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    rows = {r['slug'] for r in csv.DictReader(open(f'{HERE}/brands.csv'))
            if r['source'] == 'roster-import-2026-08' or r['primary_category_slug'] in new}
    open(fp, 'w').write('\n'.join(sorted(rows)) + '\n')
    return fp, len(rows)


def ship(days, label):
    """classify -> score -> delete-sync -> publish. The half that turns mentions into pages."""
    fp, n = classify_targets()
    print(f'classify targets: {n} brand slugs', flush=True)
    step(f'{label}: classify', [sys.executable, f'{ROOT}/worker/classify_brands.py',
                                '--slugs-file', fp, '--allow-metered'], fatal=False)
    step(f'{label}: score', [sys.executable, f'{ROOT}/worker/score_db.py'], fatal=False)
    # decisions/0002: a legal condition of showing comment text at all. Never skipped,
    # never deferred to "the end of the run".
    step(f'{label}: delete-sync', [sys.executable, f'{ROOT}/worker/delete_sync.py',
                                   '--limit', '20000', '--publish-follows'], fatal=False)
    step(f'{label}: publish', [sys.executable, f'{ROOT}/worker/publish.py'], fatal=False)
    live, total, _ = boards_live()
    print(f'\n>>> {live}/{total} new boards now have at least one scored company', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wave', type=int, help='run only this wave (1-based)')
    ap.add_argument('--plan', action='store_true')
    a = ap.parse_args()

    ws = waves()
    if a.plan:
        for i, (w, days) in enumerate(ws, 1):
            print(f'wave {i}: {len(w)} subreddits at {days}d')
            print(f'   {", ".join(w[:12])}{" ..." if len(w) > 12 else ""}')
        live, total, _ = boards_live()
        print(f'\ncurrently {live}/{total} new boards have a scored company')
        print(f'reddit floor for the sweep: {FLOOR}s')
        return 0

    if not expansion_ready():
        print(f'ABORT: no expansion marker at {EXPANSION_MARKER}.\n'
              f'  The sweep resolves comments against the gazetteer as it stores them, so\n'
              f'  brands seeded afterwards are never attached to already-swept threads.\n'
              f'  Run the expansion leg first (enumerate_brands --expand -> load.py --seed),\n'
              f'  or set RI_SKIP_EXPANSION_GATE=1 to collect without it deliberately.',
              file=sys.stderr)
        return 1

    todo = [(i, w, d) for i, (w, d) in enumerate(ws, 1) if not a.wave or i == a.wave]

    for i, w, days in todo:
        already = depth_done()
        subs = [s for s in w if already.get(s.lower(), 0) < days]
        if not subs:
            print(f'\nwave {i}: nothing left to sweep at {days}d', flush=True)
            continue
        have = seeded(subs)
        missing = [s for s in subs if s.lower() not in have]
        if missing:
            print(f'ABORT: {len(missing)} subs are not in the subreddits table, e.g. '
                  f'{missing[:5]}. sweep_sub SKIPS these SILENTLY. Run worker/load.py --seed.',
                  file=sys.stderr)
            return 1

        print(f'\n########## WAVE {i}: {len(subs)} subreddits at {days}d '
              f'· {time.strftime("%H:%M:%S")} ##########', flush=True)

        # Sweep in chunks and bank each one. A wave is ~100 subreddits and hours long; on a
        # flaky link that is a long way to fall back. Chunked, an interruption costs at most
        # CHUNK subs, and the next run skips everything already banked.
        for c0 in range(0, len(subs), CHUNK):
            chunk = subs[c0:c0 + CHUNK]
            rc = step(f'wave {i}: sweep {c0 + 1}-{c0 + len(chunk)} of {len(subs)}',
                      [sys.executable, f'{ROOT}/worker/sweep.py', '--days', str(days),
                       '--only', ','.join(chunk)],
                      env={'RI_SLEEP': FLOOR})
            if rc != 0:
                # everything banked so far still counts; only this chunk is redone
                print(f'sweep failed at chunk {c0 // CHUNK + 1}. '
                      f'{c0} subreddits banked; rerun to continue from here.',
                      file=sys.stderr)
                return rc
            mark(chunk, days)
            print(f'  banked {c0 + len(chunk)}/{len(subs)}', flush=True)
        ship(days, f'wave {i}')

    print(f'\nCOLLECTION COMPLETE {time.strftime("%H:%M:%S")}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
