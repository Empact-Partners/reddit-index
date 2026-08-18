#!/bin/zsh
# THE manual update for the Reddit Index (decisions/0010, ruled 2026-08-18).
#
# There are NO scheduled jobs any more — no launchd lanes, no Railway cron
# (service taken Offline 2026-08-18; the retired plists are archived in
# worker/launchd/retired-2026-08-18/). The index updates when a human runs
# THIS script. See SOP.md at the repo root for the full operating procedure.
#
#   worker/update.sh              # the real thing: collect → classify → score
#                                 #   → delete-sync → publish → verify
#   worker/update.sh --rehearse   # bounded end-to-end rehearsal (~15 min):
#                                 #   10-min collect, 800-item classify
#
# Classification runs on the DeepSeek API (deepseek-v4-flash) — Vlad's ruling
# 2026-08-18, superseding the free-Haiku ruling of 2026-08-17. ~1,100 items/min
# and ~$0.18 per 1,000 items measured in production (153,748 items / 112 min /
# $27.22, zero truncations). --allow-metered is passed EXPLICITLY here because
# the flag is a decision, and decisions/0010 is where it was made.
#
# NOT `set -e`, deliberately. A stalled or failed stage must not abort the
# chain before scoring and publishing: each stage reports its exit code and the
# chain continues with whatever data it has (the original daily_mac.sh lesson).
#
# Every stage is idempotent and resumable — classify is an anti-join against
# mention_sentiment, scoring is a full recompute, delete-sync walks a cursor,
# publishing is a rebuild. An interrupted run costs nothing but a re-run of
# this script BY HAND. Nothing auto-resumes anything, ever (see
# ~/.claude/scripts/retired/resume-on-reset-RETIRED-2026-08-18/RETIRED.md).
cd "$(dirname "$0")"
stamp() { echo "\n=== $(date '+%F %T') $1" }

# caffeinate -i holds off idle sleep for the duration of THIS run only — the
# permanent keepawake lane is retired with the rest of the daemons.
if [ -z "$RI_CAFFEINATED" ]; then
  RI_CAFFEINATED=1 exec /usr/bin/caffeinate -i /bin/zsh "$0" "$@"
fi

COLLECT_ARGS=(--core-only)
# ARRAYS, quoted on use. zsh does not word-split an unquoted parameter the way
# bash does; the string form once passed "--haiku 16 --limit 800" as ONE
# argument, argparse exited 2, and classification silently no-opped while the
# rest of the chain scored and published as if nothing was wrong.
CLASSIFY_ARGS=(--deepseek 16 --haiku 0 --allow-metered)

if [ "$1" = "--rehearse" ]; then
  echo "REHEARSAL RUN — bounded stages, expect healthcheck grumbles about run size"
  COLLECT_ARGS+=(--max-minutes 10)
  CLASSIFY_ARGS+=(--limit 800)
elif [ -n "$RI_CLASSIFY_LIMIT" ]; then
  CLASSIFY_ARGS+=(--limit "$RI_CLASSIFY_LIMIT")
fi

stamp "collect (daily.py — was Railway's cron; runs Mac-side now)"
python3 -u daily.py "${COLLECT_ARGS[@]}"
echo "collect exited $?"

stamp "classify (DeepSeek API, 16 HTTP workers; drains the backlog, then exits)"
python3 -u classify_api.py "${CLASSIFY_ARGS[@]}"
CLASSIFIED=$?
echo "classify exited $CLASSIFIED"
# An exit code the chain cannot act on is still worth SAYING. 2 is argparse:
# the lane never ran, and no amount of scoring downstream will notice.
[ $CLASSIFIED -eq 2 ] && echo "!! classify never started (bad arguments) — nothing was labelled"
[ $CLASSIFIED -eq 1 ] && echo "!! classify refused or died early — check the gate/key message above"

stamp "score + load + prune"
python3 -u score_db.py
echo "score exited $?"

stamp "delete-sync (content removed on Reddit leaves the index — decisions/0002)"
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
  git commit --allow-empty --quiet -m "manual publish $(date '+%F')" && git push --quiet
  cd worker
fi

stamp "verify"
python3 -u healthcheck.py --json
HEALTH=$?
echo "\nDONE $(date '+%F %T') — health exit $HEALTH"
exit $HEALTH
