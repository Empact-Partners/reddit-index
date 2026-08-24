#!/usr/bin/env python3
"""Depth discovery v2 — every subreddit that makes sense, per category.

Executes Stages 1-2 of docs/depth-execution-plan.md. Four candidate angles,
then qualification bars with NO top-N cap: every (category, subreddit) pair
that passes all bars becomes is_scoring.

    python3 data/discover_v2.py --stage enumerate   # Angle A: fleet knowledge
    python3 data/discover_v2.py --stage evidence    # Angle B: sitewide search
    python3 data/discover_v2.py --stage rescue      # Angle C: posture v2 + vendor
    python3 data/discover_v2.py --stage siblings    # Angle D: one-hop sidebar
    python3 data/discover_v2.py --stage candidates  # merge + Gate 1 report
    python3 data/discover_v2.py --stage qualify     # bars -> CSV v2 [--dry-run]
    python3 data/discover_v2.py --stage status

Everything is disk-idempotent: per-category and per-sub state under
data/.discover-v2/ (gitignored), Reddit responses cached by reddit_client,
fleet out-files re-polled never repaired. Kill and re-run at any point.

Doctrine carried over from v1's measured failures:
- The v1 HOSTILE regex read "no self-promotion" as "no brand discussion" and
  killed 904 rows; posture here is a fleet judgment where only `forbid`
  excludes. Rules TEXT was never cached by v1, so this stage re-fetches it.
- The v1 vendor token-intersection detector is trigger-happy at 6,040 brands
  (466 flags); here the fleet judges vendor-ness with the sub's own rules and
  description in hand, token matching demoted to a prompt hint + a full-name
  equality fallback.
- refine_local.py must NEVER re-run over the shipped CSV; this script writes
  v2 columns additively and never touches the fleet-judged `topicality`.
- ONE HTTP client only (worker/reddit_client.py): a second client means a
  second independent 0.75s floor stacking above the ~100 QPM app budget.
"""
import argparse, functools
import collections
import csv
import hashlib
import json
import os
import re
import shutil
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "worker"))
sys.path.insert(0, os.path.expanduser("~/.claude/api_helpers"))

import reddit_client as rc  # noqa: E402
from codex_fleet import CodexFleet  # noqa: E402
import discover  # noqa: E402  (VENDOR_TOKENS, SHIPPED — read-only import)

V2 = os.path.join(HERE, ".discover-v2")
ENUM = os.path.join(V2, "enum")
EVID = os.path.join(V2, "evidence")
RULES = os.path.join(V2, "rules")
POSTURE = os.path.join(V2, "posture")          # per-sub verdicts
POSTURE_OUT = os.path.join(V2, "posture-out")  # fleet batch out-files
TOPIC_OUT = os.path.join(V2, "topic-out")      # fleet batch out-files
SIB = os.path.join(V2, "siblings")
QUAL = os.path.join(V2, "qual")
CACHE = os.path.join(HERE, ".discover-cache")           # v1 probe cache, shared
BODIES = os.path.join(CACHE, "bodies")                  # v1 bodies cache, shared
TOPIC = os.path.join(CACHE, "topicality")               # v1 topicality cache, shared
for d in (V2, ENUM, EVID, RULES, POSTURE, POSTURE_OUT, TOPIC_OUT, SIB, QUAL,
          CACHE, BODIES, TOPIC):
    os.makedirs(d, exist_ok=True)

CSV_PATH = os.path.join(HERE, "category-subreddits.csv")
RUN_ID_V2 = "v2-" + time.strftime("%Y%m%d", time.gmtime())

SERVER = "local-mac"
# Overridable because 40 is not a universal constant — it is what THIS box could sustain in
# August when it was idle. On 2026-08-21, with swap at 33.8 GB of 34.8 and a runaway system
# process, 40-wide put 80 enumerate jobs into the 25-minute timeout without a single
# completion: each session was starved, not stuck. Fleet width has to track the machine, so
# set RI_FLEET_WIDTH rather than editing this line.
MAX_INFLIGHT = int(os.environ.get("RI_FLEET_WIDTH", "40"))
fleet = CodexFleet()

# Reddit subreddit names: 2-21 chars, alnum + underscore, not a profile sub.
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_]{1,20}$")

V1_COLS = ["category", "category_slug", "subreddit", "status", "subscribers",
           "rule_posture", "posture_source", "is_vendor_sub", "scorable",
           "is_scoring", "comments_per_hour", "brand_bearing_share",
           "bb_per_hour", "distinct_threads_in_page", "measured_at", "source",
           "run_id", "brand_bearing_share_substring", "topicality", "worth"]
V2_COLS = ["posture_v2", "vendor_v2", "type_tag", "angle", "evidence_count",
           "topicality_v2", "alive_ppw", "qualified", "run_id_v2"]

POSTURE_MAP = {"allow": "permissive", "restricted": "capped", "forbid": "hostile"}


# ───────────────────────────────────────────────────── fleet plumbing (lifted)
# Parameterized lift of data/enumerate_brands.py::run_fleet_phase — that one
# hardcodes model by label and reasoning_effort=medium; we need terra AND luna.
# Behavior otherwise identical: journal-before-submit, 3 rounds recomputed
# from disk, idle-detect 180s, UNKNOWN==FULL.

def fleet_running():
    try:
        h = fleet.health()
        for e in (h if isinstance(h, list) else [h]):
            inner = e.get("health") or e
            if not e.get("ok", True):
                return None
            n = inner.get("running")
            if isinstance(n, int):
                return n + (inner.get("queued") or 0)
    except Exception:
        return None
    return None


def wait_for_slot():
    while True:
        n = fleet_running()
        if n is not None and n < MAX_INFLIGHT:
            return
        time.sleep(20 if n is None else 8)


def require_fleet():
    for _ in range(3):
        if fleet_running() is not None:
            return
        time.sleep(5)
    sys.exit("fleet unreachable (local-mac :8787) — start it before fleet stages")


def journal(rec):
    with open(os.path.join(V2, "journal.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")


def parse_out(fp, want="object"):
    """A mid-write out-file parses as None = still pending. Never 'repair'."""
    try:
        raw = open(fp).read()
        pat = r"\{.*\}" if want == "object" else r"\[.*\]"
        m = re.search(pat, raw, re.S)
        obj = json.loads(m.group(0) if m else raw)
        ok = isinstance(obj, dict) if want == "object" else isinstance(obj, list)
        return obj if ok else None
    except Exception:
        return None


def run_fleet(jobs, label, model, effort="medium", job_timeout=600,
              round_deadline=None, want="object"):
    """jobs: list of (job_id, task, out_fp). Disk-idempotent, 3 rounds."""
    if round_deadline is None:
        round_deadline = max(720, 60 * len(jobs))
    for rnd in range(1, 4):
        pending = [(j, t, fp) for j, t, fp in jobs if parse_out(fp, want) is None]
        if not pending:
            break
        print(f"{label} round {rnd}: {len(pending)} jobs", flush=True)
        for jid, task, fp in pending:
            if os.path.exists(fp):
                os.remove(fp)
            wait_for_slot()
            journal({"phase": label, "job": jid, "round": rnd, "t": time.time()})
            for attempt in range(5):
                try:
                    r = fleet.submit(task, server=SERVER, mode="workspace-write",
                                     model=model, workspace=V2, timeout=job_timeout,
                                     reasoning_effort=effort)
                    journal({"phase": label, "job": jid, "job_id": r["job_id"]})
                    break
                except Exception:
                    time.sleep(10 * (attempt + 1))
        deadline = time.time() + round_deadline
        last_done, last_change = -1, time.time()
        while time.time() < deadline:
            left = [1 for _, _, fp in pending if parse_out(fp, want) is None]
            done = len(jobs) - len([1 for _, _, fp in jobs if parse_out(fp, want) is None])
            print(f"  {done}/{len(jobs)} {label} done", flush=True)
            if not left:
                break
            if done != last_done:
                last_done, last_change = done, time.time()
            elif time.time() - last_change > 180 and (fleet_running() or 0) == 0:
                print(f"  {label}: fleet idle, no progress 180s -> next round", flush=True)
                break
            time.sleep(25)


# ─────────────────────────────────────────────────────────── shared data reads

def taxonomy():
    return list(csv.DictReader(open(os.path.join(HERE, "taxonomy-100.csv"))))


def categories_meta():
    """slug -> row of categories.csv (display name + qualification nouns)."""
    return {r["slug"]: r for r in csv.DictReader(open(os.path.join(HERE, "categories.csv")))}


def csv_rows():
    return list(csv.DictReader(open(CSV_PATH)))


def brands_by_cat():
    out = collections.defaultdict(list)
    for r in csv.DictReader(open(os.path.join(HERE, "brands.csv"))):
        out[r["primary_category_slug"]].append(r)
    return out


def norm_sub(s):
    if not isinstance(s, str):
        return None
    s = s.strip().strip("/").strip()
    s = re.sub(r"^(r/|/r/)", "", s, flags=re.I).strip().rstrip(".,;:!?)")
    if not NAME_RE.match(s) or s.lower().startswith("u_"):
        return None
    return s


def atomic_json(fp, obj):
    with open(fp + ".tmp", "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(fp + ".tmp", fp)


def cand_fp(slug):
    return os.path.join(V2, f"cand_{slug}.json")


def load_cand(slug):
    fp = cand_fp(slug)
    return json.load(open(fp)) if os.path.exists(fp) else {}


def add_candidate(cands, sub, angle, type_tag=None, confidence=None, why=None,
                  source_sub=None):
    k = sub.lower()
    rec = cands.setdefault(k, {"sub": sub, "angles": [], "type_tag": type_tag or "",
                               "confidence": confidence, "why": why or "",
                               "source_sub": source_sub or ""})
    if angle not in rec["angles"]:
        rec["angles"].append(angle)
    if type_tag and not rec.get("type_tag"):
        rec["type_tag"] = type_tag
    if confidence is not None:
        rec["confidence"] = max(rec.get("confidence") or 0, confidence)
    return rec


def evidence_state(slug):
    fp = os.path.join(EVID, f"{slug}.json")
    return json.load(open(fp)) if os.path.exists(fp) else {"queries": {}, "tally": {}, "examples": {}}


def evidence_tally(slug):
    """Read-only tally for the qualify loop. evidence_state() is left uncached because
    stage_evidence MUTATES what it returns."""
    rec = _json_cached(os.path.join(EVID, f"{slug}.json"))
    return (rec or {}).get("tally", {})


def build_candidates(slugs=None):
    """Merge A/D cand files + B evidence tallies. Returns {slug: {sub_lower: rec}}."""
    out = {}
    for row in taxonomy():
        slug = row["slug"]
        if slugs and slug not in slugs:
            continue
        cands = load_cand(slug)
        ev = evidence_state(slug)
        for sub_l, n in ev["tally"].items():
            if n >= 2 and sub_l not in cands:
                # evidence alone creates a candidate; a single stray crosspost
                # never does (the r/all junk guard)
                add_candidate(cands, ev.get("names", {}).get(sub_l, sub_l), "B")
        for sub_l, rec in cands.items():
            rec["evidence_count"] = ev["tally"].get(sub_l, 0)
        out[slug] = cands
    return out


def starved_categories():
    per = collections.Counter()
    for r in csv_rows():
        if r["is_scoring"] == "True":
            per[r["category_slug"]] += 1
    return sorted(s for s in {r["slug"] for r in taxonomy()} if per[s] < 5)


# ──────────────────────────────────────────────────────── Angle A: enumeration

ENUM_SUBS_PROMPT = """You know Reddit's community landscape deeply. List every \
subreddit where {name} software is discussed by the people who buy, use, or \
administer it.

Include ALL of these kinds:
- dedicated: subs about this software category or a specific comparison space
- profession: the JOB that uses these tools daily — this matters more than
  generic tech subs (r/restaurantowners for restaurant POS, r/eventplanning
  for event management, r/msp for RMM)
- industry: the industry vertical these buyers work in
- adjacent: workflow-adjacent communities where the category comes up as a
  tool of the trade
- selfhosted: self-hosted / open-source alternative communities

Category nouns: {nouns}. Example brands: {brands}.

Return 30-80 entries. Only subreddits you are confident actually exist — omit
rather than guess; every name you output will be verified against Reddit.
Each entry: {{"sub": "name without r/", "type": "dedicated|profession|industry|adjacent|selfhosted", "why": "one line", "confidence": 0.0-1.0}}

Write ONLY a JSON array of these objects to the file {out_fp} (create it).
Do not print the JSON to the console. Do not write any other file."""


def stage_enumerate(only):
    require_fleet()
    bmap = brands_by_cat()
    jobs = []
    for row in taxonomy():
        slug = row["slug"]
        if only and slug not in only:
            continue
        fp = os.path.join(ENUM, f"out_{slug}.json")
        brands = ", ".join(b["brand"] for b in bmap.get(slug, [])[:10]) or "(none)"
        task = ENUM_SUBS_PROMPT.format(name=row["category"],
                                       nouns=row["nouns"].replace(";", ", "),
                                       brands=brands, out_fp=fp)
        jobs.append((slug, task, fp))
    run_fleet(jobs, "enum-subs", model="gpt-5.6-terra", job_timeout=1500, want="array")

    # harvest into cand files
    kept = dropped = 0
    for slug, _, fp in jobs:
        arr = parse_out(fp, want="array")
        if arr is None:
            continue
        cands = load_cand(slug)
        for e in arr:
            if not isinstance(e, dict):
                continue
            sub = norm_sub(e.get("sub"))
            if not sub:
                dropped += 1
                continue
            tag = e.get("type") if e.get("type") in (
                "dedicated", "profession", "industry", "adjacent", "selfhosted") else "adjacent"
            try:
                conf = float(e.get("confidence") or 0)
            except (TypeError, ValueError):
                conf = 0.0
            add_candidate(cands, sub, "A", type_tag=tag, confidence=conf,
                          why=str(e.get("why") or "")[:160])
            kept += 1
        atomic_json(cand_fp(slug), cands)
    done = sum(1 for _, _, fp in jobs if parse_out(fp, want="array") is not None)
    print(f"enumerate: {done}/{len(jobs)} categories, {kept} names kept, "
          f"{dropped} invalid names dropped", flush=True)


# ─────────────────────────────────────────────────── Angle B: evidence search

def evidence_queries(row, bmap, both_sorts):
    slug = row["slug"]
    nouns = [n.strip() for n in row["nouns"].split(";") if n.strip()][:3]
    brands = [b["brand"] for b in bmap.get(slug, []) if b["ambiguity_class"] == "low"][:10]
    qs = []
    for b in brands:
        q = f'"{b}"' if " " in b else b
        qs.append((q, "relevance"))
        if both_sorts:
            qs.append((q, "new"))
    intent = ([f"best {nouns[0]}", f"{nouns[0]} recommendation"] if nouns else [])
    for n in nouns + intent:
        qs.append((n, "relevance"))
        qs.append((n, "new"))
    return qs


def stage_evidence(only, both_sorts=False):
    bmap = brands_by_cat()
    for row in taxonomy():
        slug = row["slug"]
        if only and slug not in only:
            continue
        st = evidence_state(slug)
        st.setdefault("names", {})
        qs = evidence_queries(row, bmap, both_sorts)
        todo = [(q, s) for q, s in qs if f"{q}|{s}" not in st["queries"]]
        if not todo:
            continue
        for q, sort in todo:
            resp = rc.get("/search", {"q": q, "limit": 100, "type": "link",
                                      "raw_json": 1, "sort": sort, "t": "year",
                                      "include_over_18": "on"}, bucket="search_v2")
            if "_err" in resp:
                print(f"  {slug}: search error {resp['_err']} on {q!r} — will retry", flush=True)
                continue
            n = 0
            for x in resp.get("data", {}).get("children", []):
                d = x.get("data", {})
                if x.get("kind") != "t3" or d.get("over_18"):
                    continue
                sub = norm_sub(d.get("subreddit") or "")
                if not sub:
                    continue
                k = sub.lower()
                st["tally"][k] = st["tally"].get(k, 0) + 1
                st["names"][k] = sub
                ex = st["examples"].setdefault(k, [])
                if len(ex) < 3 and d.get("permalink"):
                    ex.append("https://reddit.com" + d["permalink"])
                n += 1
            st["queries"][f"{q}|{sort}"] = {"done": True, "n": n}
            atomic_json(os.path.join(EVID, f"{slug}.json"), st)
        done = len(st["queries"])
        print(f"evidence {slug}: {done}/{len(qs)} queries, "
              f"{len(st['tally'])} subs tallied", flush=True)


# ──────────────────────────────── Angle C: rules re-fetch + posture v2 rescue

POSTURE_PROMPT = """You judge subreddit rules. For each subreddit below decide \
whether COMMUNITY MEMBERS may discuss, compare, and recommend software \
brands/products there, and whether the community is vendor-run.

posture — one of:
  allow       members freely discuss and recommend products. Rules against
              self-promotion, advertising, spam, or vendor solicitation do
              NOT make a sub restricted or forbid — those rules bind vendors
              promoting themselves, not members discussing tools.
  restricted  member brand talk is genuinely confined: weekly recommendation
              megathreads only, "no product recommendation posts", karma
              gates on product talk, mod pre-approval of such posts.
  forbid      the rules prohibit members from discussing or recommending
              commercial products at all.
vendor — true when the community is run by or dedicated to ONE commercial
product/company (its official or de-facto user/support community); false for
independent multi-product communities.

Items:
{items}

Write ONLY a JSON object to the file {out_fp} (create it): keys are the
subreddit names exactly as given, values {{"posture": "allow"|"restricted"|"forbid", "vendor": true|false}}.
Judge every item. Do not print JSON to the console."""


def rules_text(sub):
    """Fetch + cache the ACTUAL rules text (v1 threw it away)."""
    fp = os.path.join(RULES, f"{sub.lower()}.json")
    if os.path.exists(fp):
        return json.load(open(fp))
    rl = rc.get(f"/r/{sub}/about/rules", {"raw_json": 1}, bucket="rules_v2")
    if "_err" in rl:
        return None  # no file -> retried on next run
    txt, n = "", 0
    for r in rl.get("rules", []):
        txt += " ".join(filter(None, [r.get("short_name"), r.get("description"),
                                      r.get("violation_reason")])) + "\n"
        n += 1
    src = "rules"
    if not txt.strip():
        about = get_about(sub)
        side = ""
        if about:
            side = (about.get("description") or "") + " " + (about.get("public_description") or "")
        txt = side if len(side) > 120 else ""
        src = "sidebar" if txt else "none"
    rec = {"sub": sub, "text": txt.strip()[:4000], "n_rules": n, "source": src}
    atomic_json(fp, rec)
    return rec


_about_mem = {}


def get_about(sub):
    """about.json data dict, cached (bucket about_v2 + in-process)."""
    k = sub.lower()
    if k in _about_mem:
        return _about_mem[k]
    a = rc.get(f"/r/{sub}/about", {"raw_json": 1}, bucket="about_v2")
    d = a.get("data") if isinstance(a, dict) and "_err" not in a and a.get("kind") == "t5" else None
    _about_mem[k] = d
    return d


def posture_verdict(sub):
    return _json_cached(os.path.join(POSTURE, f"{sub.lower()}.json"))


def universe_subs(cands=None):
    """Every unique sub in candidates ∪ the existing CSV (name -> display)."""
    subs = {}
    for r in csv_rows():
        subs.setdefault(r["subreddit"].lower(), r["subreddit"])
    for slug_cands in (cands or build_candidates()).values():
        for k, rec in slug_cands.items():
            subs.setdefault(k, rec["sub"])
    return subs


def stage_rescue(cands=None):
    require_fleet()
    subs = universe_subs(cands)
    need = [s for k, s in sorted(subs.items()) if posture_verdict(s) is None]
    print(f"rescue: {len(subs)} subs in universe, {len(need)} need verdicts", flush=True)

    # 1. rules text (1 call/sub, cached; existing subs' text was never kept)
    with_text = []
    for s in need:
        rec = rules_text(s)
        if rec is not None:
            with_text.append((s, rec))
    print(f"  rules text present for {len(with_text)}/{len(need)}", flush=True)

    # 2. fleet judgment, batches of 20
    jobs = []
    for i in range(0, len(with_text), 20):
        chunk = with_text[i:i + 20]
        bid = hashlib.sha256("".join(s.lower() for s, _ in chunk).encode()).hexdigest()[:16]
        fp = os.path.join(POSTURE_OUT, f"out_{bid}.json")
        items = []
        for s, rec in chunk:
            about = get_about(s) or {}
            desc = (about.get("public_description") or "")[:200]
            hint = ""
            if s.lower() in discover.VENDOR_TOKENS:
                hint = "note: the name equals a known brand token\n"
            items.append(f"### {s}\ndescription: {desc or '(none)'}\n{hint}"
                         f"rules ({rec['source']}): {rec['text'][:1500] or '(no rules text found)'}")
        task = POSTURE_PROMPT.format(items="\n\n".join(items), out_fp=fp)
        jobs.append((bid, task, fp, chunk))
    run_fleet([(b, t, fp) for b, t, fp, _ in jobs], "posture",
              model="gpt-5.6-terra", job_timeout=600)

    # 3. harvest per-sub verdicts (the resumable truth)
    coded = 0
    for bid, _, fp, chunk in jobs:
        obj = parse_out(fp)
        if not isinstance(obj, dict):
            continue
        low = {k.lower().lstrip("r/"): v for k, v in obj.items() if isinstance(v, dict)}
        for s, _ in chunk:
            v = obj.get(s) or low.get(s.lower())
            if not isinstance(v, dict):
                continue
            p = v.get("posture")
            if p not in ("allow", "restricted", "forbid"):
                continue
            atomic_json(os.path.join(POSTURE, f"{s.lower()}.json"),
                        {"sub": s, "posture_v2": p, "vendor_v2": bool(v.get("vendor")),
                         "source": "fleet"})
            coded += 1
    have = sum(1 for s in subs.values() if posture_verdict(s) is not None)
    print(f"rescue: {coded} newly coded, {have}/{len(subs)} total verdicts", flush=True)


# ─────────────────────────────────────────────── Angle D: sibling expansion

SIB_RE = re.compile(r"(?:^|[\s(\[/])/?r/([A-Za-z0-9][A-Za-z0-9_]{1,20})\b")


def stage_siblings():
    cands = build_candidates()
    scoring = collections.defaultdict(set)   # sub_lower -> {slugs}
    for r in csv_rows():
        if r["is_scoring"] == "True":
            scoring[r["subreddit"].lower()].add(r["category_slug"])
    # sources: scoring subs + all current candidates (one hop, never recursive)
    sources = {}
    for k in scoring:
        sources.setdefault(k, k)
    for slug, cc in cands.items():
        for k, rec in cc.items():
            sources.setdefault(k, rec["sub"])
    added = 0
    for k, name in sorted(sources.items()):
        fp = os.path.join(SIB, f"{k}.json")
        if os.path.exists(fp):
            parsed = json.load(open(fp))["parsed"]
        else:
            about = get_about(name)
            if about is None:
                continue
            text = (about.get("description") or "") + "\n" + (about.get("public_description") or "")
            parsed, seen = [], set()
            for m in SIB_RE.finditer(text):
                sib = norm_sub(m.group(1))
                if not sib or sib.lower() == k or sib.lower() in seen:
                    continue
                seen.add(sib.lower())
                parsed.append(sib)
                if len(parsed) >= 15:  # hub subs list 100+; each sibling costs calls
                    break
            atomic_json(fp, {"parsed": parsed, "at": time.time()})
        # a sibling inherits candidacy in every category its source belongs to
        slugs = set(scoring.get(k, set()))
        for slug, cc in cands.items():
            if k in cc:
                slugs.add(slug)
        for slug in slugs:
            cc = load_cand(slug)
            for sib in parsed:
                if sib.lower() not in cc:
                    add_candidate(cc, sib, "D", source_sub=name)
                    added += 1
            atomic_json(cand_fp(slug), cc)
    print(f"siblings: {len(sources)} sources parsed, {added} new candidates", flush=True)


# ─────────────────────────────────────────────────────── candidates + Gate 1

def stage_candidates():
    cands = build_candidates()
    fp = os.path.join(V2, "candidates.csv")
    with open(fp + ".tmp", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["category_slug", "subreddit", "angles", "type_tag",
                    "evidence_count", "confidence", "source_sub", "why"])
        for slug in sorted(cands):
            for k, r in sorted(cands[slug].items()):
                w.writerow([slug, r["sub"], "+".join(r["angles"]), r.get("type_tag") or "",
                            r.get("evidence_count") or 0, r.get("confidence") if r.get("confidence") is not None else "",
                            r.get("source_sub") or "", (r.get("why") or "")[:120]])
    os.replace(fp + ".tmp", fp)

    counts = {slug: len(cc) for slug, cc in cands.items()}
    uniq = {k for cc in cands.values() for k in cc}
    angle_uniq = collections.Counter()
    for cc in cands.values():
        for r in cc.values():
            if len(r["angles"]) == 1:
                angle_uniq[r["angles"][0]] += 1
    angle_any = collections.Counter(a for cc in cands.values() for r in cc.values() for a in r["angles"])
    vals = sorted(counts.values())
    print(f"\n=== GATE 1 — candidate discovery ===")
    print(f"categories: {len(counts)} | unique subs: {len(uniq)}")
    if vals:
        print(f"candidates/category  min {vals[0]}  med {statistics.median(vals):.0f}  max {vals[-1]}")
    print(f"angle contribution (any): {dict(angle_any)}")
    print(f"angle contribution (sole discoverer): {dict(angle_uniq)}")
    print(f"\nstarved categories ({len(starved_categories())}):")
    for slug in starved_categories():
        cc = cands.get(slug, {})
        subs = sorted(cc.values(), key=lambda r: -(r.get("evidence_count") or 0))
        line = ", ".join(f"{r['sub']}[{'+'.join(r['angles'])}"
                         f"{',' + str(r['evidence_count']) + 'ev' if r.get('evidence_count') else ''}]"
                         for r in subs[:40])
        print(f"  {slug} ({len(cc)}): {line}")
    print(f"\ncandidates.csv written: {fp}")


# ──────────────────────────────────────────────────── cache-file memoisation
# qualify walks 283,113 (category, subreddit) pairs, and every reader below used to do
# json.load(open(fp)) on each call: ~2.8M parses of ~30K distinct files. Measured on
# 2026-08-23 the stage was 52% done after 176 minutes, i.e. ~5.7 hours of almost pure JSON
# decoding, and a restart paid it again from scratch.
#
# Keyed by (path, mtime) so a file rewritten mid-run is re-read rather than served stale.
# Bounded because bodies files are large — an unbounded cache over 29,658 subs is gigabytes
# on a box that has already hit an OOM once.
#
# ONLY read-only callers use these. evidence_state() stays uncached: stage_evidence does
# st.setdefault("names", {}) on the result, and a shared mutable dict there would leak the
# mutation into every later reader.
@functools.lru_cache(maxsize=40_000)
def _json_at(fp, _mtime):
    try:
        with open(fp) as f:
            return json.load(f)
    except Exception:
        return None


def _json_cached(fp):
    try:
        return _json_at(fp, os.path.getmtime(fp))
    except OSError:
        return None


# Subs whose qual_rec fetch failed THIS RUN. qualify walks ~9.5 pairs per subreddit, and
# qual_rec is the one reader that returns None WITHOUT writing a cache file, so a single
# unreachable subreddit paid a full network timeout plus 10-40s of backoff about nine times
# over. (measure_v2 always writes its record, even "unavailable", so it self-caches.)
# Measured 2026-08-23: the stage was network-bound (libcrypto+libssl+dnssd dominated the
# profile, _json was noise) and ran at ~5.7 hours.
#
# A failure is remembered for the run only — nothing is written to disk, so the next run
# still retries, which is the documented behaviour ("retried next run").
_fetch_failed = set()


@functools.lru_cache(maxsize=1024)
def _bodies_at(fp, _mtime):
    try:
        with open(fp) as f:
            return tuple(json.load(f).get("bodies") or ())
    except Exception:
        return ()


# ──────────────────────────────────────────────────────────── qualification

def measure_v2(sub):
    """v1-schema probe record for a sub, from cache or 2 fresh calls."""
    fp = os.path.join(CACHE, sub.lower() + ".json")
    hit = _json_cached(fp)
    if hit is not None:
        return hit
    rec = {"subreddit": sub, "source": "discover_v2", "run_id": RUN_ID_V2}
    about = get_about(sub)
    if about is None:
        rec.update(status="unavailable", error="not_t5")
        atomic_json(fp, rec)
        return rec
    rec.update(status="ok", subscribers=about.get("subscribers") or 0,
               subreddit_type=about.get("subreddit_type"),
               over18=about.get("over18", False),
               quarantine=about.get("quarantine", False),
               public_description=(about.get("public_description") or "")[:300])
    c = rc.get(f"/r/{sub}/comments", {"limit": 100, "raw_json": 1}, bucket="comments_v2")
    ch = c.get("data", {}).get("children", []) if "_err" not in c else []
    bodies = [(x["data"].get("body") or "") for x in ch]
    if ch:
        now = time.time()
        oldest = min(int(x["data"]["created_utc"]) for x in ch)
        span_h = max((now - oldest) / 3600.0, 0.01)
        rec.update(comment_page_n=len(ch), comment_span_hours=round(span_h, 2),
                   comments_per_hour=round(len(ch) / span_h, 2),
                   distinct_threads_in_page=len({x["data"]["link_id"] for x in ch}))
    else:
        rec.update(comment_page_n=0, comment_span_hours=0.0, comments_per_hour=0.0,
                   distinct_threads_in_page=0)
    # rules posture arrives via the rescue stage; bodies cached for the
    # evidence bar and any future re-measure
    bfp = os.path.join(BODIES, sub.lower() + ".json")
    if not os.path.exists(bfp):
        atomic_json(bfp, {"bodies": bodies,
                          "oldest": min((int(x["data"]["created_utc"]) for x in ch), default=0),
                          "n": len(ch), "fetched_at": time.time()})
    rec["measured_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    atomic_json(fp, rec)
    return rec


def qual_rec(sub):
    fp = os.path.join(QUAL, f"{sub.lower()}.json")
    hit = _json_cached(fp)
    if hit is not None:
        return hit
    if ("q", sub.lower()) in _fetch_failed:
        return None
    nl = rc.get(f"/r/{sub}/new", {"limit": 25, "raw_json": 1}, bucket="new_v2")
    if "_err" in nl:
        _fetch_failed.add(("q", sub.lower()))
        return None  # retried next run, not nine more times in this one
    now = time.time()
    posts = [x["data"] for x in nl.get("data", {}).get("children", [])
             if not x["data"].get("stickied")]
    n14 = sum(1 for p in posts if now - (p.get("created_utc") or 0) <= 14 * 86400)
    rec = {"sub": sub, "alive_n14": n14, "alive_ppw": round(n14 / 2.0, 2),
           "titles": [(p.get("title") or "")[:200] for p in posts],
           "evaluated_at": time.time()}
    atomic_json(fp, rec)
    return rec


# per-category qualification matchers: SAFE word-boundary aliases (lifted from
# refine.py — not imported: refine's module top pulls in claude_cli) + nouns
def probe_terms():
    by_brand = {r["slug"]: r for r in csv.DictReader(open(os.path.join(HERE, "brands.csv")))}
    out = {}
    for a in csv.DictReader(open(os.path.join(HERE, "brand-aliases.csv"))):
        if a["surface_class"] != "SAFE" or a["bare_disabled"] == "True":
            continue
        b = by_brand.get(a["brand_slug"])
        if not b:
            continue
        for slug in [b["primary_category_slug"]] + [
                s for s in (b["also_in_category_slugs"] or "").split(";") if s]:
            out.setdefault(slug, set()).add(a["alias"].lower())
    return {k: sorted(v) for k, v in out.items()}


_matchers = {}


def matcher(slug, terms_map, nouns_map):
    if slug not in _matchers:
        terms = terms_map.get(slug, []) + nouns_map.get(slug, [])
        if terms:
            pat = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
            _matchers[slug] = re.compile(rf"(?<![a-z0-9]){pat}(?![a-z0-9])", re.I)
        else:
            _matchers[slug] = None
    return _matchers[slug]


def topicality_of(slug, sub):
    fp = os.path.join(TOPIC, re.sub(r"[^a-z0-9|]+", "_", f"{slug}|{sub}".lower()) + ".json")
    rec = _json_cached(fp)
    try:
        return rec["t"]
    except (TypeError, KeyError):
        return None


TOPIC_SYSTEM = """You judge whether a Reddit community is a place where a named
software category is actually evaluated and discussed by its practitioners.

Answer for each item with one number:
  1.0  the community IS about this category, or about the work that uses it
       daily, so buying and switching decisions get discussed there
  0.5  adjacent: the category comes up as a tool of a broader trade
  0.0  wrong: brand names may appear, but never as a product evaluation
       (hobby, sport, local, meme, marketplace, news, or unrelated trade
       communities all score 0.0 even when the words appear constantly)

Be strict. A used-hardware marketplace where people say "PayPal" to arrange a
sale is 0.0 for Payment Processing. A jiu-jitsu community is 0.0 for everything."""


def topicality_fill(pairs, cat_names):
    """Code uncached (slug, sub) pairs on the fleet. Shared v1 cache format."""
    require_fleet()
    todo = [(f"{slug}|{sub}", slug, sub) for slug, sub in pairs
            if topicality_of(slug, sub) is None]
    if not todo:
        return
    print(f"topicality: {len(todo)} uncoded pairs", flush=True)
    jobs = []
    for i in range(0, len(todo), 25):
        chunk = todo[i:i + 25]
        bid = hashlib.sha256("".join(t[0] for t in chunk).encode()).hexdigest()[:16]
        fp = os.path.join(TOPIC_OUT, f"out_{bid}.json")
        lines = []
        for iid, slug, sub in chunk:
            rec = measure_v2(sub)
            d = (rec.get("public_description") or "").replace("\n", " ")[:260]
            lines.append(f'{iid}\tcategory="{cat_names[slug]}"\tr/{sub}\t{d or "(no description)"}')
        task = (TOPIC_SYSTEM + "\n\nRate each item below. Write ONLY a JSON object "
                f"mapping every item id (the first tab-separated field) to its "
                f"number to the file {fp} (create it). Every id present.\n\n"
                + "\n".join(lines))
        jobs.append((bid, task, fp, chunk))
    run_fleet([(b, t, fp) for b, t, fp, _ in jobs], "topicality",
              model="gpt-5.6-luna", effort="low", job_timeout=300)
    # A batch that comes back SHORT loses its missing pairs silently: they stay uncoded, so
    # topicality_of() returns None, so topic_ok is False, so the pair fails qualification —
    # with no error anywhere. Measured 2026-08-24 at batch 25: 40/40 batches complete. If
    # that ever changes (a bigger batch, a slower model, a tighter timeout) this says so
    # instead of quietly shrinking the mapping.
    short_batches, missing_pairs = 0, 0
    for bid, _, fp, chunk in jobs:
        obj = parse_out(fp)
        if not isinstance(obj, dict):
            short_batches += 1
            missing_pairs += len(chunk)
            continue
        got = sum(1 for iid, _, _ in chunk if iid in obj)
        if got < len(chunk):
            short_batches += 1
            missing_pairs += len(chunk) - got
        for iid, slug, sub in chunk:
            v = obj.get(iid)
            try:
                t = float(v)
            except (TypeError, ValueError):
                continue
            if t in (0.0, 0.5, 1.0):
                tf = os.path.join(TOPIC, re.sub(r"[^a-z0-9|]+", "_", iid.lower()) + ".json")
                json.dump({"t": t}, open(tf, "w"))
    if short_batches:
        print(f"  !! {short_batches} topicality batches came back short — {missing_pairs} "
              f"pairs left uncoded and will FAIL qualification silently. Re-run the stage to "
              f"fill them before trusting the mapping.", flush=True)


def vendor_of(sub, verdict):
    """Precedence: hand-checked shipped prior -> fleet -> full-name equality."""
    prior = discover.SHIPPED.get(sub.lower())
    if prior and prior.get("is_vendor_sub") in ("True", "False"):
        return prior["is_vendor_sub"] == "True"
    if verdict is not None:
        return bool(verdict.get("vendor_v2"))
    return sub.lower() in discover.VENDOR_TOKENS


def bodies_of(sub):
    fp = os.path.join(BODIES, sub.lower() + ".json")
    try:
        return _bodies_at(fp, os.path.getmtime(fp))
    except OSError:
        return ()


def stage_qualify(dry_run=False):
    cands = build_candidates()
    cats = categories_meta()
    cat_names = {r["slug"]: r["category"] for r in taxonomy()}
    terms_map = probe_terms()
    nouns_map = {slug: [n.strip() for n in (r.get("nouns") or "").split(";") if n.strip()]
                 for slug, r in cats.items()}
    rows = csv_rows()
    existing = {(r["category_slug"], r["subreddit"].lower()): r for r in rows}
    csv_casing = {r["subreddit"].lower(): r["subreddit"] for r in rows}

    # the qualification universe: every candidate pair + every existing pair
    pairs = {}
    for slug, cc in cands.items():
        for k, rec in cc.items():
            # existing CSV casing is canonical for known subs (protects the
            # seeder's lower() dedup from case-variant double rows)
            pairs[(slug, k)] = csv_casing.get(k, rec["sub"])
    for (slug, k), r in existing.items():
        pairs.setdefault((slug, k), r["subreddit"])
    print(f"qualify: {len(pairs)} (category, sub) pairs, "
          f"{len({k for _, k in pairs})} unique subs", flush=True)

    # q1+q2: probe + alive, per unique sub (network, cached)
    subs = {}
    for (slug, k), name in pairs.items():
        subs.setdefault(k, name)
    for i, (k, name) in enumerate(sorted(subs.items())):
        measure_v2(name)
        qual_rec(name)
        if i % 250 == 0:
            print(f"  probe/alive {i}/{len(subs)}", flush=True)

    # cheap bars first — topicality (fleet) is only DECISIVE for pairs that
    # pass everything else, and posture (fleet + rules fetch) only matters for
    # subs that are open and alive. At a sibling-expanded universe (~17k subs,
    # ~82k pairs) this ordering is the difference between ~3,200 luna batches
    # and ~1,000.
    was_scoring_subs = {r["subreddit"].lower() for r in rows if r["is_scoring"] == "True"}

    def cheap_bars(slug, k, name):
        m = measure_v2(name)
        q = qual_rec(name) or {}
        open_ok = (m.get("status") == "ok"
                   and m.get("subreddit_type") in (None, "public")
                   and not m.get("over18") and not m.get("quarantine"))
        alive_ok = (q.get("alive_n14") or 0) >= 4
        ev = evidence_tally(slug).get(k, 0)
        mm = matcher(slug, terms_map, nouns_map)
        evidence_ok = ev >= 1 or bool(mm and open_ok and (
            any(mm.search(b) for b in bodies_of(name))
            or any(mm.search(ti) for ti in q.get("titles", []))))
        return m, q, open_ok, alive_ok, ev, evidence_ok

    # q3a: posture fill — only subs that are open AND (alive or historically
    # scoring); a dead or dormant sub needs no rules judgment
    missing_posture = [name for k, name in subs.items()
                       if posture_verdict(name) is None
                       and measure_v2(name).get("status") == "ok"
                       and ((qual_rec(name) or {}).get("alive_n14", 0) >= 4
                            or k in was_scoring_subs)]
    if missing_posture:
        print(f"  {len(missing_posture)} open+alive subs missing posture -> rescue",
              flush=True)
        stage_rescue(cands)

    # q3b: topicality fill — only pairs where every cheap bar already passes
    # (for anything else topicality cannot change the outcome)
    # Both loops below walk 283,113 pairs and used to print NOTHING until they finished.
    # On 2026-08-23 that silence hid a network bug for three hours: "no output" and "no
    # progress" are indistinguishable from outside, and memoising the cache reads removed
    # even the lsof signal a probe could have used. A counter costs nothing and makes the
    # phase observable.
    need_topic = []
    for _i, ((slug, k), name) in enumerate(pairs.items()):
        if _i % 10000 == 0:
            print(f"  cheap bars {_i}/{len(pairs)} · {slug}", flush=True)
        if topicality_of(slug, name) is not None:
            continue
        m, q, open_ok, alive_ok, ev, evidence_ok = cheap_bars(slug, k, name)
        verdict = posture_verdict(name)
        if (open_ok and alive_ok and evidence_ok and not vendor_of(name, verdict)
                and (verdict or {}).get("posture_v2") in ("allow", "restricted")):
            need_topic.append((slug, name))
    topicality_fill(need_topic, cat_names)

    # q4: evaluate the six bars
    out_rows, report, drops = [], collections.defaultdict(lambda: [0, 0]), []
    for _i, ((slug, k), name) in enumerate(sorted(pairs.items())):
        if _i % 10000 == 0:
            print(f"  verdicts {_i}/{len(pairs)} · {slug}", flush=True)
        m, q, open_ok, alive_ok, ev, evidence_ok = cheap_bars(slug, k, name)
        verdict = posture_verdict(name)
        t = topicality_of(slug, name)

        vendor = vendor_of(name, verdict)
        posture = (verdict or {}).get("posture_v2")
        posture_ok = posture in ("allow", "restricted")
        topic_ok = (t or 0.0) >= 0.5

        qualified = all([open_ok, alive_ok, not vendor, posture_ok, topic_ok, evidence_ok])
        prev = existing.get((slug, k))
        was_scoring = bool(prev) and prev["is_scoring"] == "True"
        hard_ok = open_ok and posture != "forbid" and not vendor
        is_scoring = qualified or (was_scoring and hard_ok)
        if was_scoring and not is_scoring:
            drops.append((slug, name, "closed" if not open_ok else
                          ("forbid" if posture == "forbid" else "vendor")))
        report[slug][0] += 1 if is_scoring else 0
        report[slug][1] += 1

        rec = cands.get(slug, {}).get(k, {})
        posture_mapped = POSTURE_MAP.get(posture)
        if prev:
            row = dict(prev)
            # sanctioned exception to additive-only: the DB CHECK constraint
            # accepts only the 4 v1 values and seed_subreddits reads this
            # column verbatim — without the overwrite the rescue never lands
            if posture_mapped:
                row["rule_posture"] = posture_mapped
                row["posture_source"] = "fleet_v2"
            row["is_vendor_sub"] = str(vendor)
        else:
            bodies = bodies_of(name)
            bb = 0.0
            m2 = matcher(slug, {k2: v for k2, v in terms_map.items()}, {})
            if m2 and bodies:
                bb = round(sum(1 for b in bodies if m2.search(b)) / len(bodies), 4)
            cph = float(m.get("comments_per_hour") or 0)
            row = {c: "" for c in V1_COLS}
            row.update(category=cat_names.get(slug, slug), category_slug=slug,
                       subreddit=name, status=m.get("status", ""),
                       subscribers=m.get("subscribers") or 0,
                       rule_posture=posture_mapped or "unknown",
                       posture_source="fleet_v2" if posture_mapped else "none",
                       is_vendor_sub=str(vendor),
                       comments_per_hour=cph, brand_bearing_share=bb,
                       bb_per_hour=round(cph * bb, 4),
                       distinct_threads_in_page=m.get("distinct_threads_in_page") or 0,
                       measured_at=m.get("measured_at", ""), source="discover_v2",
                       run_id=RUN_ID_V2, brand_bearing_share_substring="",
                       topicality=t if t is not None else "",
                       worth=round((t or 0.0) * cph * bb, 4))
        row["scorable"] = str(bool(open_ok and posture != "forbid" and not vendor))
        row["is_scoring"] = str(is_scoring)
        row["posture_v2"] = posture or ""
        row["vendor_v2"] = str(bool((verdict or {}).get("vendor_v2"))) if verdict else ""
        row["type_tag"] = rec.get("type_tag") or ("v1" if prev else "")
        row["angle"] = "+".join(rec.get("angles") or (["v1"] if prev else []))
        row["evidence_count"] = ev
        row["topicality_v2"] = t if t is not None else ""
        row["alive_ppw"] = q.get("alive_ppw", "")
        row["qualified"] = str(qualified)
        row["run_id_v2"] = RUN_ID_V2
        out_rows.append(row)

    # never publish a scoring row that is hostile/vendor (13-algorithm invariant)
    bad = [r for r in out_rows if r["is_scoring"] == "True"
           and (r["rule_posture"] == "hostile" or r["is_vendor_sub"] == "True")]
    assert not bad, f"scoring rows violate posture/vendor invariant: {bad[:5]}"

    per = sorted(((slug, sc, tot) for slug, (sc, tot) in report.items()), key=lambda x: x[1])
    print(f"\n=== qualify summary ({'DRY RUN' if dry_run else 'writing CSV'}) ===")
    scs = sorted(sc for _, sc, _ in per)
    print(f"scoring/category  min {scs[0]}  med {statistics.median(scs):.0f}  max {scs[-1]}"
          f"  | total scoring rows {sum(scs)}  | under-5 categories "
          f"{[s for s, sc, _ in per if sc < 5]}")
    if drops:
        print(f"hard-bar DROPS of currently-scoring subs ({len(drops)}):")
        for slug, name, why in drops:
            print(f"  {slug}: r/{name} ({why})")
    if dry_run:
        return

    bak = os.path.join(V2, "category-subreddits.v1.bak.csv")
    if not os.path.exists(bak):
        shutil.copy2(CSV_PATH, bak)
    # Preserve every column the live CSV already carries. This wrote V1_COLS + V2_COLS with
    # extrasaction="ignore", which SILENTLY DROPS any column added after this function was
    # written — and `is_core` was added later (8628130). A qualify run would have wiped all
    # 1,741 core slots across 527 subs, collapsed `daily.py --core-only` for the shipped 100
    # categories, and then crashed select_core_subs on a fieldname mismatch. Nothing would
    # have raised. The union below, plus the round-trip assertion, is why it cannot recur.
    existing_cols = []
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="") as f:
            existing_cols = next(csv.reader(f), [])
    cols = list(dict.fromkeys(V1_COLS + V2_COLS + existing_cols))
    lost = [c for c in existing_cols if c not in cols]
    if lost:
        raise SystemExit(f"refusing to write: would drop columns {lost}")
    with open(CSV_PATH + ".tmp", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for row in sorted(out_rows, key=lambda r: (r["category_slug"], r["subreddit"].lower())):
            w.writerow({c: row.get(c, "") for c in cols})
    # a preserved column must survive with its VALUES, not just its header
    with open(CSV_PATH + ".tmp", newline="") as f:
        wrote = next(csv.reader(f), [])
    if set(existing_cols) - set(wrote):
        os.remove(CSV_PATH + ".tmp")
        raise SystemExit(f"refusing to write: header lost {set(existing_cols) - set(wrote)}")
    os.replace(CSV_PATH + ".tmp", CSV_PATH)
    print(f"category-subreddits.csv written: {len(out_rows)} rows "
          f"(backup: {bak})", flush=True)


# ────────────────────────────────────────────────────────────────── status

def stage_status():
    tax = taxonomy()
    cands = build_candidates()
    n_enum = sum(1 for r in tax
                 if parse_out(os.path.join(ENUM, f"out_{r['slug']}.json"), "array") is not None)
    bmap = brands_by_cat()
    ev_done = sum(1 for r in tax
                  if not [1 for q, s in evidence_queries(r, bmap, False)
                          if f"{q}|{s}" not in evidence_state(r["slug"])["queries"]])
    subs = universe_subs(cands)
    n_post = sum(1 for s in subs.values() if posture_verdict(s) is not None)
    n_rules = len([f for f in os.listdir(RULES) if f.endswith(".json")])
    n_qual = len([f for f in os.listdir(QUAL) if f.endswith(".json")])
    n_sib = len([f for f in os.listdir(SIB) if f.endswith(".json")])
    pairs = sum(len(cc) for cc in cands.values())
    print(f"enumerate : {n_enum}/{len(tax)} categories harvested")
    print(f"evidence  : {ev_done}/{len(tax)} categories complete")
    print(f"rescue    : rules {n_rules} | verdicts {n_post}/{len(subs)} universe subs")
    print(f"siblings  : {n_sib} sources parsed")
    print(f"candidates: {pairs} pairs across {sum(1 for c in cands.values() if c)} categories")
    print(f"qualify   : {n_qual} subs probed for aliveness")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=["enumerate", "evidence", "rescue", "siblings",
                             "candidates", "qualify", "status"])
    ap.add_argument("--category", action="append", help="restrict to slug (repeatable)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--both-sorts", action="store_true",
                    help="evidence: run sort=new on brand queries too")
    args = ap.parse_args()
    only = set(args.category or []) or None
    if only:
        bad = only - {r["slug"] for r in taxonomy()}
        if bad:
            sys.exit(f"unknown category slugs: {sorted(bad)}")

    if args.stage == "enumerate":
        stage_enumerate(only)
    elif args.stage == "evidence":
        stage_evidence(only, args.both_sorts)
    elif args.stage == "rescue":
        stage_rescue()
    elif args.stage == "siblings":
        stage_siblings()
    elif args.stage == "candidates":
        stage_candidates()
    elif args.stage == "qualify":
        stage_qualify(args.dry_run)
    elif args.stage == "status":
        stage_status()


if __name__ == "__main__":
    main()
