#!/usr/bin/env python3
"""Reddit Index — category -> subreddit discovery, all 20 categories in one pass.

Supersedes `category-candidates-20.json`, which shipped the PRE-WIDENING list:
254 slots / 156 unique subreddits, against the 347 / 232 that
`category-tests-20.csv` and `data/README.md` claim. 76 of the 232 measured
subreddits have no category attribution anywhere in the repo, and only 13 of 20
categories reproduce the five-scorable-subreddit floor from what shipped.

This script re-derives the mapping from Reddit itself and writes ONE joinable
file, `data/category-subreddits.csv`, which every downstream stage reads.

Disk is the source of truth. Per-subreddit measurements are cached as JSON, so
an interrupted run resumes without re-spending a single call. Measurements
already in `subreddit-measurements.csv` are reused unless their rule posture is
`unknown` (HANDOFF.md item 3: 28 subreddits returned no parseable rules and 22
of them are counted scorable, which means they could be scoring brands in
communities that forbid brand talk).

Instrument is the one in `probe.py`, unchanged, so the numbers stay comparable
to the shipped study.
"""
import base64, csv, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".discover-cache")
os.makedirs(CACHE, exist_ok=True)

RUN_ID = os.environ.get("RUN_ID") or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

cfg = json.load(open(os.path.expanduser("~/.claude.json")))
env = cfg["projects"]["/Users/vladshvets/.claude"]["mcpServers"]["reddit"]["env"]
CID, CS, UA = env["REDDIT_CLIENT_ID"], env["REDDIT_CLIENT_SECRET"], env["REDDIT_USER_AGENT"]

_tok = {"v": None, "t": 0}


def token():
    if _tok["v"] and time.time() - _tok["t"] < 3000:
        return _tok["v"]
    basic = base64.b64encode(f"{CID}:{CS}".encode()).decode()
    r = urllib.request.Request(
        "https://www.reddit.com/api/v1/access_token",
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={"User-Agent": UA, "Authorization": "Basic " + basic})
    _tok["v"] = json.loads(urllib.request.urlopen(r, timeout=25).read())["access_token"]
    _tok["t"] = time.time()
    return _tok["v"]


CALLS = {"n": 0}


def api(path, params=None, tries=3):
    """~80 req/min via a 0.75s floor, per 13-algorithm.md's rate discipline."""
    for i in range(tries):
        u = "https://oauth.reddit.com" + path + ("?" + urllib.parse.urlencode(params) if params else "")
        rq = urllib.request.Request(u, headers={"User-Agent": UA, "Authorization": "Bearer " + token()})
        try:
            with urllib.request.urlopen(rq, timeout=35) as f:
                CALLS["n"] += 1
                time.sleep(0.75)
                return json.loads(f.read())
        except urllib.error.HTTPError as e:
            if e.code == 401:
                _tok["v"] = None
                continue
            if e.code in (429, 500, 502, 503):
                time.sleep(3 * (i + 1))
                continue
            return {"_err": e.code}
        except Exception:
            time.sleep(2)
            continue
    return {"_err": "fail"}


# ---------------------------------------------------------------- rule posture
HOSTILE = re.compile(
    r"no (self.?)?promo|zero tolerance|no advertis|will be removed if.*promotional"
    r"|no vendor|product mentions will be removed|no soliciting", re.I)
CAPPED = re.compile(
    r"weekly (promo|thread)|self.?promotion (is )?(allowed|permitted).{0,40}(saturday|thread|once)"
    r"|max \d+ mention|karma requirement|\d+ karma", re.I)


def posture(rules_txt):
    if HOSTILE.search(rules_txt):
        return "hostile"
    if CAPPED.search(rules_txt):
        return "capped"
    return "permissive"


# ------------------------------------------------------------ vendor detection
# data/README.md: "derived from the brand gazetteer plus each category's seed
# brands, then token-matched against the subreddit name; it is not a
# hand-maintained regex." A prefix matcher previously misclassified r/Frontend
# because `Front` is a brand prefix. Token splitting is what fixes that boundary.
def tokenize(s):
    return [t for t in re.split(r"[^a-z0-9]+", s.lower()) if t]


# Generic words that appear inside brand names and are not themselves brands.
# Without this list "Sales Cloud" would make every r/sales* a vendor community.
VENDOR_STOPWORDS = {
    "crm", "suite", "cloud", "sales", "com", "software", "app", "apps", "one",
    "pro", "plus", "team", "teams", "work", "desk", "book", "books", "box",
    "base", "hub", "flow", "core", "data", "mail", "chat", "shop", "pay", "net",
}


def build_vendor_tokens():
    toks = set()
    with open(os.path.join(HERE, "brand-gazetteer-seed.csv")) as f:
        for row in csv.DictReader(f):
            forms = [row["brand"]] + [a for a in (row.get("aliases") or "").split(";") if a]
            for form in forms:
                for t in tokenize(form):
                    if len(t) >= 3 and t not in VENDOR_STOPWORDS:
                        toks.add(t)
    for cat in json.load(open(os.path.join(HERE, "category-candidates-20.json"))):
        for b in cat["brands"]:
            for t in tokenize(b):
                if len(t) >= 3 and t not in VENDOR_STOPWORDS:
                    toks.add(t)
    return toks


VENDOR_TOKENS = build_vendor_tokens()


def is_vendor_sub(name):
    """A subreddit whose NAME *is* a brand token is a single-product or ecosystem
    community. 13-algorithm.md excludes those from scoring; they stay as evidence.

    Token equality only — never a prefix match. A prefix matcher classified
    r/Frontend as a vendor sub because `Front` is a brand (data/README.md), and
    a prefix rule is also what missed r/ObsidianMD, r/logseq and r/Anytype.

    The shipped study's own `is_vendor_sub` column wins where it exists: those
    232 rows were derived and then hand-checked, and r/gohighlevel and r/SAP
    carry brands that are not in the 113-row seed gazetteer.
    """
    prior = SHIPPED.get(name.lower())
    if prior and prior.get("is_vendor_sub") in ("True", "False"):
        return prior["is_vendor_sub"] == "True"
    parts = set(re.findall(r"[a-z]+|\d+", re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).lower()))
    return bool(parts & VENDOR_TOKENS) or name.lower() in VENDOR_TOKENS


# --------------------------------------------------------------- prior results
def load_shipped_measurements():
    out = {}
    p = os.path.join(HERE, "subreddit-measurements.csv")
    if not os.path.exists(p):
        return out
    with open(p) as f:
        for row in csv.DictReader(f):
            out[row["subreddit"].lower()] = row
    return out


SHIPPED = load_shipped_measurements()


def measure(sub, brands):
    """3 API calls: /about, /about/rules, /comments. Cached on disk by subreddit."""
    fp = os.path.join(CACHE, sub.lower() + ".json")
    if os.path.exists(fp):
        try:
            return json.load(open(fp))
        except Exception:
            pass

    prior = SHIPPED.get(sub.lower())
    if prior and prior.get("status") == "ok" and prior.get("rule_posture") not in ("unknown", ""):
        rec = {
            "subreddit": prior["subreddit"],
            "status": "ok",
            "subscribers": int(prior["subscribers"] or 0),
            "rule_posture": prior["rule_posture"],
            "comment_page_n": int(prior["comment_page_n"] or 0),
            "comments_per_hour": float(prior["comments_per_hour"] or 0),
            "comment_span_hours": float(prior["comment_span_hours"] or 0),
            "brand_bearing_share": float(prior["brand_bearing_share"] or 0),
            "distinct_threads_in_page": int(prior["distinct_threads_in_page"] or 0),
            "measured_at": prior["measured_at"],
            "source": "shipped",
        }
        json.dump(rec, open(fp + ".tmp", "w"))
        os.replace(fp + ".tmp", fp)
        return rec

    rec = {"subreddit": sub, "source": "measured", "run_id": RUN_ID}
    a = api(f"/r/{sub}/about", {"raw_json": 1})
    if "_err" in a or a.get("kind") != "t5":
        rec.update(status="unavailable", error=a.get("_err", "not_t5"))
        json.dump(rec, open(fp + ".tmp", "w"))
        os.replace(fp + ".tmp", fp)
        return rec
    d = a["data"]
    rec.update(status="ok", subscribers=d.get("subscribers") or 0,
               subreddit_type=d.get("subreddit_type"), over18=d.get("over18", False),
               public_description=(d.get("public_description") or "")[:300])

    rl = api(f"/r/{sub}/about/rules", {"raw_json": 1})
    txt = ""
    if "_err" not in rl:
        for r in rl.get("rules", []):
            txt += " " + (r.get("short_name") or "") + " " + (r.get("description") or "")
    if not txt:
        # HANDOFF item 3: do not default an unread subreddit to scorable. Read the
        # sidebar before falling back, and only then call the posture unknown.
        side = (d.get("description") or "") + " " + (d.get("public_description") or "")
        txt = side if len(side) > 120 else ""
        rec["posture_source"] = "sidebar" if txt else "none"
    else:
        rec["posture_source"] = "rules"
    rec["rule_posture"] = posture(txt) if txt else "unknown"
    rec["rule_chars"] = len(txt)

    c = api(f"/r/{sub}/comments", {"limit": 100, "raw_json": 1})
    ch = c.get("data", {}).get("children", []) if "_err" not in c else []
    if ch:
        now = time.time()
        oldest = min(int(x["data"]["created_utc"]) for x in ch)
        span_h = max((now - oldest) / 3600.0, 0.01)
        bodies = [(x["data"].get("body") or "").lower() for x in ch]
        rec.update(
            comment_page_n=len(ch),
            comment_span_hours=round(span_h, 2),
            comments_per_hour=round(len(ch) / span_h, 2),
            distinct_threads_in_page=len({x["data"]["link_id"] for x in ch}),
            brand_bearing_share=round(
                sum(1 for b in bodies if any(br.lower() in b for br in brands)) / len(ch), 3),
        )
    else:
        rec.update(comment_page_n=0, comment_span_hours=0.0,
                   comments_per_hour=0.0, distinct_threads_in_page=0,
                   brand_bearing_share=0.0)
    rec["measured_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(rec, open(fp + ".tmp", "w"), indent=1)
    os.replace(fp + ".tmp", fp)
    return rec


# ------------------------------------------------------------------- discovery
def queries_for(cat_name, brands):
    """Category nouns plus seed brands. `X and Y` names carry two nouns."""
    qs = [cat_name]
    for part in re.split(r"\s+and\s+", cat_name):
        part = part.strip()
        if part and part.lower() != cat_name.lower():
            qs.append(part)
    qs.extend(brands[:4])
    seen, out = set(), []
    for q in qs:
        k = q.lower()
        if k not in seen:
            seen.add(k)
            out.append(q)
    return out


def discover_candidates(cat_name, brands, seeds, cap=34):
    """Seeds always survive. Search fills the rest, largest communities first."""
    fp = os.path.join(CACHE, "_cand_" + re.sub(r"[^a-z0-9]+", "-", cat_name.lower()) + ".json")
    if os.path.exists(fp):
        return json.load(open(fp))

    found = {}
    for q in queries_for(cat_name, brands):
        r = api("/subreddits/search", {"q": q, "limit": 25, "raw_json": 1,
                                       "show": "all", "sort": "relevance"})
        for k in r.get("data", {}).get("children", []) if "_err" not in r else []:
            d = k.get("data", {})
            name = d.get("display_name")
            if not name:
                continue
            if d.get("over18") or d.get("subreddit_type") != "public":
                continue
            if (d.get("subscribers") or 0) < 1500:
                continue
            found[name] = max(found.get(name, 0), d.get("subscribers") or 0)

    for s in seeds:
        found.setdefault(s, 10 ** 9)  # seeds sort first, never dropped

    ranked = [n for n, _ in sorted(found.items(), key=lambda kv: -kv[1])][:cap]
    json.dump(ranked, open(fp + ".tmp", "w"), indent=1)
    os.replace(fp + ".tmp", fp)
    return ranked


SCORING_CAP = 8  # 13-algorithm.md caps a category at 8 scoring subreddits


def main():
    cats_meta = {r["category"]: r for r in
                 csv.DictReader(open(os.path.join(HERE, "categories.csv")))}
    seeded = {c["category"]: c for c in
              json.load(open(os.path.join(HERE, "category-candidates-20.json")))}

    rows = []
    for ci, (cat_name, meta) in enumerate(cats_meta.items(), 1):
        seed = seeded.get(cat_name, {})
        brands = seed.get("brands", [])
        seeds = seed.get("subreddits", [])
        cands = discover_candidates(cat_name, brands, seeds)
        print(f"\n=== [{ci}/20] {cat_name} — {len(cands)} candidates "
              f"({len(seeds)} seeded) — {CALLS['n']} calls so far", flush=True)

        measured = []
        for sub in cands:
            m = measure(sub, brands)
            vend = is_vendor_sub(sub)
            ok = m.get("status") == "ok"
            scorable = ok and m.get("rule_posture") != "hostile" and not vend
            bbph = round((m.get("comments_per_hour") or 0) * (m.get("brand_bearing_share") or 0), 4)
            measured.append({
                "category": cat_name,
                "category_slug": meta["slug"],
                "subreddit": m.get("subreddit", sub),
                "status": m.get("status", "unavailable"),
                "subscribers": m.get("subscribers", 0),
                "rule_posture": m.get("rule_posture", "unknown"),
                "posture_source": m.get("posture_source", "shipped"),
                "is_vendor_sub": vend,
                "scorable": scorable,
                "is_scoring": False,
                "comments_per_hour": m.get("comments_per_hour", 0.0),
                "brand_bearing_share": m.get("brand_bearing_share", 0.0),
                "bb_per_hour": bbph,
                "distinct_threads_in_page": m.get("distinct_threads_in_page", 0),
                "measured_at": m.get("measured_at", ""),
                "source": m.get("source", "measured"),
                "run_id": RUN_ID,
            })
            print(f"  r/{sub:26} {m.get('status','?'):11} "
                  f"posture={m.get('rule_posture','?'):10} vendor={str(vend):5} "
                  f"scorable={str(scorable):5} bb/h={bbph}", flush=True)

        # is_scoring: top 8 scorable by MEASURED YIELD PER CALL, never subscribers
        for r in sorted([m for m in measured if m["scorable"]],
                        key=lambda x: -x["bb_per_hour"])[:SCORING_CAP]:
            r["is_scoring"] = True
        rows.extend(measured)

    out = os.path.join(HERE, "category-subreddits.csv")
    cols = ["category", "category_slug", "subreddit", "status", "subscribers",
            "rule_posture", "posture_source", "is_vendor_sub", "scorable", "is_scoring",
            "comments_per_hour", "brand_bearing_share", "bb_per_hour",
            "distinct_threads_in_page", "measured_at", "source", "run_id"]
    with open(out + ".tmp", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    os.replace(out + ".tmp", out)

    uniq = {r["subreddit"].lower() for r in rows}
    per_cat = {}
    for r in rows:
        per_cat.setdefault(r["category"], []).append(r)
    floor = sum(1 for v in per_cat.values() if sum(1 for r in v if r["scorable"]) >= 5)
    print(f"\nWROTE {out}")
    print(f"  slots           {len(rows)}")
    print(f"  unique subs     {len(uniq)}")
    print(f"  scorable slots  {sum(1 for r in rows if r['scorable'])}")
    print(f"  vendor slots    {sum(1 for r in rows if r['is_vendor_sub'])}")
    print(f"  scoring slots   {sum(1 for r in rows if r['is_scoring'])}")
    print(f"  categories clearing the 5-scorable floor: {floor}/20")
    print(f"  API calls this run: {CALLS['n']}")
    print("DONE")


if __name__ == "__main__":
    sys.exit(main())
