#!/usr/bin/env python3
"""Report where qualify actually is, every few minutes, and shout when it stops moving.

qualify's longest phase prints NOTHING for hours: it walks 283,113 (category, subreddit)
pairs in memory. On 2026-08-23 that silence hid a bug for three hours — the stage was
network-bound, re-fetching every unreachable subreddit about nine times, and nobody knew
because "no output" and "no progress" look identical from outside.

They are not identical from inside. The loop opens evidence/<category>.json as it goes, so
sampling the process's open files names the category it is on, and the category's row in
taxonomy-100.csv gives a percentage. That turns a silent phase into a progress bar.

Emits one line per sample. A line starting STALL means the position has not moved in
STALL_AFTER seconds while the process still holds CPU — the exact shape of the bug that
cost three hours.

  python3 data/progress_probe.py            # run until qualify exits
"""
import csv, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, '.pipeline', 'progress.log')
EVERY = 180          # sample cadence
STALL_AFTER = 900    # no movement for this long, with CPU burning, is a stall
SAMPLES = 300        # lsof passes per sample; the loop is fast, so we need many


def slugs():
    return [r['slug'] for r in csv.DictReader(open(f'{HERE}/taxonomy-100.csv'))]


def lane_pid():
    r = subprocess.run(['pgrep', '-f', 'discover_v2.py'], capture_output=True, text=True)
    pids = [int(p) for p in r.stdout.split() if p.strip()]
    return pids[0] if pids else None


def cpu_seconds(pid):
    r = subprocess.run(['ps', '-p', str(pid), '-o', 'time='], capture_output=True, text=True)
    t = r.stdout.strip()
    if not t:
        return None
    parts = [float(x) for x in re.split(r'[:.]', t)]
    if len(parts) == 3:      # MM:SS.ss
        return parts[0] * 60 + parts[1] + parts[2] / 100
    if len(parts) == 4:      # HH:MM:SS.ss
        return parts[0] * 3600 + parts[1] * 60 + parts[2] + parts[3] / 100
    return None


PIPELINE_LOG = os.path.join(HERE, '.pipeline', 'pipeline.log')


def position():
    """Position from the stage's own counter lines, not from open files.

    lsof was the original signal, but memoising the cache readers removed the file opens it
    depended on — a probe that reads a side effect breaks the moment the side effect is
    optimised away. discover_v2 now prints "cheap bars i/N" and "verdicts i/N" every 10,000
    pairs; that is a first-class signal that cannot be optimised out from under us.

    Returns (label, done, total) or None."""
    try:
        with open(PIPELINE_LOG, errors='replace') as f:
            tail = f.readlines()[-400:]
    except Exception:
        return None
    for line in reversed(tail):
        m = re.search(r'(cheap bars|verdicts) (\d+)/(\d+)', line)
        if m:
            return m.group(1), int(m.group(2)), int(m.group(3))
    return None


def say(line):
    stamped = f'{time.strftime("%H:%M:%S")} {line}'
    print(stamped, flush=True)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, 'a') as f:
        f.write(stamped + '\n')


def main():
    order = slugs()
    last_idx, last_move, last_cpu = None, time.time(), None
    say(f'probe started · {len(order)} categories in the loop')

    while True:
        pid = lane_pid()
        if pid is None:
            say('qualify is not running — probe exiting')
            return 0

        cpu = cpu_seconds(pid)
        burning = (last_cpu is not None and cpu is not None and cpu - last_cpu > 1)
        pos = position()

        if pos:
            label, done, total = pos
            pct = done / total * 100 if total else 0
            if last_idx is None or done > last_idx:
                mins = (time.time() - last_move) / 60
                rate = (f' · +{done - last_idx:,} pairs in {mins:.0f}m'
                        if last_idx is not None else '')
                last_idx, last_move = done, time.time()
                say(f'{label} {done:,}/{total:,} ({pct:.0f}%){rate}')
            elif time.time() - last_move > STALL_AFTER:
                say(f'STALL · {label} stuck at {done:,}/{total:,} for '
                    f'{(time.time() - last_move) / 60:.0f}m · '
                    f'cpu {"BURNING" if burning else "IDLE"} — investigate now, do not wait')
        else:
            # no counter line yet: this build predates them, or we are between loops.
            # CPU burn is still a liveness signal even without a position.
            if time.time() - last_move > STALL_AFTER:
                say(f'no counter for {(time.time() - last_move) / 60:.0f}m · '
                    f'cpu {"burning (alive, position unknown)" if burning else "IDLE — check it"}')
                last_move = time.time()

        last_cpu = cpu
        time.sleep(EVERY)


if __name__ == '__main__':
    sys.exit(main())
