-- Rows the retention steps remove are first copied here and kept 14 days (docs/retention.md). Same database, so
-- copying costs no egress; the managed daily backup is the second copy.
create schema if not exists archive;
revoke all on schema archive from public;

create table if not exists archive.threads (like public.threads);
alter table archive.threads add column if not exists archived_at timestamptz not null default now();

create table if not exists archive.mentions (like public.mentions);
alter table archive.mentions add column if not exists archived_at timestamptz not null default now();

create table if not exists archive.mention_sentiment (like public.mention_sentiment);
alter table archive.mention_sentiment add column if not exists archived_at timestamptz not null default now();

create index if not exists archive_threads_at on archive.threads (archived_at);
create index if not exists archive_mentions_at on archive.mentions (archived_at);
create index if not exists archive_sentiment_at on archive.mention_sentiment (archived_at);

-- The sweep runs steps 1 and 2 daily.
grant usage on schema archive to ri_sweep;
grant select, insert, delete on all tables in schema archive to ri_sweep;
grant delete on public.threads to ri_sweep;
grant update (body, body_from) on public.mentions to ri_sweep;
