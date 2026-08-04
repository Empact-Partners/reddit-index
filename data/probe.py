#!/usr/bin/env python3
"""Reddit Index — 20-category empirical probe.

Measures, per candidate subreddit: subscribers, live comment rate, rule posture,
and brand-probe yield. Writes per-sub JSON to disk (resumable) then a flat CSV.

Disk is the source of truth: re-running skips anything already measured.
"""
import base64, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

OUT = "/private/tmp/claude-501/-Users-vladshvets--claude/f6928dd3-ec32-4042-ab81-563839239aff/scratchpad/probe20"
os.makedirs(OUT, exist_ok=True)

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

# rule posture classification
HOSTILE = re.compile(r"no (self.?)?promo|zero tolerance|no advertis|will be removed if.*promotional|no vendor|product mentions will be removed|no soliciting", re.I)
CAPPED  = re.compile(r"weekly (promo|thread)|self.?promotion (is )?(allowed|permitted).{0,40}(saturday|thread|once)|max \d+ mention|karma requirement|\d+ karma", re.I)

def posture(rules_txt):
    if HOSTILE.search(rules_txt): return "hostile"
    if CAPPED.search(rules_txt):  return "capped"
    return "permissive"

CATEGORIES = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cat20.json")))

def probe_sub(sub, brands):
    fp = os.path.join(OUT, f"{sub.lower()}.json")
    if os.path.exists(fp):
        try: return json.load(open(fp))
        except Exception: pass
    rec = {"subreddit": sub}
    a = api(f"/r/{sub}/about", {"raw_json": 1})
    if "_err" in a or a.get("kind") != "t5":
        rec["status"] = "unavailable"; rec["error"] = a.get("_err", "not_t5")
        json.dump(rec, open(fp + ".tmp", "w")); os.replace(fp + ".tmp", fp); return rec
    d = a["data"]
    rec.update(status="ok", subscribers=d.get("subscribers", 0),
               title=(d.get("title") or "")[:120],
               public_description=(d.get("public_description") or "")[:400],
               over18=d.get("over18", False),
               subreddit_type=d.get("subreddit_type"),
               active_user_count=d.get("active_user_count"))
    # rules
    rl = api(f"/r/{sub}/about/rules", {"raw_json": 1})
    txt = ""
    if "_err" not in rl:
        for r in rl.get("rules", []):
            txt += " " + (r.get("short_name") or "") + " " + (r.get("description") or "")
    rec["rule_posture"] = posture(txt) if txt else "unknown"
    rec["rule_chars"] = len(txt)
    # live comment stream: rate + span
    c = api(f"/r/{sub}/comments", {"limit": 100, "raw_json": 1})
    ch = c.get("data", {}).get("children", []) if "_err" not in c else []
    if ch:
        now = time.time()
        oldest = min(int(x["data"]["created_utc"]) for x in ch)
        span_h = max((now - oldest) / 3600.0, 0.01)
        rec["comment_page_n"] = len(ch)
        rec["comment_span_hours"] = round(span_h, 2)
        rec["comments_per_hour"] = round(len(ch) / span_h, 2)
        rec["distinct_threads_in_page"] = len({x["data"]["link_id"] for x in ch})
        bodies = " ".join((x["data"].get("body") or "").lower() for x in ch)
        hits = {b: bodies.count(b.lower()) for b in brands}
        rec["brand_hits_in_live_page"] = {k: v for k, v in hits.items() if v}
        rec["brand_bearing_share"] = round(
            sum(1 for x in ch if any(b.lower() in (x["data"].get("body") or "").lower() for b in brands)) / len(ch), 3)
    else:
        rec["comment_page_n"] = 0; rec["comments_per_hour"] = 0.0
        rec["comment_span_hours"] = 0.0; rec["brand_bearing_share"] = 0.0
        rec["brand_hits_in_live_page"] = {}
    # brand probe via scoped search (posts only — measures discoverability, not census)
    probe = {}
    for b in brands[:2]:
        s = api(f"/r/{sub}/search", {"q": b, "restrict_sr": 1, "t": "all",
                                     "sort": "relevance", "limit": 100, "raw_json": 1})
        kids = s.get("data", {}).get("children", []) if "_err" not in s else []
        exact = sum(1 for k in kids
                    if b.lower() in ((k["data"].get("title") or "") + " " + (k["data"].get("selftext") or "")).lower())
        probe[b] = {"returned": len(kids), "exact": exact,
                    "cursor": bool(s.get("data", {}).get("after"))}
    rec["search_probe"] = probe
    rec["measured_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(rec, open(fp + ".tmp", "w"), indent=1); os.replace(fp + ".tmp", fp)
    return rec

def main():
    total = sum(len(c["subreddits"]) for c in CATEGORIES)
    i = 0
    for cat in CATEGORIES:
        for sub in cat["subreddits"]:
            i += 1
            r = probe_sub(sub, cat["brands"])
            print(f"[{i}/{total}] {cat['category'][:26]:26} r/{sub:22} "
                  f"{r.get('status'):11} subs={r.get('subscribers',0):>9} "
                  f"c/h={r.get('comments_per_hour',0):>7} posture={r.get('rule_posture','?'):10} "
                  f"brandshare={r.get('brand_bearing_share',0)}", flush=True)
    print("DONE")

if __name__ == "__main__":
    main()
