# Go-live runbook (decision 0017)

Run on the morning after the second gate night (the run of 6 October), from `~/Projects/reddit-index` on the
laptop. Every step refuses or prints a problem when its precondition is not met; stop at the first one.

## 0. The gates

```
python3 ops/gate_meter.py tick --night 2026-10-05 --night 2026-10-06   # if the launchd tick has not run since 05:50 UTC
python3 ops/go_live.py preflight
```

`"ready": true` means: both nights' scheduled runs finished `ok` or `capped`; each measured under 1 GB (the laptop
window, or the watchdog's 07:01 reading when that came after the run); each receipt carries its core counts and
equals the rows in the database; no text pointer dangles; `scripts/schedule_check.py` has no finding. Anything
else: fix, and the next night is the new second gate night.

## 1. Vercel builds only site changes on main

```
python3 ops/go_live.py vercel
```

Replaces the Ignored Build Step (today: build only `feat/site-read-path`, never production) with: only `main`
builds, and only when something outside `worker/ ops/ supabase/ docs/ decisions/ deploy/ *.md` changed. Data never
builds the site.

## 2. Merge, in order

```
gh pr ready 7 && gh pr merge 7 --squash      # the read path: production builds from main (about 150 MB of reads)
# wait for the production deployment to be READY (Vercel dashboard or the API) before the next merge
gh pr ready 8 && gh pr merge 8 --squash      # the sweep: worker/ops/docs only, so the ignore step skips the build
git checkout main && git pull --ff-only
```

The production build prerenders the home page and the 151 category pages only; company pages render when first
requested and stay cached until the sweep names them.

## 3. Point the sweep at production

```
python3 ops/go_live.py point
```

Marks every page unserved on production (the fingerprints so far were proven on the preview), sets
`site_url` to `https://redditindex.com` in `ops/schedule.json`, and redeploys the sweep. From the next run the
publisher expires, renders and proves 1,000 production pages a night, takedown pages first. Commit the
`ops/schedule.json` change on `main`.

## 4. Verify production

```
python3 ops/go_live.py verify
```

Home, `/methodology/` and the five largest company pages answer 200 with the non-affiliation notice, each company
page's fingerprint equals its row, `/freshness.json` carries a date, an unknown slug answers 404.

## 5. Re-record the egress watchdog's baseline

The go-live build and the first production renders are planned heavy work; the next watchdog pass must not read
them as an anomaly. In the `empact-panel-receiver` Railway project, service `supabase-watchdog`:

```
railway variable set WATCHDOG_MODE=record --service supabase-watchdog     # redeploys, about 30 s
railway api 'mutation Run($input: DeploymentInstanceExecutionCreateInput!) { deploymentInstanceExecutionCreate(input: $input) }' \
  --variables '{"input": {"serviceInstanceId": "7130b1ef-ba5d-4479-9c88-e02d4a496c66"}}'
# wait for "record-only ... read and recorded" in its log, then:
railway variable set WATCHDOG_MODE=live --service supabase-watchdog
```

## 6. Record it

- `decisions/0017-daily-sweep.md`: status Accepted, the gate table filled with the two nights' numbers, the
  normal-day column of the budget table.
- `decisions/0016-frozen.md` and `decisions/0010-manual-on-demand.md`: superseded by 0017.
- `README.md`: STATUS says live and refreshing daily, with the date of the last run; the "still frozen" banner goes.
- Memory: `project_reddit_index_frozen` rewritten as the live state.
- Remove the gate meter: `launchctl bootout gui/$(id -u)/com.vladshvets.ri-gate-meter && rm ~/Library/LaunchAgents/com.vladshvets.ri-gate-meter.plist`.
- The site stays noindex.

## 7. A week later

Drop `mention_rail_mv` (the site no longer reads it; `published.mention_rail` stays as a view).
