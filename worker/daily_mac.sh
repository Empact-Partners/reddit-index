#!/bin/zsh
# The Mac half of the daily loop (launchd: com.reddit-index.daily, 04:30 local).
#
# Railway fetches (railway.json: 0 2,14 * * * UTC) because it is always on.
# Classification runs HERE because the free lane is `claude -p` on the Max
# plan, which exists only on this machine. Scoring and publishing follow.
#
# Every stage is idempotent and resumable, so a missed night costs nothing but
# a bigger batch tomorrow — the classifier is an anti-join against
# mention_sentiment, and scoring is a full recompute.
#
# NOT `set -e`. The old version was, and a stalled classifier therefore aborted
# the script BEFORE scoring and publishing: one slow lane and the site stopped
# updating with data it already had. Each stage reports, and the chain
# continues.
cd "$(dirname "$0")"
LOG_PREFIX="=== $(date '+%F %T')"

echo "$LOG_PREFIX classify (free Haiku lane, drains the backlog then exits)"
# 16 local `claude -p` processes is the measured sweet spot: ~350 items/min.
# Concurrency here costs kernel scheduling, not RAM — see classify_api.py.
/usr/bin/caffeinate -i python3 -u classify_api.py --haiku 16 --deepseek 0
echo "$LOG_PREFIX classify exited $?"

echo "$LOG_PREFIX score + load + prune"
python3 -u score_db.py
echo "$LOG_PREFIX score exited $?"

echo "$LOG_PREFIX delete-sync (content removed on Reddit leaves the index)"
# 60,000 mention rows ~= 12,000 distinct documents = ~120 /api/info calls,
# about two minutes. With the least-recently-checked ordering that walks the
# whole corpus in roughly a week; the default 5,000 would have taken two months.
python3 -u delete_sync.py --limit 60000 --publish-follows
echo "$LOG_PREFIX delete_sync exited $?"

echo "$LOG_PREFIX publish"
HOOK=$(python3 -c "
import json, os
print(json.load(open(os.path.expanduser('~/.claude/.reddit-index.json'))).get('deploy_hook',''))")
if [ -n "$HOOK" ]; then
  curl -fsS -X POST "$HOOK" > /dev/null && echo "deploy hook triggered"
else
  # Fallback: an empty commit is a rebuild too, because Vercel builds every
  # push. Paste a Vercel Deploy Hook URL into ~/.claude/.reddit-index.json
  # under "deploy_hook" for the cleaner path.
  cd ..
  git pull --ff-only --quiet
  git commit --allow-empty --quiet -m "daily publish $(date '+%F')" && git push --quiet
  echo "published via empty-commit push"
  cd worker
fi

echo "$LOG_PREFIX health"
python3 -u healthcheck.py --slack
echo "DONE $(date '+%F %T')"
