#!/usr/bin/env python3
"""Calibrate Jev against the labels the index already has, BEFORE it writes a single one.

Three sets, scored separately (G21: the hard rows are their own column):

  ordinary  5,000 labelled mentions drawn at random (the newest label of each pair, any of the three old
            engines). These are also the "this IS the product" examples: the old classifier wrote a label
            only when it judged the span to be the product.
  hard      up to 1,000 of the 2,837 pairs the old pipeline re-judged because its engines disagreed.
  entity    the 190 mentions read by hand on 2026-10-02 (docs/investigation-2026-10/quality_hand_check.csv):
            43 are not about the product they were filed under. The only "not this product" examples that
            exist, because the old classifier's rejections were never stored.

Jev is asked exactly what worker/classify_sweep.py asks, at the batch size it will run (twenty), pinned to
jev-1.13.0. The answers (ids and probabilities only, no Reddit text) go to worker/.cache/calibration/, so
thresholds can be re-chosen without paying again. The chosen thresholds go to ops/classify_thresholds.json.

The rule for choosing them (doctrine: a recall dial, not a taste dial):
  reject_below   the highest probability-of-product under which at most 1% of the ordinary labelled
                 mentions fall (they are on-product), so a rejection is almost never a real mention;
  product_at     the lowest gate that lets at most 5% of the hand-checked "not this product" mentions through;
  label_at[c]    for each of positive, negative, no opinion: the lowest confidence at which Jev's answer
                 agrees with the REFERENCE at least 96% of the time on the ordinary set (95% held out). Below it, GLM.

The reference is GLM-5.3's own answer on the same mentions (ops/classify_glm_pilot.py --model glm-5.3), not
the old labels. Read by hand on 2026-10-02: where GLM said "no opinion" against an old positive or negative,
GLM was right about 15 times, the old label about 6, and the rest could go either way; the old engines gave
opinions to mentions that held none. Jev settles what GLM-5.3 would have said; GLM-5.3 judges the rest. The
old labels are still reported beside it, for comparison.

  ops/classify_calibrate.py            # draw, ask Jev (about $0.15), choose, write thresholds
  ops/classify_glm_pilot.py --model glm-5.3 --ordinary 2000 --hard 200   # the reference (about 280 credits)
  ops/classify_calibrate.py --reuse    # re-choose from the stored answers, no spend
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
CACHE = os.path.join(ROOT, "worker", ".cache", "calibration")
OUT = os.path.join(ROOT, "ops", "classify_thresholds.json")
CODE = {0: "neu", 1: "pos", 2: "neg", 3: "abstain"}


def draw(conn) -> list[dict]:
    conn.execute("set statement_timeout = '15min'")
    rows = []
    q = """
      with latest as (
        select distinct on (s.doc_id, s.brand_id) s.doc_id, s.brand_id, s.label, s.model_version
          from public.mention_sentiment s
         order by s.doc_id, s.brand_id, s.scored_at desc nulls last, s.model_version desc)
      select l.brand_id, l.doc_id, m.created_utc, l.label, l.model_version
        from latest l join public.mentions m on m.brand_id = l.brand_id and m.doc_id = l.doc_id
       where {where}
       order by md5(l.doc_id || l.brand_id::text || 'cal-2026-10') limit {n}"""
    for name, where, n in (("ordinary", "l.model_version not like '%%-r2'", 5000),
                           ("hard", "l.model_version like '%%-r2'", 1000)):
        for r in conn.execute(q.format(where=where, n=n)).fetchall():
            rows.append({"set": name, "brand_id": r[0], "doc_id": r[1], "created_utc": r[2],
                         "old": CODE.get(r[3], "abstain"), "old_model": r[4]})
    hand = list(csv.DictReader(open(os.path.join(ROOT, "docs", "investigation-2026-10", "quality_hand_check.csv"))))
    slugs = {r["brand"] for r in hand}
    ids = dict(conn.execute("select slug, id from public.brands where slug = any(%s)", (list(slugs),)).fetchall())
    seen = set()
    for r in hand:
        if r["verdict"] == "unjudged" or r["repeat_of"]:
            continue
        key = (r["doc_id"], r["brand"])
        if key in seen or r["brand"] not in ids:
            continue
        seen.add(key)
        m = conn.execute("select created_utc from public.mentions where brand_id = %s and doc_id = %s",
                         (ids[r["brand"]], r["doc_id"])).fetchone()
        if m:
            rows.append({"set": "entity", "brand_id": ids[r["brand"]], "doc_id": r["doc_id"], "created_utc": m[0],
                         "old": None, "product": r["verdict"] == "the_product"})
    return rows


def attach_reference(rows: list[dict], path: str) -> int:
    """r["ref"] = GLM-5.3's label (pos / neg / neu / reject), where it answered."""
    ref = {(g["brand_id"], g["doc_id"]): g["glm"][0] for g in json.load(open(path)) if g.get("glm")}
    n = 0
    for r in rows:
        v = ref.get((r["brand_id"], r["doc_id"]))
        if v in ("pos", "neg", "neu", "reject"):
            r["ref"] = v
            n += 1
    return n


def choose(rows: list[dict], target: float = 0.96) -> dict:
    ordinary = [r for r in rows if r["set"] == "ordinary" and r.get("jev") and r.get("ref")]
    e_on = sorted(r["jev"]["e"] for r in ordinary)
    reject_below = e_on[max(0, int(len(e_on) * 0.01) - 1)] if e_on else 0.0
    reject_below = min(reject_below, 0.2)
    # product_at: the lowest gate at which at most 5% of the hand-checked "not this product" mentions get
    # through. Measured 2026-10-02: 0.5 lets 27 of 43 through, 0.8 lets 9, 0.9 lets 1.
    ent_neg = [r for r in rows if r["set"] == "entity" and r.get("jev") and not r["product"]]
    product_at = 0.95
    for pa in (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95):
        if ent_neg and sum(r["jev"]["e"] >= pa for r in ent_neg) / len(ent_neg) <= 0.05:
            product_at = pa
            break
    t = {"reject_below": round(reject_below, 3), "product_at": product_at, "label_at": {}}
    report = {"n": {s: sum(1 for r in rows if r["set"] == s and r.get("jev")) for s in ("ordinary", "hard", "entity")}}
    for c in ("pos", "neg", "neu"):
        best = None
        for p in [x / 100 for x in range(50, 100)]:
            dec = [r for r in ordinary if r["jev"]["e"] >= t["product_at"] and r["ref"] != "reject"
                   and max(r["jev"]["probs"], key=r["jev"]["probs"].get) == c and r["jev"]["probs"][c] >= p]
            if len(dec) < 30:
                continue
            agree = sum(r["ref"] == c for r in dec) / len(dec)
            if agree >= target:
                best = (p, agree, len(dec))
                break
        t["label_at"][c] = best[0] if best else 1.01          # 1.01: never decide this class
        report[f"label_{c}"] = {"at": t["label_at"][c], "agreement": round(best[1], 4) if best else None,
                                "decided": best[2] if best else 0}

    def decided(rs):
        out = {"n": len(rs), "decided": 0, "agree_reference": 0, "agree_old": 0, "rejected": 0,
               "rejected_reference_says_product": 0}
        for r in rs:
            j = r["jev"]
            if j["e"] <= t["reject_below"]:
                out["rejected"] += 1
                out["rejected_reference_says_product"] += r.get("ref") in ("pos", "neg", "neu")
                continue
            if j["e"] < t["product_at"]:
                continue
            lab = max(j["probs"], key=j["probs"].get)
            if lab != "unsure" and j["probs"][lab] >= t["label_at"].get(lab, 1.01):
                out["decided"] += 1
                out["agree_reference"] += (r.get("ref") == lab)
                out["agree_old"] += (r["old"] == lab)
        out["settled_share"] = round((out["decided"] + out["rejected"]) / max(1, len(rs)), 3)
        out["agreement_reference"] = round(out["agree_reference"] / max(1, out["decided"]), 4)
        out["agreement_old"] = round(out["agree_old"] / max(1, out["decided"]), 4)
        return out

    report["ordinary"] = decided(ordinary)
    report["hard"] = decided([r for r in rows if r["set"] == "hard" and r.get("jev") and r.get("ref")])
    ent = [r for r in rows if r["set"] == "entity" and r.get("jev")]
    neg = [r for r in ent if not r["product"]]
    pos = [r for r in ent if r["product"]]
    report["entity"] = {
        "not_product_n": len(neg), "product_n": len(pos),
        "not_product_rejected": sum(r["jev"]["e"] <= t["reject_below"] for r in neg),
        "not_product_sent_to_glm": sum(t["reject_below"] < r["jev"]["e"] < t["product_at"] for r in neg),
        "not_product_passed_as_product": sum(r["jev"]["e"] >= t["product_at"] for r in neg),
        "product_wrongly_rejected": sum(r["jev"]["e"] <= t["reject_below"] for r in pos),
        "auc": auc([r["jev"]["e"] for r in pos], [r["jev"]["e"] for r in neg]),
    }
    report["ordinary_wrongly_rejected"] = sum(r["jev"]["e"] <= t["reject_below"] for r in ordinary)
    report["reference"] = {"model": "glm-5.3", "target": target,
                           "glm_agrees_with_old": round(sum(r["ref"] == r["old"] for r in ordinary) / max(1, len(ordinary)), 4)}
    report["note"] = ("label_* agreement and 'ordinary' above are IN-SAMPLE (thresholds chosen on the same rows); "
                      "'held_out' is the number to quote")
    return {"model": "jev-1.13.0", "measured": None, "thresholds": t, "report": report}


def held_out(rows: list[dict], target: float = 0.96, splits: int = 20) -> dict:
    """Choose thresholds on half of the reference rows, score them on the other half, twenty random splits."""
    ordinary = [r for r in rows if r["set"] == "ordinary" and r.get("jev") and r.get("ref")]
    others = [r for r in rows if r["set"] != "ordinary"]
    settled, agree = [], []
    for seed in range(splits):
        pool = ordinary[:]
        random.Random(seed).shuffle(pool)
        a, b = pool[: len(pool) // 2], pool[len(pool) // 2:]
        t = choose(a + others, target)["thresholds"]
        dec = ok = 0
        for r in b:
            j = r["jev"]
            if j["e"] < t["product_at"] or r["ref"] == "reject":
                continue
            lab = max(j["probs"], key=j["probs"].get)
            if lab != "unsure" and j["probs"][lab] >= t["label_at"].get(lab, 1.01):
                dec += 1
                ok += r["ref"] == lab
        settled.append(dec / max(1, len(b)))
        agree.append(ok / max(1, dec))
    return {"splits": splits, "settled_mean": round(sum(settled) / splits, 4), "settled_min": round(min(settled), 4),
            "agreement_mean": round(sum(agree) / splits, 4), "agreement_min": round(min(agree), 4)}



def auc(pos: list[float], neg: list[float]) -> float | None:
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return round(wins / (len(pos) * len(neg)), 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse", action="store_true")
    a = ap.parse_args()
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, "jev_answers.json")
    import datetime as dt
    if a.reuse:
        rows = json.load(open(path))
    else:
        import db
        import classify_sweep as cs
        with db.connect() as conn:
            conn.autocommit = True
            rows = draw(conn)
            random.Random(2026).shuffle(rows)    # mix the sets inside batches, as production mixes them
            items = cs.fetch_items(conn, [(r["brand_id"], r["doc_id"], r["created_utc"]) for r in rows])
        by_key = {(it["brand_id"], it["doc_id"]): it for it in items}
        rows = [r for r in rows if (r["brand_id"], r["doc_id"]) in by_key]
        answers = cs.jev_judge([by_key[(r["brand_id"], r["doc_id"])] for r in rows])
        for r, j in zip(rows, answers):
            r["jev"] = j
            r["created_utc"] = str(r["created_utc"])
        print(f"Jev: {sum(r['jev'] is not None for r in rows)} of {len(rows)} answered, ${cs.jev_judge.last_usd:.4f}")
        json.dump(rows, open(path, "w"))
    n_ref = attach_reference(rows, os.path.join(CACHE, "glm_answers.glm-5.3.json"))
    print(f"reference: GLM-5.3 answered {n_ref} of the calibration mentions")
    result = choose(rows)
    result["report"]["held_out"] = held_out(rows)
    result["measured"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    result["answered"] = sum(r.get("jev") is not None for r in rows)
    with open(OUT, "w") as f:
        json.dump({"model": result["model"], "measured": result["measured"], **result["thresholds"],
                   "report": result["report"]}, f, indent=1)
    print(json.dumps(result["report"], indent=1))
    print("thresholds:", json.dumps(result["thresholds"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
