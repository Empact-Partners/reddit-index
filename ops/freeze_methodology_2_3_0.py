#!/usr/bin/env python3
"""Record methodology version 2.3.0 in public.methodology_params (append-only; 2.2.0's rows stay as they are).

Every 2.2.0 parameter is carried forward unchanged except the ones below, each with the reason it changed. Four of
them describe rules the published numbers stopped following before October 2026 (decision 0011 removed the
12-month window and the median display floor; classification left the local fleet when the laptop died); version
2.3.0 is where the record catches up, alongside the two real changes of 2026-10-03.

  ops/freeze_methodology_2_3_0.py --commit <sha>      # the commit that ships 2.3.0
  ops/freeze_methodology_2_3_0.py --check             # print what 2.3.0 holds
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))

CHANGES = {
    "resolution_mode": ("rules_then_entity_check",
        "A mention the classifier judges not to be about the company (the word 'snow' is not ServiceNow) is "
        "recorded in public.mention_rejections and is not counted. Until 2.3.0 such mentions were counted as "
        "neutral, because the old classifier's verdict was never stored."),
    "parent_address_rule": ("address_must_name_the_whole_product",
        "A web address identifies a product only when every word of the product's name appears in it, or the "
        "address is the product's own short address (youtu.be). github.com is not GitHub Actions; "
        "sheets.google.com is Google Sheets. Applied to stored mentions on 2026-10-03: 171,263 set aside."),
    "sentiment_engine": ("jev_then_glm_5_3",
        "Jev (TypeSafe, jev-1.13.0) settles a mention when it is sure the word is the product and sure of the "
        "feeling; GLM-5.3 reads the rest with the 2.2 rubric word for word. Jev's thresholds were measured "
        "against GLM-5.3's own answers on 2,380 mentions: 95.9% agreement held out over twenty splits."),
    "sentiment_model_version": (["jev-1.13.0-absa-1", "glm-5.3-absa-1"],
        "Labels written from 2026-10-03. Labels written before 2026-08-25 keep their lanes' versions; the newest "
        "label per (mention, brand) is the one counted."),
    "scoring_window_months": ("all_collected",
        "Decision 0011: the page score uses every opinionated mention collected, not a trailing 12 months. "
        "2.2.0 still said 12."),
    "ranking_threshold": ({"rule": "one_opinionated_mention"},
        "Decision 0011: a company is ranked once it has one opinionated mention; the estimator handles thin "
        "evidence. 2.2.0 still described the category-median floor that decision removed."),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    import db
    with db.connect() as conn:
        conn.autocommit = True
        if a.check:
            for r in conn.execute("select key, value, git_commit from public.methodology_params "
                                  "where version = '2.3.0' order by key").fetchall():
                print(r)
            return 0
        if not a.commit:
            print("--commit is required")
            return 2
        if conn.execute("select count(*) from public.methodology_params where version = '2.3.0'").fetchone()[0]:
            print("2.3.0 is already recorded; versions are append-only")
            return 1
        with conn.transaction():
            n = conn.execute("""
                insert into public.methodology_params (version, scope, key, value, rationale, effective_from, git_commit, frozen_at)
                select '2.3.0', scope, key, value, rationale, now(), %s, now()
                  from public.methodology_params where version = '2.2.0' and not (key = any(%s))""",
                (a.commit, list(CHANGES))).rowcount
            for key, (value, why) in CHANGES.items():
                conn.execute("""
                    insert into public.methodology_params (version, scope, key, value, rationale, effective_from, git_commit, frozen_at)
                    values ('2.3.0', 'global', %s, %s::jsonb, %s, now(), %s, now())""",
                    (key, json.dumps(value), why, a.commit))
        print(f"2.3.0 recorded: {n} parameters carried forward, {len(CHANGES)} changed, commit {a.commit[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
