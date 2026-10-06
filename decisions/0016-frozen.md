# 0016 — The index is frozen: no collection, no rebuilds

> **Superseded 2026-10-06 by [0017](0017-daily-sweep.md):** the index refreshes itself once a day on Railway.

**Status:** Accepted · **Date:** 2026-10-01 · **Decided by:** Vlad Shvets

**Supersedes:** decision 0010's "run `worker/update.sh` at least weekly". Nothing updates the index now, by hand or otherwise.

## Bottom line

redditindex.com stays up, serving the pages it was last built with (2026-09-22). The database stays up. **Nothing writes to it and nothing rebuilds the site.** Vlad, 2026-10-01: "Reddit index should not be updated. All the updates to Reddit index must stop, and it should stop sending data. Do not take it down, but just stop the updates."

## What was running, against the record

Decision 0010 (2026-08-18) says the Railway collection cron was removed and the service taken Offline. **It was not.** The cron lives on the Railway service, not in `railway.json`, so removing it from the file changed nothing. The deployment created 2026-08-19 02:04 UTC still carried `cronSchedule: 0 2 * * *`, and `worker/daily.py` ran every night at 02:00 UTC for about 5.5 hours. Every day from 2026-09-11 to 2026-10-01 shows 6,800–8,700 new threads first seen between 02:00 and 08:53 UTC, and 15,500–20,100 new mentions per run. The last run finished 2026-10-01 07:41 UTC: 11,454 threads, 18,775 mentions, 17,720 Reddit calls in 338 minutes. Classification has not run since 2026-08-25, so those mentions were stored and never scored.

The Supabase egress watchdog flagged reddit-index on 2026-10-01 at 1.28 GB/day against a usual ~0.33. The usual figure was the nightly collection: its writes, and the backup and replication traffic they cause, count against the egress counter. The extra ~0.95 GB on that one day is unattributed. No Vercel build ran (the last was 2026-09-22), no other Railway service holds this database's credentials, and the only Claude session that tried to read it that night failed to connect. Supabase's logs endpoint was returning backend errors when this was written.

## What was done, 2026-10-01

1. **The collector's deployment was removed** (`railway down`, project `reddit-index` 90cd4c29…, service ff501aef…). The service, its variables and its history remain. With no active deployment the cron has nothing to run. Verified: zero active deployments, `nextCronRunAt` empty.
2. **Vercel skips every git-triggered build** of project `reddit-index` (`prj_OhSRGKEKFeN2A9JU1BTeebdR6E29`): Ignored Build Step = `exit 0`. A push no longer rebuilds the site, so no build re-reads the corpus (~400 MB each). The live site keeps serving its prerendered pages. It has no runtime data path (`force-static`, `dynamicParams = false`, `revalidate = false`) and no Vercel crons.
3. **Measured after:** 0.31 MB in 301 s, about 0.09 GB/day, with no client connected to the database.

## Not touched

- The database, its roles and its data.
- The outreach repos (`reddit-index-outreach`, `reddit-index-followup`, `partner-development`) read this database only when someone runs their scripts. Running them is a read, and it costs egress.
- `com.vladshvets.ri-fu-sibling-delete` works on Instantly leads, not on this database.

## To undo (only on a new ruling)

- Collection: `railway up` from this repo, linked to the `reddit-index` service. A first deploy before a schedule exists runs once immediately. Set the schedule on the service with `railway config` and prove it with `nextCronRunAt`, never through `railway.json`.
- Rebuilds: clear the Ignored Build Step in the Vercel project settings, then redeploy.


## Addendum, 2026-10-02: the freeze above did not hold, and what stopped it

**What happened.** Step 1 above removed the deployment and read "zero active deployments, `nextCronRunAt`
empty" as proof. At 2026-10-02 02:01:57 UTC Railway created a new deployment of the same image by itself
(reason `redeploy`, manifest `cronSchedule: 0 2 * * *`). It collected from 02:04 to 07:43 UTC: 18,155
mentions, 8,258 threads, 2,029 of 2,029 subreddits. This is the second time the same command failed the
same way (the first was 2026-08-18, see above).

**Why.** The schedule is not a property of the service that `railway down` clears. Every deployment in
this service's history carries the cron in its own manifest (it entered through `railway.json` on
2026-08-09), and at the next tick Railway redeploys the newest one. The service's `cronSchedule` and
`nextCronRunAt` read empty the whole time. No deployment had ever been made from the cron-less
`railway.json`, so removing the key from the file on 2026-08-18 changed nothing that runs.

**What was done, 2026-10-02 20:45 to 20:48 UTC.**

1. **The database's `postgres` password was reset** through Supabase's Management API. The old collector's
   image connects to the database before it makes any Reddit call, and Railway held the only copy of the
   old password, so a resurrected run now ends at the connection with zero Reddit calls and zero rows.
   Verified: the password stored on the Railway service is refused on both pooler ports. The new password
   is in `~/.claude/.reddit-index.json` (0600) on Vlad's Mac. Nothing else used the old one: the site
   builds as `site_reader`, and every script on the Mac reads through the Management API.
2. **The service was given a deployment that does nothing.** `Dockerfile.parked` prints one line and
   exits; `railway.json` points at it and has no cron. Deployed with `railway up`, linked by project and
   service id. Verified: the newest deployment's manifest has `cronSchedule: null` and
   `dockerfilePath: Dockerfile.parked`; its log is the one parked line; the collector's deployment is
   `REMOVED`.
3. **The proof is the data, not the config.** `ops/park_watch.py` checks, at 02:20, 03:00 and 08:00 UTC,
   that no collector deployment exists and that `mentions`, `threads` and `ingest_state` have zero rows
   written after the park. It removes a resurrected deployment and sends one DM if a check is not clean.
   The freeze counts as real after two clean nights (3 and 4 October). Results are appended below.

**The corrected dates.** The collector ran nightly from 2026-08-19 to **2026-10-02** inclusive. The freeze
began on 2026-10-02 at 20:47 UTC, not on 2026-10-01.

**The "To undo" section above is wrong and must not be followed.** `railway up` from the tree as it was
on 2026-10-01 starts a full collection at once (the image's command is `daily.py` with no flags), and
"set the schedule on the service and prove it with `nextCronRunAt`" trusts the two fields that read empty
while the cron fired. The relaunch (decision 0017) deploys a new job from a new service with its own
database role, and proves its schedule by receipts.

### Verification log

| Check (UTC) | Collector deployment | Rows written since the park | Result |
|---|---|---|---|
| 2026-10-02 20:49 | none (newest is the parked image, no cron) | 0 mentions, 0 threads, 0 receipts | clean |
| 2026-10-03 02:20 | none (newest is still the parked image, no cron) — the old 02:00 slot passed | 0 outside a receipt (the new sweep's pilot wrote inside its own) | clean |
| 2026-10-03 03:00 | none | 0 outside a receipt | clean |
| 2026-10-03 08:00 | none | 0 outside a receipt | clean (first night proven) |
| 2026-10-04 12:12 | none (newest is still the parked image, no cron) — the 02:00 slot passed a second time | 0 outside a receipt (the first scheduled sweep wrote inside its own) | clean (second night proven: **stopped**). The 02:20/03:00/08:00 watcher died with the session that started it; this check reads the same data afterwards |

From 3 October the new sweep (decision 0017) writes too, always inside a receipt (`public.pipeline_runs`). The
check counts only writes outside every receipt; `scripts/schedule_check.py` applies the same rule daily.

