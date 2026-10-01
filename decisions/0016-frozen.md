# 0016 — The index is frozen: no collection, no rebuilds

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
