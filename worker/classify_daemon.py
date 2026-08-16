#!/usr/bin/env python3
"""Continuous classification daemon — pipelined, never blocks collection.

Replaces the per-category `classify_daily.py --loop` burn, which was the
single largest waste in the pipeline. Measured on the live fleet:

    old: wait_for_slot() returns on ONE free slot, submit ONE job, sleep 8s
         -> 6.1-7.5 submits/min -> ~280 items/min, against a fleet worth 700
    new: burst-fill every free slot each tick, 56 of 60 slots, no round
         barrier -> ~700 items/min

Four structural changes, each measured in the audit:

1. BURST-FILL. The old loop's 8-second sleep, not the fleet, set the rate.
   Here one tick submits as many jobs as there are free slots.
2. NO ROUND BARRIER. The old code would not submit round n+1 until every
   batch of round n left `pending` — with p90 job latency 288s and max 420s,
   the fleet sat idle at every round tail waiting on one straggler. Here a
   freeing slot immediately takes the next batch.
3. INCREMENTAL COMMITS. The old code upserted labels once, at the very END of
   a whole cycle, so nothing reached Postgres for hours and a kill lost all of
   it. Here labels commit every COMMIT_EVERY or COMMIT_SECS, whichever first.
4. THE DB IS NOT HELD DURING FLEET WORK. The old cycle ran the entire fleet
   phase inside db.run(), pinning a session-pooler connection for hours.

Backlog paging is KEYSET ASCENDING, not `ORDER BY created_utc DESC LIMIT n`:
the old query measured 51.7s and, because a collector is writing newer rows
the whole time, its newest-first ordering starved the oldest tail forever.

    python3 worker/classify_daemon.py                 # run until backlog empty, then idle
    python3 worker/classify_daemon.py --once          # one drain, then exit
    python3 worker/classify_daemon.py --max-inflight 48
"""
import argparse
import json
import os
import signal
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import csv  # noqa: E402
import db  # noqa: E402
from classify import MODEL_VERSION, STAGE_LLM, LABEL_CODE, mark_target, load_known  # noqa: E402
from classify_codex import (  # noqa: E402
    batch_task, valid_result, journal, fleet, MODEL, SERVER, RUN, CACHE,
    burn_lock, burn_refresh, burn_release,
)

WINDOW_DAYS = 400
PAGE = 2000                # backlog rows per keyset page
BATCH = int(os.environ.get("CLASSIFY_BATCH", "40"))
TICK = 2.0                 # submit-loop period
JOB_TIMEOUT = 900   # was 420: jobs exceed it whenever the box is busy, and a
                    # timeout wastes the whole batch and re-queues it
STALE_AFTER = JOB_TIMEOUT + 180  # no out-file by now => the job died
COMMIT_EVERY = 500         # labels
COMMIT_SECS = 30


def pg_text(v, limit):
    """Model-authored text, made safe for a Postgres text column.

    A single NUL byte in one model's evidence span cost ~10 hours: psycopg
    rejects the whole executemany, the batch was requeued whole, and the same
    poison row killed every retry forever while the fleet kept judging. Text
    that came out of a model is untrusted input to the DB and gets cleaned
    here, at the one place every row is built.
    """
    s = str(v or "")
    if "\x00" in s:
        s = s.replace("\x00", "")
    return s[:limit]
READY_LOW = 20             # keep at least this many batches pre-cut
SUBMIT_STAGGER = 1.0       # seconds between submits inside one burst
MAX_ATTEMPTS = 3

_stop = threading.Event()


# ── backlog: keyset ascending, oldest first ─────────────────────────────────

class Backlog:
    """Pages the unlabelled anti-join oldest-first with a keyset cursor.

    Ascending is deliberate. Descending (the old behaviour) means an actively
    writing collector keeps refilling the head of the ordering, so the oldest
    mentions are served last, indefinitely. Ascending also lets Postgres prune
    monthly partitions and bounds the sort to one page.
    """

    def __init__(self, state, slugs=None):
        self.state = state
        self.slugs = slugs
        self.cursor = None       # (created_utc, doc_id)
        self.exhausted = False

    def reset(self):
        self.cursor = None
        self.exhausted = False

    def page(self):
        scope, params = "", [WINDOW_DAYS]
        if self.slugs:
            scope = ("\n              AND m.subreddit_id IN ("
                     "SELECT cs.subreddit_id FROM category_subreddits cs "
                     "JOIN categories c ON c.id = cs.category_id "
                     "WHERE c.slug = ANY(%s) AND cs.is_scoring)")
            params.append(list(self.slugs))
        keyset = ""
        if self.cursor:
            keyset = "\n              AND (m.created_utc, m.doc_id) > (%s, %s)"
            params.extend([self.cursor[0], self.cursor[1]])
        params.append(PAGE)

        def _q(c):
            with c.cursor() as cur:
                cur.execute(f"""
                    SELECT m.created_utc, m.doc_id, b.slug, s.name,
                           coalesce(t.link_title, ''), m.body, m.matched_form
                    FROM mentions m
                    JOIN brands b ON b.id = m.brand_id
                    JOIN subreddits s ON s.id = m.subreddit_id
                    LEFT JOIN threads t ON t.id = m.thread_id
                    LEFT JOIN mention_sentiment ms
                           ON ms.doc_id = m.doc_id AND ms.brand_id = m.brand_id
                    WHERE ms.doc_id IS NULL
                      AND m.created_utc >= now() - make_interval(days => %s){scope}{keyset}
                    ORDER BY m.created_utc, m.doc_id
                    LIMIT %s
                """, params)
                return cur.fetchall()

        rows = db.run(self.state, _q, label="backlog page")
        if rows:
            self.cursor = (rows[-1][0], rows[-1][1])
        else:
            self.exhausted = True
        return rows


# ── the daemon ──────────────────────────────────────────────────────────────

class Daemon:
    def __init__(self, args):
        self.args = args
        self.max_inflight = args.max_inflight
        # 3x cores. These jobs are mostly WAITING on the model API, so a
        # run-queue length of 2x cores is normal and healthy here; at 2.0 the
        # guard stalled the whole lane every time the collector got busy. The
        # failure it exists to prevent was load 154 on 10 cores, an order of
        # magnitude above this.
        self.load_ceiling = args.load_ceiling or (os.cpu_count() or 8) * 3.0
        self._load_warned = False
        self.state = {"conn": db.connect()}
        self.db_lock = threading.Lock()
        self.brand_names = {r["slug"]: r["brand"] for r in
                            csv.DictReader(open(os.path.join(REPO, "data", "brands.csv")))}
        self.backlog = Backlog(self.state, args.category)
        self.ready = []                 # pre-cut batches waiting for a slot
        self.inflight = {}              # bid -> {"t": submitted_at, "items": [...], "att": n}
        self.pending_labels = []        # harvested, not yet committed
        self.seen_files = {}            # out-file name -> mtime
        self.lock = threading.Lock()
        self.n_submitted = self.n_harvested = self.n_committed = 0
        self.n_skipped = 0
        # The item-level cache is the ONLY record of an entity-rejected item:
        # those never get a mention_sentiment row, so the anti-join returns
        # them forever and the fleet re-judges the same rejects every cycle.
        # 74,584 of 210,576 cached items (35%) were in that state — a third of
        # every cycle spent re-deciding what we already decided.
        self.known = set(load_known().keys())
        self.last_commit = time.time()
        self.started = time.time()

    # ---- item shaping ----
    def cut_batches(self, rows):
        items = []
        for created, doc_id, bslug, sub, title, body, form in rows:
            iid = f"{doc_id}:{bslug}"
            if iid in self.known:
                self.n_skipped += 1     # already judged; never re-spend on it
                continue
            off = (body or "").lower().find((form or "").lower())
            items.append({"item_id": iid, "brand_slug": bslug, "subreddit": sub,
                          "link_title": title, "doc_id": doc_id,
                          "marked": mark_target(body or "", form or "", max(0, off))})
        out = []
        for i in range(0, len(items), BATCH):
            chunk = items[i:i + BATCH]
            bid = _bid(chunk)
            out.append({"bid": bid, "items": chunk, "att": 0})
        return out

    def prefetch(self):
        """Keep `ready` stocked so the submit loop never waits on SQL."""
        while not _stop.is_set():
            try:
                with self.lock:
                    need = len(self.ready) < READY_LOW
                if need and not self.backlog.exhausted:
                    rows = self.backlog.page()
                    if rows:
                        batches = self.cut_batches(rows)
                        with self.lock:
                            self.ready.extend(batches)
                        continue
                if self.backlog.exhausted:
                    with self.lock:
                        idle = not self.ready and not self.inflight
                    if idle:
                        if self.args.once:
                            _stop.set()
                            return
                        time.sleep(30)
                        self.backlog.reset()   # sweep the window again
                        continue
                time.sleep(2)
            except Exception as e:
                print(f"  prefetch error: {str(e).splitlines()[0][:120]}", flush=True)
                time.sleep(10)

    # ---- fleet ----
    def free_slots(self):
        # LOAD GUARD, checked before the fleet is even asked. Every codex job
        # is a local node process, so concurrency and job LATENCY are not
        # independent: the fleet advertises 60 slots, but filling them on a
        # 10-core Mac drove load average to 154, made each job ~10x slower and
        # cut throughput to 58 items/min against the old serial loop's 280.
        # The old code never hit this only because its 8s sleep accidentally
        # capped real concurrency near 22. Slots are not capacity.
        try:
            load1 = os.getloadavg()[0]
        except OSError:
            load1 = 0.0
        if load1 > self.load_ceiling:
            if not self._load_warned:
                print(f"  load {load1:.0f} > {self.load_ceiling:.0f} — holding "
                      f"submissions", flush=True)
                self._load_warned = True
            return 0
        self._load_warned = False
        try:
            h = fleet.health()
            for e in (h if isinstance(h, list) else [h]):
                inner = e.get("health") or e
                if not e.get("ok", True):
                    return 0
                running = inner.get("running")
                if isinstance(running, int):
                    busy = running + (inner.get("queued") or 0)
                    return max(0, min(self.max_inflight - busy,
                                      self.max_inflight - len(self.inflight)))
        except Exception:
            pass
        # The health probe times out precisely when the box is busiest, and
        # treating UNKNOWN as FULL meant every timeout submitted nothing:
        # measured ~150 items/min against a theoretical 363 at p50=106s and 16
        # slots. Our OWN inflight count is authoritative for the jobs we
        # submitted, and the load guard above is the real safety rail — so an
        # unreadable probe falls back to local accounting instead of stalling.
        return max(0, self.max_inflight - len(self.inflight))

    def submit_loop(self):
        while not _stop.is_set():
            try:
                n = self.free_slots()
                for _ in range(n):
                    with self.lock:
                        if not self.ready:
                            break
                        b = self.ready.pop(0)
                    fp = os.path.join(RUN, f"out_{b['bid']}.json")
                    if os.path.exists(fp):
                        os.remove(fp)
                    journal({"daemon": True, "batch": b["bid"], "att": b["att"],
                             "t": time.time()})
                    try:
                        fleet.submit(batch_task(b["items"], self.brand_names, fp),
                                     server=SERVER, mode="workspace-write", model=MODEL,
                                     workspace=RUN, timeout=JOB_TIMEOUT,
                                     reasoning_effort="low")
                    except Exception as e:
                        print(f"  submit failed ({str(e)[:70]}) — requeue", flush=True)
                        with self.lock:
                            self.ready.insert(0, b)
                        time.sleep(5)
                        break
                    with self.lock:
                        self.inflight[b["bid"]] = {"t": time.time(), "items": b["items"],
                                                   "att": b["att"]}
                        self.n_submitted += 1
                    # STAGGER. Filling every slot in the same instant makes N
                    # node processes boot and call the model simultaneously;
                    # they contend, each job slows past its timeout, and a
                    # timeout wastes the entire batch. Measured: 68 of 223 jobs
                    # timed out when submitted in bursts. The old loop never saw
                    # this only because its 8s sleep staggered starts by
                    # accident. One second is enough to smear the boot spike
                    # while still filling 16 slots in 16s rather than 3 minutes.
                    time.sleep(SUBMIT_STAGGER)
                self.harvest_tick()
                self.reap_stale()
                self.maybe_commit()
                time.sleep(TICK)
            except Exception as e:
                print(f"  submit loop error: {str(e).splitlines()[0][:140]}", flush=True)
                time.sleep(5)

    def harvest_tick(self):
        """ONE scandir per tick, parse only files that are new or changed.

        The old code called harvest_out() twice per batch per 20s tick — 1,884
        file reads, JSON parses and cache rewrites per tick at 942 batches,
        just to print a progress line.
        """
        try:
            entries = list(os.scandir(RUN))
        except FileNotFoundError:
            return
        for e in entries:
            if not e.name.startswith("out_") or not e.name.endswith(".json"):
                continue
            bid = e.name[4:-5]
            with self.lock:
                rec = self.inflight.get(bid)
            if rec is None:
                continue
            try:
                mtime = e.stat().st_mtime
            except OSError:
                continue
            if self.seen_files.get(e.name) == mtime:
                continue
            self.seen_files[e.name] = mtime
            obj = _parse(e.path)
            if obj is None:
                continue                      # mid-write is not corruption
            ids = [it["item_id"] for it in rec["items"]]
            if not valid_result(obj, ids):
                continue
            keep = {}
            for it in rec["items"]:
                r = obj.get(it["item_id"])
                if not isinstance(r, dict):
                    continue
                if str(r.get("label", "")).lower() not in LABEL_CODE:
                    r["label"] = "abstain"
                r["_engine"] = MODEL
                keep[it["item_id"]] = r
            # the shared item-level cache: written ONCE per batch now
            cfp = os.path.join(CACHE, f"codex_{bid}.json")
            with open(cfp + ".tmp", "w") as f:
                json.dump(keep, f)
            os.replace(cfp + ".tmp", cfp)
            rows = []
            with self.lock:
                self.known.update(keep.keys())
            for it in rec["items"]:
                r = keep.get(it["item_id"])
                if not isinstance(r, dict) or r.get("entity_ok") is False:
                    continue
                rows.append((it["doc_id"], MODEL_VERSION,
                             LABEL_CODE.get(str(r.get("label", "abstain")).lower(), 3),
                             float(r.get("intensity") or 0), float(r.get("confidence") or 0),
                             STAGE_LLM, bool(r.get("comparative")),
                             bool(r.get("recommendation")), bool(r.get("category_gripe")),
                             pg_text(r.get("evidence"), 300), it["brand_slug"]))
            with self.lock:
                self.pending_labels.extend(rows)
                self.inflight.pop(bid, None)
                self.n_harvested += len(keep)
            try:
                os.remove(e.path)             # keeps RUN from growing without bound
            except OSError:
                pass

    def reap_stale(self):
        now = time.time()
        with self.lock:
            dead = [b for b, r in self.inflight.items() if now - r["t"] > STALE_AFTER]
        for bid in dead:
            with self.lock:
                rec = self.inflight.pop(bid, None)
            if not rec:
                continue
            if rec["att"] + 1 >= MAX_ATTEMPTS:
                print(f"  batch {bid} dead after {MAX_ATTEMPTS} attempts — dropped",
                      flush=True)
                continue
            fp = os.path.join(RUN, f"out_{bid}.json")
            if os.path.exists(fp):
                try:
                    os.remove(fp)
                except OSError:
                    pass
            with self.lock:
                self.ready.append({"bid": bid, "items": rec["items"], "att": rec["att"] + 1})

    # ---- commit ----
    def maybe_commit(self, force=False):
        with self.lock:
            n = len(self.pending_labels)
            due = force or n >= COMMIT_EVERY or (n and time.time() - self.last_commit > COMMIT_SECS)
            if not due or not n:
                return
            rows, self.pending_labels = self.pending_labels, []
            self.last_commit = time.time()

        def _ins(c):
            with c.cursor() as cur:
                cur.executemany("""
                    INSERT INTO mention_sentiment (doc_id, brand_id, model_version, label,
                        intensity, conf, stage, is_comparative, is_recommendation,
                        is_category_gripe, evidence_span)
                    SELECT %s, b.id, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    FROM brands b WHERE b.slug = %s
                    ON CONFLICT (doc_id, brand_id, model_version) DO NOTHING
                """, rows)
                c.commit()
        try:
            with self.db_lock:
                db.run(self.state, _ins, label="commit labels")
            with self.lock:
                self.n_committed += len(rows)
        except Exception as e:
            # A batch insert is all-or-nothing, so ONE malformed row blocks
            # every good row behind it — forever, since we requeue and retry.
            # Fall back to row-at-a-time: the good rows land and only the
            # genuinely bad one is dropped, named in the log.
            print(f"  batch commit failed ({str(e)[:90]}) — isolating bad rows",
                  flush=True)
            good = bad = 0

            def _ins_one(c, row=None):
                with c.cursor() as cur:
                    cur.execute("""
                        INSERT INTO mention_sentiment (doc_id, brand_id, model_version,
                            label, intensity, conf, stage, is_comparative,
                            is_recommendation, is_category_gripe, evidence_span)
                        SELECT %s, b.id, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        FROM brands b WHERE b.slug = %s
                        ON CONFLICT (doc_id, brand_id, model_version) DO NOTHING
                    """, row)
                    c.commit()

            for row in rows:
                try:
                    with self.db_lock:
                        db.run(self.state, lambda c, r=row: _ins_one(c, r),
                               label="commit label")
                    good += 1
                except Exception as re:
                    bad += 1
                    if bad <= 3:
                        print(f"    dropped doc_id={row[0]} brand={row[-1]}: "
                              f"{str(re)[:70]}", flush=True)
            print(f"  isolated: {good} committed, {bad} dropped", flush=True)
            with self.lock:
                self.n_committed += good

    def report(self):
        while not _stop.is_set():
            time.sleep(30)
            el = max(time.time() - self.started, 1)
            with self.lock:
                inf, rdy, com = len(self.inflight), len(self.ready), self.n_committed
                harv = self.n_harvested
            print(f"  [{el/60:5.1f}m] inflight {inf:>2}/{self.max_inflight} | ready {rdy:>3} "
                  f"| harvested {harv:>6} | committed {com:>6} "
                  f"| skipped {self.n_skipped:>6} "
                  f"| {harv/el*60:>5.0f} items/min", flush=True)
            burn_refresh()

    def run(self):
        threads = [threading.Thread(target=self.prefetch, daemon=True),
                   threading.Thread(target=self.report, daemon=True)]
        for t in threads:
            t.start()
        try:
            self.submit_loop()
        finally:
            self.maybe_commit(force=True)
            try:
                self.state["conn"].close()
            except Exception:
                pass


def _bid(chunk):
    import hashlib
    return hashlib.sha256("".join(it["item_id"] for it in chunk).encode()).hexdigest()[:16]


def _parse(fp):
    import re
    try:
        raw = open(fp).read()
        m = re.search(r"\{.*\}", raw, re.S)
        return json.loads(m.group(0) if m else raw)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", action="append", help="restrict to category slug(s)")
    ap.add_argument("--max-inflight", type=int,
                    default=int(os.environ.get("RI_MAX_INFLIGHT", "16")),
                    help="concurrent fleet jobs. NOT the fleet's slot count: 56 "
                         "drove load to 154 on 10 cores and cut throughput 5x; "
                         "24 still timed out 30%% of jobs. 16 is the measured "
                         "healthy ceiling on this box.")
    ap.add_argument("--load-ceiling", type=float, default=0,
                    help="hold submissions above this 1-min load average (default 2x cores)")
    ap.add_argument("--once", action="store_true", help="drain the backlog once, then exit")
    args = ap.parse_args()

    if not burn_lock():
        print("another classifier holds burn.lock — refusing to double-run", flush=True)
        return 1

    def _sig(*_):
        print("\nstopping — committing what is harvested…", flush=True)
        _stop.set()
    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    print(f"classify daemon: max_inflight={args.max_inflight} batch={BATCH} "
          f"model={MODEL}", flush=True)
    d = Daemon(args)
    try:
        d.run()
    finally:
        burn_release()
    print(f"done: {d.n_committed} labels committed", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
