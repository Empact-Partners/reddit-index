#!/usr/bin/env python3
"""Fix two measurement defects in the discovery output before anything scores on it.

The discovery pass reproduced the shipped study's instrument exactly, including
the coarseness `HANDOFF.md` item 2 already records: it counts a comment as
brand-bearing when a seed brand name appears as a SUBSTRING. Run over a widened
candidate set, that instrument produces obvious nonsense —

    Payment Processing  r/bjj            bb/h 1.628
    Payment Processing  r/hardwareswap   bb/h 1.962
    Payment Processing  r/StudentLoans   bb/h 0.554

— because "PayPal" and "square" are said constantly in a jiu-jitsu subreddit and
a used-hardware marketplace. Left alone, those three would be selected as SCORING
subreddits for Payment Processing, and a merchant payments ranking would be
computed partly from people arranging gi sales.

Two fixes, each one already prescribed somewhere in the repo:

  1. WORD-BOUNDARY MATCHING, RESTRICTED TO LOW-AMBIGUITY BRANDS.
     data/README.md's own correction rule, after the same instrument matched
     "Monday" the weekday in r/nfl and "SAP" the fluid in r/worldbuilding.
     Re-measured live, one call per unique subreddit.

  2. A TOPICALITY TERM.
     13-algorithm.md's bootstrap score already has one — `T = 1.0 exact
     practitioner/category fit · 0.5 adjacent · 0 wrong` — and marks it
     human-coded. Coding 680 pairs by hand is not on, so it is coded by a local
     Claude pass over each subreddit's own description, which is the same
     judgment from the same evidence. It runs on the Max subscription, on this
     machine; no metered API is touched.

`is_scoring` then becomes the top 8 per category by `T x bb_per_hour` among
subreddits that are scorable AND topically at least adjacent — measured yield
per call, weighted by whether the community is actually about the category.
Never subscriber count.
"""
import csv, json, os, re, sys, time
import base64, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.expanduser("~/.claude/api_helpers"))
from claude_cli import claude_p, HAIKU  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".discover-cache")
BODIES = os.path.join(CACHE, "bodies")
TOPIC = os.path.join(CACHE, "topicality")
os.makedirs(BODIES, exist_ok=True)
os.makedirs(TOPIC, exist_ok=True)

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


def api(path, params=None, tries=3):
    for i in range(tries):
        u = "https://oauth.reddit.com" + path + ("?" + urllib.parse.urlencode(params) if params else "")
        rq = urllib.request.Request(u, headers={"User-Agent": UA, "Authorization": "Bearer " + token()})
        try:
            with urllib.request.urlopen(rq, timeout=35) as f:
                time.sleep(0.75)
                return json.loads(f.read())
        except urllib.error.HTTPError as e:
            if e.code == 401:
                _tok["v"] = None; continue
            if e.code in (429, 500, 502, 503):
                time.sleep(3 * (i + 1)); continue
            return {"_err": e.code}
        except Exception:
            time.sleep(2); continue
    return {"_err": "fail"}


def fetch_bodies(sub):
    """One /r/{sub}/comments page, cached. The raw text the measurement needs."""
    fp = os.path.join(BODIES, sub.lower() + ".json")
    if os.path.exists(fp):
        return json.load(open(fp))
    c = api(f"/r/{sub}/comments", {"limit": 100, "raw_json": 1})
    ch = c.get("data", {}).get("children", []) if "_err" not in c else []
    rec = {
        "bodies": [(x["data"].get("body") or "") for x in ch],
        "oldest": min((int(x["data"]["created_utc"]) for x in ch), default=0),
        "n": len(ch),
        "fetched_at": time.time(),
    }
    json.dump(rec, open(fp + ".tmp", "w"))
    os.replace(fp + ".tmp", fp)
    return rec


# ── fix 1: word-boundary matching over LOW-ambiguity surface forms ───────────
def probe_terms():
    """Per category slug, the surface forms safe to count with a regex.

    Restricted to SAFE forms — the low-ambiguity class — because that is exactly
    the restriction data/README.md records as the fix for the false matches this
    instrument produced last time. A `medium` or `high` form needs corroborating
    context the pipeline supplies and a bare regex cannot.
    """
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


TERMS = probe_terms()
_re_cache = {}


def matcher(slug):
    if slug in _re_cache:
        return _re_cache[slug]
    terms = TERMS.get(slug, [])
    if not terms:
        _re_cache[slug] = None
        return None
    # Word boundaries that also refuse a match inside a longer token:
    # `stripe` in `pinstripe` is not a match.
    pat = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
    _re_cache[slug] = re.compile(rf"(?<![a-z0-9]){pat}(?![a-z0-9])", re.I)
    return _re_cache[slug]


def brand_bearing_share(slug, bodies):
    m = matcher(slug)
    if not m or not bodies:
        return 0.0
    return round(sum(1 for b in bodies if m.search(b)) / len(bodies), 4)


# ── fix 2: the topicality term T, coded from each subreddit's own description ─
SYSTEM = """You judge whether a Reddit community is a place where a named
software category is actually evaluated and discussed by its practitioners.

Answer for each item with one number:
  1.0  the community IS about this category, or about the work that uses it
       daily, so buying and switching decisions get discussed there
  0.5  adjacent: the category comes up as a tool of a broader trade
  0.0  wrong: brand names may appear, but never as a product evaluation
       (hobby, sport, local, meme, marketplace, news, or unrelated trade
       communities all score 0.0 even when the words appear constantly)

Be strict. A used-hardware marketplace where people say "PayPal" to arrange a
sale is 0.0 for Payment Processing. A jiu-jitsu community is 0.0 for everything.
Output ONLY a JSON object mapping the item id to the number. No prose."""


def topicality_batch(items):
    """items: [(id, category, subreddit, description)] -> {id: float}"""
    lines = []
    for i, (iid, cat, sub, desc) in enumerate(items, 1):
        d = (desc or "").replace("\n", " ")[:260]
        lines.append(f'{iid}\tcategory="{cat}"\tr/{sub}\t{d or "(no description)"}')
    prompt = "Rate each item.\n\n" + "\n".join(lines)
    raw = claude_p(prompt, system=SYSTEM, model=HAIKU, json_mode=True, timeout=180)
    try:
        obj = json.loads(raw)
    except Exception:
        obj = {}
        for m in re.finditer(r'"([^"]+)"\s*:\s*([01](?:\.\d+)?)', raw):
            obj[m.group(1)] = float(m.group(2))
    return {k: float(v) for k, v in obj.items()}


def main():
    src = os.path.join(HERE, "category-subreddits.csv")
    rows = list(csv.DictReader(open(src)))
    print(f"{len(rows)} slots, {len({r['subreddit'].lower() for r in rows})} unique subreddits")

    # ── re-measure ──────────────────────────────────────────────────────────
    subs = sorted({r["subreddit"] for r in rows}, key=str.lower)
    print(f"\nre-measuring brand-bearing share on {len(subs)} subreddits "
          f"(word boundary, low-ambiguity forms only)…")
    for i, s in enumerate(subs, 1):
        fetch_bodies(s)
        if i % 50 == 0:
            print(f"  {i}/{len(subs)}", flush=True)

    for r in rows:
        rec = fetch_bodies(r["subreddit"])
        share = brand_bearing_share(r["category_slug"], rec["bodies"])
        old = float(r["brand_bearing_share"] or 0)
        r["brand_bearing_share_substring"] = old
        r["brand_bearing_share"] = share
        r["bb_per_hour"] = round(float(r["comments_per_hour"] or 0) * share, 4)

    # ── topicality ──────────────────────────────────────────────────────────
    descs = {}
    for s in subs:
        fp = os.path.join(CACHE, s.lower() + ".json")
        if os.path.exists(fp):
            try:
                d = json.load(open(fp))
                descs[s.lower()] = (d.get("public_description") or "")[:300]
            except Exception:
                pass

    todo, cached = [], {}
    for r in rows:
        iid = f"{r['category_slug']}|{r['subreddit']}"
        fp = os.path.join(TOPIC, re.sub(r"[^a-z0-9|]+", "_", iid.lower()) + ".json")
        if os.path.exists(fp):
            cached[iid] = json.load(open(fp))["t"]
        else:
            todo.append((iid, r["category"], r["subreddit"], descs.get(r["subreddit"].lower(), "")))

    print(f"\ntopicality: {len(cached)} cached, {len(todo)} to code (Claude Max, local)…")
    BATCH = 25
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]

    def run(batch):
        try:
            return batch, topicality_batch(batch)
        except Exception as e:
            print(f"  batch failed: {e}", flush=True)
            return batch, {}

    with ThreadPoolExecutor(max_workers=6) as ex:
        for n, (batch, got) in enumerate(ex.map(run, batches), 1):
            for iid, *_ in batch:
                t = got.get(iid)
                if t is None:
                    continue
                cached[iid] = t
                fp = os.path.join(TOPIC, re.sub(r"[^a-z0-9|]+", "_", iid.lower()) + ".json")
                json.dump({"t": t}, open(fp, "w"))
            print(f"  batch {n}/{len(batches)} — {len(got)}/{len(batch)} coded", flush=True)

    for r in rows:
        iid = f"{r['category_slug']}|{r['subreddit']}"
        # Uncoded defaults to 0.0: an unjudged community does not get to score,
        # for the same reason an unread rulebook does not (HANDOFF item 3).
        r["topicality"] = cached.get(iid, 0.0)
        r["worth"] = round(float(r["topicality"]) * float(r["bb_per_hour"]), 5)

    # ── is_scoring: top 8 by T x yield, among scorable and at least adjacent ──
    for r in rows:
        r["is_scoring"] = False
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    for cat, rs in by_cat.items():
        pool = [r for r in rs if r["scorable"] == "True" and float(r["topicality"]) >= 0.5]
        for r in sorted(pool, key=lambda x: -float(x["worth"]))[:8]:
            r["is_scoring"] = True

    cols = list(rows[0].keys())
    for c in ("topicality", "worth", "brand_bearing_share_substring"):
        if c not in cols:
            cols.append(c)
    with open(src + ".tmp", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    os.replace(src + ".tmp", src)

    print(f"\nWROTE {src}")
    scoring = [r for r in rows if r["is_scoring"]]
    print(f"  scoring slots {len(scoring)}")
    print(f"  categories with >=5 scoring subs: "
          f"{sum(1 for rs in by_cat.values() if sum(1 for r in rs if r['is_scoring']) >= 5)}/20")
    for cat, rs in by_cat.items():
        picked = sorted([r for r in rs if r["is_scoring"]], key=lambda x: -float(x["worth"]))
        print(f"\n  {cat}")
        for r in picked:
            print(f"    r/{r['subreddit']:<26} T={r['topicality']:<4} "
                  f"bb/h={r['bb_per_hour']:<8} worth={r['worth']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
