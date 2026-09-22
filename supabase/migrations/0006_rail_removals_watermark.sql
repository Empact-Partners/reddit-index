-- The rail learns about takedowns from the ledger, and a takedown in flight stops everything.
--
-- WHY. 0005 judged deletions partly by the net mention COUNT, and two review rounds of PR #3 (Codex, astra, on
-- clean clones) took that apart:
--   * a count is NET: five takedowns inside a window that collected 910 mentions read as +905, "only added";
--   * delete-sync writes the ledger, deletes the mention, THEN stamps purged_at — a crash between the last two
--     leaves the card gone from `mentions` but invisible to any watermark built on purged rows only;
--   * a refresh taken while a removal is pending would record that removal as "known" while the rail still
--     carries its card, because the mention had not been deleted yet when the rail was rebuilt;
--   * inferring what an existing rail contains from its refreshed_at timestamp is a guess — the only proof is
--     to rebuild it.
-- delete-sync's order is "ledger first, then purge" (worker/delete_sync.py), so the ledger row is the earliest,
-- most reliable fact there is. From here: the watermark is EVERY ledger row (count, newest detected_at); any
-- row still pending purge is a takedown in flight — the build refuses and the refresh refuses; and this
-- migration ends by rebuilding the rail rather than seeding a guess.
--
-- RUN IT IN ORDER, AS ONE FILE. Step 3 recreates `published.mention_rail_meta`, a `select *` view whose column
-- list is fixed when created (skipping it failed production build dpl_GW38TwHWBx37m6x6HvKKre6bGVSf). Step 5
-- rebuilds the rail and takes minutes: it sets its own statement timeout first.

-- 1. the rail's record carries the ledger's mark
alter table public.mention_rail_meta add column if not exists removals_max  timestamptz;
alter table public.mention_rail_meta add column if not exists removals_rows bigint;
comment on column public.mention_rail_meta.removals_rows is 'every removals row that existed when the rail was built (detected, not only purged)';
comment on column public.mention_rail_meta.removals_max  is 'the newest removals.detected_at when the rail was built';

-- 2. the refresh refuses while a takedown is mid-purge, and captures the ledger BEFORE it rebuilds
create or replace function public.refresh_mention_rail(do_concurrently boolean default true)
returns public.mention_rail_meta
language plpgsql
security definer
set search_path = public
set statement_timeout = '30min'
as $$
declare
  meta    public.mention_rail_meta;
  m_rows  bigint; m_max timestamptz;
  s_rows  bigint; s_max timestamptz;
  r_rows  bigint; r_max timestamptz;
  pending bigint;
begin
  select count(*) into pending from public.removals where purged_at is null;
  if pending > 0 then
    raise exception 'refresh_mention_rail: % takedown(s) are recorded but not yet purged — finish delete-sync first; a rail rebuilt now would record them as known while still carrying their cards', pending;
  end if;

  select count(*), max(created_utc) into m_rows, m_max from public.mentions;
  select count(*), max(scored_at)   into s_rows, s_max from public.mention_sentiment;
  select count(*), max(detected_at) into r_rows, r_max from public.removals;

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

-- 3. the doors (both MUST be recreated to show new columns)
create or replace view published.mention_rail_meta as select * from public.mention_rail_meta;
create or replace view published.corpus_revision as
select (select count(*)           from public.mentions)          as mentions_rows,
       (select max(created_utc)   from public.mentions)          as mentions_max,
       (select count(*)           from public.mention_sentiment) as sentiment_rows,
       (select max(scored_at)     from public.mention_sentiment) as sentiment_max,
       (select count(*)           from public.removals)          as removals_rows,
       (select max(detected_at)   from public.removals)          as removals_max,
       (select count(*)           from public.removals where purged_at is null) as removals_pending;

-- 4. grants
grant select on published.mention_rail_meta to site_reader;
grant select on published.corpus_revision   to site_reader;

-- 5. rebuild the rail under the new function instead of inferring what the old one contains. Refuses (by
--    design) if a takedown is mid-purge; finish delete-sync and re-run this statement.
set statement_timeout = '30min';
select public.refresh_mention_rail(false);
