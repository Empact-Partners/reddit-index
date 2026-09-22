-- The rail learns about takedowns from the ledger, not from a net count.
--
-- WHY. 0005 judged a stale rail partly by the mention COUNT: fewer mentions than the rail recorded meant
-- deletions, and deletions block the build, because delete-sync propagates takedowns (decisions/0002, a legal
-- condition, never skipped) and a stale materialised rail keeps showing a deleted card. A review of PR #3 found
-- the hole: a count is a NET figure. Five takedowns inside a window that also collected 910 mentions read as
-- +905, "mentions were only added", a warning — and five deleted cards stay on the site.
--
-- Delete-sync already writes the fact that is needed. It records every removal in `removals` FIRST, then
-- purges, then stamps `purged_at` (worker/delete_sync.py, "ledger first, then purge"). A purge after the rail
-- was built is a takedown the rail may still carry, whatever else happened to the count. So the rail records
-- the ledger's high-water mark when it is built, and the build compares it.
--
-- Applied with IF NOT EXISTS / OR REPLACE throughout, so re-running is a no-op. RUN IT IN ORDER: step 3
-- recreates `published.mention_rail_meta`, which is a `select *` view — a view's column list is fixed when it is
-- created, and adding columns to the table without recreating it is what failed production build
-- dpl_GW38TwHWBx37m6x6HvKKre6bGVSf on 2026-09-22.

-- 1. the rail's record gains the ledger's high-water mark
alter table public.mention_rail_meta add column if not exists removals_max  timestamptz;
alter table public.mention_rail_meta add column if not exists removals_rows bigint;

-- 2. the refresh captures it, BEFORE the rebuild like every other mark (a removal that lands mid-refresh makes
--    the mark conservative: the build sees the ledger ahead of the rail and refuses — one rebuild, never a
--    deleted card served)
create or replace function public.refresh_mention_rail(do_concurrently boolean default true)
returns public.mention_rail_meta
language plpgsql
security definer
set search_path = public
set statement_timeout = '30min'
as $$
declare
  meta   public.mention_rail_meta;
  m_rows bigint; m_max timestamptz;
  s_rows bigint; s_max timestamptz;
  r_rows bigint; r_max timestamptz;
begin
  select count(*), max(created_utc) into m_rows, m_max from public.mentions;
  select count(*), max(scored_at)   into s_rows, s_max from public.mention_sentiment;
  select count(*), max(purged_at)   into r_rows, r_max from public.removals where purged_at is not null;

  if do_concurrently then
    refresh materialized view concurrently public.mention_rail_mv;
  else
    refresh materialized view public.mention_rail_mv;
  end if;

  insert into public.mention_rail_meta
         (only_row, refreshed_at, rail_rows, mentions_max, mentions_rows, sentiment_max, sentiment_rows,
          removals_max, removals_rows)
  select true, now(), (select count(*) from public.mention_rail_mv), m_max, m_rows, s_max, s_rows, r_max, r_rows
  on conflict (only_row) do update
     set refreshed_at   = excluded.refreshed_at,
         rail_rows      = excluded.rail_rows,
         mentions_max   = excluded.mentions_max,
         mentions_rows  = excluded.mentions_rows,
         sentiment_max  = excluded.sentiment_max,
         sentiment_rows = excluded.sentiment_rows,
         removals_max   = excluded.removals_max,
         removals_rows  = excluded.removals_rows
  returning * into meta;

  return meta;
end;
$$;

-- 3. the doors: both are `select *` / an explicit list, and both MUST be recreated to show the new columns
create or replace view published.mention_rail_meta as select * from public.mention_rail_meta;
create or replace view published.corpus_revision as
select (select count(*)           from public.mentions)          as mentions_rows,
       (select max(created_utc)   from public.mentions)          as mentions_max,
       (select count(*)           from public.mention_sentiment) as sentiment_rows,
       (select max(scored_at)     from public.mention_sentiment) as sentiment_max,
       (select count(*)           from public.removals where purged_at is not null) as removals_rows,
       (select max(purged_at)     from public.removals where purged_at is not null) as removals_max;

grant select on published.mention_rail_meta to site_reader;
grant select on published.corpus_revision   to site_reader;

-- 4. seed the ledger mark for the rail that exists now — with what the ledger held WHEN THAT RAIL WAS BUILT,
--    never with today's figure. Seeding "now" would silently accept every takedown purged between the last
--    refresh and this migration, which is precisely the case the migration exists to catch; seeded as of
--    refreshed_at, those purges read as ahead of the rail and the next build refuses until it is refreshed.
update public.mention_rail_meta m
   set removals_rows = (select count(*) from public.removals r
                         where r.purged_at is not null and r.purged_at <= m.refreshed_at),
       removals_max  = (select max(r.purged_at) from public.removals r
                         where r.purged_at is not null and r.purged_at <= m.refreshed_at)
 where m.removals_rows is null;
