#!/usr/bin/env python3
"""Offline checks for the daily sweep's pure functions: no database, no Reddit, no model call.

  python3 tests/test_sweep_units.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
os.environ.setdefault("REDDIT_CLIENT_ID", "test")
os.environ.setdefault("REDDIT_CLIENT_SECRET", "test")
os.environ.setdefault("REDDIT_USER_AGENT", "test")

FAILS: list[str] = []


def check(name: str, ok: bool, detail="") -> None:
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))
    if not ok:
        FAILS.append(name)


# ---- the address rule (worker/resolve.py) ---------------------------------------------------------------
import resolve  # noqa: E402

for domain, slug, want in [
    ("github.com", "github-actions", False), ("google.com", "google-sheets", False), ("apple.com", "keynote", False),
    ("github.com", "git", False), ("gitlab.com", "git", False), ("duckduckgo.com", "duck-ai", False),
    ("openai.com", "chatgpt", False), ("x.ai", "grok", False),
    ("sheets.google.com", "google-sheets", True), ("hubspot.com", "hubspot", True), ("notion.so", "notion", True),
    ("linear.app", "linear-app", True), ("monday.com", "monday-com", True), ("getoutline.com", "outline", True),
    ("squareup.com", "square", True), ("surferseo.com", "surfer", True), ("zoho.com/crm", "zoho-crm", True),
    ("youtu.be", "youtube", True), ("keepersecurity.com", "keeper", True),
]:
    check(f"address {domain} names {slug}: {want}", resolve.address_names_product(domain, slug) is want)

# ---- GLM's answers (worker/classify_sweep.py) ------------------------------------------------------------
import classify_sweep as cs  # noqa: E402

check("glm: array answer", cs._glm_answer(["pos", 0.9, True]) == ("pos", 0.9))
check("glm: object answer", cs._glm_answer({"label": "neg", "confidence": 0.7, "entity_ok": True}) == ("neg", 0.7))
check("glm: not this product", cs._glm_answer(["neu", 0.8, False]) == ("reject", 0.8))
check("glm: 'false' as text is still not this product", cs._glm_answer(["neu", 0.8, "false"]) == ("reject", 0.8))
check("glm: explicit abstain is a label", cs._glm_answer(["abstain", 0.2, True]) == ("abstain", 0.2))
check("glm: unknown label is not an answer", cs._glm_answer(["mixed", 0.4, True]) is None)
check("glm: missing label is not an answer", cs._glm_answer({"entity_ok": True}) is None)
check("glm: garbage is not an answer", cs._glm_answer("pos") is None and cs._glm_answer(None) is None)
check("glm: prompt numbers items i1..iN", "### i1\n" in cs.glm_prompt([
    {"subreddit": "x", "thread": "t", "brand_name": "B", "text": "hello"}]))

import time as _time  # noqa: E402

_items = [{"subreddit": "x", "thread": "t", "brand_name": "B", "text": "hello"}] * 150
_out, _spend = cs.glm_judge(_items, in_flight=2, model="glm-5.3", deadline=_time.time() - 1)
check("glm: past the deadline no job starts and no item counts as asked",
      _spend["skipped_jobs"] == 2 and _spend["failed_jobs"] == 0 and not any(_spend["asked"]) and _out == [None] * 150)

# the provider's rate limit: retried after a wait, then answered; a lasting limit is reported as a limit
_calls = {"n": 0}
_real_job, _real_sleep = cs.glm_job, cs.time.sleep


def _flaky(chunk, model, timeout=900):
    _calls["n"] += 1
    if _calls["n"] <= 2:
        return None, {"_error": "rate limit exceeded: Rate limit reached for requests[x]"}
    return {f"i{j + 1}": ["pos", 0.9, True] for j in range(len(chunk))}, {"input_tokens": 10}


cs.glm_job, cs.time.sleep = _flaky, (lambda s: None)
_out, _spend = cs.glm_judge(_items[:200], in_flight=2, model="glm-5.3", deadline=_time.time() + 3600)
check("glm: a rate-limited batch is retried and answered",
      _spend["retried_jobs"] == 2 and _spend["failed_jobs"] == 0 and all(_spend["asked"]) and _out[0] == ("pos", 0.9))
cs.glm_job = lambda chunk, model, timeout=900: (None, {"_error": "Rate limit reached for requests"})
_out, _spend = cs.glm_judge(_items[:200], in_flight=2, model="glm-5.3", deadline=_time.time() + 3600)
check("glm: a lasting rate limit is reported as the limit, items not asked",
      _spend["rate_limited"] and _spend["failed_jobs"] == 2 and not any(_spend["asked"]) and _spend["retried_jobs"] == 6)
cs.glm_job = lambda chunk, model, timeout=900: (None, {"_error": "401 unauthorized"})
_out, _spend = cs.glm_judge(_items[:200], in_flight=2, model="glm-5.3", deadline=_time.time() + 3600)
check("glm: another error is not retried and not called a rate limit",
      not _spend["rate_limited"] and _spend["retried_jobs"] == 0 and _spend["failed_jobs"] == 2)
# the plan's weekly allowance used up (2026-10-07): no retries, the wall's reset time reported, not a rate limit
_WALL = ("rate limit exceeded: Weekly/Monthly Limit Exhausted. Your limit will reset at 2026-10-10 21:12:22"
         "[20251204-quota]")
check("glm: a wall error is read as UTC from Beijing time", cs.glm_wall_until(_WALL) == "2026-10-10T13:12:22+00:00")
check("glm: a plain rate limit is not a wall", cs.glm_wall_until("Rate limit reached for requests") is None)
cs.glm_job = lambda chunk, model, timeout=900: (None, {"_error": _WALL})
_out, _spend = cs.glm_judge(_items[:200], in_flight=2, model="glm-5.3", deadline=_time.time() + 3600)
check("glm: a used-up allowance is not retried and not called a rate limit",
      _spend.get("walled_until") == "2026-10-10T13:12:22+00:00" and _spend["retried_jobs"] == 0
      and not _spend["rate_limited"] and not any(_spend["asked"]))


class _Row:
    def __init__(self, v):
        self.v = v

    def fetchone(self):
        return (self.v,)


class _Conn:
    def __init__(self, v):
        self.v = v

    def execute(self, *a):
        return _Row(self.v)


check("glm: a wall a receipt recorded holds until its time", cs.known_glm_wall(_Conn("2999-01-01T00:00+00:00")))
check("glm: a past wall is forgotten", cs.known_glm_wall(_Conn("2020-01-01T00:00+00:00")) is None)
check("glm: no recorded wall", cs.known_glm_wall(_Conn(None)) is None)
check("glm: a wall whose time has passed lets GLM back in mid-run",
      not cs._walled({"glm_walled_until": "2020-01-01T00:00:00+00:00"}) and cs._walled({"glm_walled_until": "2999-01-01T00:00:00+00:00"}))
cs.glm_job, cs.time.sleep = _real_job, _real_sleep

# ---- Jev's precedence as arithmetic ----------------------------------------------------------------------
T = {"reject_below": 0.2, "product_at": 0.9, "label_at": {"pos": 0.76, "neg": 0.81, "neu": 0.77}}
check("jev: unanswered goes to GLM", cs.decide(None, T) is None)
check("jev: sure it is not the product is a rejection",
      cs.decide({"e": 0.1, "probs": {"pos": 1, "neg": 0, "neu": 0, "unsure": 0}}, T) == ("reject", 0.9))
check("jev: unsure it is the product goes to GLM",
      cs.decide({"e": 0.5, "probs": {"pos": 0.99, "neg": 0, "neu": 0, "unsure": 0}}, T) is None)
check("jev: sure product and sure feeling is a label",
      cs.decide({"e": 0.95, "probs": {"pos": 0.8, "neg": 0.1, "neu": 0.1, "unsure": 0}}, T) == ("pos", 0.8))
check("jev: a feeling under its threshold goes to GLM",
      cs.decide({"e": 0.95, "probs": {"pos": 0.1, "neg": 0.8, "neu": 0.1, "unsure": 0}}, T) is None)
check("jev: 'cannot tell' goes to GLM",
      cs.decide({"e": 0.95, "probs": {"pos": 0, "neg": 0, "neu": 0.1, "unsure": 0.9}}, T) is None)

# ---- collection order (worker/collect.py) ----------------------------------------------------------------
import datetime as _dt  # noqa: E402
import collect  # noqa: E402

_now = _dt.datetime(2026, 10, 5, tzinfo=_dt.timezone.utc)
check("collect: never visited is the most overdue", collect.overdue(None, False, _now) == float("inf"))
check("collect: a core subreddit a day old is due once", round(collect.overdue(_now - _dt.timedelta(days=1), True, _now), 3) == 1.0)
check("collect: a non-core subreddit six days old outranks a core one a day old",
      collect.overdue(_now - _dt.timedelta(days=6), False, _now) > collect.overdue(_now - _dt.timedelta(days=1), True, _now))
check("collect: a non-core subreddit a day old waits behind a core one a day old",
      collect.overdue(_now - _dt.timedelta(days=1), False, _now) < collect.overdue(_now - _dt.timedelta(days=1), True, _now))

# ---- the publisher's deadline (worker/site_publish.py) ----------------------------------------------------
import site_publish  # noqa: E402

site_publish.DEADLINE[0] = _time.time() - 1
_r = site_publish.fetch("https://example.invalid", "/x/", "h")
check("publish: no request starts after the run's end", _r["ok"] is False and _r["status"] is None and "error" in _r)
site_publish.DEADLINE[0] = None

check("collect: a due partner-priority subreddit goes before a more overdue ordinary one",
      collect.rank(1.2, True, False) < collect.rank(5.0, False, True))
check("collect: a partner-priority subreddit not yet due waits behind a due one",
      collect.rank(0.4, True, False) > collect.rank(1.1, False, False))
check("collect: a vendor-named subreddit is never visited, whatever its case",
      collect.without_vendor(["AZURE", "sysadmin", "ClaudeAI", "devops"], {"azure", "claudeai"}) == (["sysadmin", "devops"], 2))
check("collect: with no vendor-named subreddit the list is unchanged",
      collect.without_vendor(["sysadmin", "devops"], set()) == (["sysadmin", "devops"], 0))
_m, _c, _f = collect.merge_case({"Accounting": ["accounting", "erp"], "accounting": ["erp", "tax"], "devops": ["ci"]},
                               {"accounting"}, {"accounting": _now, "Accounting": _now - _dt.timedelta(days=2)})
check("collect: two spellings of one subreddit are one visit, under the spelling visited last",
      sorted(_m) == ["accounting", "devops"] and _f == 1)
check("collect: the merged subreddit carries both spellings' categories, each once",
      _m["accounting"] == ["accounting", "erp", "tax"])
check("collect: the merged subreddit is core if either spelling was", _c == {"accounting"})
_m2, _c2, _f2 = collect.merge_case({"Big4": ["a"], "big4": ["b"]}, {"Big4"}, {})
check("collect: never visited under either spelling, the first in sort order is kept",
      list(_m2) == ["Big4"] and _m2["Big4"] == ["a", "b"] and _c2 == {"Big4"} and _f2 == 1)
_m3, _, _f3 = collect.merge_case({"Big4": ["a"], "big4": ["b"]}, set(), {"big4": _now})
check("collect: a spelling with a visit beats one without", list(_m3) == ["big4"] and _f3 == 1)

# ---- the takedown judge (worker/takedown.py) -------------------------------------------------------------
import takedown as td  # noqa: E402


def child(name, **d):
    return {"data": {"name": name, **d}}


asked = ["t1_a", "t1_b", "t1_c", "t1_d", "t1_e", "t3_f"]
got = td.judge([child("t1_a", body="fine", author="u", edited=False),
                child("t1_b", body="[deleted]", author="[deleted]"),
                child("t1_c", body="[removed]", author="u"),
                child("t1_d", body="new text", author="u", edited=2000.0),
                child("t3_f", selftext="", author="u", removed_by_category="moderator")],
               asked, {d: 1000.0 for d in asked})
check("takedown: alive stays", got["t1_a"] == "alive")
check("takedown: deleted author is gone", got["t1_b"] == "source_deleted")
check("takedown: removed body is gone", got["t1_c"] == "source_deleted")
check("takedown: edited after we stored it", got["t1_d"] == "source_edited")
check("takedown: not in Reddit's answer is gone", got["t1_e"] == "source_deleted")
check("takedown: a post removed by moderators is gone even with its title kept", got["t3_f"] == "source_deleted")

# ---- the backfill wrapper's night guard (ops/backfill_run.py, review round 3) -----------------------------
import datetime as _dt  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "ops"))
import backfill_run as bfr  # noqa: E402

_t = _dt.datetime(2026, 10, 6, 21, 0, tzinfo=_dt.timezone.utc)
check("backfill: a day job is stopped by 23:40 UTC that day", bfr.night_deadline(_t) == _t.replace(hour=23, minute=40))
check("backfill: 21:00 UTC is outside the night", not bfr.in_night(_t))
check("backfill: 23:45 UTC is inside the night", bfr.in_night(_t.replace(hour=23, minute=45)))
check("backfill: 03:00 UTC is inside the night", bfr.in_night(_t.replace(hour=3)))
check("backfill: 05:30 UTC is outside the night", not bfr.in_night(_t.replace(hour=5, minute=30)))

# ---- the Railway backfill's queue (worker/run_daily.py backfill_subs, decision 0018) ----------------------------
import tempfile as _tf  # noqa: E402
import run_daily as _rd  # noqa: E402
_csv = _tf.NamedTemporaryFile("w", suffix=".csv", delete=False)
_csv.write("category_slug,subreddit,is_core\nb,Zeta,True\na,beta,True\na,Alpha,True\nb,alpha,True\na,gamma,False\nc,x,True\n")
_csv.close()
check("backfill: core subreddits, category by category in the given order, each once, lower case",
      _rd.backfill_subs(["a", "b"], _csv.name) == ["alpha", "beta", "zeta"], _rd.backfill_subs(["a", "b"], _csv.name))

# ---- work that cannot yield anything is not done (worker/collect.py: worth_storing, choose_trees) ---------------
_t0 = 1_760_000_000.0
check("collect: a post that names a brand is stored whatever its age or comments",
      collect.worth_storing({"num_comments": 0, "created_utc": _t0 - 30 * 86400}, True, _t0))
check("collect: a post with a comment is stored (its tree can be read)",
      collect.worth_storing({"num_comments": 1, "created_utc": _t0 - 30 * 86400}, False, _t0))
check("collect: a young post with no comment yet is stored (it can still get one)",
      collect.worth_storing({"num_comments": 0, "created_utc": _t0 - 47 * 3600}, False, _t0))
check("collect: a post with no brand and no comment after 48 hours is not stored",
      not collect.worth_storing({"num_comments": 0, "created_utc": _t0 - 49 * 3600}, False, _t0)
      and not collect.worth_storing({"num_comments": None, "created_utc": _t0 - 400 * 3600}, False, _t0))
_cands = [("t3_a", "A", 0, None, None),      # never read, no comment stored, none now
          ("t3_b", "B", 5, None, None),      # never read, 5 stored, 9 now
          ("t3_c", "C", 0, None, None),      # never read, none stored, 3 now (it got comments since)
          ("t3_d", "D", 7, _now, 7),         # read at 7, still 7
          ("t3_e", "E", 7, _now, 7),         # read at 7, now 20
          ("t3_f", "F", 2, _now, None),      # read before the count was kept, 4 now
          ("t3_g", "G", 9, _now, 9),         # read, not known now
          ("t3_h", "H", 4, None, None)]      # never read, not known now: the stored 4 stands
_pick, _skip = collect.choose_trees(_cands, {"t3_a": 0, "t3_b": 9, "t3_c": 3, "t3_d": 7, "t3_e": 20, "t3_f": 4}, 24)
check("collect: threads never read come first, most comments first; then threads that grew, most growth first",
      [x[0] for x in _pick] == ["t3_b", "t3_h", "t3_c", "t3_e", "t3_f"], _pick)
check("collect: a thread with no comment, and a read thread that has not grown or is not known, are not read",
      _skip == {"no_comments": 1, "unchanged": 2}, _skip)
check("collect: the limit cuts from the end of that order",
      [x[0] for x in collect.choose_trees(_cands, {"t3_b": 9, "t3_c": 3, "t3_e": 20}, 2)[0]] == ["t3_b", "t3_h"])
check("collect: the titles travel with the ids", dict(_pick)["t3_e"] == "E")
_real_get = collect.rc.get
collect.rc.get = lambda path, params=None, bucket="misc", tries=3, use_cache=True: (
    {"data": {"children": [{"kind": "t3", "data": {"name": "t3_x", "num_comments": 12}},
                           {"kind": "t3", "data": {"name": "t3_y", "num_comments": None}},
                           {"kind": "t1", "data": {"name": "t1_z"}}]}} if path == "/api/info" else {"_err": 500})
try:
    check("collect: one /api/info call gives the comment counts now", collect.info_counts(["t3_x", "t3_y"]) == {"t3_x": 12, "t3_y": 0})
    collect.rc.get = lambda *a, **k: {"_err": 503}
    check("collect: a failed /api/info call is 'not known' for every thread", collect.info_counts(["t3_x"]) == {})
    _pages = [{"data": {"after": None, "children": [
        {"kind": "t3", "data": {"id": "n1", "created_utc": 200.0, "num_comments": 4}},
        {"kind": "t3", "data": {"id": "o1", "created_utc": 50.0, "num_comments": 31}}]}}]
    collect.rc.get = lambda *a, **k: _pages[0]
    _seen = {}
    _posts, _ok, _capped = collect.d.fetch_new("x", 100.0, seen=_seen)
    check("listing: posts newer than the watermark are returned; every post on the page is counted in `seen`",
          [p["id"] for p in _posts] == ["n1"] and _ok and not _capped and _seen == {"t3_n1": 4, "t3_o1": 31}, (_posts, _seen))
finally:
    collect.rc.get = _real_get
check("collect: the comment count on a tree's own post is read; a failed tree has none",
      collect.tree_count([{"data": {"children": [{"data": {"num_comments": 17}}]}}, {}]) == 17 and collect.tree_count({"_err": 404}) is None)

# ---- comment trees in flight side by side (worker/collect.py fetch_trees, worker/reddit_client.py) -------------
import concurrent.futures as _cf  # noqa: E402
import threading as _th  # noqa: E402
import time as _time  # noqa: E402

_revisit = [(f"t3_{i}", f"title {i}") for i in range(9)]
_real_tree_fresh = collect.d.tree_fresh
_in_flight, _peak, _lk = [0], [0], _th.Lock()


def _slow_tree(post_id):
    with _lk:
        _in_flight[0] += 1
        _peak[0] = max(_peak[0], _in_flight[0])
    _time.sleep(0.08)
    with _lk:
        _in_flight[0] -= 1
    return [post_id]


collect.d.tree_fresh = _slow_tree
try:
    _asked, _w = [], [0.0]
    _t = _time.time()
    _serial = list(collect.fetch_trees(None, _revisit, lambda: _asked.append(1), _w))
    _serial_s = _time.time() - _t
    check("trees one at a time: every thread, in order, asked before each",
          [x[0] for x in _serial] == [r[0] for r in _revisit] and [x[2] for x in _serial] == [[str(i)] for i in range(9)]
          and len(_asked) == 9 and _peak[0] == 1, (_peak[0], len(_asked)))
    check("trees one at a time: the waiting is counted", 0.6 < _w[0] <= _serial_s + 0.01, _w[0])
    _peak[0] = 0
    _pool = _cf.ThreadPoolExecutor(max_workers=3)
    _asked2, _w2 = [], [0.0]
    _t = _time.time()
    _par = list(collect.fetch_trees(_pool, _revisit, lambda: _asked2.append(1), _w2))
    _par_s = _time.time() - _t
    check("trees three at a time: the same threads in the same order",
          [(x[0], x[1], x[2]) for x in _par] == [(x[0], x[1], x[2]) for x in _serial] and len(_asked2) == 9)
    check("trees three at a time: never more than three in flight, and more than one", 1 < _peak[0] <= 3, _peak[0])
    check("trees three at a time: faster than one at a time", _par_s < _serial_s * 0.6, (_par_s, _serial_s))

    class _Cap(Exception):
        pass
    _n = [0]

    def _cap_at_5():
        _n[0] += 1
        if _n[0] > 5:
            raise _Cap("the cap")
    _got = []
    try:
        for _x in collect.fetch_trees(_pool, _revisit, _cap_at_5, [0.0]):
            _got.append(_x[0])
    except _Cap:
        pass
    check("trees three at a time: a cap raised before a request stops the fetch, nothing later is started",
          _n[0] == 6 and len(_got) <= 5, (_n[0], _got))
    _started = []

    def _counting_tree(post_id):
        _started.append(post_id)
        _time.sleep(0.1)
        return [post_id]
    collect.d.tree_fresh = _counting_tree
    _gen = collect.fetch_trees(_pool, _revisit, lambda: None, [0.0])
    next(_gen)
    _gen.close()               # the caller left after one tree (an error of its own)
    _time.sleep(0.5)
    check("trees three at a time: when the caller leaves, nothing more is started than was already in flight",
          len(_started) <= 1 + 3, _started)

    def _failing_tree(post_id):
        if post_id == "2":
            raise OSError("one tree failed")
        _time.sleep(0.05)
        return [post_id]
    collect.d.tree_fresh = _failing_tree
    _seen, _err = [], None
    try:
        for _x in collect.fetch_trees(_pool, _revisit, lambda: None, [0.0]):
            _seen.append(_x[0])
    except OSError as e:
        _err = e
    check("trees three at a time: a tree that raised is raised to the caller, in its place in the order",
          _err is not None and _seen == ["t3_0", "t3_1"], (_err, _seen))
    _pool.shutdown(wait=True)
finally:
    collect.d.tree_fresh = _real_tree_fresh

import io as _io  # noqa: E402
import json as _json  # noqa: E402
import urllib.error as _ue  # noqa: E402
import email.message as _em  # noqa: E402
import reddit_client as _rc  # noqa: E402


class _Resp(_io.BytesIO):
    def __init__(self, body):
        super().__init__(body)
        self.headers = {"x-ratelimit-remaining": "500", "x-ratelimit-reset": "300"}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


_starts, _n429 = [], [0]


def _fake_urlopen(req, timeout=40):
    with _lk:
        _starts.append(_time.time())
        k = len(_starts)
    _time.sleep(0.25)   # the request's own time, longer than the period
    if k == 4 and not _n429[0]:
        _n429[0] = 1
        h = _em.Message()
        h["x-ratelimit-reset"] = "1"
        raise _ue.HTTPError(req.full_url, 429, "Too Many Requests", h, _io.BytesIO(b""))
    return _Resp(_json.dumps({"n": k}).encode())


_saved = (_rc.urllib.request.urlopen, _rc._access_token, _rc.SLEEP, _rc._adaptive[0])
_rc.urllib.request.urlopen, _rc._access_token = _fake_urlopen, (lambda tries=6: "token")
_rc.SLEEP = _rc._adaptive[0] = 0.1
try:
    _c0 = _rc.stats()["calls"]
    _t = _time.time()
    with _cf.ThreadPoolExecutor(max_workers=3) as _p:
        _out = list(_p.map(lambda i: _rc.get(f"/t{i}", None, use_cache=False), range(3)))
    _three_s = _time.time() - _t
    _gaps = [b - a for a, b in zip(sorted(_starts), sorted(_starts)[1:])]
    check("client, three threads: one request starts per period, never two together",
          len(_starts) == 3 and min(_gaps) >= 0.095, _gaps)
    check("client, three threads: the requests overlap (three 0.25 s requests in well under 0.75 s)",
          _three_s < 0.6 and all(isinstance(o, dict) and "n" in o for o in _out), _three_s)
    _starts.clear()
    _starts.extend([0.0] * 3)   # the next request is the fourth: it answers 429, wait 1 s
    _t = _time.time()
    with _cf.ThreadPoolExecutor(max_workers=3) as _p:
        _out = list(_p.map(lambda i: _rc.get(f"/u{i}", None, use_cache=False), range(3)))
    _real = sorted(x for x in _starts if x)
    _after_429 = [x for x in _real[1:] if x - _real[0] > 0.3]   # the starts that came after the 429 was answered
    check("client, three threads: after a 429 nobody starts before the wait it named has passed",
          all(isinstance(o, dict) and "n" in o for o in _out) and len(_real) == 4
          and min(_after_429) - _real[0] >= 0.25 + 1.0 - 0.05, [round(x - _real[0], 2) for x in _real])
    check("client: every answer is counted once", _rc.stats()["calls"] - _c0 == 6, _rc.stats()["calls"] - _c0)
finally:
    _rc.urllib.request.urlopen, _rc._access_token, _rc.SLEEP, _rc._adaptive[0] = _saved
    _rc._hold_until[0] = 0.0

import day_passes as _dp  # noqa: E402
_wf = _tf.NamedTemporaryFile("w", suffix=".txt", delete=False)
_wf.write("3\n")
_wf.close()
_bad = _tf.NamedTemporaryFile("w", suffix=".txt", delete=False)
_bad.write("12")
_bad.close()
check("day passes: the width file's number is the next pass's width", _dp.tree_workers(_wf.name) == 3)
check("day passes: no file, or a number outside 1 to 4, leaves the sweep's own setting",
      _dp.tree_workers("/nonexistent/tree-workers") is None and _dp.tree_workers(_bad.name) is None)
_refused = 0
for _stages, _end in (("collect'); select 1; --", "23:15"), ("collect,classify", "23:15'; --"), ("", "23:15")):
    try:
        _dp.request(_stages, 100, _end, 0.1)
    except ValueError:
        _refused += 1
check("day passes: a stage list or an end time of any other shape is refused before anything is sent", _refused == 3)

# ---- which changed pages go out first (worker/site_publish.py pick) -------------------------------------------
import site_publish as _sp  # noqa: E402
_rows = [(i, f"s{i}", "h", False, True, i % 3 == 0) for i in range(30)]   # in waiting order; every third: own data changed
_p10 = _sp.pick(_rows, 10)
check("publish: with fewer slots than pages, pages whose own data changed go first, longest-waiting first",
      [r[0] for r in _p10[:8]] == [0, 3, 6, 9, 12, 15, 18, 21], [r[0] for r in _p10])
check("publish: a fifth of the slots goes to the longest-waiting pages whatever changed on them",
      [r[0] for r in _p10[8:]] == [1, 2] and len(_p10) == 10, [r[0] for r in _p10])
check("publish: with slots for every page, every page goes out in waiting order",
      [r[0] for r in _sp.pick(_rows, 30)] == list(range(30)) and len(_sp.pick(_rows, 99)) == 30)
_few = [(i, f"s{i}", "h", False, True, i == 0) for i in range(30)]
check("publish: fewer own-data pages than their slots: the rest of the slots go to the longest-waiting",
      [r[0] for r in _sp.pick(_few, 10)] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
check("publish: no slots, nothing goes out", _sp.pick(_rows, 0) == [])

# ---- the node counter read by the sweep (worker/meter.py) and the day's line (run_daily.Run.day_line_reason) -------
import meter as _mt  # noqa: E402
_metrics_text = """# HELP node_network_transmit_bytes_total Network device statistic transmit_bytes.
node_network_transmit_bytes_total{supabase_project_ref="x",service_type="db",device="ens5"} 1.463055024361e+12
node_network_transmit_bytes_total{supabase_project_ref="x",service_type="db",device="lo"} 9.9e+12
node_network_receive_bytes_total{supabase_project_ref="x",service_type="db",device="ens5"} 2.3e+10
"""
check("meter: the counter is the transmit total of every interface but loopback",
      _mt.parse(_metrics_text) == 1463055024361.0, _mt.parse(_metrics_text))
check("meter: no transmit series is 'not known', never zero", _mt.parse("node_memory_MemTotal_bytes 1e9") is None)
check("meter: a counter that is not a finite number is 'not known'",
      _mt.parse('node_network_transmit_bytes_total{device="ens5"} NaN') is None
      and _mt.parse('node_network_transmit_bytes_total{device="ens5"} +Inf') is None)
_old_env = (os.environ.pop("SUPABASE_METRICS_KEY", None), os.environ.get("SUPABASE_PROJECT_REF"))
check("meter: without a key in the environment nothing is read", _mt.read() is None)


class _MeterConn:
    def __init__(self, older):
        self.older, self.kept, self.closed = older, [], False

    def execute(self, sql, params=None):
        if sql.startswith("insert into public.egress_counter"):
            self.kept.append(params)
        rows = [self.older] if ("egress_counter where at <=" in sql and self.older) else []
        return type("R", (), {"fetchone": lambda s: rows[0] if rows else None, "rowcount": 0})()

    def rollback(self):
        pass


_then = _now - _dt.timedelta(hours=25)
check("meter: the 24 hours are the reading now less the newest reading at least 24 hours old",
      _mt.used_24h(_MeterConn((1_000_000_000_000, _then)), 1_001_500_000_000)[0] == 1_500_000_000)
check("meter: no reading old enough, or a counter that went backwards, is 'not known'",
      _mt.used_24h(_MeterConn(None), 5)[0] is None and _mt.used_24h(_MeterConn((10, _then)), 5)[0] is None)

_real_read = _mt.read
_reads = [1_001_000_000_000.0]
_mt.read = lambda timeout=30.0: _reads[0]
try:
    class _A:
        manual, max_calls, takedown_calls, max_mentions, max_egress_gb, day_end, options, stages = True, None, None, None, None, None, {}, []
    _sched = {"caps": {"reddit_calls": 1, "takedown_calls": 1, "mentions": 1, "minutes": 10, "egress_gb": 0.7}, "day_line_gb": 1.9}
    _wal = _rd.wal_bytes
    _rd.wal_bytes = lambda conn: 0
    _c = _MeterConn((1_000_000_000_000, _then))
    _night = _rd.Run(_c, _sched, _A())
    _night._meter_at = 0
    _reads[0] = 1_009_000_000_000.0
    check("day line: the night's run is never stopped by it, whatever the counter says", _night.day_line_reason() is None)
    _A.day_end = _dt.time(23, 15)
    _reads[0] = 1_001_200_000_000.0
    _day = _rd.Run(_MeterConn((1_000_000_000_000, _then)), _sched, _A())
    check("day line: a daytime pass under the line goes on (and a reading younger than three minutes is not repeated)",
          _day.day_line_reason() is None and _day.meter["readings"] == 1 and _day.meter["last_24h_gb"] == 1.2)
    _reads[0] = 1_002_500_000_000.0
    _late = _rd.Run(_MeterConn((1_000_000_000_000, _then)), _sched, _A())
    check("day line: a pass that starts with the line already reached stops before its first stage",
          _rd.is_egress_stop(_late.day_line_reason()) and "2.50 GB" in _late.day_line_reason(), _late.day_line_reason())
    _reads[0] = 1_001_300_000_000.0
    _day._meter_at = 0
    check("day line: under the line after a fresh reading, the pass goes on and the receipt carries the figure",
          _day.day_line_reason() is None and _day.meter["last_24h_gb"] == 1.3 and _day.meter["readings"] == 2)
    _day._meter_at = 0
    _reads[0] = 1_001_950_000_000.0
    _why = _day.day_line_reason()
    check("day line: at 1.9 GB in 24 hours the pass stops itself, as an egress stop (capped, not failed)",
          bool(_why) and _rd.is_egress_stop(_why) and "1.95 GB" in _why, _why)
    _reads[0] = None
    _day2 = _rd.Run(_MeterConn((1_000_000_000_000, _then)), _sched, _A())
    _day2._meter_at = 0
    check("day line: a counter that cannot be read stops nothing and is counted as unread",
          _day2.day_line_reason() is None and _day2.meter.get("unread", 0) >= 1)
    check("day line: the run's own estimate cap is an egress stop too; the switch is not",
          _rd.is_egress_stop("estimated database egress cap (0.7 GB) reached") and not _rd.is_egress_stop("stopped by the switch: x"))
finally:
    _mt.read = _real_read
    _rd.wal_bytes = _wal
    if _old_env[0] is not None:
        os.environ["SUPABASE_METRICS_KEY"] = _old_env[0]

# ---- the daytime passes' tick on Railway (ops/day_tick.py decide) ----------------------------------------------
import day_tick as _dtk  # noqa: E402
_daycfg = {"window_utc": ["06:15", "21:30"], "min_room_gb": 0.15, "estimate_factor": 1.25}


def _at(h, m):
    return _dt.datetime(2026, 10, 12, h, m, tzinfo=_dt.timezone.utc)


check("day tick: before 06:15 and after 21:30 UTC no pass starts, whatever the room",
      not _dtk.decide(_at(6, 0), 0, 0.2, _daycfg, 1.9)[0] and not _dtk.decide(_at(21, 31), 0, 0.2, _daycfg, 1.9)[0]
      and not _dtk.decide(_at(2, 0), 0, 0.2, _daycfg, 1.9)[0])
check("day tick: nothing starts beside a run or a retention step", not _dtk.decide(_at(9, 0), 1, 0.2, _daycfg, 1.9)[0])
check("day tick: a counter that is not known starts nothing", not _dtk.decide(_at(9, 0), 0, None, _daycfg, 1.9)[0])
check("day tick: under 0.15 GB of room no pass starts",
      not _dtk.decide(_at(9, 0), 0, 1.80, _daycfg, 1.9)[0] and not _dtk.decide(_at(9, 0), 0, 2.4, _daycfg, 1.9)[0])
_go = _dtk.decide(_at(9, 0), 0, 1.10, _daycfg, 1.9)
check("day tick: with room a pass starts, capped at (room - 0.05) / 1.25 on its own estimate",
      _go[0] and _go[2] == 0.6, _go)
check("day tick: the cap never passes 0.7 GB (the request table refuses more) and never falls under 0.05",
      _dtk.decide(_at(9, 0), 0, 0.1, _daycfg, 1.9)[2] == 0.7 and _dtk.decide(_at(9, 0), 0, 1.74, _daycfg, 1.9)[2] == 0.088,
      (_dtk.decide(_at(9, 0), 0, 0.1, _daycfg, 1.9), _dtk.decide(_at(9, 0), 0, 1.74, _daycfg, 1.9)))
check("day tick: the first and the last minute of the window are inside it",
      _dtk.decide(_at(6, 15), 0, 0.5, _daycfg, 1.9)[0] and _dtk.decide(_at(21, 30), 0, 0.5, _daycfg, 1.9)[0])

# ---- the archive copies name their columns (ops/retention.py) -----------------------------------------------------
import re as _re  # noqa: E402
_ret_src = open(os.path.join(ROOT, "ops", "retention.py")).read()
_code = "\n".join(ln for ln in _ret_src.splitlines() if not ln.lstrip().startswith("#"))
check("retention: no archive copy is by position (`select moved.*` or `returning t.*`): a column added to a live "
      "table must not fail the night", not _re.search(r"moved\.\*|returning\s+\w+\.\*", _code), "found a positional copy")
import retention as _ret  # noqa: E402
check("retention: the archived thread columns are the ten the archive table has",
      [c.strip() for c in _ret.THREAD_COLS.split(",")] == ["id", "subreddit_id", "link_title", "permalink", "created_utc",
                                                           "num_comments", "archived", "score", "first_seen_at", "tree_fetched_at"])
# ---- the takedown check's slow lap by position (worker/takedown.py lap_next, lap_reached) -------------------------
import takedown as _td  # noqa: E402


class _LapConn:
    """doc_probe as a sorted list of ids; the two queries lap_next sends."""
    def __init__(self, ids):
        self.ids = sorted(ids)

    def execute(self, sql, params=None):
        assert "checked_at is not null" in sql, "the lap is over documents already checked once"
        if "doc_id <= %s" in sql:
            lo, hi, lim = params
            rows = [(d,) for d in self.ids if lo < d <= hi][:lim]
        else:
            lo, lim = params
            rows = [(d,) for d in self.ids if d > lo][:lim]
        return rows


_docs = [f"t1_{c}" for c in "abcdefghij"]
check("slow lap: from the start, the first documents in id order", _td.lap_next(_LapConn(_docs), "", 3) == (["t1_a", "t1_b", "t1_c"], False))
check("slow lap: from a position, the documents after it", _td.lap_next(_LapConn(_docs), "t1_c", 3) == (["t1_d", "t1_e", "t1_f"], False))
check("slow lap: at the end it wraps to the start, and stops at its own position",
      _td.lap_next(_LapConn(_docs), "t1_h", 5) == (["t1_i", "t1_j", "t1_a", "t1_b", "t1_c"], True))
check("slow lap: with room for everything, each document is taken once, never twice",
      sorted(_td.lap_next(_LapConn(_docs), "t1_e", 99)[0]) == _docs and len(_td.lap_next(_LapConn(_docs), "t1_e", 99)[0]) == 10)
check("slow lap: a position past the last document starts again from the first",
      _td.lap_next(_LapConn(_docs), "t1_zzz", 2) == (["t1_a", "t1_b"], True))
check("slow lap: no room, nothing taken", _td.lap_next(_LapConn(_docs), "t1_c", 0) == ([], False))
_rest = ["t1_d", "t1_e", "t1_f", "t1_g"]
check("slow lap: the position moves to the last document Reddit was asked about, in an unbroken run from the start",
      _td.lap_reached(_rest, {"t1_d", "t1_e", "t1_f", "t1_g"}) == "t1_g" and _td.lap_reached(_rest, {"t1_d", "t1_e", "t1_g"}) == "t1_e")
check("slow lap: nothing asked (the run's time ended first), the position does not move",
      _td.lap_reached(_rest, set()) is None and _td.lap_reached([], {"x"}) is None)

print(f"\ntest_sweep_units: {len(FAILS)} failure(s)" + (": " + "; ".join(FAILS) if FAILS else ""))
sys.exit(bool(FAILS))

