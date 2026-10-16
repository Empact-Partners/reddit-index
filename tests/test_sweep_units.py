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

# ---- post qualification: the automaton gives the regex's answers (worker/harvest.py AliasMatcher) -------------------
import re as _re  # noqa: E402
import harvest as _hv0  # noqa: E402

_brands0 = [{"brand": n, "ambiguity_class": a, "domains": d} for n, a, d in [
    ("HubSpot", "low", "hubspot.com"), ("Notion", "low", "notion.so"), ("Portant", "low", ""), ("Monday", "high", "monday.com"),
    ("WithSecure Elements Endpoint Detection and Response", "low", ""), ("x.ai", "low", ""), ("iubenda", "low", ""),
    ("Zus", "low", "")]]
_forms0 = [b["brand"] for b in _brands0 if b["ambiguity_class"] == "low"] + [d for b in _brands0 for d in b["domains"].split(";") if d]
_old0 = _re.compile(r"(?<![a-z0-9])" + "|".join(_re.escape(f) for f in sorted(set(_forms0), key=len, reverse=True))
                    + r"(?![a-z0-9])", _re.I)
_new0 = _hv0.build_alias_re(_brands0)
_texts0 = ["We moved to HubSpot last year", "hubspotting", "an important decision", "notional value", "I use NOTION daily",
           "visit hubspot.com/crm", "monday.com pricing", "Monday morning", "x.ai launched", "", "nothing here",
           "WithSecure Elements Endpoint Detection and Responses", "the subreddit", "portant", "İUBENDA politika",
           "the İubenda banner", "hubſpot", "HUBSPOT", "ıubenda"]
check("qualification: the automaton is not the regex object any more", isinstance(_new0, _hv0.AliasMatcher))
check("qualification: the automaton answers every text as the regex did (forms found anywhere, case ignored)",
      [bool(_old0.search(t)) for t in _texts0] == [bool(_new0.search(t)) for t in _texts0],
      [(t, bool(_old0.search(t)), bool(_new0.search(t))) for t in _texts0])
check("qualification: the regex's last form and its first (by the set's order) are now found inside a word too, "
      "like every other form", not _old0.search("zusammen") and _new0.search("zusammen")
      and not _old0.search("xWithSecure Elements Endpoint Detection and Response")
      and _new0.search("xWithSecure Elements Endpoint Detection and Response"))
check("qualification: letters are compared as re.IGNORECASE compares them (Turkish dotted I, long s, final sigma)",
      _hv0.re_i_fold("İubenda") == "iubenda" and _hv0.re_i_fold("HUBſPOT") == "hubspot"
      and _hv0.re_i_fold("ΣΟΦΟΣ") == _hv0.re_i_fold("σοφοσ") and len(_hv0.re_i_fold("İİ")) == 2)
check("qualification: forms that are empty or blank give a matcher that matches nothing",
      _hv0.AliasMatcher(["", "  "]).search("anything") is None)
check("qualification: a high-ambiguity name is not a form, its domain is",
      not _new0.search("Monday morning") and _new0.search("see monday.com"))
check("qualification: no forms, no matcher", _hv0.build_alias_re([{"brand": "Monday", "ambiguity_class": "high", "domains": ""}]) is None)

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
_real_clock = _rd.Run.__dict__["clock"]   # the staticmethod itself, not the function it wraps
_U = lambda d, h, m: _dt.datetime(2026, 10, d, h, m, tzinfo=_dt.timezone.utc)  # noqa: E731


class _LedgerConn:
    """The readings the ledger asks for (decision 0035), and the database's size."""
    def __init__(self, readings, db_bytes=3.6e9):
        self.rs, self.db, self.kept, self.closed = readings, db_bytes, [], False

    def execute(self, sql, params=None):
        if sql.startswith("insert into public.egress_counter"):
            self.kept.append(params)
        rows = ([tuple(r) for r in self.rs if r[0] > params[0]] if "from public.egress_counter where at >" in sql
                else [(self.db,)] if "pg_database_size" in sql else [])
        return type("R", (), {"fetchone": lambda s: rows[0] if rows else None, "fetchall": lambda s: rows,
                              "rowcount": 0})()

    def rollback(self):
        pass


# 12 Oct 23:55 to 13 Oct 11:30: the night (0.6 GB), the watchdog's reading, then the backup at 11:10 to 11:30
_day13 = [(_U(12, 11, 20), 999.5e9), (_U(12, 23, 55), 1000.0e9), (_U(13, 5, 0), 1000.6e9), (_U(13, 6, 55), 1000.62e9),
          (_U(13, 11, 10), 1000.8e9), (_U(13, 11, 30), 1001.2e9)]
_morning13 = _day13[:4]
_real_read = _mt.read
_reads = [1_001_000_000_000.0]
_mt.read = lambda timeout=30.0: _reads[0]
_rd.Run.clock = staticmethod(lambda: _U(13, 13, 0))   # after the backup
try:
    class _A:
        manual, max_calls, takedown_calls, max_mentions, max_egress_gb, day_end, options, stages = True, None, None, None, None, None, {}, []
    _sched = {"caps": {"reddit_calls": 1, "takedown_calls": 1, "mentions": 1, "minutes": 10, "egress_gb": 0.7},
              "day_line_gb": 1.9, "backup": {"fraction": 0.3}}
    _wal = _rd.wal_bytes
    _rd.wal_bytes = lambda conn: 0
    _night = _rd.Run(_LedgerConn(_day13), _sched, _A())
    _night._meter_at = 0
    _reads[0] = 1_009_000_000_000.0
    check("day line: the night's run is never stopped by it, whatever the counter says", _night.day_line_reason() is None)
    _A.day_end = _dt.time(23, 15)
    _reads[0] = 1_001_500_000_000.0
    _day = _rd.Run(_LedgerConn(_day13), _sched, _A())
    check("day line: a pass under the line goes on; the receipt carries the watchdog's day (0.88 GB since 06:55) and "
          "tonight's run held (0.6 GB, the night before)",
          _day.day_line_reason() is None and _day.meter["readings"] == 1 and _day.meter["day_sent_gb"] == 0.88
          and _day.meter["night_held_gb"] == 0.6 and _day.meter["backup_held_gb"] == 0.0, _day.meter)
    _reads[0] = 1_002_000_000_000.0
    _late = _rd.Run(_LedgerConn(_day13), _sched, _A())
    check("day line: 1.38 GB sent and 0.6 held for tonight reach the line: the pass stops before its first stage",
          _rd.is_egress_stop(_late.day_line_reason()) and "1.38 GB" in _late.day_line_reason()
          and "held for tonight's run" in _late.day_line_reason(), _late.day_line_reason())
    _rd.Run.clock = staticmethod(lambda: _U(13, 9, 0))   # before the backup
    _reads[0] = 1_001_000_000_000.0
    _early = _rd.Run(_LedgerConn(_morning13), _sched, _A())
    check("day line: before the backup shows, 0.3 of what was sent since 11:30 yesterday is held with tonight's run "
          "(0.38 + 0.45 + 0.6): the pass goes on",
          _early.day_line_reason() is None and _early.meter["backup_held_gb"] == 0.45, _early.meter)
    _reads[0] = 1_001_400_000_000.0
    _held = _rd.Run(_LedgerConn(_morning13), _sched, _A())
    check("day line: 0.78 sent + 0.57 for the backup + 0.6 for tonight reach the line, and the reason says so",
          _rd.is_egress_stop(_held.day_line_reason()) and "held for the day's backup" in _held.day_line_reason(),
          (_held.day_line_reason(), _held.meter))
    _full = _rd.Run(_LedgerConn(_morning13), dict(_sched, backup={"full_last": "2026-10-06", "full_gb": 1.4}), _A())
    _reads[0] = 1_001_000_000_000.0
    _full._meter_at = 0
    check("day line: on a full-backup day the full one is held (0.38 + 1.4 + 0.6): the pass stops",
          _rd.is_egress_stop(_full.day_line_reason()) and "full backup" in _full.day_line_reason(), _full.day_line_reason())
    _rd.Run.clock = staticmethod(lambda: _U(13, 13, 0))
    _reads[0] = 1_001_300_000_000.0
    _day._meter_at = 0
    check("day line: after a fresh reading under the line, the pass goes on and the figure moves",
          _day.day_line_reason() is None and _day.meter["day_sent_gb"] == 0.68 and _day.meter["readings"] == 2)
    _day._meter_at = 0
    _reads[0] = 1_001_950_000_000.0
    _why = _day.day_line_reason()
    check("day line: at the line the pass stops itself, as an egress stop (capped, not failed)",
          bool(_why) and _rd.is_egress_stop(_why) and "1.33 GB" in _why, _why)
    _reads[0] = None
    _day2 = _rd.Run(_LedgerConn(_day13), _sched, _A())
    _day2._meter_at = 0
    check("day line: a counter that cannot be read stops nothing and is counted as unread",
          _day2.day_line_reason() is None and _day2.meter.get("unread", 0) >= 1)
    _reads[0] = 1_001_000_000_000.0
    _blind = _rd.Run(_LedgerConn([]), _sched, _A())
    check("day line: no reading before the watchdog's day: not known, nothing stopped", _blind.day_line_reason() is None)
    # the night's share (decision 0035): what the day has left once publish and refresh are counted
    _A.day_end = None
    _rd.Run.clock = staticmethod(lambda: _U(14, 1, 0))
    _reads[0] = 1_002_000_000_000.0
    _n = _rd.Run(_LedgerConn(_day13), dict(_sched, night={"publish_reserve_gb": 0.35}), _A())
    _nr = _n.night_room()
    check("night room: 1.38 GB sent in the watchdog's day leaves 1.9 - 1.38 - 0.35 = 0.17 GB for collecting and "
          "labelling", _nr is not None and _nr["gb"] == 0.17 and _nr["sent_gb"] == 1.38, _nr)
    _A.day_end = _dt.time(23, 15)
    check("night room: a daytime pass has none (it is judged on the line)",
          _rd.Run(_LedgerConn(_day13), _sched, _A()).night_room() is None)
    check("day line: the run's own estimate cap is an egress stop too; the switch is not",
          _rd.is_egress_stop("estimated database egress cap (0.7 GB) reached") and not _rd.is_egress_stop("stopped by the switch: x"))
finally:
    _rd.Run.clock = _real_clock
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

_pq = dict(_daycfg, peak_queue_max=20000)
check("day tick: in GLM's peak hours (06:00 to 10:00 UTC) no pass starts while 20,000 or more mentions wait for a label",
      not _dtk.decide(_at(8, 30), 0, 1.10, _pq, 1.9, 23958)[0] and not _dtk.decide(_at(9, 59), 0, 1.10, _pq, 1.9, 20000)[0]
      and "wait for a label" in _dtk.decide(_at(8, 30), 0, 1.10, _pq, 1.9, 23958)[1])
check("day tick: in the peak hours with a short queue, and outside them with any queue, a pass starts",
      _dtk.decide(_at(8, 30), 0, 1.10, _pq, 1.9, 19999)[0] and _dtk.decide(_at(10, 0), 0, 1.10, _pq, 1.9, 90000)[0]
      and _dtk.decide(_at(6, 30), 0, 1.10, _pq, 1.9, 0)[0])

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

# ---- a deploy never stops a run (ops/deploy_sweep.py safe_to_deploy) ---------------------------------------------
import deploy_sweep as _ds  # noqa: E402


def _t(h, m):
    return _dt.datetime(2026, 10, 12, h, m, tzinfo=_dt.timezone.utc)


check("deploy: the day service is not deployed in the six minutes before a tick, nor in the tick's minute",
      not _ds.safe_to_deploy("day", _t(18, 26))[0] and not _ds.safe_to_deploy("day", _t(18, 29))[0]
      and not _ds.safe_to_deploy("day", _t(18, 30))[0] and not _ds.safe_to_deploy("day", _t(17, 57))[0]
      and not _ds.safe_to_deploy("day", _t(6, 0))[0] and not _ds.safe_to_deploy("day", _t(21, 28))[0])
check("deploy: the day service can be deployed between ticks and outside its hours",
      _ds.safe_to_deploy("day", _t(18, 1))[0] and _ds.safe_to_deploy("day", _t(18, 24))[0]
      and _ds.safe_to_deploy("day", _t(18, 31))[0] and _ds.safe_to_deploy("day", _t(22, 59))[0]
      and _ds.safe_to_deploy("day", _t(3, 28))[0])
check("deploy: the night service is not deployed from 23:54 to 00:00 UTC, and is otherwise",
      not _ds.safe_to_deploy("sweep", _t(23, 55))[0] and not _ds.safe_to_deploy("sweep", _t(0, 0))[0]
      and _ds.safe_to_deploy("sweep", _t(23, 53))[0] and _ds.safe_to_deploy("sweep", _t(18, 29))[0])

# ---- comments from the subreddit's comment listing (decision 0029: harvest.stream_docs, collect.fetch_comments,
# ---- collect.stream_visit, collect.mentions_room) ----------------------------------------------------------------
import harvest as _hv  # noqa: E402


def _c(cid, ts, body="We moved from HubSpot to Salesforce.", author="ann", link="t3_L1", title="CRM thread"):
    return {"kind": "t1", "data": {"id": cid, "author": author, "body": body, "created_utc": ts, "score": 3,
                                   "permalink": f"/r/x/comments/{link[3:]}/_/{cid}/", "link_id": link,
                                   "link_title": title, "num_comments": 9, "replies": ""}}


_page = {"data": {"after": "t1_c2", "children": [
    _c("c1", 500.0), _c("c2", 400.0, body="[removed]"), _c("c3", 390.0, author="[deleted]"),
    _c("c4", 380.0, author="AutoModerator"), _c("c5", 370.0, body="thanks! I am a bot, beep boop"),
    {"kind": "more", "data": {"count": 3}}, {"kind": "t1", "data": {"id": "c6", "author": "bob", "body": "no link"}}]}}
_sd = _hv.stream_docs(_page)
_td2 = _hv.tree_docs([{"data": {"children": []}}, {"data": {"children": [_c("c1", 500.0)]}}])[0]
check("stream: deleted, removed and automated comments are left out, like the comment tree's",
      [x["id"] for x in _sd] == ["t1_c1"], _sd)
check("stream: a comment reads the same from the listing as from its tree (id, body, author, time, address, score)",
      len(_td2) == 1 and all(_sd[0][k] == _td2[0][k] for k in ("id", "doc_type", "author", "body", "created_utc",
                                                                 "permalink", "score")), (_sd, _td2))
check("stream: each comment carries its thread", _sd[0]["link_id"] == "t3_L1" and _sd[0]["link_title"] == "CRM thread"
      and _sd[0]["num_comments"] == 9)
check("stream: an answer that is not a listing gives nothing", _hv.stream_docs({"_err": 503}) == [] and _hv.stream_docs(None) == [])


def _listing(pages):
    """A fake comment listing: `pages` is a list of pages (each a list of comments), served by cursor."""
    calls = []

    def fake(subs, limit=100, before=None, after=None):
        calls.append(after)
        i = 0 if after is None else int(after[1:])
        if i >= len(pages) or pages[i] is None:
            return {"_err": 503} if i < len(pages) else {"data": {"children": [], "after": None}}
        return {"data": {"children": pages[i], "after": f"p{i + 1}" if i + 1 < len(pages) else None}}
    return fake, calls


_real_sc = collect.rc.subreddit_comments
try:
    _f, _calls = _listing([[_c("a", 900.0), _c("b", 800.0)], [_c("c", 700.0), _c("d", 600.0)], [_c("e", 500.0)]])
    collect.rc.subreddit_comments = _f
    _g = collect.fetch_comments("x", 650.0, 0.0, 10)
    check("stream: the listing is read back to the newest comment already read, and no further",
          [x["id"] for x in _g["docs"]] == ["t1_a", "t1_b", "t1_c"] and _g["reached"] and _g["ok"] and _g["calls"] == 2
          and _g["newest"] == 900.0 and _g["comments"] == 4, _g)
    _g = collect.fetch_comments("x", 700.0, 0.0, 10)
    check("stream: a comment in the watermark's own second is read again (another may share that second)",
          [x["id"] for x in _g["docs"]] == ["t1_a", "t1_b", "t1_c"] and _g["reached"] and _g["calls"] == 2, _g)
    _g = collect.fetch_comments("x", 600.0, 0.0, 10)
    check("stream: a page that ends exactly on the watermark's second reads one page more",
          [x["id"] for x in _g["docs"]] == ["t1_a", "t1_b", "t1_c", "t1_d"] and _g["reached"] and _g["calls"] == 3, _g)
    _f, _calls = _listing([[_c("a", 900.0)], [_c("b", 800.0)], [_c("c", 700.0)], [_c("d", 600.0)]])
    collect.rc.subreddit_comments = _f
    _g = collect.fetch_comments("x", None, 0.0, 3)
    check("stream: a first visit reads its pages and stops (not a gap: nothing was read before)",
          [x["id"] for x in _g["docs"]] == ["t1_a", "t1_b", "t1_c"] and _g["calls"] == 3 and not _g["reached"] and _g["ok"], _g)
    _g = collect.fetch_comments("x", 100.0, 0.0, 2)
    check("stream: the pages ran out before the watermark: not reached (the caller records the gap)",
          _g["calls"] == 2 and not _g["reached"] and _g["ok"] and len(_g["docs"]) == 2, _g)
    _g = collect.fetch_comments("x", 100.0, 0.0, 10)
    check("stream: the listing's own end counts as reached", _g["reached"] and _g["calls"] == 4 and len(_g["docs"]) == 4, _g)
    _g = collect.fetch_comments("x", 100.0, 750.0, 10)
    check("stream: nothing older than the 400-day floor is kept, and the read stops there",
          [x["id"] for x in _g["docs"]] == ["t1_a", "t1_b"] and _g["calls"] == 3 and _g["reached"], _g)
    _f, _calls = _listing([[_c("a", 900.0)], None, [_c("c", 700.0)]])
    collect.rc.subreddit_comments = _f
    _g = collect.fetch_comments("x", 100.0, 0.0, 10)
    check("stream: a failed page ends the read as not ok, keeping what was read",
          not _g["ok"] and not _g["reached"] and [x["id"] for x in _g["docs"]] == ["t1_a"] and _g["calls"] == 2, _g)
    _f, _calls = _listing([])
    collect.rc.subreddit_comments = _f
    _g = collect.fetch_comments("x", 100.0, 0.0, 10)
    check("stream: an empty listing is a complete read of nothing", _g["ok"] and _g["reached"] and _g["docs"] == [] and _g["newest"] == 0, _g)
    _stops = []

    def _before():
        _stops.append(1)
        if len(_stops) > 1:
            raise collect.Allowance("calls used")
    _f, _calls = _listing([[_c("a", 900.0)], [_c("b", 800.0)]])
    collect.rc.subreddit_comments = _f
    try:
        collect.fetch_comments("x", 100.0, 0.0, 10, _before)
        check("stream: the caps are checked before every call", False)
    except collect.Allowance:
        check("stream: the caps are checked before every call", len(_calls) == 1, _calls)
finally:
    collect.rc.subreddit_comments = _real_sc

check("stream: a thread's row comes from its post, stamped with the comment count it had",
      collect.thread_row({"id": "L1", "title": "T" * 600, "permalink": "/r/x/comments/L1/t/", "created_utc": 123.0,
                          "num_comments": 7, "archived": False, "score": 5}, 44)
      == ("t3_L1", 44, "T" * 500, "https://www.reddit.com/r/x/comments/L1/t/", 123.0, 7, False, 5, 7))
check("stream: a post without an id, an address or a time gives no row",
      collect.thread_row({"id": "L1", "permalink": "/r/x/", "created_utc": None}, 1) is None
      and collect.thread_row({"title": "t", "permalink": "/r/x/", "created_utc": 1.0}, 1) is None
      and collect.thread_row({"id": "L1", "created_utc": 1.0}, 1) is None)
check("stream: the room for new mentions is the run's egress cap, less a margin, over one mention's bytes",
      collect.mentions_room(0.434, 13000) == 30046 and collect.mentions_room(0.0, 13000) == 0
      and collect.mentions_room(0.7, 13000, share=1.0) == 53846)


class _SCur:
    """The few statements stream_visit sends, against dicts."""
    def __init__(self, threads, wm):
        self.threads, self.wm, self.inserted, self.set_wm, self.rows = set(threads), wm, [], [], []

    def execute(self, sql, params=None):
        if sql.startswith("SELECT watermark"):
            self.rows = [(self.wm,)] if (self.wm is not None and params[1] == "comment_stream") else []
        elif sql.startswith("SELECT id FROM threads"):
            self.rows = [(t,) for t in params[0] if t in self.threads]
        elif sql.startswith("INSERT INTO ingest_state"):
            self.set_wm.append((params[1], params[3], params[4]))
        return self

    def executemany(self, sql, rows):
        assert "tree_fetched_at" in sql and "DO NOTHING" in sql
        self.inserted += [r[0] for r in rows]

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class _Res:
    def resolve(self, body, sub, title):
        return ([{"brand_slug": "hubspot", "alias": "hubspot", "conf": 0.9, "rule_fired": "safe_word_boundary"}]
                if "hubspot" in body.lower() else [])


_real_sc, _real_get = collect.rc.subreddit_comments, collect.rc.get
try:
    _f, _calls = _listing([[_c("a", 900.0, link="t3_known"), _c("b", 890.0, link="t3_listed"),
                            _c("c", 880.0, link="t3_asked"), _c("d", 870.0, link="t3_gone"),
                            _c("e", 860.0, body="nothing here", link="t3_other"), _c("f", 500.0, link="t3_old")]])
    collect.rc.subreddit_comments = _f
    _info = []

    def _get(path, params=None, bucket="misc", tries=3, use_cache=True):
        _info.append(params["id"])
        return {"data": {"children": [{"kind": "t3", "data": {
            "name": "t3_asked", "id": "asked", "title": "Asked", "permalink": "/r/x/comments/asked/t/",
            "created_utc": 100.0, "num_comments": 3, "score": 1}}]}}
    collect.rc.get = _get
    _cur = _SCur({"t3_known"}, "1970-01-01T00:10:00+00:00")     # the comment watermark: 600 s
    _mrows, _m, _w = [], [0.0], [0.0]
    _listed = {"t3_listed": {"id": "listed", "title": "Listed", "permalink": "/r/x/comments/listed/t/",
                             "created_utc": 200.0, "num_comments": 2, "score": 1}}
    _qual = [{"id": "post1", "title": "HubSpot?", "permalink": "/r/x/comments/post1/t/", "created_utc": 950.0,
              "num_comments": 0, "score": 1},
             {"id": "post2", "title": "nothing", "permalink": "/r/x/comments/post2/t/", "created_utc": 940.0}]
    _sv = collect.stream_visit(_cur, "x", 7, _qual, {"post1"}, _listed, _mrows, _Res(), "run-1", _m, _w, 0.0, 3, 10)
    check("stream visit: a row for every comment that names a brand, newer than the watermark, whose thread Reddit returns",
          [r[0] for r in _mrows] == ["t1_a", "t1_b", "t1_c"] and all(r[1] == 1 and r[3] == 7 and r[12] == "run-1" for r in _mrows)
          and [r[2] for r in _mrows] == ["t3_known", "t3_listed", "t3_asked"], _mrows)
    check("stream visit: threads stored: the post that names a brand, one from the post listing, one from /api/info; "
          "not the stored one, not a post that names nothing",
          sorted(_cur.inserted) == ["t3_asked", "t3_listed", "t3_post1"], _cur.inserted)
    check("stream visit: one /api/info call for the threads not on the listing, and its counts",
          _info == ["t3_asked,t3_gone"] and _sv["info_calls"] == 1 and _sv["from_info"] == 1 and _sv["from_listing"] == 1
          and _sv["from_posts"] == 1, (_info, _sv))
    check("stream visit: a comment whose thread Reddit no longer returns is counted, not stored",
          _sv["without_thread"] == 1 and _sv["rows"] == 3, _sv)
    check("stream visit: the comment watermark moves to the newest comment listed",
          _cur.set_wm == [("comment_stream", "1970-01-01T00:15:00+00:00", 6)] and _sv["failed"] == 0 and _sv["first"] == 0
          and _sv["gap"] == 0, _cur.set_wm)
    collect.rc.get = lambda *a, **k: {"_err": 503}
    _cur = _SCur({"t3_known"}, "1970-01-01T00:10:00+00:00")
    _mrows = []
    _sv = collect.stream_visit(_cur, "x", 7, [], set(), _listed, _mrows, _Res(), "run-1", _m, _w, 0.0, 3, 10)
    check("stream visit: a failed /api/info call keeps the rows whose thread is known, holds the watermark, and counts "
          "nothing as lost", [r[0] for r in _mrows] == ["t1_a", "t1_b"] and _cur.set_wm == [] and _sv["failed"] == 1
          and _sv["without_thread"] == 0, (_mrows, _cur.set_wm, _sv))
    _f, _calls = _listing([[_c("a", 900.0)], [_c("b", 890.0)], [_c("c", 880.0)], [_c("d", 870.0)]])
    collect.rc.subreddit_comments = _f
    _cur = _SCur({"t3_L1"}, None)
    _mrows = []
    _sv = collect.stream_visit(_cur, "x", 7, [], set(), {}, _mrows, _Res(), "run-1", _m, _w, 0.0, 3, 10)
    check("stream visit: a first visit reads its three pages, is not a gap, and sets the watermark",
          _sv["first"] == 1 and _sv["gap"] == 0 and _sv["calls"] == 3 and len(_mrows) == 3 and len(_cur.set_wm) == 1, _sv)
    _cur = _SCur({"t3_L1"}, "1970-01-01T00:01:40+00:00")
    _mrows = []
    _sv = collect.stream_visit(_cur, "x", 7, [], set(), {}, _mrows, _Res(), "run-1", _m, _w, 0.0, 3, 2)
    check("stream visit: the pages ending before the watermark is a gap, and the watermark still moves on",
          _sv["gap"] == 1 and _sv["calls"] == 2 and len(_cur.set_wm) == 1, _sv)
    _cur = _SCur({"t3_L1"}, "1970-01-01T00:16:40+00:00")     # 1,000 s: the comment that set it was deleted since
    _mrows = []
    _sv = collect.stream_visit(_cur, "x", 7, [], set(), {}, _mrows, _Res(), "run-1", _m, _w, 0.0, 3, 10)
    check("stream visit: the watermark never moves back (its own comment was deleted, the newest listed is older)",
          _cur.set_wm == [] and _mrows == [] and _sv["failed"] == 0 and _sv["gap"] == 0 and _sv["calls"] == 1, (_cur.set_wm, _sv))
finally:
    collect.rc.subreddit_comments, collect.rc.get = _real_sc, _real_get

# the whole stage under the comment listing, against a fake database and a fake Reddit
import contextlib as _ctx  # noqa: E402


class _RConn:
    def __init__(self):
        self.cur = _SCur(set(), None)
        self.wm_new = []

    def execute(self, sql, params=None):
        c = _SCur(set(), None)
        if "FROM subreddits" in sql:
            c.rows = [("alpha", 1), ("beta", 2), ("gamma", 3)]
        elif "count(*)" in sql:
            c.rows = [(len(self.cur.inserted),)]
        return c

    def cursor(self):
        return self.cur

    @_ctx.contextmanager
    def transaction(self):
        yield


_saved = (collect.plan, collect.d.fetch_new, collect.d.insert_mentions, collect.d.load_brands, collect.d.build_alias_re,
          collect.d.Resolver, collect.rc.subreddit_comments, collect.rc.get, collect.d.content_qualify)
try:
    collect.plan = lambda conn, today: (["alpha", "beta", "gamma"], {x: ["crm"] for x in ("alpha", "beta", "gamma")},
                                        {"alpha"}, 0, {"vendor": 0, "second_spelling": 0})
    _now_ts = __import__("time").time()

    def _fn(sub, wm, seen=None, listed=None, err=None):
        post = {"id": f"{sub}p", "title": "HubSpot or not", "selftext": "", "author": "op", "created_utc": _now_ts - 60,
                "permalink": f"/r/{sub}/comments/{sub}p/t/", "num_comments": 2, "score": 1}
        if listed is not None:
            listed[f"t3_{sub}p"] = post
        return [post], True, False
    collect.d.fetch_new = _fn
    collect.d.content_qualify = lambda p, cats, alias_re: True
    _stored = []

    def _ins(cur, rows):
        _stored.extend(rows)
        return len(rows), 0
    collect.d.insert_mentions = _ins
    collect.d.load_brands = lambda: {}
    collect.d.build_alias_re = lambda brands: None
    collect.d.Resolver = _Res
    collect.rc.subreddit_comments = lambda subs, limit=100, before=None, after=None: {"data": {"after": None, "children": [
        _c(f"{subs}1", _now_ts - 30, link=f"t3_{subs}p"), _c(f"{subs}2", _now_ts - 40, link=f"t3_{subs}p"),
        _c(f"{subs}3", _now_ts - 50, body="nothing", link=f"t3_{subs}p")]}}
    collect.rc.get = lambda *a, **k: {"_err": 500}
    _conn = _RConn()
    _rec = collect.run(_conn, {"reddit_calls": 100, "mentions": 1000, "mode": "stream", "mentions_room": 5},
                       _now_ts + 60, log=lambda *a, **k: None, run_id="run-2")
    check("stream stage: two subreddits are read, then the run's room for new mentions ends the stage as planned",
          _rec["subs_visited"] == 2 and _rec["mentions_new"] == 6 and _rec["stopped"] is None
          and "room for were collected" in (_rec["allowance_used"] or ""), _rec)
    check("stream stage: a post row and two comment rows a subreddit, the comments on the post's thread",
          [(r[0], r[1], r[2]) for r in _stored[:3]] == [("t3_alphap", 2, "t3_alphap"), ("t1_alpha1", 1, "t3_alphap"),
                                                       ("t1_alpha2", 1, "t3_alphap")], _stored[:3])
    check("stream stage: the receipt says the mode and what the listing gave; no comment tree is read",
          _rec["mode"] == "stream" and _rec["stream_calls"] == 2 and _rec["comments_listed"] == 6
          and _rec["stream_first_visits"] == 2 and _rec["trees_fetched"] == 0 and _rec["stream_gaps"] == 0
          and _rec["threads_from_posts"] == 2 and _rec["threads_from_listing"] == 0 and _rec["info_calls"] == 0, _rec)
    check("stream stage: one thread a subreddit (the post that names a brand), both watermarks set",
          sorted(_conn.cur.inserted) == ["t3_alphap", "t3_betap"]
          and sorted(x[0] for x in _conn.cur.set_wm) == ["comment_stream", "comment_stream", "new_listing", "new_listing"]
          and all(x[2] == 3 for x in _conn.cur.set_wm), (_conn.cur.inserted, _conn.cur.set_wm))
    _asked = []
    _ok_fn = collect.d.fetch_new
    collect.d.fetch_new = lambda sub, wm, seen=None, listed=None, err=None: ([], False, False) if sub == "alpha" else _ok_fn(sub, wm, seen, listed)
    _sc = collect.rc.subreddit_comments

    def _sc2(subs, limit=100, before=None, after=None):
        _asked.append(subs)
        return _sc(subs, limit, before, after)
    collect.rc.subreddit_comments = _sc2
    _conn = _RConn()
    _rec = collect.run(_conn, {"reddit_calls": 100, "mentions": 1000, "mode": "stream"}, _now_ts + 60,
                       log=lambda *a, **k: None, run_id="run-4")
    check("stream stage: a subreddit whose post listing failed is not asked for its comments",
          _asked == ["beta", "gamma"] and _rec["listings_failed"] == 1 and _rec["stream_failed"] == 0
          and _rec["subs_visited"] == 3 and _rec["mentions_new"] == 6, (_asked, _rec))
    collect.d.fetch_new, collect.rc.subreddit_comments = _ok_fn, _sc
    _conn = _RConn()
    _conn.cur.executemany = lambda sql, rows: None      # the comment-tree path's own upsert
    _rec = collect.run(_conn, {"reddit_calls": 100, "mentions": 1000}, _now_ts + 60, log=lambda *a, **k: None, run_id="run-3")
    check("trees stage: the default mode is unchanged and reports itself", _rec["mode"] == "trees" and "stream_calls" not in _rec
          and _rec["subs_visited"] == 3, _rec)
finally:
    (collect.plan, collect.d.fetch_new, collect.d.insert_mentions, collect.d.load_brands, collect.d.build_alias_re,
     collect.d.Resolver, collect.rc.subreddit_comments, collect.rc.get, collect.d.content_qualify) = _saved

# ---- every visit is recorded (decision 0030: worker/collect.py, daily.fetch_new's err) -------------------------
class _VCur:
    """Records the visit ledger's writes; every other statement answers nothing."""
    def __init__(self, wms):
        self.wms, self.visits, self.rows = wms, [], []

    def execute(self, sql, params=None):
        self.rows = []
        if sql.startswith("SELECT watermark"):
            v = self.wms.get(params[0])
            self.rows = [(v,)] if v is not None else []
        elif sql.startswith("INSERT INTO ingest_state"):
            self.visits.append((params[0], params[1], params[3], params[4], params[5]))
        return self

    def executemany(self, sql, rows):
        pass

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class _VConn:
    def __init__(self, wms):
        self.cur = _VCur(wms)

    def execute(self, sql, params=None):
        c = _VCur({})
        if "FROM subreddits" in sql:
            c.rows = [(n, i + 1) for i, n in enumerate(["empty", "capped", "gone", "flaky", "gone2", "fine"])]
        elif "count(*)" in sql:
            c.rows = [(0,)]
        return c

    def cursor(self):
        return self.cur

    @_ctx.contextmanager
    def transaction(self):
        yield


_saved = (collect.plan, collect.d.fetch_new, collect.d.insert_mentions, collect.d.load_brands, collect.d.build_alias_re,
          collect.d.Resolver, collect.d.content_qualify, collect.GONE_STAMPS)
try:
    _subs = ["empty", "capped", "gone", "flaky", "gone2", "fine"]
    collect.plan = lambda conn, today: (list(_subs), {x: ["crm"] for x in _subs}, set(), 0,
                                        {"vendor": 0, "second_spelling": 0})
    _n = __import__("time").time()

    def _fn(sub, wm, seen=None, listed=None, err=None):
        post = {"id": f"{sub}p", "title": "a post", "author": "op", "created_utc": _n - 600,
                "permalink": f"/r/{sub}/comments/{sub}p/t/", "num_comments": 0}
        if sub == "empty":
            return [], True, False
        if sub == "capped":
            return [post], True, True
        if sub in ("gone", "gone2", "flaky"):
            if err is not None:
                err["code"] = {"gone": 404, "gone2": 403, "flaky": 503}[sub]
            return [], False, False
        return [post], True, False
    collect.d.fetch_new = _fn
    collect.d.content_qualify = lambda p, cats, alias_re: False
    collect.d.insert_mentions = lambda cur, rows: (0, 0)
    collect.d.load_brands = lambda: {}
    collect.d.build_alias_re = lambda brands: None
    collect.d.Resolver = _Res
    _conn = _VConn({"capped": "2026-10-01T00:00:00+00:00", "gone": "2026-09-01T00:00:00+00:00"})
    _rec = collect.run(_conn, {"reddit_calls": 100, "mentions": 1000}, _n + 60, log=lambda *a, **k: None, run_id="r5")
    _v = {x[0]: x for x in _conn.cur.visits}
    _iso = lambda t: __import__("datetime").datetime.fromtimestamp(t, __import__("datetime").timezone.utc).isoformat()
    check("visits: an empty first listing is recorded (no watermark yet, nothing found)",
          _v.get("empty") == ("empty", "new_listing", None, 0, "ok") and _rec["empty_first_listings"] == 1, _v.get("empty"))
    check("visits: a listing whose pages ran out before the watermark holds it and records the visit, marked capped",
          _v.get("capped") == ("capped", "new_listing", "2026-10-01T00:00:00+00:00", 0, "capped")
          and _rec["capped_listings"] == 1 and _rec["capped_subs"] == ["capped"], _v.get("capped"))
    check("visits: a subreddit Reddit no longer serves (404, 403) is recorded as gone, its watermark kept",
          _v.get("gone") == ("gone", "new_listing", "2026-09-01T00:00:00+00:00", 0, "gone")
          and _v.get("gone2") == ("gone2", "new_listing", None, 0, "gone")
          and _rec["subs_gone"] == 2 and _rec["subs_gone_names"] == ["gone (404)", "gone2 (403)"], (_v, _rec))
    check("visits: a listing that failed for another reason (503) leaves no record, and is tried first again",
          "flaky" not in _v and _rec["listings_failed"] == 3, (_v, _rec["listings_failed"]))
    check("visits: a normal listing moves the watermark as before", _v.get("fine") == ("fine", "new_listing", _iso(_n - 600), 0, "ok"))
    collect.GONE_STAMPS = 1
    _conn = _VConn({})
    _rec = collect.run(_conn, {"reddit_calls": 100, "mentions": 1000}, _n + 60, log=lambda *a, **k: None, run_id="r6")
    check("visits: no more than GONE_STAMPS gone subreddits are recorded a run (an app-wide refusal marks nothing more)",
          _rec["subs_gone"] == 1 and [x[0] for x in _conn.cur.visits if x[4] == "gone"] == ["gone"], _conn.cur.visits)
    _pages = [{"_err": 404}]
    _real_get2 = collect.rc.get
    collect.rc.get = lambda *a, **k: _pages[0]
    _e = {}
    _r = _saved[1]("x", None, err=_e)
    collect.rc.get = _real_get2
    check("listing: a failed page says what Reddit answered", _r == ([], False, False) and _e == {"code": 404}, (_r, _e))
    # a held watermark is reachable by a larger page budget (the remedy docs/worker.md names): pages of 2 posts, newest
    # first, the watermark at t=10
    _pg = [{"data": {"after": f"p{i + 1}" if i < 4 else None, "children": [
        {"kind": "t3", "data": {"id": f"{i}a", "created_utc": 100 - 20 * i}},
        {"kind": "t3", "data": {"id": f"{i}b", "created_utc": 90 - 20 * i}}]}} for i in range(5)]
    collect.rc.get = lambda path, params=None, **k: _pg[0 if not (params or {}).get("after") else int(params["after"][1:])]
    _mp = collect.d.MAX_PAGES
    try:
        collect.d.MAX_PAGES = 2
        _a = _saved[1]("x", 10.0)
        collect.d.MAX_PAGES = 8
        _b = _saved[1]("x", 10.0)
    finally:
        collect.d.MAX_PAGES = _mp
        collect.rc.get = _real_get2
    check("listing: two pages do not reach the watermark (capped); eight do, and return every post above it",
          _a[2] is True and len(_a[0]) == 4 and _b[2] is False and _b[1] and len(_b[0]) == 9, (_a[1:], len(_a[0]), _b[1:], len(_b[0])))
finally:
    (collect.plan, collect.d.fetch_new, collect.d.insert_mentions, collect.d.load_brands, collect.d.build_alias_re,
     collect.d.Resolver, collect.d.content_qualify, collect.GONE_STAMPS) = _saved

# ---- labelling first (decision 0032: collect.room_after_queue, a run with no room) ----------------------------------
check("label first: the waiting mentions take their share of the room, each as 4 KB of a 13 KB new one",
      collect.room_after_queue(23953, 24000, 4000, 13000) == 16568 and collect.room_after_queue(15000, 0, 4000, 13000) == 15000
      and collect.room_after_queue(15000, 60000, 4000, 13000) == 0, collect.room_after_queue(23953, 24000, 4000, 13000))
import classify_sweep as _cs2  # noqa: E402
check("label first: the queue is weighed as the classifier takes it (fewer than five tries), in both places",
      "attempts < 5" in _cs2.LABELLABLE_SQL
      and "classify_sweep.LABELLABLE_SQL" in open(os.path.join(ROOT, "worker", "run_daily.py")).read()
      and "LABELLABLE_SQL" in open(os.path.join(ROOT, "ops", "day_tick.py")).read()
      and all("attempts < 5" in q for q in _re.findall(r'"where attempts < \d[^"]*"', open(os.path.join(ROOT, "worker", "classify_sweep.py")).read())))
_saved = (collect.plan, collect.d.fetch_new)
try:
    _visited = []
    collect.plan = lambda conn, today: (["alpha"], {"alpha": ["crm"]}, set(), 0, {"vendor": 0, "second_spelling": 0})
    collect.d.fetch_new = lambda *a, **k: _visited.append(1) or ([], True, False)
    _rec = collect.run(_RConn(), {"reddit_calls": 100, "mentions": 1000, "mode": "stream", "mentions_room": 0,
                                  "labelling_queue": 61000}, __import__("time").time() + 60, log=lambda *a, **k: None,
                       run_id="r7")
    check("label first: a run with no room visits nothing and says why, as a planned end",
          _visited == [] and _rec["subs_visited"] == 0 and _rec["stopped"] is None
          and _rec["allowance_used"] == "no room for new mentions this run: 61,000 wait to be labelled first"
          and _rec["labelling_queue"] == 61000, _rec)
finally:
    collect.plan, collect.d.fetch_new = _saved

# ---- Jev labels in Z.ai's peak hours; GLM is not asked (classify_sweep._loop, 15 Oct) -------------------------------
import classify_sweep as _cs3  # noqa: E402


class _QConn:
    def __init__(self, keys):
        self.keys, self.sql = list(keys), []

    def execute(self, sql, params=None):
        self.sql.append(sql)
        rows = []
        if "from public.classify_queue" in sql and sql.lstrip().startswith("select brand_id"):
            rows, self.keys = self.keys, []
        return type("R", (), {"fetchall": lambda s: rows, "fetchone": lambda s: (0,), "rowcount": 0})()


_saved3 = {k: getattr(_cs3, k) for k in ("fetch_items", "jev_judge", "decide", "glm_judge", "write", "glm_peak_now")}
try:
    _asked_glm, _written = [], []
    _cs3.fetch_items = lambda conn, keys: [{"brand_id": b, "doc_id": d, "created_utc": c} for b, d, c in keys]

    def _jev(items, log=print):
        return [{"i": i} for i in range(len(items))]
    _jev.last_usd, _jev.last_errors = 0.001, {}
    _cs3.jev_judge = _jev
    _cs3.decide = lambda x, t: "positive" if (x is not None and x["i"] == 0) else None   # Jev settles one of three
    _cs3.glm_judge = lambda items, **k: (_asked_glm.append(len(items)) or (["neutral"] * len(items), {
        "credits": 1.0, "failed_jobs": 0, "retried_jobs": 0, "errors": {}, "asked": [True] * len(items), "jobs": 1,
        "skipped_jobs": 0, "rate_limited": False}))
    _cs3.write = lambda conn, items, verdicts, models, tried, jev_seen: (
        _written.append((list(verdicts), list(tried))) or {"labelled": sum(v is not None for v in verdicts), "rejected": 0})
    _keys = [(1, "t1_a", 0), (1, "t1_b", 0), (2, "t1_c", 0)]
    _cs3.glm_peak_now = lambda: True
    _r3 = {"jev_decided": 0, "glm_decided": 0, "labelled": 0, "rejected": 0, "not_checked": 0, "jev_usd": 0.0,
           "glm_credits": 0.0, "allowance_used": None}
    _q3 = _QConn(_keys)
    _cs3._loop(_q3, {}, {}, "glm-5.3", _r3, {"glm": 0.0, "jev": 0.0}, 100, 1e12, lambda: None, lambda *a, **k: None)
    check("peak hours: Jev's settled share is written, GLM is not asked, the residue keeps its tries, and only items "
          "Jev has not seen are taken",
          _asked_glm == [] and _written == [(["positive", None, None], [True, False, False])]
          and _r3["labelled"] == 1 and _r3["glm_peak"] and any("jev_checked_at is null" in q for q in _q3.sql),
          (_asked_glm, _written, _r3))
    _asked_glm.clear(); _written.clear()
    _cs3.glm_peak_now = lambda: False
    _r4 = dict(_r3, labelled=0, jev_decided=0, glm_decided=0, not_checked=0)
    _r4.pop("glm_peak")
    _cs3._loop(_QConn(_keys), {}, {}, "glm-5.3", _r4, {"glm": 0.0, "jev": 0.0}, 100, 1e12, lambda: None,
               lambda *a, **k: None)
    check("off peak: GLM takes Jev's residue as before", _asked_glm == [2] and _r4["labelled"] == 3
          and "glm_peak" not in _r4, (_asked_glm, _r4))
    # Jev failing in the peak hours: what it did not answer is not re-sent this run; a batch it answered none of ends
    _asked_jev, _written = [], []

    def _jev_flaky(items, log=print):
        _asked_jev.append([it["doc_id"] for it in items])
        return [None if it["doc_id"] == "t1_b" else {"i": 0} for it in items]
    _jev_flaky.last_usd, _jev_flaky.last_errors = 0.0, {}
    _cs3.jev_judge = _jev_flaky
    _cs3.glm_peak_now = lambda: True

    _seen_docs: set = set()
    _cs3.write = lambda conn, items, verdicts, models, tried, jev_seen: (
        _seen_docs.update(it["doc_id"] for it, sn in zip(items, jev_seen) if sn)
        or {"labelled": sum(v is not None for v in verdicts), "rejected": 0})

    class _QRepeat(_QConn):   # the queue as the database keeps it: what Jev answered is marked seen, its misses are not
        def execute(self, sql, params=None):
            self.sql.append(sql)
            rows = ([k for k in _keys if k[1] not in _seen_docs]
                    if ("from public.classify_queue" in sql and sql.lstrip().startswith("select brand_id")
                        and "<= now()" not in sql) else [])
            return type("R", (), {"fetchall": lambda s: rows, "fetchone": lambda s: (0,), "rowcount": 0})()
    _r5 = dict(_r3, labelled=0, jev_decided=0, not_checked=0, allowance_used=None)
    _cs3._loop(_QRepeat([]), {}, {}, "glm-5.3", _r5, {"glm": 0.0, "jev": 0.0}, 100, 1e12, lambda: None,
               lambda *a, **k: None)
    check("peak hours: an item Jev did not answer is not sent to it again this run (one round, not a loop to the "
          "cap)", _asked_jev[0] == ["t1_a", "t1_b", "t1_c"] and all("t1_b" not in a for a in _asked_jev[1:])
          and len(_asked_jev) <= 3, _asked_jev)
    _cs3.jev_judge = lambda items, log=print: [None] * len(items)
    _cs3.jev_judge.last_usd, _cs3.jev_judge.last_errors = 0.0, {}
    _r6 = dict(_r3, labelled=0, jev_decided=0, not_checked=0, allowance_used=None)
    _q6 = _QRepeat([])
    _cs3._loop(_q6, {}, {}, "glm-5.3", _r6, {"glm": 0.0, "jev": 0.0}, 100, 1e12, lambda: None, lambda *a, **k: None)
    check("peak hours: a batch Jev answered none of ends the labelling, said on the receipt",
          "answered none" in (_r6["allowance_used"] or "") and _r6["labelled"] == 0, _r6)
finally:
    for k, v in _saved3.items():
        setattr(_cs3, k, v)

# ---- labelling beside collection (worker/alongside.py, decision 0037) -------------------------------------------------
import alongside as _al  # noqa: E402
import threading as _thr  # noqa: E402


class _AConn:
    def __init__(self):
        self.closed, self.autocommit = False, False

    def close(self):
        self.closed = True


_aconns = []


def _aconnect():
    c = _AConn()
    _aconns.append(c)
    return c


_rounds = []


def _arun(conn, cfg, deadline, should_stop=lambda: None, log=print):
    _rounds.append((conn, dict(cfg)))
    n = len(_rounds)
    if n <= 2:   # two rounds with work, then an empty queue
        return {"labelled": 100, "rejected": 10, "not_checked": 5, "jev_usd": 0.01, "glm_credits": 40.0}
    return {"labelled": 0, "rejected": 0, "not_checked": 0, "jev_usd": 0.0, "glm_credits": 0.0}


_a = _al.Alongside(_aconnect, _arun, {"glm_credits_max": 100, "jev_usd_max": 1.0, "max_items": 1000}, 1e12,
                   log=lambda *a, **k: None, pause_s=0.05).start()
import time as _tm  # noqa: E402
_t_end = _tm.time() + 3
while len(_rounds) < 4 and _tm.time() < _t_end:
    _tm.sleep(0.01)
_aout = _a.finish(timeout=5)
check("alongside: rounds run on the thread's own connection, the allowance left shrinks after each, an empty queue "
      "waits and asks again, and finish() stops it and sums what it did",
      len(_aconns) == 1 and all(r[0] is _aconns[0] for r in _rounds) and _aconns[0].closed
      and _rounds[1][1]["glm_credits_max"] == 60.0 and _rounds[2][1]["max_items"] == 1000 - 230
      and _aout["labelled"] == 200 and _aout["rejected"] == 20 and _aout["rounds"] >= 3
      and _aout["ended"] == "collection ended", (_aout, [r[1] for r in _rounds][:3]))
_rounds.clear()
_b = _al.Alongside(_aconnect, _arun, {"glm_credits_max": 60, "jev_usd_max": 1.0, "max_items": 1000}, 1e12,
                   log=lambda *a, **k: None, pause_s=0.05).start()
_bout = _b.finish(timeout=5) if (_tm.sleep(0.3) or True) else None
check("alongside: once the pass's GLM allowance is used it stops on its own and says so",
      _bout["ended"] == "the pass's labelling allowance is used" and _bout["rounds"] == 2, _bout)
check("alongside: left() is what the pass's own classify stage then gets", _b.left()["glm_credits_max"] == 0.0
      and _b.left()["max_items"] == 1000 - 230)
_c = _al.Alongside(_aconnect, lambda *a, **k: {"error": "every GLM job of a batch failed"},
                   {"glm_credits_max": 60}, 1e12, log=lambda *a, **k: None, pause_s=0.05).start()
_tm.sleep(0.2)
_cout = _c.finish(timeout=5)
check("alongside: a round that failed ends the thread, the error on the receipt",
      "failed" in _cout.get("error", "") and _cout["rounds"] == 1, _cout)
_d = _al.Alongside(_aconnect, _arun, {}, 1e12, log=lambda *a, **k: None, pause_s=0.05,
                   switch=lambda c: "stopped by the switch: test").start()
_tm.sleep(0.2)
check("alongside: the stop switch ends it before a round", _d.finish(timeout=5)["ended"] == "stopped by the switch: test")
_e = _al.Alongside(lambda: (_ for _ in ()).throw(RuntimeError("no database")), _arun, {}, 1e12,
                   log=lambda *a, **k: None).start()
_tm.sleep(0.1)
check("alongside: a thread that cannot connect says so and the pass goes on", "no database" in _e.finish(timeout=5)["error"])
_aw = {"day": {"label_alongside": True}, "classify": {"enabled": True}}
check("alongside: only a daytime pass that asks for collect and classify, with the classifier and the switch on and "
      "the pass not stopped (run_daily.alongside_wanted)",
      _rd.alongside_wanted(True, _aw, ["collect", "classify"], None)
      and not _rd.alongside_wanted(False, _aw, ["takedowns", "collect", "classify", "publish"], None)   # the night
      and not _rd.alongside_wanted(True, _aw, ["collect"], None)
      and not _rd.alongside_wanted(True, _aw, ["classify"], None)
      and not _rd.alongside_wanted(True, {"day": {"label_alongside": True}, "classify": {"enabled": False}},
                                   ["collect", "classify"], None)
      and not _rd.alongside_wanted(True, {"day": {}, "classify": {"enabled": True}}, ["collect", "classify"], None)
      and not _rd.alongside_wanted(True, _aw, ["collect", "classify"], "the day's egress line: x"))
_halt = _thr.Event()
_rounds.clear()
_h = _al.Alongside(_aconnect, _arun, {"glm_credits_max": 1000, "jev_usd_max": 1.0, "max_items": 100000}, 1e12,
                   log=lambda *a, **k: None, pause_s=0.05, halt=_halt).start()
_tm.sleep(0.2)
_halt.set()
_tm.sleep(0.2)
_hout = _h.finish(timeout=5)
check("alongside: the pass's egress stop (its halt event) ends the thread, and the round's own check sees it",
      _hout["ended"] == "the pass stopped for egress" and _h._should_stop() == "the pass stopped for egress", _hout)
_slow_started = _thr.Event()


class _Fence:
    def __init__(self):
        self.closed, self.autocommit, self.cancelled, self.closed_by = False, False, False, None

    def cancel(self):
        self.cancelled = True

    def close(self):
        self.closed, self.closed_by = True, _thr.current_thread().name


_fc = _Fence()


def _stuck(conn, cfg, deadline, should_stop=lambda: None, log=print):
    _slow_started.set()
    while not conn.cancelled:
        _tm.sleep(0.01)
    return {"labelled": 1, "error": "cancelled"}


_f = _al.Alongside(lambda: _fc, _stuck, {"glm_credits_max": 10}, 1e12, log=lambda *a, **k: None).start()
_slow_started.wait(2)
_fout = _f.finish(timeout=0.2)
check("alongside: a round that does not end when told is fenced: its query cancelled from the pass, its connection "
      "closed by its own thread, and the receipt says fenced (so the pass's classify stage does not run)",
      _fc.cancelled and _fc.closed and _fc.closed_by == "label-alongside" and _fout.get("fenced") is True, _fout)

# ---- the shared app's windows (reddit_client._win, 15 Oct) ---------------------------------------------------------
import reddit_client as _rc5  # noqa: E402
_t0 = [1_000_000.0]
_realtime = _rc5.time.time
_rc5.time.time = lambda: _t0[0]
_saved_stats = dict(_rc5._stats)
_rc5._win.update(end=None, max_used=0.0, own=0, first=True)
for k in ("app_windows", "app_used", "app_own"):
    _rc5._stats[k] = 0
try:
    def _hit(used, reset):
        _rc5._read_ratelimit({"x-ratelimit-remaining": str(1000 - used), "x-ratelimit-reset": str(reset),
                              "x-ratelimit-used": str(used)})
    _hit(400, 300)                      # joined midway: this window is left out
    _t0[0] += 300; _hit(10, 600)        # a new window
    _t0[0] += 100; _hit(300, 500)
    _t0[0] += 100; _hit(620, 400)       # this process made 3 calls of the 620
    _t0[0] += 400; _hit(5, 600)         # the next window closes it
    check("shared app: a complete window counts what the app used and this process's calls in it; the first, "
          "joined midway, is left out",
          _rc5._stats["app_windows"] == 1 and _rc5._stats["app_used"] == 620 and _rc5._stats["app_own"] == 3,
          {k: _rc5._stats[k] for k in ("app_windows", "app_used", "app_own")})
finally:
    _rc5.time.time = _realtime
    _rc5._stats.clear(); _rc5._stats.update(_saved_stats)
    _rc5._win.update(end=None, max_used=0.0, own=0, first=True)

# ---- the watchdog's day (decision 0035: meter.ledger_from, replacing 0033's backup_reserve) -------------------------
import meter as _mt  # noqa: E402
check("watchdog day: 06:59 UTC is still yesterday's day; 07:00 starts today's",
      _mt.watchdog_day_start(_U(14, 6, 59)) == _U(13, 7, 0) and _mt.watchdog_day_start(_U(14, 7, 0)) == _U(14, 7, 0))
_rate = 3e6 / 60
check("bursts: 14 Oct's full backup (1,285 MB in 4 minutes) and 13 Oct's (390 MB in 17) are seen; a pass's 9 MB "
      "in 3 minutes and anything before `since` are not",
      [round(b / 1e6) for _, b in _mt.bursts([(_U(13, 11, 13), 0.0), (_U(13, 11, 30), 390e6), (_U(13, 11, 33), 399e6),
                                              (_U(14, 12, 21), 600e6), (_U(14, 12, 25), 1885e6)],
                                             _U(13, 10, 30), _rate, 1e8)] == [390, 1285]
      and _mt.bursts([(_U(13, 11, 13), 0.0), (_U(13, 11, 30), 390e6)], _U(13, 11, 30), _rate, 1e8) == [])
check("bursts: an interval longer than an hour says nothing about what sent it (11 Oct: seven hours, 1.93 GB)",
      _mt.bursts([(_U(11, 5, 9), 0.0), (_U(11, 12, 17), 1.929e9)], _U(11, 10, 30), _rate, 1e8) == [])
_sp = [(_U(13, 23, 50), 10e9), (_U(14, 2, 45), 10.52e9), (_U(14, 5, 59), 10.55e9), (_U(14, 23, 40), 11e9),
       (_U(15, 3, 0), 11.6e9)]
check("night spends: 00:00 to 06:00 UTC per night, tonight's left out until 06:00, a night without its readings "
      "skipped", [round(x / 1e9, 2) for x in _mt.night_spends(_sp, _U(15, 4, 0))] == [0.55]
      and [round(x / 1e9, 2) for x in _mt.night_spends(_sp + [(_U(15, 5, 50), 11.7e9)], _U(15, 6, 30))] == [0.7, 0.55])
# the day of 14 Oct replayed: the night before, the watchdog's reading, passes, the full backup at 12:21-12:25
_r14 = [(_U(13, 11, 20), 1465.4e9), (_U(13, 23, 55), 1466.29e9), (_U(14, 2, 46), 1466.814e9), (_U(14, 6, 32), 1466.853e9),
        (_U(14, 9, 47), 1466.945e9), (_U(14, 12, 21), 1467.041e9), (_U(14, 12, 25), 1468.326e9)]
_s14 = {"day_line_gb": 1.9, "backup": {"fraction": 0.3, "full_last": "2026-10-14", "full_gb": 1.4, "full_share": 0.37},
        "night": {"reserve_min_gb": 0.6, "publish_reserve_gb": 0.35}}
_upto = lambda t: [r for r in _r14 if r[0] <= t]  # noqa: E731
_L = _mt.ledger_from(_upto(_U(14, 9, 47)), 1466.945e9, _U(14, 9, 47), _s14, 3.58e9)
check("ledger: on 14 Oct (a full-backup day) at 09:47 the full one is held and tonight's run: no room for a pass",
      _L["full_backup_day"] and _L["backup_held"] == 1.4e9 and _L["night_held"] == 0.6e9
      and _L["used"] > 1.9e9 and round(_L["sent"] / 1e6) == 92, _L)
_L = _mt.ledger_from(_upto(_U(14, 9, 47)), 1466.945e9, _U(14, 9, 47), _s14, 4.2e9)
check("ledger: a full backup is held at full_share of the database when that is more (0.37 x 4.2 GB)",
      abs(_L["backup_held"] - 1.554e9) < 1, _L["backup_held"])
_L = _mt.ledger_from(_r14 + [(_U(14, 12, 30), 1468.33e9)], 1468.33e9, _U(14, 12, 30), _s14, 3.58e9)
check("ledger: from 12:25 the backup is in the counter (1.28 GB seen, a pass's reading after it) and nothing more is "
      "held for it",
      _L["backup_held"] == 0 and _L.get("backup_seen_gb") == 1.285 and "in the counter" in _L["backup_why"], _L)
_L = _mt.ledger_from(_r14, 1468.426e9, _U(15, 0, 52), _s14, 3.58e9)
check("ledger: tonight's run, once in the day, is not held; its room is the line less the day and the publish "
      "(1.9 - 1.573 - 0.35 < 0: the night collects nothing)",
      _L["night_held"] == 0 and _L["night_room"] < 0 and round(_L["sent"] / 1e9, 3) == 1.573, _L)
_r15 = _r14 + [(_U(15, 3, 0), 1469.0e9), (_U(15, 6, 58), 1469.01e9)]
_L = _mt.ledger_from(_r15, 1469.02e9, _U(15, 7, 30), _s14, 3.58e9)
check("ledger: the morning after, a new day: the delta backup is held on what was sent since 11:30 yesterday less the "
      "full backup itself (0.3 x 0.79 GB), with tonight's run, and a pass has its room from 07:00",
      not _L["full_backup_day"] and abs(_L["backup_held"] - 0.3 * (1469.02e9 - 1466.945e9 - 1.285e9)) < 1e6
      and _L["used"] < 1.75e9, _L)
_split = _upto(_U(14, 12, 21)) + [(_U(14, 12, 23), 1467.941e9)]   # 0.9 GB of the full backup by 12:23
_L = _mt.ledger_from(_split, 1467.941e9, _U(14, 12, 23), _s14, 3.58e9)
check("ledger: a backup seen in its first reading only keeps the rest of its estimate held until the counter "
      "settles (1.4 - 0.9 GB)", abs(_L["backup_held"] - 0.5e9) < 1e6 and "held until the counter settles"
      in _L["backup_why"], (_L["backup_held"], _L["backup_why"]))
_L = _mt.ledger_from(_split + [(_U(14, 12, 25), 1468.326e9), (_U(14, 12, 28), 1468.33e9)], 1468.33e9,
                     _U(14, 12, 28), _s14, 3.58e9)
check("ledger: its two readings add up (1.285 GB) and, once a reading at a pass's pace follows, nothing is held",
      _L["backup_held"] == 0 and _L.get("backup_seen_gb") == 1.285, _L)
_tail = _split + [(_U(14, 12, 26), 1468.0e9)]   # 59 MB in three minutes after the burst: the backup is still sending
_L = _mt.ledger_from(_tail, 1468.0e9, _U(14, 12, 26), _s14, 3.58e9)
check("ledger: a tail under the burst threshold but over a pass's pace does not end the hold (review round 2)",
      abs(_L["backup_held"] - 0.5e9) < 1e6, (_L["backup_held"], _L["backup_why"]))
_L = _mt.ledger_from(_tail + [(_U(14, 12, 29), 1468.005e9)], 1468.005e9, _U(14, 12, 29), _s14, 3.58e9)
check("ledger: the hold ends when a reading comes back at a pass's pace (5 MB in three minutes)",
      _L["backup_held"] == 0, (_L["backup_held"], _L["backup_why"]))
_L = _mt.ledger_from(_r14, 1466.945e9, _U(14, 9, 47), _s14, 3.58e9)
check("ledger: readings after `now` never count (the full backup at 12:25 is not seen at 09:47)",
      _L["backup_held"] == 1.4e9 and "backup_seen_gb" not in _L, _L)
_L = _mt.ledger_from([(_U(13, 6, 50), 1e12)], 1e12 + 5e8, _U(13, 15, 0), {"backup": {}}, None)
check("ledger: no backup seen by 14:00 UTC: none is held after it", _L["backup_held"] == 0
      and "none is held after it" in _L["backup_why"], _L["backup_why"])
check("ledger: no reading before the day's start, or a counter that went back: 'not known' (used None)",
      _mt.ledger_from([], 5e9, _U(13, 9, 0), {}, None)["used"] is None
      and _mt.ledger_from([(_U(13, 6, 0), 9e9)], 5e9, _U(13, 9, 0), {}, None)["used"] is None)

# the tick figures the room on the same ledger (ops/day_tick.py effective_used)
_u, _w = _dtk.effective_used(_LedgerConn(_morning13), 1_001_000_000_000, _U(13, 9, 0), {"backup": {"fraction": 0.3}})
check("day tick: the room is figured on the watchdog's day with the backup and tonight's run held, and says why",
      abs(_u - 1.43e9) < 1 and "held for the day's backup" in _w and "tonight's run" in _w, (_u, _w))
check("day tick: unknown (no reading before the day, or nothing read now) stays unknown, nothing held",
      _dtk.effective_used(_LedgerConn([]), 5.0, _U(13, 9, 0), {}) == (None, "")
      and _dtk.effective_used(_LedgerConn(_morning13), None, _U(13, 9, 0), {}) == (None, ""))

# the backup's real times are checked against the hold (scripts/schedule_check.py backup_timing)
import schedule_check as _sc  # noqa: E402
_bnow = _dt.datetime(2026, 10, 13, 14, 0, tzinfo=_dt.timezone.utc)
_ok = [{"inserted_at": "2026-10-11T11:15:57.428Z"}, {"inserted_at": "2026-10-12T11:20:47.151Z"},
       {"inserted_at": "2026-10-13T11:21:03.000Z"}]
check("backup timing: backups between 10:30 and 14:00 UTC are no finding (14 Oct's full one at 12:25 included)",
      _sc.backup_timing({}, _bnow, _ok)[0] == []
      and _sc.backup_timing({}, _bnow, _ok[:2] + [{"inserted_at": "2026-10-13T12:25:02Z"}])[0] == [])
_moved = _ok[:2] + [{"inserted_at": "2026-10-13T14:30:00Z"}]
check("backup timing: a backup that moved past 14:00 UTC is a finding that names it",
      any("14:30" in f for f in _sc.backup_timing({}, _bnow, _moved)[0]))
_fb = {"backup": {"full_last": "2026-10-14", "full_every_days": 7, "full_gb": 1.4}}
check("full backups: 14 Oct's on its predicted day is no finding",
      _sc.full_backups(_fb, _r14, _U(15, 9, 0))[0] == [], _sc.full_backups(_fb, _r14, _U(15, 9, 0)))
_r14s = _r14[:5] + [(_U(14, 12, 21), 1467.041e9), (_U(14, 12, 23), 1467.68e9), (_U(14, 12, 25), 1468.326e9)]
check("full backups: one split across two readings (0.64 + 0.65 GB) is still one full backup",
      _sc.full_backups(dict(_fb, backup=dict(_fb["backup"], full_last="2026-10-12")), _r14s, _U(15, 9, 0))[1]
      .get("full_backups") == {"2026-10-14": 1.285}, _sc.full_backups(dict(_fb, backup=dict(_fb["backup"], full_last="2026-10-12")), _r14s, _U(15, 9, 0)))
check("full backups: the night's publish (0.3 GB at 02:30) is never added to a day's backup",
      _sc.full_backups(_fb, [(_U(13, 2, 27), 0.0), (_U(13, 2, 45), 0.3e9), (_U(13, 11, 13), 0.31e9),
                             (_U(13, 11, 30), 0.72e9)], _U(13, 16, 0))[1].get("full_backups") == {}, "publish")
check("full backups: one on a day the schedule does not call full is a finding that names the day to set",
      any("2026-10-14" in f for f in _sc.full_backups({"backup": dict(_fb["backup"], full_last="2026-10-12")}, _r14,
                                                      _U(15, 9, 0))[0]))
check("full backups: a full day of the last week without one, read on the counter, is a finding",
      any("13 Oct" in f for f in _sc.full_backups({"backup": dict(_fb["backup"], full_last="2026-10-06")},
                                                  _r14[:2] + [(_U(13, 12, 0), 1465.6e9), (_U(13, 15, 0), 1465.7e9)],
                                                  _U(13, 16, 0))[0]))
check("backup timing: none in 30 hours is a finding; none listed is a finding",
      any("30 hours" in f for f in _sc.backup_timing({}, _bnow + _dt.timedelta(days=2), _ok)[0])
      and _sc.backup_timing({}, _bnow, [])[0] == ["no daily backup is listed for the project"])

check("day line: the pass's clock is restored as it was (a staticmethod, callable on an instance)",
      isinstance(_rd.Run.__dict__["clock"], staticmethod) and _rd.Run.clock() is not None)

# ---- every document on a page is checked, whatever the night's calls (decision 0034: takedown.build_queue) ---------
import takedown as _td3  # noqa: E402
_pages = [f"t1_p{i}" for i in range(250)]
_rest = [f"t1_r{i}" for i in range(500)]
check("takedown: under the cap, the pages first and then the rest up to it",
      _td3.build_queue(_pages[:150], _rest, 3) == _pages[:150] + _rest[:150] and _td3.calls_for(150, 3) == 3)
check("takedown: past the cap every document on a page is still checked, and nothing else",
      _td3.build_queue(_pages, _rest, 2) == _pages and _td3.calls_for(250, 2) == 3 and _td3.calls_for(200, 2) == 2)


class _TCur(list):
    def fetchone(self):
        return self[0] if self else None

    def fetchall(self):
        return list(self)


class _TConn:
    """The statements takedown.run sends on a dry run, against lists."""
    def __init__(self, pages, never, lap):
        self.pages, self.never, self.lap = pages, never, lap

    def execute(self, sql, params=None):
        if sql.startswith("select count(*) from public.mentions m where exists"):
            return _TCur([(0,)])
        if "from site.rail_key union" in sql:
            return _TCur([(d,) for d in self.pages])
        if "from site.watch_card group by" in sql:
            return _TCur([])
        if sql == _td3.NEVER_SQL:
            return _TCur([(d,) for d in self.never[:params[0]]])
        if "from public.ingest_state" in sql:
            return _TCur([])
        if "from public.doc_probe p where p.checked_at is not null" in sql:
            return _TCur([(d,) for d in self.lap[:params[-1]]])
        if "from public.mentions where doc_id = any" in sql:
            return _TCur([(d, 1.0) for d in params[0]])
        return _TCur([])


_real_info = _td3.__dict__.get("rc")
import reddit_client as _rc3  # noqa: E402
_saved_info = _rc3.info
_fail = set()


def _info(chunk):
    if chunk[0] in _fail:
        return {"_err": 503}
    return {"data": {"children": [{"kind": "t1", "data": {"name": d, "body": "ok", "author": "a"}} for d in chunk]}}


try:
    _rc3.info = _info
    _r = _td3.run(_TConn(_pages, _rest, []), max_calls=2, dry_run=True, log=lambda *a, **k: None)
    check("takedown run: past the cap every document on a page is asked, nothing else; the receipt says so",
          _r["docs_checked"] == 250 and _r["on_pages"] == 250 and _r["calls_planned"] == 3
          and _r["calls_over_cap_for_pages"] == 1 and _r["never_checked_before"] == 0
          and _r["slow_lap"]["documents"] == 0 and _r["on_pages_not_checked"] == 0, _r)
    _r = _td3.run(_TConn(_pages[:150], _rest, []), max_calls=200, dry_run=True, log=lambda *a, **k: None)
    check("takedown run: the calls planned are the queue's, not the cap (150 on pages, 500 more: 7 calls)",
          _r["calls_planned"] == 7 and "calls_over_cap_for_pages" not in _r and _r["never_checked_before"] == 500, _r)
    _fail.add("t1_p100")
    _r = _td3.run(_TConn(_pages, [], []), max_calls=2, dry_run=True, log=lambda *a, **k: None)
    check("takedown run: a failed batch of documents on pages is counted as not checked",
          _r["on_pages_not_checked"] == 100 and _r["docs_checked"] == 150, _r)
    _fail.clear()
    _r = _td3.run(_TConn(_pages, [], []), max_calls=2, dry_run=True, log=lambda *a, **k: None, deadline=1.0)
    check("takedown run: out of time is a stop on the receipt, and every page document not reached is counted",
          _r["stopped"] and _r["on_pages_not_checked"] == 250, _r)
finally:
    _rc3.info = _saved_info
_tp = _rd.takedown_problems({"on_pages_not_checked": 120})
check("takedown: documents on pages left unchecked are a problem that fails the run (it says 'failed')",
      len(_tp) == 1 and "failed" in _tp[0] and "120" in _tp[0] and _rd.takedown_problems({"on_pages_not_checked": 0}) == []
      and _rd.takedown_problems({}) == [] and "brake" in _rd.takedown_problems({"brake": True, "gone_share": 0.2})[0], _tp)
check("takedown: the check ends at the run's end less the reserve for labelling, refresh and publish",
      _rd.takedown_deadline(10_000.0, {"reserve_minutes_after_collect": 105}) == 10_000.0 - 6300
      and _rd.takedown_deadline(10_000.0, {}) == 10_000.0 - 6300)
_net = []
_saved_info = _rc3.info


def _info2(chunk):
    _net.append(_rc3.NET_MAX_WAIT)
    return _info(chunk)


try:
    _rc3.info = _info2
    _nw = _rc3.NET_MAX_WAIT
    _td3.run(_TConn(_pages[:150], [], []), max_calls=2, dry_run=True, log=lambda *a, **k: None,
             deadline=__import__("time").time() + 300)
    check("takedown: a call rides out a network outage no longer than the check's own end, and the wait is restored",
          _net and all(60 <= x <= 300 for x in _net) and _rc3.NET_MAX_WAIT == _nw, (_net, _rc3.NET_MAX_WAIT))
finally:
    _rc3.info = _saved_info

# ---- the disk on the night's receipt (decision 0038: meter.parse_disk, run_daily.storage_notes, the DM) ------------
_disk_text = """node_filesystem_size_bytes{device="/dev/nvme1n1",fstype="ext4",mountpoint="/data"} 8.416882688e+09
node_filesystem_avail_bytes{device="/dev/nvme1n1",fstype="ext4",mountpoint="/data"} 1.859715072e+09
node_filesystem_size_bytes{device="/dev/root",fstype="ext4",mountpoint="/"} 1.0e+10
node_filesystem_avail_bytes{device="/dev/root",fstype="ext4",mountpoint="/"} 9.0e+09
node_network_transmit_bytes_total{device="ens5"} 1.5e+12
"""
check("disk: the data disk's size and free bytes are read from the mountpoint /data only",
      _mt.parse_disk(_disk_text) == (8416882688.0, 1859715072.0), _mt.parse_disk(_disk_text))
check("disk: a missing series, a NaN or more free than size is 'not known'",
      _mt.parse_disk(_metrics_text) is None
      and _mt.parse_disk(_disk_text.replace("1.859715072e+09", "NaN")) is None
      and _mt.parse_disk(_disk_text.replace("1.859715072e+09", "9e+09")) is None)
_sn_ok = _rd.storage_notes((8416882688.0, 1859715072.0), 3.9e9, {})
_sn_full = _rd.storage_notes((8416882688.0, 0.5e9), 3.9e9, {"disk_warn_used_pct": 92})
_sn_none = _rd.storage_notes(None, 3.9e9, {})
check("disk: 78% used is noted on the receipt with no warning",
      _sn_ok[1] == [] and _sn_ok[0]["disk_used_pct"] == 77.9 and _sn_ok[0]["db_mb"] == 3719
      and _sn_ok[0]["disk_free_gb"] == 1.86, _sn_ok)
check("disk: past 92% is a warning, never a problem word (the run stays ok)",
      len(_sn_full[1]) == 1 and "94%" in _sn_full[1][0]
      and not any(w in _sn_full[1][0] for w in ("failed", "brake")), _sn_full)
check("disk: a disk that was not read is said, and warns of nothing", _sn_none == ({"db_mb": 3719, "disk": "not read"}, []),
      _sn_none)


class _DiskResp:
    headers = {}

    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


import importlib.util as _ilu  # noqa: E402
_mspec = _ilu.spec_from_file_location("meter_fresh", os.path.join(ROOT, "worker", "meter.py"))
_mf = _ilu.module_from_spec(_mspec)
_mspec.loader.exec_module(_mf)   # a fresh copy: the tests above leave meter.read patched
_saved_urlopen, _saved_env = _mf.urllib.request.urlopen, dict(os.environ)
try:
    os.environ.update({"SUPABASE_METRICS_KEY": "k", "SUPABASE_PROJECT_REF": "x"})
    _mf.urllib.request.urlopen = lambda req, timeout=30.0: _DiskResp(_disk_text.encode())
    _got = _mf.read()
    check("disk: one metrics read gives the counter and the disk (no read of its own)",
          _got == 1.5e12 and _mf.last_disk() == (8416882688.0, 1859715072.0), (_got, _mf.last_disk()))

    def _boom(req, timeout=30.0):
        raise OSError("metrics endpoint down")
    _mf.urllib.request.urlopen = _boom
    check("disk: a failed read leaves no disk, never the reading before it",
          _mf.read() is None and _mf.last_disk() is None, _mf.last_disk())
finally:
    _mf.urllib.request.urlopen = _saved_urlopen
    os.environ.clear()
    os.environ.update(_saved_env)

_sent = []
_saved_dm = _rd.dm
try:
    _rd.dm = lambda text: _sent.append(text)
    _wr = type("W", (), {"receipt": {"run_id": "abcdef0123", "status": "ok", "caps_hit": [], "problems": [],
                                     "warnings": _sn_full[1], "stages": {}}})()
    _rd.tell_vlad(_wr)
    _quiet = type("Q", (), {"receipt": {"run_id": "abcdef0123", "status": "ok", "caps_hit": [], "problems": [],
                                        "warnings": [], "stages": {}}})()
    _rd.tell_vlad(_quiet)
    check("disk: an ok night with a disk warning sends one DM naming the disk and the step; a quiet ok night sends none",
          len(_sent) == 1 and "disk is nearly full" in _sent[0] and "Compute and Disk" in _sent[0]
          and "Nothing for anyone to do" not in _sent[0], _sent)
    _sent.clear()
    _fr = type("F", (), {"receipt": {"run_id": "abcdef0123", "status": "ok", "caps_hit": [], "warnings": _sn_full[1],
                                     "problems": ["the site's freshness date reads x eight minutes after the run"],
                                     "stages": {}}})()
    _rd.tell_vlad(_fr)
    check("disk: with another problem on the night the DM names it and does not say the site is current",
          len(_sent) == 1 and "freshness" in _sent[0] and "site is current" not in _sent[0], _sent)
finally:
    _rd.dm = _saved_dm

print(f"\ntest_sweep_units: {len(FAILS)} failure(s)" + (": " + "; ".join(FAILS) if FAILS else ""))
sys.exit(bool(FAILS))

