-- One more index nothing reads (2026-10-14).
--
-- Every new mention writes an entry into each index of its partition, and the first write to an index page after a
-- checkpoint ships the whole page in the write-ahead log; the daily backup ships changed pages again (decision 0033).
-- The sweep's mention insert wrote 5.6 KB of log a row, 1.5 full-page images a row, over five indexes (11-14 Oct,
-- pg_stat_statements, role ri_sweep).
--
-- Read from pg_stat_user_indexes, 11 Oct 07:10 to 14 Oct 05:50 UTC: three nights' runs (takedowns, collect,
-- classify, refresh, score, publish of every changed page, retention) and nine daytime passes:
--
--   mentions_*_brand_id_author_idx   0 scans   77 MB   (4.3 million from 24 Jul to 11 Oct, before the read path)
--
-- The other four were all read: the primary key 1.9 million times, doc_id 2.6 million, (brand_id, created_utc)
-- 1.5 million, (brand_id, doc_type, created_utc) 0.7 million. The distinct-author floors are counted by the refresh
-- from rows it reads by brand, not through this index. A reader that wants it again pays a sequential scan of a
-- brand's rows until it is rebuilt.
set lock_timeout = '5s';
drop index if exists public.mentions_brand_id_author_idx;
