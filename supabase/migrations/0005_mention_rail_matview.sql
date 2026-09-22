-- The mention rail, precomputed once per publish instead of once per build worker.
--
-- WHY. 0004 fixed the whole-table AGGREGATE (119,053 ms -> 14,633 ms). It did not fix the RAIL, and after that
-- fix the rail is the most expensive thing the build does. Measured on production 2026-09-22, with the 0004
-- indexes valid and attached on all 49 partitions:
--
--     rail   : 86,909 ms, 2,786,173 shared buffers (~22 GB of buffer traffic), 161,660 rows at width 735
--     aggregate: 11,894 ms, 1,240,014 rows scanned
--
-- The rail is slow for a reason no index removes. It asks for the newest 80 comments and 40 posts PER BRAND (doc_type 1 is a comment, 2 is a post),
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

-- A UNIQUE index is what REFRESH ... CONCURRENTLY requires, and it must be unique for real. The source's
-- primary key is (brand_id, doc_id, CREATED_UTC) — 0001 line 138 — so a brand CAN hold two rows for one
-- document at different timestamps, and (brand_slug, doc_id) alone would refuse the refresh the first time
-- one appeared. Today's corpus has no such pair, which is exactly how this would have shipped and then
-- broken a publish months later, on data nobody changed on purpose.
create unique index if not exists mention_rail_mv_key
  on public.mention_rail_mv (brand_slug, doc_id, created_utc);
-- The build groups by brand; the read is a scan per brand, not a seek.
create index if not exists mention_rail_mv_brand on public.mention_rail_mv (brand_slug);

-- 2. What the build asks to know whether the rail it is about to read is the rail this data deserves.
--    A matview cannot timestamp itself, so the refresh records what it saw.
--    FOUR numbers, not one. A high-water mark on created_utc alone answers "did new mentions arrive" and
--    nothing else, and the commonest publish in this repo changes no mention at all: collect -> classify ->
--    score -> publish re-LABELS existing rows, and the rail carries the label. A rescored corpus under an
--    unchanged newest-mention timestamp is precisely the stale rail this guard exists to catch. The counts
--    close the other doors: a deletion, an edited body, and a backfill of an older document into a brand's
--    underfilled rail all move a count without moving a maximum.
create table if not exists public.mention_rail_meta (
  only_row       boolean primary key default true check (only_row),
  refreshed_at   timestamptz not null,
  rail_rows      bigint      not null,
  mentions_max   timestamptz,            -- the newest mention that existed when the rail was built
  mentions_rows  bigint,                 -- and how many there were
  sentiment_max  timestamptz,            -- the newest label, so a rescore cannot hide
  sentiment_rows bigint
);
--    The two ALTERs are for a store that already holds the first version of this table. They MUST come
--    before section 4, because `published.mention_rail_meta` is a view defined as `select *` and a view's
--    column list is FIXED WHEN IT IS CREATED: adding a column to the table does not add it to the view.
--    Applying these two lines by hand without re-running section 4 is what failed production build
--    dpl_GW38TwHWBx37m6x6HvKKre6bGVSf on 2026-09-22 with `column "sentiment_max" does not exist` — the
--    column existed, the view just could not see it. Run this file in order, or not at all.
alter table public.mention_rail_meta add column if not exists sentiment_max  timestamptz;
alter table public.mention_rail_meta add column if not exists sentiment_rows bigint;

-- 3. The one way to refresh it. Publishing calls this; nothing else should.
create or replace function public.refresh_mention_rail(do_concurrently boolean default true)
returns public.mention_rail_meta
language plpgsql
security definer
set search_path = public
-- The refresh takes minutes, and it must not inherit the caller's timeout. Measured 2026-09-22: a
-- CONCURRENTLY refresh called through the Management API (a 120 s cap) was cancelled at 120.5 s with
-- 57014, mid-diff. This clause is NOT sufficient on its own — a timeout already armed for the calling
-- statement keeps running — so worker/publish.py also sets it on the session before it calls. Both.
set statement_timeout = '30min'
as $$
declare
  meta   public.mention_rail_meta;
  m_rows bigint; m_max timestamptz;
  s_rows bigint; s_max timestamptz;
begin
  -- CAPTURED BEFORE THE REFRESH, deliberately. A mention that commits while the rail is rebuilding lands
  -- outside this snapshot, so the recorded mark is CONSERVATIVE: the build sees the corpus ahead of the
  -- rail and refuses, which costs one rebuild. Capturing it afterwards has the opposite error — the mark
  -- would include a row the rail does not carry, and the guard would wave an incomplete rail through.
  select count(*), max(created_utc) into m_rows, m_max from public.mentions;
  select count(*), max(scored_at)   into s_rows, s_max from public.mention_sentiment;

  if do_concurrently then
    refresh materialized view concurrently public.mention_rail_mv;
  else
    refresh materialized view public.mention_rail_mv;
  end if;

  insert into public.mention_rail_meta
         (only_row, refreshed_at, rail_rows, mentions_max, mentions_rows, sentiment_max, sentiment_rows)
  select true, now(), (select count(*) from public.mention_rail_mv), m_max, m_rows, s_max, s_rows
  on conflict (only_row) do update
     set refreshed_at   = excluded.refreshed_at,
         rail_rows      = excluded.rail_rows,
         mentions_max   = excluded.mentions_max,
         mentions_rows  = excluded.mentions_rows,
         sentiment_max  = excluded.sentiment_max,
         sentiment_rows = excluded.sentiment_rows
  returning * into meta;

  return meta;
end;
$$;

-- 4. The reader's doors, mirroring the published.* pattern: the site never touches public.
create or replace view published.mention_rail as select * from public.mention_rail_mv;
create or replace view published.mention_rail_meta as select * from public.mention_rail_meta;

-- The corpus revision behind ONE door. The site never reads public.* directly, and the build needs all four
-- numbers in one round trip: 4.8 s measured, run beside the 11.9 s aggregate so it costs nothing.
create or replace view published.corpus_revision as
select (select count(*)           from public.mentions)          as mentions_rows,
       (select max(created_utc)   from public.mentions)          as mentions_max,
       (select count(*)           from public.mention_sentiment) as sentiment_rows,
       (select max(scored_at)     from public.mention_sentiment) as sentiment_max;

grant select on published.corpus_revision     to site_reader;
grant select on public.mention_rail_mv        to site_reader;
grant select on public.mention_rail_meta      to site_reader;
grant select on published.mention_rail        to site_reader;
grant select on published.mention_rail_meta   to site_reader;

-- 5. The migration materialises the rail WITH data (step 1), so it must also record that it did. Without
--    this, applying the migration and letting a push-triggered build run before the next publish throws
--    STALE_RAIL against a rail that is in fact current.
insert into public.mention_rail_meta
       (only_row, refreshed_at, rail_rows, mentions_max, mentions_rows, sentiment_max, sentiment_rows)
select true, now(), (select count(*) from public.mention_rail_mv),
       (select max(created_utc) from public.mentions), (select count(*) from public.mentions),
       (select max(scored_at) from public.mention_sentiment), (select count(*) from public.mention_sentiment)
on conflict (only_row) do nothing;
