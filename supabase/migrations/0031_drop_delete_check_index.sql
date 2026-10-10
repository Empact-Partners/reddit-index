-- mentions.delete_checked_at has not been written since the takedown check moved its stamps to public.doc_probe
-- (migration 0013); no live code reads it (checked 10 Oct). Its index was still written on every new mention in every
-- partition: one of eight index entries per insert, each first-touched page copied whole into the write-ahead log the
-- egress line pays for. 3,372 scans since 24 July, 18 MB. The column stays (history); only the index goes.
set lock_timeout = '5s';
drop index if exists public.mentions_delete_check_idx;
