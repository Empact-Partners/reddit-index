#!/bin/zsh
# The Mac half of the daily loop (launchd: com.reddit-index.daily, 04:30 local).
#
# Railway fetches once a day (railway.json: 0 2 * * * UTC) because it is always
# on. Classification runs HERE because the free lane is `claude -p` Haiku on the
# Max plan, which exists only on this machine. Scoring, delete-sync and
# publishing follow: collect daily, classify daily, publish daily — the index is
# rebuilt every day (ruled 2026-08-17).
#
# Every stage is idempotent and resumable, so a missed night costs nothing but a
# bigger batch tomorrow: the classifier is an anti-join against
# mention_sentiment, scoring is a full recompute, delete-sync walks a
# least-recently-checked cursor, and publishing is a rebuild.
#
# NOT `set -e`. The old version was, and a stalled classifier therefore aborted
# the script BEFORE scoring and publishing: one slow lane and the site stopped
# updating with data it already had. Each stage reports its exit code and the
# chain continues.
cd "$(dirname "$0")"
stamp() { echo "\n=== $(date '+%F %T') $1" }

# Unbounded by default. RI_CLASSIFY_LIMIT exists so the whole chain can be
# rehearsed end to end in fifteen minutes instead of waiting out a six-hour
# backlog — the difference between a chain that is believed to work and one
# that has been watched working.
# An ARRAY, and quoted on use. zsh does not word-split an unquoted parameter
# the way bash does, so the string form passed "--haiku 16 --limit 800" as ONE
# argument: argparse exited 2, classification became a silent no-op, and the
# rest of the chain carried on scoring and publishing as if nothing was wrong.
# That is the exact failure shape this whole rebuild exists to make impossible.
CLASSIFY_ARGS=(--haiku 16)
[ -n "$RI_CLASSIFY_LIMIT" ] && CLASSIFY_ARGS+=(--limit "$RI_CLASSIFY_LIMIT")

stamp "classify (free Haiku on the Max plan; drains the backlog, then exits)"
# 16 local `claude -p` processes is the measured sweet spot: ~310 items/min,
# 1,908 batches with zero errors and zero rate-limiting on 2026-08-17.
# Concurrency here costs kernel scheduling, not RAM — see classify_api.py. The
# metered lane needs a flag this chain deliberately does not pass.
/usr/bin/caffeinate -i python3 -u classify_api.py "${CLASSIFY_ARGS[@]}"
CLASSIFIED=$?
echo "classify exited $CLASSIFIED"
# An exit code the chain cannot act on is still worth SAYING. 2 is argparse:
# the lane never ran, and no amount of scoring downstream will notice.
[ $CLASSIFIED -eq 2 ] && echo "!! classify never started (bad arguments) — nothing was labelled"

stamp "score + load + prune"
python3 -u score_db.py
echo "score exited $?"

stamp "delete-sync (content removed on Reddit leaves the index)"
# 60,000 mention rows ~= 12,000 distinct documents = ~120 /api/info calls, about
# two minutes. With the least-recently-checked ordering that walks the whole
# corpus in roughly a week; the default 5,000 would have taken two months.
python3 -u delete_sync.py --limit 60000 --publish-follows
echo "delete_sync exited $?"

stamp "publish (the site is static — a production rebuild IS the publish)"
python3 -u publish.py
PUBLISHED=$?
if [ $PUBLISHED -ne 0 ]; then
  # Fallback: Vercel builds every push, so an empty commit is a rebuild too.
  # Only reached when the API refuses, and then the noise in git history is
  # worth having, because the alternative is a site that quietly stops moving.
  echo "publish.py failed ($PUBLISHED) — falling back to an empty commit"
  cd ..
  git pull --ff-only --quiet
  git commit --allow-empty --quiet -m "daily publish $(date '+%F')" && git push --quiet
  cd worker
fi

stamp "health"
python3 -u healthcheck.py --slack
echo "\nDONE $(date '+%F %T')"
