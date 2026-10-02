-- The classifier takes the newest mentions first: what arrived since the last run, then the backlog from its
-- newest mention down (worker/classify_sweep.py). Without this index every batch of 2,000 sorted the whole
-- queue (about 800,000 rows when the backlog starts).
create index if not exists classify_queue_order
    on public.classify_queue (enqueued_at desc, created_utc desc)
    where attempts < 5;
