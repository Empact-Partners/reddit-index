#!/bin/zsh
# The Mac half of the daily loop (launchd: com.reddit-index.daily, ~07:30 UTC,
# after the Railway fetch). Classify new mentions on the Codex fleet, score
# from Supabase, publish via the Vercel deploy hook. Every stage idempotent.
set -e
cd "$(dirname "$0")"

echo "=== $(date '+%F %T') classify"
/usr/bin/caffeinate -i python3 -u classify_daily.py

echo "=== score + load + prune"
python3 -u score_db.py

echo "=== publish"
HOOK=$(python3 -c "
import json, os
print(json.load(open(os.path.expanduser('~/.claude/.reddit-index.json'))).get('deploy_hook',''))")
if [ -n "$HOOK" ]; then
  curl -fsS -X POST "$HOOK" > /dev/null && echo "deploy hook triggered"
else
  # Fallback: an empty commit is a rebuild too. Paste a Vercel Deploy Hook URL
  # into ~/.claude/.reddit-index.json under "deploy_hook" for the cleaner path.
  cd ..
  git pull --ff-only --quiet
  git commit --allow-empty --quiet -m "daily publish $(date '+%F')" && git push --quiet
  echo "published via empty-commit push"
fi
echo "DONE $(date '+%F %T')"
