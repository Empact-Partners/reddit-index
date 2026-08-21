#!/usr/bin/env bash
# P4 stage 5-6: subreddit discovery + core selection for the 51 new categories.
#
# SERIALIZED BY CONSTRUCTION. Every stage below drives worker/reddit_client.py, and a second
# concurrent client stacks a second 0.75s floor on top of the ~100 req/min app budget. Nothing
# in this file may be backgrounded, and nothing else touching Reddit may run while it does.
#
# Scoped to the new slugs with repeated --category, so the shipped 100 categories' rows are
# never re-qualified (refine_local's keyword topicality would overwrite fleet judgments).
set -uo pipefail
cd "$(dirname "$0")/.."

SLUGS=$(python3 -c "
import json
p=json.load(open('data/.roster-import/map/clusters.json'))['proposed']
print(' '.join('--category '+x['slug'] for x in p))
")
N=$(python3 -c "
import json;print(len(json.load(open('data/.roster-import/map/clusters.json'))['proposed']))")
echo "== discovery for $N new categories =="

for STAGE in enumerate evidence rescue siblings candidates; do
  echo ""; echo "-- stage $STAGE --"
  python3 data/discover_v2.py --stage "$STAGE" $SLUGS
  rc=$?
  echo "   stage $STAGE exited $rc"
  [ $rc -ne 0 ] && echo "   (continuing — the chain is deliberately not set -e, like update.sh)"
done

# Snapshot BEFORE qualify. qualify rewrites the WHOLE csv, so a snapshot taken after it
# compares two post-qualify states and reports 0 drift even if qualify destroyed a column —
# which is exactly what it used to do to is_core. The freeze-check below is only meaningful
# because this copy happens first.
cp data/category-subreddits.csv /tmp/cs_before_qualify.csv
CORE_BEFORE=$(python3 -c "
import csv;print(sum(1 for r in csv.DictReader(open('/tmp/cs_before_qualify.csv')) if r.get('is_core')=='True'))")
echo "core slots before qualify: $CORE_BEFORE"

echo ""; echo "-- stage qualify (dry run first) --"
python3 data/discover_v2.py --stage qualify $SLUGS --dry-run
echo ""
read -r -p "apply qualification to category-subreddits.csv? [y/N] " ans
[ "$ans" = "y" ] || { echo "stopped before write"; exit 0; }
python3 data/discover_v2.py --stage qualify $SLUGS

echo ""; echo "-- post-qualify integrity: is_core must have survived --"
CORE_AFTER=$(python3 -c "
import csv;print(sum(1 for r in csv.DictReader(open('data/category-subreddits.csv')) if r.get('is_core')=='True'))")
echo "core slots after qualify: $CORE_AFTER (was $CORE_BEFORE)"
if [ "$CORE_AFTER" != "$CORE_BEFORE" ]; then
  echo "ABORT: qualify changed the core slot count — restoring and stopping"
  cp /tmp/cs_before_qualify.csv data/category-subreddits.csv
  exit 1
fi

echo ""; echo "-- core selection (ADDITIVE — existing is_core rows are frozen) --"
cp data/category-subreddits.csv /tmp/cs_before_core.csv
SL=$(python3 -c "
import json
p=json.load(open('data/.roster-import/map/clusters.json'))['proposed']
print(','.join(x['slug'] for x in p))")
python3 data/select_core_subs.py --add-categories "$SL" --budget 20000 --min 8 --max 22 --apply

echo ""; echo "-- freeze check: existing is_core rows must be untouched --"
python3 - <<'PY'
import csv
a={(r['category_slug'],r['subreddit']):r.get('is_core') for r in csv.DictReader(open('/tmp/cs_before_core.csv'))}
b={(r['category_slug'],r['subreddit']):r.get('is_core') for r in csv.DictReader(open('data/category-subreddits.csv'))}
import json
new={x['slug'] for x in json.load(open('data/.roster-import/map/clusters.json'))['proposed']}
drift=[k for k,v in a.items() if k[0] not in new and b.get(k)!=v]
print(f"existing is_core rows changed: {len(drift)}")
if drift: print("  DRIFT:",drift[:5]); raise SystemExit(1)
added=sum(1 for k,v in b.items() if k[0] in new and v=='True')
print(f"new core slots: {added}")
PY
