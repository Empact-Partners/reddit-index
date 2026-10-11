-- Three indexes nothing reads any more (2026-10-11).
--
-- Every new mention writes an entry into each index of its partition, and the first write to a page after a
-- checkpoint ships the whole page in the write-ahead log; the same pages are shipped again by the daily physical
-- backup. A new mention cost 10 KB of log at seven indexes (6.4 KB with half-hourly checkpoints), against about
-- 2 KB of row.
--
-- Read from pg_stat_user_indexes, 10 Oct 22:55 to 11 Oct 13:15 UTC: a whole night's run (takedowns, collect,
-- classify, refresh, score, publish of 1,000 pages, retention with 28,000 threads removed), retention step 3, a
-- five-hour daytime pass, 1,400 page renders and a day of visitors:
--
--   mentions_*_thread_id_idx      0 scans   35 MB   (49.8 million before, all from the collector retired on 2 Oct)
--   mentions_*_subreddit_id_idx   0 scans   19 MB   (7.2 million before, the old site's build)
--   threads_subreddit_id_created_utc_idx   0 scans   35 MB   (2,214 since August)
--
-- No foreign key needs them: mentions.subreddit_id references subreddits, whose rows are never deleted, and
-- nothing references threads. A reader that wants one again pays a sequential scan until it is rebuilt
-- (create index concurrently, about a minute each).
set lock_timeout = '5s';
drop index if exists public.mentions_thread_id_idx;
drop index if exists public.mentions_subreddit_id_idx;
drop index if exists public.threads_subreddit_id_created_utc_idx;
