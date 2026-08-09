#!/bin/zsh
# The 100-category backfill chain. Every stage disk-idempotent; re-running
# resumes. Reddit stages respect the 80/min discipline; LLM stages run on the
# Codex fleet. classify NEVER goes through pipeline.py here (its classify leg
# is claude -p) — resolve only, then the fleet.
set -e
cd "$(dirname "$0")/.."

echo "=== 1/8 gazetteer (brand-seed-new.csv -> brands.csv + aliases)"
python3 -u data/gen_brands.py

echo "=== 2/8 subreddit discovery (100 categories, resumable)"
python3 -u data/discover.py

echo "=== 3/8 topicality on the fleet"
python3 -u data/topicality_fleet.py

echo "=== 4/8 refine (word-boundary re-measure + is_scoring; zero claude calls)"
python3 -u data/refine.py

echo "=== 5/8 thin harvest, new categories (existing 20 skip via corpus cache)"
python3 -u worker/harvest.py --all --depth thin

echo "=== 6/8 resolve (rules only)"
python3 - <<'EOF'
import sys, os, csv
sys.path.insert(0, "worker")
from pipeline import resolve_one
slugs = [r["slug"] for r in csv.DictReader(open("data/categories.csv"))]
for s in slugs:
    if os.path.exists(os.path.join("worker/.cache/corpus", s + ".json")):
        resolve_one(s)
EOF

echo "=== 7/8 classify on the fleet"
python3 -u worker/classify_codex.py --all --batch 40

echo "=== 8/8 assemble + score + load + verify"
./worker/finalize.sh
echo "BACKFILL DONE — push to main to publish"
