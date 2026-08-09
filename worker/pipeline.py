#!/usr/bin/env python3
"""Drive resolve -> classify for every harvested corpus, then score and load.

Each stage checks disk before doing work, so this is safe to re-run, safe to
interrupt, and safe to start while the harvester is still going: a category
appears, gets processed, and the loop moves on.

    python3 worker/pipeline.py --max-mentions 200 --watch
"""
import argparse, json, os, subprocess, sys, time, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CORPUS = os.path.join(HERE, ".cache", "corpus")
RESOLVED = os.path.join(HERE, ".cache", "resolved")
SCORED = os.path.join(HERE, ".cache", "scored")
os.makedirs(RESOLVED, exist_ok=True)
os.makedirs(SCORED, exist_ok=True)

_resolver = None


def resolve_one(slug):
    """Entity resolution. Pure CPU, no API, so it never blocks on anything."""
    global _resolver
    out = os.path.join(RESOLVED, slug + ".json")
    if os.path.exists(out):
        return json.load(open(out))
    if _resolver is None:
        from resolve import Resolver
        _resolver = Resolver()
    d = json.load(open(os.path.join(CORPUS, slug + ".json")))
    mentions, by_rule = [], collections.Counter()
    for doc in d["documents"]:
        for h in _resolver.resolve(doc.get("body") or "", doc.get("subreddit"),
                                   doc.get("link_title")):
            by_rule[h["rule_fired"]] += 1
            mentions.append({
                **{k: doc.get(k) for k in ("doc_type", "thread_id", "subreddit", "author",
                                           "created_utc", "permalink", "score", "body",
                                           "link_title")},
                "doc_id": doc["id"], "brand_slug": h["brand_slug"],
                "matched_form": h["alias"], "char_offset": h["pos"],
                "match_conf": h["conf"], "rule_fired": h["rule_fired"],
            })
    payload = {"category_slug": slug, "mentions": mentions, "rule_counts": dict(by_rule)}
    json.dump(payload, open(out + ".tmp", "w"))
    os.replace(out + ".tmp", out)
    print(f"  resolve  {slug:<24} {len(d['documents']):>6} docs -> {len(mentions):>5} mentions "
          f"over {len({m['brand_slug'] for m in mentions})} brands", flush=True)
    return payload


def classify_one(slug, cap, batch, workers, window_days=0, window_only=False):
    out = os.path.join(SCORED, slug + ".json")
    if os.path.exists(out):
        return
    cmd = [sys.executable, "-u", os.path.join(HERE, "classify.py"),
           "--category", slug, "--batch", str(batch), "--workers", str(workers)]
    if window_days:
        cmd += ["--window-days", str(window_days)]
    if window_only:
        cmd += ["--window-only"]
    if cap:
        cmd += ["--max-mentions", str(cap)]
    print(f"  classify {slug} …", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    tail = [l for l in (r.stdout or "").strip().split("\n") if l.strip()][-1:]
    print(f"  classify {slug:<24} {tail[0].strip() if tail else 'no output'}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-mentions", type=int, default=200)
    ap.add_argument("--batch", type=int, default=100)
    # SERIAL. Concurrent headless `claude -p` sessions wedge — alive, producing
    # nothing, 300s timeout + retries. Batch size is the lever, never workers.
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--window-days", type=int, default=365)
    ap.add_argument("--window-only", action="store_true")
    ap.add_argument("--watch", action="store_true",
                    help="keep looping while the harvester is still producing corpora")
    ap.add_argument("--expect", type=int, default=20)
    args = ap.parse_args()

    seen = set()
    while True:
        slugs = sorted(f[:-5] for f in os.listdir(CORPUS)
                       if f.endswith(".json") and not f.startswith("_"))
        for slug in slugs:
            if slug in seen:
                continue
            try:
                resolve_one(slug)
                classify_one(slug, args.max_mentions, args.batch, args.workers,
                             args.window_days, args.window_only)
                seen.add(slug)
            except Exception as e:
                print(f"  !! {slug}: {type(e).__name__}: {e}", flush=True)
                seen.add(slug)
        if not args.watch or len(seen) >= args.expect:
            break
        time.sleep(60)

    print(f"\n{len(seen)} categories through resolve + classify", flush=True)
    subprocess.run([sys.executable, os.path.join(HERE, "run_scoring.py")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
