-- How many comments a thread had when its comment tree was last read (2026-10-11).
--
-- The collect stage read a thread's tree again on every visit inside 72 hours. On 11 Oct, 84% of those repeat reads
-- found nothing new (1,438 of 1,710), each one a Reddit call and a row rewritten. With the count kept here the next
-- visit reads a thread again only when Reddit shows more comments than it had (the listing just read says so for
-- free; /api/info for the rest, 100 threads a call). Null: read before this column existed, or never read.
set lock_timeout = '5s';
alter table public.threads add column if not exists tree_comments integer;
