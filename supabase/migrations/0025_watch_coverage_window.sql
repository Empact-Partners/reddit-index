-- 0024's coverage view, corrected (Codex review, 2026-10-06): a mention with no known time is looked up in every
-- partition instead of reading as missing, and the time window is an hour, not a minute.
create or replace view watch.organic_coverage as
select o.*,
       exists (select 1 from public.mentions m
               where m.brand_id = o.brand_id and m.doc_id = o.reddit_id
                 and (o.written_at is null
                      or m.created_utc between o.written_at - interval '1 hour' and o.written_at + interval '1 hour')) as in_index
from watch.organic_mentions o;
revoke all on watch.organic_coverage from public;
