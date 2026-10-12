"""One page of the newest comments per sampled subreddit: how many name a brand, how fast the subreddit talks,
and how many of those mentions the present collector (listing + comment trees) already holds.

Read-only on Reddit (app-only OAuth, the shared app, at the client's own pace) and on the database (Management API).
Usage: stream_probe.py <n_core> <n_other> <out.csv> [seed]
"""
import csv, datetime as dt, json, os, random, sys, time

REPO = os.path.expanduser("~/Projects/reddit-index")
sys.path[:0] = [REPO + "/" + p for p in ("ops", "scripts", "worker")]
import watch_link as w          # noqa: E402
import reddit_client as rc      # noqa: E402
import daily as d               # noqa: E402
import collect                  # noqa: E402
from resolve import Resolver    # noqa: E402
import harvest                  # noqa: E402
import collections              # noqa: E402

n_core, n_other, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 20261012
MAX_CALLS, MAX_SECONDS = n_core + n_other + 6, 40 * 60
t0 = time.time()

mapping = d.load_scoring_map()
core = set(d.load_scoring_map(core_only=True))
vendor = {r["name"].lower() for r in w.query("select name from subreddits where is_vendor_sub")}
visits = {}
for r in w.query("select scope, max(finished_at)::text f from ingest_state where ym='daily' and stage='new_listing' "
                 "and scope not like '\\_%' group by 1"):
    k = r["scope"].lower()
    if r["f"] and (k not in visits or r["f"] > visits[k]):
        visits[k] = r["f"]
mapping, core, _ = collect.merge_case(mapping, core, {})
names, _ = collect.without_vendor(list(mapping), vendor)
rnd = random.Random(seed)
cs = sorted(n for n in names if n in core)
os_ = sorted(n for n in names if n not in core)
sample = rnd.sample(cs, min(n_core, len(cs))) + rnd.sample(os_, min(n_other, len(os_)))
print(f"{len(names)} subreddits in the plan ({len(cs)} core); sampling {len(sample)}", flush=True)

resolver = Resolver()
rows, hits_all = [], []      # hits_all: (sub, doc_id, link_id, created_utc)
brand_rows = collections.Counter()
bots = [0]
calls0 = rc.stats()["calls"]
for i, sub in enumerate(sample, 1):
    if rc.stats()["calls"] - calls0 >= MAX_CALLS or time.time() - t0 > MAX_SECONDS:
        print("stopping: the probe's own cap", flush=True)
        break
    r = rc.subreddit_comments(sub, limit=100)
    row = {"subreddit": sub, "core": int(sub in core), "last_visit": visits.get(sub.lower(), "")}
    if not isinstance(r, dict) or "_err" in r:
        row["error"] = (r or {}).get("_err", "bad answer") if isinstance(r, dict) else "bad answer"
        rows.append(row)
        continue
    kids = [k["data"] for k in r.get("data", {}).get("children", []) if k.get("kind") == "t1"]
    row["comments"] = len(kids)
    if kids:
        ts = [k.get("created_utc") or 0 for k in kids]
        row["span_hours"] = round((max(ts) - min(ts)) / 3600, 2)
        row["newest_age_hours"] = round((time.time() - max(ts)) / 3600, 2)
        row["threads_on_page"] = len({k.get("link_id") for k in kids})
    bearing = pairs = 0
    for k in kids:
        body = k.get("body") or ""
        if body in ("[deleted]", "[removed]") or not body:
            continue
        if harvest.is_bot_doc(k.get("author"), body):      # the collector's own rule (tree_docs)
            bots[0] += 1
            continue
        hs = resolver.resolve(body, sub, k.get("link_title") or "")
        if hs:
            slugs = {h["brand_slug"] for h in hs}
            brand_rows.update(slugs)
            if slugs - {"reddit"}:
                row["bearing_not_reddit"] = row.get("bearing_not_reddit", 0) + 1
            row["rows_not_reddit"] = row.get("rows_not_reddit", 0) + len(slugs - {"reddit"})
            bearing += 1
            pairs += len(slugs)
            hits_all.append((sub, "t1_" + k["id"], k.get("link_id"), k.get("created_utc") or 0))
    row["brand_bearing"], row["mention_rows"] = bearing, pairs
    rows.append(row)
    if i % 20 == 0:
        print(f"  {i}/{len(sample)} subreddits, {rc.stats()['calls'] - calls0} calls, {len(hits_all)} brand-bearing "
              f"comments, {(time.time() - t0) / 60:.1f} min", flush=True)

# which of the brand-bearing comments the database already holds, and which sit in a thread it knows
have, known = set(), set()
ids = [h[1] for h in hits_all]
links = sorted({h[2] for h in hits_all if h[2]})
for i in range(0, len(ids), 400):
    part = ",".join("'" + x.replace("'", "") + "'" for x in ids[i:i + 400])
    have |= {r["doc_id"] for r in w.query(f"select distinct doc_id from mentions where doc_id in ({part})")}
for i in range(0, len(links), 400):
    part = ",".join("'" + x.replace("'", "") + "'" for x in links[i:i + 400])
    known |= {r["id"] for r in w.query(f"select id from threads where id in ({part})")}
by = {}
for sub, doc, link, ts in hits_all:
    b = by.setdefault(sub, {"held": 0, "in_known_thread": 0, "before_visit": 0, "before_visit_held": 0})
    b["held"] += doc in have
    b["in_known_thread"] += link in known
    lv = visits.get(sub.lower())
    if lv:
        lv_ts = dt.datetime.fromisoformat(lv.replace(" ", "T").replace("+00", "+00:00")).timestamp()
        if ts < lv_ts - 3600:          # written an hour or more before the last visit: the trees could have read it
            b["before_visit"] += 1
            b["before_visit_held"] += doc in have
for row in rows:
    row.update(by.get(row["subreddit"], {}))

cols = ["subreddit", "core", "last_visit", "comments", "span_hours", "newest_age_hours", "threads_on_page",
        "brand_bearing", "mention_rows", "bearing_not_reddit", "rows_not_reddit", "held", "in_known_thread", "before_visit", "before_visit_held", "error"]
with open(out, "w", newline="") as f:
    wr = csv.DictWriter(f, fieldnames=cols)
    wr.writeheader()
    for row in rows:
        wr.writerow({c: row.get(c, "") for c in cols})


def tot(rs, k):
    return sum(int(r.get(k) or 0) for r in rs)


ok = [r for r in rows if r.get("comments")]
summary = {"calls": rc.stats()["calls"] - calls0, "minutes": round((time.time() - t0) / 60, 1), "sampled": len(rows),
           "answered_with_comments": len(ok), "errors": [(r["subreddit"], r["error"]) for r in rows if r.get("error")][:20],
           "empty": len([r for r in rows if not r.get("comments") and not r.get("error")])}
for label, rs in (("all", ok), ("core", [r for r in ok if r["core"]]), ("other", [r for r in ok if not r["core"]])):
    c = tot(rs, "comments")
    summary[label] = {
        "subreddits": len(rs), "comments": c, "brand_bearing": tot(rs, "brand_bearing"),
        "mention_rows": tot(rs, "mention_rows"),
        "brand_bearing_share": round(tot(rs, "brand_bearing") / c, 4) if c else None,
        "mention_rows_per_call": round(tot(rs, "mention_rows") / len(rs), 2) if rs else None,
        "rows_not_reddit": tot(rs, "rows_not_reddit"),
        "rows_not_reddit_per_call": round(tot(rs, "rows_not_reddit") / len(rs), 2) if rs else None,
        "already_held": tot(rs, "held"), "in_a_thread_the_database_knows": tot(rs, "in_known_thread"),
        "written_before_the_last_visit": tot(rs, "before_visit"),
        "of_those_held": tot(rs, "before_visit_held"),
    }
summary["bot_comments_skipped"] = bots[0]
summary["top_brands"] = brand_rows.most_common(25)
print(json.dumps(summary, indent=1))
json.dump(summary, open(out.replace(".csv", ".json"), "w"), indent=1)
