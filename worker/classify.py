#!/usr/bin/env python3
"""Targeted aspect-based sentiment, run locally on the Claude Max subscription.

Document-level sentiment is the wrong task. The unit is (comment, target span),
so a comment naming three products produces three verdicts, and "we moved off
HubSpot to Pipedrive and haven't looked back" is negative for one and positive
for the other. 06-sentiment.md §1's formulation, unchanged.

WHAT IS DIFFERENT FROM 06-sentiment.md, and why:

  The specification's eight-stage cascade — a fine-tuned DeBERTa doing the bulk
  with an LLM tail on the hard 15-25% — exists to avoid roughly $200 per million
  mentions of API spend. Two things retire that argument here. This build uses
  no metered API at all: classification runs through `claude -p` on the Max
  plan, on this machine, at zero marginal cost. And the encoder the cascade
  needs is trained on a 1,000-1,500 item gold set that does not exist and is not
  scheduled, while 06 §3 itself says "build stage 6 and the gold set FIRST" —
  which is circular, because the gold set is adjudicated FROM labels.

  Running everything through the model breaks that circle: this pass produces
  the labels, a stratified sample of its output becomes the gold set, and the
  encoder can be trained on it later if volume ever justifies one.

  Recorded in methodology_params as `sentiment_engine`, and in HANDOFF.md.

The label set is four-way and the fourth is not a bin. Only pos and neg enter a
score. `neu` is a real judgment — the comment names the brand without an opinion
about it. `abstain` is the classifier declining. Collapsing either into the
other changes the denominator and therefore the rank.
"""
import argparse, datetime, hashlib, json, os, re, sys, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.expanduser("~/.claude/api_helpers"))
from claude_cli import claude_p, HAIKU  # noqa: E402

CACHE = os.path.join(HERE, ".cache", "sentiment")
os.makedirs(CACHE, exist_ok=True)

MODEL_VERSION = "claude-cli-absa-1"
STAGE_LLM = 3

SYSTEM = """You label how a Reddit comment feels about ONE NAMED PRODUCT at a time.

For each item you get: the subreddit, the thread title, and the comment with the
target product marked as <<TARGET:name>>. Judge ONLY the marked product.

label — exactly one of:
  pos      the author is positive about this product
  neg      the author is negative about this product
  neu      the product is named without an opinion about it (a factual mention,
           a question, a list, "we use X" with no verdict attached)
  abstain  you cannot tell. Use this rather than guessing.

Hard rules:
  · "We switched from A to B" is negative for A and positive for B.
  · A complaint about the whole category is NOT a complaint about this product.
    Set category_gripe true and label neu unless the product is singled out.
  · Sarcasm inverts. If you are unsure whether it is sarcasm, abstain.
  · Text the author QUOTED from someone else is not the author's opinion.
  · A recommendation with no stated feeling ("just use X") is pos ONLY if the
    author endorses it; set recommendation true either way.
  · Price complaints are negative about the product. So is "it's fine, I guess".

Also return:
  intensity   0.0 to 1.0, how strongly the feeling is expressed (0 for neu)
  confidence  0.0 to 1.0, how sure you are of the label
  comparative true if the comment compares this product against another
  recommendation true if the comment recommends or advises against it
  entity_ok   false if the marked span is NOT this software product at all —
              the weekday, the herb, the verb, a different company's product
  evidence    the shortest phrase from the comment that justifies the label,
              quoted verbatim, or "" for neu

Output ONLY a JSON object mapping each item id to an object with keys:
label, intensity, confidence, comparative, recommendation, category_gripe,
entity_ok, evidence. No prose, no markdown fence."""

LABEL_CODE = {"neu": 0, "pos": 1, "neg": 2, "abstain": 3}


def mark_target(body, form, offset, width=1200):
    """Mark the target span and window the body so a 6,000-character comment
    does not drown the thing being judged."""
    lo = max(0, offset - width // 2)
    hi = min(len(body), offset + width // 2)
    seg = body[lo:hi]
    rel = offset - lo
    # Re-find the form near the offset; normalisation may have shifted it.
    m = re.search(re.escape(form), seg[max(0, rel - 40):rel + 80], re.I)
    if m:
        s = max(0, rel - 40) + m.start()
        e = max(0, rel - 40) + m.end()
        seg = seg[:s] + f"<<TARGET:{seg[s:e]}>>" + seg[e:]
    else:
        seg = f"[target: {form}]\n" + seg
    prefix = "…" if lo > 0 else ""
    suffix = "…" if hi < len(body) else ""
    return prefix + seg + suffix


def load_known():
    """Every label ever produced, keyed by item_id.

    The batch cache is keyed by the SHA of the batch's item_id set, so any
    change to corpus selection re-cuts the batches and misses every cached
    result — re-classifying work that was already paid for. Merging the batch
    files into one item-level dict makes classification incremental at item
    granularity: only genuinely new (document x brand) pairs reach the model.
    """
    known = {}
    for fn in os.listdir(CACHE):
        if not fn.endswith(".json"):
            continue
        try:
            known.update(json.load(open(os.path.join(CACHE, fn))))
        except Exception:
            pass
    return known


def select_mentions(mentions, window_days, window_only, max_mentions):
    """Whole-thread selection, in-window threads first.

    The first run took threads in qualification-score order alone, and the
    budget was spent on strong-but-stale threads before recent ones were
    reached — backup-storage classified 0 in-window mentions while 299 sat on
    disk. Recency now outranks qualification score; qualification order is
    preserved within each group. A thread stays wholly in or wholly out.
    """
    per_thread, order = defaultdict(list), []
    for m in mentions:
        tid = m.get("thread_id")
        if tid not in per_thread:
            order.append(tid)
        per_thread[tid].append(m)

    if window_days:
        cutoff = datetime.date.today() - datetime.timedelta(days=window_days)

        def in_window(tid):
            for m in per_thread[tid]:
                ts = m.get("created_utc")
                if ts and datetime.datetime.utcfromtimestamp(float(ts)).date() >= cutoff:
                    return True
            return False

        fresh = [t for t in order if in_window(t)]
        stale = [] if window_only else [t for t in order if not in_window(t)]
        order = fresh + stale

    kept, taken = set(), 0
    for tid in order:
        group = per_thread[tid]
        if max_mentions and taken + len(group) > max_mentions and taken > 0:
            continue
        for m in group:
            kept.add(f"{m['doc_id']}:{m['brand_slug']}")
        taken += len(group)
        if max_mentions and taken >= max_mentions:
            break
    return kept


def batch_key(items):
    h = hashlib.sha256()
    for i in items:
        h.update(i["item_id"].encode())
    h.update(MODEL_VERSION.encode())
    h.update(SYSTEM.encode())
    return h.hexdigest()[:32]


def classify_batch(items, brand_names):
    key = batch_key(items)
    fp = os.path.join(CACHE, key + ".json")
    if os.path.exists(fp):
        try:
            return json.load(open(fp))
        except Exception:
            pass

    lines = []
    for it in items:
        lines.append(
            f"### {it['item_id']}\n"
            f"subreddit: r/{it['subreddit']}\n"
            f"thread: {(it.get('link_title') or '')[:160]}\n"
            f"product: {brand_names.get(it['brand_slug'], it['brand_slug'])}\n"
            f"comment:\n{it['marked']}\n")
    prompt = "Label each item.\n\n" + "\n".join(lines)

    last = None
    for attempt in range(3):
        try:
            raw = claude_p(prompt, system=SYSTEM, model=HAIKU, json_mode=True, timeout=300)
            obj = json.loads(raw)
            if isinstance(obj, dict) and obj:
                with open(fp + ".tmp", "w") as f:
                    json.dump(obj, f)
                os.replace(fp + ".tmp", fp)
                return obj
        except Exception as e:
            last = e
            time.sleep(3 * (attempt + 1))
    print(f"    batch {key[:8]} failed: {last}", flush=True)
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", action="append")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--batch", type=int, default=12)
    ap.add_argument("--workers", type=int, default=1,
                    help="SERIAL by default. Concurrent headless `claude -p` sessions do not "
                         "merely fail — they WEDGE: the processes stay alive, produce nothing, "
                         "and the 300s timeout plus retries turns a five-minute category into "
                         "an hour. Bigger batches amortise startup instead; that is the lever.")
    ap.add_argument("--max-mentions", type=int, default=0,
                    help="Cap the CLASSIFIED corpus. Selection is by thread, so a thread is "
                         "either wholly in or wholly out — never a per-brand sample, which "
                         "would make n and the score disagree.")
    ap.add_argument("--window-days", type=int, default=0,
                    help="Order selection in-window-first: threads with any mention newer "
                         "than N days ago are budgeted before older threads.")
    ap.add_argument("--window-only", action="store_true",
                    help="With --window-days: skip threads with zero in-window mentions "
                         "entirely. Scoring only reads the window, so out-of-window "
                         "classification is spend without a score.")
    args = ap.parse_args()

    import csv
    brand_names = {r["slug"]: r["brand"] for r in
                   csv.DictReader(open(os.path.join(REPO, "data", "brands.csv")))}

    resolved_dir = os.path.join(HERE, ".cache", "resolved")
    out_dir = os.path.join(HERE, ".cache", "scored")
    os.makedirs(out_dir, exist_ok=True)

    slugs = ([f[:-5] for f in sorted(os.listdir(resolved_dir)) if f.endswith(".json")]
             if args.all else (args.category or []))
    if not slugs:
        ap.error("pass --category SLUG or --all")

    known = load_known()
    print(f"{len(known)} labels already on disk (item-level cache)", flush=True)

    for slug in slugs:
        payload = json.load(open(os.path.join(resolved_dir, slug + ".json")))
        mentions = payload["mentions"]

        if args.max_mentions or args.window_days:
            before = len(mentions)
            kept_ids = select_mentions(mentions, args.window_days, args.window_only,
                                       args.max_mentions)
            mentions = [m for m in mentions if f"{m['doc_id']}:{m['brand_slug']}" in kept_ids]
            print(f"  selection: {before} -> {len(mentions)} mentions over "
                  f"{len({m.get('thread_id') for m in mentions})} whole threads", flush=True)

        items = []
        for m in mentions:
            items.append({
                "item_id": f"{m['doc_id']}:{m['brand_slug']}",
                "brand_slug": m["brand_slug"],
                "subreddit": m.get("subreddit") or "",
                "link_title": m.get("link_title") or "",
                "marked": mark_target(m.get("body") or "", m["matched_form"],
                                      m.get("char_offset", 0)),
            })

        results = {it["item_id"]: known[it["item_id"]] for it in items
                   if it["item_id"] in known}
        todo = [it for it in items if it["item_id"] not in results]
        batches = [todo[i:i + args.batch] for i in range(0, len(todo), args.batch)]
        print(f"{slug}: {len(items)} (document x brand) pairs · {len(results)} cached · "
              f"{len(todo)} to classify in {len(batches)} batches", flush=True)

        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for n, got in enumerate(
                    ex.map(lambda b: classify_batch(b, brand_names), batches), 1):
                results.update(got)
                known.update(got)
                if n % 10 == 0 or n == len(batches):
                    print(f"  {n}/{len(batches)} batches · {len(results)} labelled", flush=True)

        scored, counts = [], defaultdict(int)
        for m in mentions:
            iid = f"{m['doc_id']}:{m['brand_slug']}"
            r = results.get(iid) or {}
            label = str(r.get("label", "abstain")).lower()
            if label not in LABEL_CODE:
                label = "abstain"
            # entity_ok = false is the model saying the span is not this product
            # at all — the weekday, the herb, a different vendor. That is an
            # ENTITY decision, not a sentiment one, so the mention is dropped
            # rather than labelled: excluded, not guessed.
            if r.get("entity_ok") is False:
                counts["entity_rejected"] += 1
                continue
            counts[label] += 1
            scored.append({
                **m,
                "label": LABEL_CODE[label],
                "label_word": label,
                "intensity": float(r.get("intensity") or 0.0),
                "conf": float(r.get("confidence") or 0.0),
                "stage": STAGE_LLM,
                "model_version": MODEL_VERSION,
                "is_comparative": bool(r.get("comparative")),
                "is_recommendation": bool(r.get("recommendation")),
                "is_category_gripe": bool(r.get("category_gripe")),
                "evidence_span": (r.get("evidence") or "")[:300],
            })

        with open(os.path.join(out_dir, slug + ".json"), "w") as f:
            json.dump({"category_slug": slug, "model_version": MODEL_VERSION,
                       "mentions": scored, "counts": dict(counts)}, f)
        n_op = counts["pos"] + counts["neg"]
        print(f"  -> {len(scored)} scored · pos {counts['pos']} neg {counts['neg']} "
              f"neu {counts['neu']} abstain {counts['abstain']} · "
              f"N_op {n_op} · entity-rejected {counts['entity_rejected']}\n", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
