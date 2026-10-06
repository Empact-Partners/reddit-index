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

print(f"\ntest_sweep_units: {len(FAILS)} failure(s)" + (": " + "; ".join(FAILS) if FAILS else ""))
sys.exit(bool(FAILS))

