"""Reddit access: app-only OAuth, rate discipline, and disk-as-truth caching.

Rate discipline is 13-algorithm.md's, unchanged: a ~100 req/min budget run at
80, a 0.75s floor between calls, back off on 429/5xx, re-fetch the token once
on 401.

Every response is cached to disk before anything parses it, so an interrupted
run resumes without re-spending a single call and a parser bug never costs a
re-harvest. Write to `path.tmp`, then `os.replace` — the atomic form, so a kill
mid-write leaves the previous file rather than half a file.
"""
import base64, hashlib, json, os, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.environ.get("RI_CACHE") or os.path.join(HERE, ".cache")

_cfg = json.load(open(os.path.expanduser("~/.claude.json")))
_env = _cfg["projects"]["/Users/vladshvets/.claude"]["mcpServers"]["reddit"]["env"]
CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID") or _env["REDDIT_CLIENT_ID"]
CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET") or _env["REDDIT_CLIENT_SECRET"]
USER_AGENT = os.environ.get("REDDIT_USER_AGENT") or _env["REDDIT_USER_AGENT"]

SLEEP = 0.75          # the floor between calls
MAX_PER_MIN = 80      # run under the ~100 budget, never at it

_token = {"v": None, "t": 0.0}
_stats = {"calls": 0, "cached": 0, "errors": 0, "started": time.time()}


def stats():
    el = max(time.time() - _stats["started"], 1e-9)
    return dict(_stats, elapsed_s=round(el, 1),
                calls_per_min=round(_stats["calls"] / el * 60, 1))


def _access_token():
    if _token["v"] and time.time() - _token["t"] < 3000:
        return _token["v"]
    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    req = urllib.request.Request(
        "https://www.reddit.com/api/v1/access_token",
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={"User-Agent": USER_AGENT, "Authorization": "Basic " + basic})
    _token["v"] = json.loads(urllib.request.urlopen(req, timeout=25).read())["access_token"]
    _token["t"] = time.time()
    return _token["v"]


def _cache_path(path, params, bucket):
    key = hashlib.sha256((path + "?" + urllib.parse.urlencode(sorted((params or {}).items()))).encode()).hexdigest()
    d = os.path.join(CACHE, bucket, key[:2])
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, key + ".json")


_last_call = [0.0]


def get(path, params=None, bucket="misc", tries=3, use_cache=True):
    """One authenticated GET. Cached on disk by (path, params)."""
    fp = _cache_path(path, params, bucket)
    if use_cache and os.path.exists(fp):
        try:
            _stats["cached"] += 1
            return json.load(open(fp))
        except Exception:
            pass

    for attempt in range(tries):
        gap = time.time() - _last_call[0]
        if gap < SLEEP:
            time.sleep(SLEEP - gap)
        url = "https://oauth.reddit.com" + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT,
                          "Authorization": "Bearer " + _access_token()})
        try:
            with urllib.request.urlopen(req, timeout=40) as f:
                _last_call[0] = time.time()
                _stats["calls"] += 1
                data = json.loads(f.read())
            tmp = fp + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f)
            os.replace(tmp, fp)
            return data
        except urllib.error.HTTPError as e:
            _last_call[0] = time.time()
            if e.code == 401 and attempt == 0:
                _token["v"] = None
                continue
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(3 * (attempt + 1))
                continue
            _stats["errors"] += 1
            return {"_err": e.code}
        except Exception:
            _last_call[0] = time.time()
            time.sleep(2)
    _stats["errors"] += 1
    return {"_err": "fail"}


# ── the endpoints the lanes use ─────────────────────────────────────────────

def search_subreddit(sub, q, sort="relevance", t="all", limit=100, after=None):
    """Lane D discovery. `restrict_sr=1` keeps it inside the subreddit.

    Both sorts are run on every query because they return materially different
    sets — measured 12-53% overlap. Recall here comes from query DIVERSITY, not
    pagination depth: Reddit search truncates around 250 results regardless.
    """
    p = {"q": q, "restrict_sr": 1, "t": t, "sort": sort, "limit": limit, "raw_json": 1,
         "include_over_18": "on"}
    if after:
        p["after"] = after
    return get(f"/r/{sub}/search", p, bucket="search")


def comment_tree(post_id):
    """The comment tree for one thread.

    depth=6 and limit=200, per 13-algorithm.md §5. `more` branches are NOT
    expanded — recorded as a coverage gap rather than chased, because
    /api/morechildren multiplies the call count for the least dense tail.

    Returns a two-element array [post_listing, comment_listing]. `data.replies`
    is "" (an empty string) when absent, never {}.
    """
    return get(f"/comments/{post_id}",
               {"depth": 6, "limit": 200, "raw_json": 1, "sort": "top"},
               bucket="tree")


def subreddit_comments(subs, limit=100, before=None):
    """Lane B. A `+`-joined multireddit returns ONE merged feed.

    Verified to at least 40 subreddits in a single call. Merging does not reduce
    the number of comments to retrieve — the merged rate is the sum of the
    members' — it removes per-call overhead on quiet subreddits. So buckets are
    packed by RATE, never by category.
    """
    joined = "+".join(subs) if isinstance(subs, (list, tuple)) else subs
    p = {"limit": limit, "raw_json": 1}
    if before:
        p["before"] = before
    return get(f"/r/{joined}/comments", p, bucket="stream", use_cache=False)


def info(fullnames):
    """/api/info over up to 100 fullnames. The delete-sync probe."""
    return get("/api/info", {"id": ",".join(fullnames), "raw_json": 1},
               bucket="info", use_cache=False)
