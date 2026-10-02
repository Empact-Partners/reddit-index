#!/usr/bin/env python3
"""Pilot GLM-5.3-Flash on the calibration rows Jev was scored on, and cost it, before the backlog runs.

Uses the rows ops/classify_calibrate.py drew (worker/.cache/calibration/jev_answers.json): all 190 hand-checked
mentions plus a fixed slice of the ordinary and hard sets. Asks GLM exactly what worker/classify_sweep.py asks,
at the batch size it runs, and reports per set:

  entity    of the "not this product" mentions, how many GLM rejected; of the genuine ones, how many it
            wrongly rejected
  ordinary  agreement with the label the index already holds
  hard      the same, on the pairs the old engines disagreed on
  cost      Z.ai credits per mention, by the glm-assistant formula, so the backlog can be priced

Answers (ids and labels only) go to worker/.cache/calibration/glm_answers.json.

  ops/classify_glm_pilot.py                 # 190 + 120 + 40 = 350 items, about 4 jobs
  ops/classify_glm_pilot.py --ordinary 300  # a bigger ordinary slice
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
CACHE = os.path.join(ROOT, "worker", ".cache", "calibration")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ordinary", type=int, default=120)
    ap.add_argument("--hard", type=int, default=40)
    ap.add_argument("--in-flight", type=int, default=6)
    ap.add_argument("--model", default="glm-5.3-flash", choices=["glm-5.3-flash", "glm-5.3"])
    a = ap.parse_args()
    import classify_sweep as cs
    import db
    if cs.glm_peak_now():
        print("Z.ai peak hours (06:00-10:00 UTC): not running")
        return 1
    rows = json.load(open(os.path.join(CACHE, "jev_answers.json")))
    pick = ([r for r in rows if r["set"] == "entity"]
            + [r for r in rows if r["set"] == "ordinary"][: a.ordinary]
            + [r for r in rows if r["set"] == "hard"][: a.hard])
    with db.connect() as conn:
        conn.autocommit = True
        items = cs.fetch_items(conn, [(r["brand_id"], r["doc_id"], r["created_utc"]) for r in pick])
    by_key = {(it["brand_id"], it["doc_id"]): it for it in items}
    pick = [r for r in pick if (r["brand_id"], r["doc_id"]) in by_key]
    t0 = time.time()
    verdicts, spend = cs.glm_judge([by_key[(r["brand_id"], r["doc_id"])] for r in pick], in_flight=a.in_flight, model=a.model)
    secs = round(time.time() - t0)
    for r, v in zip(pick, verdicts):
        r["glm"] = list(v) if v else None
    json.dump(pick, open(os.path.join(CACHE, f"glm_answers.{a.model}.json"), "w"))

    def tally(rs, hit):
        return {"n": len(rs), "hit": sum(1 for r in rs if r["glm"] and hit(r)),
                "unanswered": sum(1 for r in rs if not r["glm"])}

    ent = [r for r in pick if r["set"] == "entity"]
    out = {
        "model": a.model, "items": len(pick), "seconds": secs, "spend": spend,
        "credits_per_item": round(spend["credits"] / max(1, len(pick)), 3),
        "not_product_rejected": tally([r for r in ent if not r["product"]], lambda r: r["glm"][0] == "reject"),
        "product_wrongly_rejected": tally([r for r in ent if r["product"]], lambda r: r["glm"][0] == "reject"),
        "ordinary_agrees": tally([r for r in pick if r["set"] == "ordinary"], lambda r: r["glm"][0] == r["old"]),
        "hard_agrees": tally([r for r in pick if r["set"] == "hard"], lambda r: r["glm"][0] == r["old"]),
    }
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
