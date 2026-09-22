-- The mention rail, precomputed once per publish instead of once per build worker.
--
-- WHY. 0004 fixed the whole-table AGGREGATE (119,053 ms -> 14,633 ms). It did not fix the RAIL, and after that
-- fix the rail is the most expensive thing the build does. Measured on production 2026-09-22, with the 0004
-- indexes valid and attached on all 49 partitions:
--
--     rail   : 86,909 ms, 2,786,173 shared buffers (~22 GB of buffer traffic), 161,660 rows at width 735
--     aggregate: 11,894 ms, 1,240,014 rows scanned
--
-- The rail is slow for a reason no index removes. It asks for the newest 80 posts and 40 comments PER BRAND,
-- and `mentions` is partitioned by month: to find one brand's newest rows Postgres must merge across all 49
-- partitions. That is 10,511 brands x 2 doc types x 49 partitions, about a million index probes, and it grows
-- on BOTH axes — one more partition every month, more brands every sweep.
--
-- next.config.ts caps the build at 2 workers and each worker runs the whole snapshot, so the site pays this
-- twice per publish, and the first page each worker touches pays it against a 300 s page timeout. That is the
-- same shape as the failure 0004 fixed, one timeout up: not "it is broken", but "it gets worse every month and
-- then one Tuesday it is broken and the site cannot be rebuilt at all".
--
-- WHAT. The rail becomes a materialised view refreshed at publish time, carrying ONLY the eleven columns the
-- page renders. The build then reads a flat table instead of merging partitions per brand.
--
-- Columns dropped from the old `select t.*`: score, intensity, stage, subreddit_id, brand_id — read from disk,
-- shipped over the wire and never rendered. doc_id stays: it is the unique key a concurrent refresh needs.
--
-- Applied with IF NOT EXISTS throughout so re-running it is a no-op.

-- 1. The rail itself. The inner laterals mirror published.mentions (the newest sentiment row per document),
--    so the matview and the view cannot disagree about a label.
create materialized view if not exists public.mention_rail_mv as
select
  b.slug             as brand_slug,
  b.name             as brand_name,
  sr.name            as subreddit,
  t.doc_id,
  t.doc_type,
  t.thread_id,
  t.author,
  t.created_utc,
  t.permalink,
  t.body,
  t.matched_form,
  t.label
from public.brands b
cross join lateral (
  (select m.doc_id, m.doc_type, m.thread_id, m.subreddit_id, m.author, m.created_utc,
          m.permalink, m.body, m.matched_form, s.label
     from public.mentions m
     left join lateral (
       select ms.label from public.mention_sentiment ms
        where ms.doc_id = m.doc_id and ms.brand_id = m.brand_id
        order by ms.scored_at desc nulls last, ms.model_version desc
        limit 1) s on true
    where m.brand_id = b.id and m.doc_type = 1
    order by m.created_utc desc
    limit 80)
  union all
  (select m.doc_id, m.doc_type, m.thread_id, m.subreddit_id, m.author, m.created_utc,
          m.permalink, m.body, m.matched_form, s.label
     from public.mentions m
     left join lateral (
       select ms.label from public.mention_sentiment ms
        where ms.doc_id = m.doc_id and ms.brand_id = m.brand_id
        order by ms.scored_at desc nulls last, ms.model_version desc
        limit 1) s on true
    where m.brand_id = b.id and m.doc_type = 2
    order by m.created_utc desc
    limit 40)
) t
join public.subreddits sr on sr.id = t.subreddit_id
where b.status = 'published';

-- A UNIQUE index is what REFRESH ... CONCURRENTLY requires. (brand_slug, doc_id) is the rail's identity: one
-- brand matched in one document once.
create unique index if not exists mention_rail_mv_key on public.mention_rail_mv (brand_slug, doc_id);
-- The build groups by brand; the read is a scan per brand, not a seek.
create index if not exists mention_rail_mv_brand on public.mention_rail_mv (brand_slug);

-- 2. What the build asks to know whether the rail it is about to read is the rail this data deserves.
--    A matview cannot timestamp itself, so the refresh records what it saw.
create table if not exists public.mention_rail_meta (
  only_row       boolean primary key default true check (only_row),
  refreshed_at   timestamptz not null,
  rail_rows      bigint      not null,
  mentions_max   timestamptz,            -- the newest mention that existed when the rail was built
  mentions_rows  bigint                  -- and how many there were
);

-- 3. The one way to refresh it. Publishing calls this; nothing else should.
create or replace function public.refresh_mention_rail(do_concurrently boolean default true)
returns public.mention_rail_meta
language plpgsql
security definer
set search_path = public
-- The refresh takes minutes, and it must not inherit the caller's timeout. Measured 2026-09-22: a
-- CONCURRENTLY refresh called through the Management API (a 120 s cap) was cancelled at 120.5 s with
-- 57014, mid-diff. A rebuild of the rail that dies half way leaves the old rail in place and the
-- publish believing it refreshed, so the timeout belongs to the FUNCTION, not to whoever calls it.
set statement_timeout = '30min'
as $$
declare
  meta public.mention_rail_meta;
begin
  if do_concurrently then
    refresh materialized view concurrently public.mention_rail_mv;
  else
    refresh materialized view public.mention_rail_mv;
  end if;

  insert into public.mention_rail_meta (only_row, refreshed_at, rail_rows, mentions_max, mentions_rows)
  select true, now(),
         (select count(*) from public.mention_rail_mv),
         (select max(created_utc) from public.mentions),
         (select count(*) from public.mentions)
  on conflict (only_row) do update
     set refreshed_at  = excluded.refreshed_at,
         rail_rows     = excluded.rail_rows,
         mentions_max  = excluded.mentions_max,
         mentions_rows = excluded.mentions_rows
  returning * into meta;

  return meta;
end;
$$;

-- 4. The reader's doors, mirroring the published.* pattern: the site never touches public.
create or replace view published.mention_rail as select * from public.mention_rail_mv;
create or replace view published.mention_rail_meta as select * from public.mention_rail_meta;

grant select on public.mention_rail_mv        to site_reader;
grant select on public.mention_rail_meta      to site_reader;
grant select on published.mention_rail        to site_reader;
grant select on published.mention_rail_meta   to site_reader;
