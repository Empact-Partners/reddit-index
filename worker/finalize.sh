#!/bin/zsh
# Assemble -> score -> load -> assert -> revalidate. Run after a classification
# pass completes. Every stage is idempotent; re-running the whole file is safe.
set -e
cd "$(dirname "$0")"

echo "=== 1/5 assemble scored files (cache only, zero model calls expected)"
python3 -u classify.py --all --window-days 365 --window-only --workers 1 --batch 100

echo "=== 2/5 score"
python3 -u run_scoring.py

echo "=== 3/5 load to Supabase"
python3 -u load.py --seed --mentions --scores

echo "=== 4/5 verify: gate assertions + permalink sample"
python3 -u verify.py

# Publish = a Vercel rebuild (git push). The /api/revalidate route flushes
# cache TAGS, but these pages are force-static over untagged direct SQL, so a
# tag POST cannot refresh them — the build is the publish mechanism.
echo "DONE — push to main to publish"
