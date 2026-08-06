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
import argparse, hashlib, json, os, re, sys, time
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
                    help="Cap the CLASSIFIED corpus. Selection is by thread, in qualification "
                         "order, so a thread is either wholly in or wholly out — never a "
                         "per-brand sample, which would make n and the score disagree.")
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

    for slug in slugs:
        payload = json.load(open(os.path.join(resolved_dir, slug + ".json")))
        mentions = payload["mentions"]
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

        if args.max_mentions and len(items) > args.max_mentions:
            # Whole threads, in the order the harvester ranked them, until the
            # budget is spent. A thread is wholly in or wholly out — never a
            # per-brand sample, which would leave `n` counting mentions nobody
            # ever labelled and make the published count disagree with the score.
            per_thread = defaultdict(list)
            for m in mentions:
                per_thread[m.get("thread_id")].append(m)
            kept_ids, taken = set(), 0
            for tid, group in per_thread.items():
                if taken + len(group) > args.max_mentions and taken > 0:
                    continue
                for m in group:
                    kept_ids.add(f"{m['doc_id']}:{m['brand_slug']}")
                taken += len(group)
                if taken >= args.max_mentions:
                    break
            before = len(items)
            items = [it for it in items if it["item_id"] in kept_ids]
            mentions = [m for m in mentions if f"{m['doc_id']}:{m['brand_slug']}" in kept_ids]
            print(f"  corpus cap: {before} -> {len(items)} mentions over "
                  f"{len({m.get('thread_id') for m in mentions})} whole threads", flush=True)

        batches = [items[i:i + args.batch] for i in range(0, len(items), args.batch)]
        print(f"{slug}: {len(items)} (document x brand) pairs in {len(batches)} batches", flush=True)

        results = {}
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for n, got in enumerate(
                    ex.map(lambda b: classify_batch(b, brand_names), batches), 1):
                results.update(got)
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
