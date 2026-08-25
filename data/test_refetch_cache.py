#!/usr/bin/env python3
"""A reader that returns None must remember that it did, or the callers re-pay for it.

Incident, 2026-08-23 (fix commit be79836, `data/discover_v2.py:752` — `qual_rec`):

  `qualify` walks 283,113 (category, subreddit) pairs over 29,658 unique subreddits, i.e.
  ~9.5 pairs per subreddit. Every other reader in that loop writes a cache file even for a
  bad answer — `measure_v2` stores `status="unavailable"` and thereby self-caches. `qual_rec`
  was the one reader that returned `None` for an unreachable / private / banned subreddit
  WITHOUT writing anything, so each of the 1,463 subs with no cached record paid a full
  network timeout plus 10-40s of backoff about nine times over: ~13,900 fetch attempts where
  1,463 would do, inside a ~100 QPM app budget.

  Cost: the stage was 52% done after 176 minutes and projecting ~5.7 hours; the post-mortem
  charges this ~3-4 hours of wall clock (docs/post-mortem-2026-08-24.md, row 3). It was
  invisible from the outside — the stage printed nothing — and was found only by sampling
  the live process, where libcrypto/libssl/dnssd dominated the stack and `_json` was noise.

  Fix: a per-run negative cache, the module-level `_fetch_failed` set at
  `data/discover_v2.py:700`. A failure is remembered for THIS run only. Nothing is written to
  disk, so the next run still retries — that is the documented behaviour ("retried next
  run"), and it is asserted here in both directions: no file on disk, and a fresh module DOES
  re-fetch.

What is checked is the DECISION, not the comment: the network call is stubbed with a counter
and the same unreachable subreddit is asked for six times.

  python3 data/test_refetch_cache.py
"""
import importlib.util
import json
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


# ─────────────────────────────────────────────────────────────────── harness
# discover_v2's module top imports the real Reddit client (credentials + a live socket),
# instantiates a CodexFleet, and mkdirs its state dirs under data/. None of that may happen
# in a test that runs offline beside a live pipeline, so the three imports are pre-empted in
# sys.modules and os.makedirs is neutered for the duration of the exec.

def _stub_modules():
    rc = types.ModuleType("reddit_client")

    def _forbidden(*a, **k):                       # replaced per-test; never a real call
        raise AssertionError("reddit_client.get called before the test stubbed it")
    rc.get = _forbidden
    rc.CACHE = "/dev/null"

    cf = types.ModuleType("codex_fleet")

    class _Fleet:                                  # discover_v2 does fleet = CodexFleet()
        def health(self):
            raise AssertionError("fleet contacted during an offline test")
    cf.CodexFleet = _Fleet

    dv = types.ModuleType("discover")
    dv.VENDOR_TOKENS = set()
    dv.SHIPPED = {}
    return {"reddit_client": rc, "codex_fleet": cf, "discover": dv}


def fresh(tmp, name):
    """A discover_v2 bound to a throwaway cache dir, with every network path stubbed.

    Cache dirs are rebound AFTER exec so the live data/.discover-v2/qual (28,195 real
    records) is never read: a real hit there would make the fetch counter meaningless.
    """
    saved = {k: sys.modules.get(k) for k in ("reddit_client", "codex_fleet", "discover")}
    real_makedirs = os.makedirs
    sys.modules.update(_stub_modules())
    os.makedirs = lambda *a, **k: None
    try:
        spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, "discover_v2.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    finally:
        os.makedirs = real_makedirs
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    for attr in ("QUAL", "CACHE", "BODIES", "TOPIC", "POSTURE", "V2", "EVID"):
        d = os.path.join(tmp, attr.lower())
        real_makedirs(d, exist_ok=True)
        setattr(m, attr, d)
    m._json_at.cache_clear()
    m._bodies_at.cache_clear()
    return m


def wire(m, alive, unreachable):
    """Stub the ONE network entry point qual_rec uses, counting calls per subreddit."""
    calls = []

    def get(path, params=None, bucket=None):
        sub = path.split("/")[2]
        calls.append(sub.lower())
        if sub.lower() in {s.lower() for s in unreachable}:
            return {"_err": "network"}             # what reddit_client returns on a dead fetch
        if sub.lower() in {s.lower() for s in alive}:
            now = m.time.time()
            kids = [{"data": {"title": f"t{i}", "created_utc": now - 3600, "stickied": False}}
                    for i in range(7)]
            return {"data": {"children": kids}}
        raise AssertionError(f"unexpected fetch for r/{sub}")
    m.rc.get = get
    return calls


N = 6                                              # >= 5, and near the measured ~9.5 pairs/sub
print("Redundant re-fetch of unreachable subreddits\n")

# 1. the incident itself: N asks, ONE fetch, and the same negative answer every time
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp, "dv2_one")
    calls = wire(m, alive=["GoodSub"], unreachable=["DeadSub"])

    answers = [m.qual_rec("DeadSub") for _ in range(N)]
    check(f"an unreachable subreddit is fetched EXACTLY once across {N} asks",
          calls.count("deadsub") == 1, f"{calls.count('deadsub')} fetches")
    check(f"all {N} asks still return the negative answer",
          answers == [None] * N, str(answers))

    # a positive record must NOT be collateral damage of the negative cache
    before = len(calls)
    goods = [m.qual_rec("GoodSub") for _ in range(N)]
    check(f"a reachable subreddit is fetched EXACTLY once across {N} asks",
          calls.count("goodsub") == 1, f"{calls.count('goodsub')} fetches")
    check("every ask for a reachable subreddit returns its record",
          all(isinstance(g, dict) and g["sub"] == "GoodSub" for g in goods), str(goods[:2]))
    check("the record carries the measurement qualify bars on (alive_n14)",
          goods[0].get("alive_n14") == 7 and goods[0].get("alive_ppw") == 3.5,
          str(goods[0].get("alive_n14")))
    check("no extra network calls beyond the one for the reachable sub",
          len(calls) - before == 1, f"{len(calls) - before}")

# 2. the cache is per-subreddit, not a single slot or a global "something failed" flag —
#    interleaved traffic is what qualify actually does
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp, "dv2_mix")
    calls = wire(m, alive=["Alive1", "Alive2"], unreachable=["Dead1", "Dead2"])
    for _ in range(N):
        for name in ("Dead1", "Alive1", "Dead2", "Alive2"):
            m.qual_rec(name)
    check("two distinct unreachable subs are each fetched once, not suppressed by one flag",
          calls.count("dead1") == 1 and calls.count("dead2") == 1,
          f"dead1={calls.count('dead1')} dead2={calls.count('dead2')}")
    check("interleaved reachable subs are still fetched once each",
          calls.count("alive1") == 1 and calls.count("alive2") == 1,
          f"alive1={calls.count('alive1')} alive2={calls.count('alive2')}")
    check(f"{4 * N} interleaved asks cost 4 fetches", len(calls) == 4, str(calls))
    check("failures are remembered under the lowercased name, as the disk cache is keyed",
          m.qual_rec("dEaD1") is None and calls.count("dead1") == 1,
          f"dead1={calls.count('dead1')}")

# 3. per-run scope: the negative cache lives in memory (module-level `_fetch_failed`) and is
#    NEVER persisted, so it cannot poison a later run. Both halves are asserted.
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp, "dv2_run1")
    calls = wire(m, alive=["GoodSub"], unreachable=["DeadSub"])
    for _ in range(N):
        m.qual_rec("DeadSub")
    m.qual_rec("GoodSub")

    check("the negative cache is an in-memory set on the module",
          isinstance(getattr(m, "_fetch_failed", None), set) and len(m._fetch_failed) == 1,
          repr(getattr(m, "_fetch_failed", None)))
    on_disk = sorted(os.listdir(m.QUAL))
    check("a failure writes NOTHING to the qual cache dir",
          "deadsub.json" not in on_disk, str(on_disk))
    check("a success DOES write its record to disk (that is how it self-caches)",
          "goodsub.json" in on_disk and json.load(open(os.path.join(m.QUAL, "goodsub.json")))
          ["alive_n14"] == 7, str(on_disk))

    # a second run over the same cache dir: the success is served from disk with no fetch,
    # the failure is retried exactly once — the documented "retried next run"
    m2 = fresh(tmp, "dv2_run2")
    for attr in ("QUAL", "CACHE", "BODIES", "TOPIC", "POSTURE", "V2", "EVID"):
        setattr(m2, attr, getattr(m, attr))
    calls2 = wire(m2, alive=["GoodSub"], unreachable=["DeadSub"])
    check("a new run starts with an empty negative cache", m2._fetch_failed == set(),
          repr(m2._fetch_failed))
    for _ in range(N):
        m2.qual_rec("DeadSub")
        m2.qual_rec("GoodSub")
    check("the next run RETRIES the failure (once), it is not poisoned by the last run",
          calls2.count("deadsub") == 1, f"{calls2.count('deadsub')} fetches")
    check("the next run re-fetches the success ZERO times (disk cache still serves it)",
          calls2.count("goodsub") == 0, f"{calls2.count('goodsub')} fetches")

# 4. the disk cache is still consulted first — a negative cache must not shadow a record that
#    landed on disk between runs (e.g. written by a parallel lane)
with tempfile.TemporaryDirectory() as tmp:
    m = fresh(tmp, "dv2_disk")
    calls = wire(m, alive=[], unreachable=["Later"])
    m.qual_rec("Later")
    m.atomic_json(os.path.join(m.QUAL, "later.json"),
                  {"sub": "Later", "alive_n14": 5, "alive_ppw": 2.5, "titles": []})
    got = m.qual_rec("Later")
    check("a record appearing on disk wins over the in-memory failure",
          isinstance(got, dict) and got["alive_n14"] == 5, repr(got))
    check("and reading it costs no fetch", calls.count("later") == 1, str(calls))

print()
if FAILS:
    print(f"{len(FAILS)} FAILURES")
    sys.exit(1)
print("all re-fetch cache checks pass")
