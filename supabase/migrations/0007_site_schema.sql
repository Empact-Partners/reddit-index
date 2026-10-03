-- 0007 — the `site` schema: what a page needs, precomputed, one brand at a time.
--
-- WHY. Until now every build ran lib/data/snapshot.ts: an aggregate over all 1.4 million mentions, every
-- thread title, and the whole card rail, twice (two build workers), about 400 MB a build. While the pages were
-- time-revalidated (5 Aug to 17 Sep 2026) every page regeneration ran the same thing: 3.80 billion rows sent
-- to `site_reader`, 97% of the organisation's egress (docs/investigation-2026-10.md).
--
-- WHAT. The numbers and the card list for one company are computed here, inside Postgres, by
-- `site.refresh_brand(brand_id)`, only for brands whose data changed (`site.dirty_brand`, filled by triggers).
-- A page then reads ONE row of `site.brand_stats` and its own cards. Nothing the site can read scans the corpus.
--
-- THE CARDS ARE NOT COPIED. `site.rail_key` holds only which documents a page shows (brand, document, time).
-- `site.rail_card` is a view that looks those documents up in `mentions` by primary key. Two consequences:
--   * no second copy of the comment text (the materialised view this replaces held 231 MB of it);
--   * a takedown is structural. A document deleted from `mentions`, or listed in `removals` and not yet purged,
--     cannot be returned by the view, whatever the key table still says.
--
-- THE GRANTS ARE THE GUARD. The role the site connects as (`ri_site`) can read this schema and nothing else,
-- with a 5 second statement timeout. `scripts/gates/bounded-reads.mjs` checks the code; the grants make the
-- rule true even if the code is wrong.
--
-- Applied by ops/migrate.py as one transaction. Additive: nothing in `public` or `published` is altered
-- except four triggers and one new empty table. To undo: `drop schema site cascade`, drop the triggers named
-- `site_dirty` on mentions, mention_sentiment, removals and brands, and `drop table public.mention_rejections`.

create schema if not exists site;
revoke all on schema site from public;

-- ── 0. "not this product": a verdict that outlives the machine that reached it ────────────────────────────
-- The old classifier returned entity_ok=false for a mention that is not about the brand ("snow" is not
-- ServiceNow) and wrote NO row; the only record was a cache file on a laptop. In the database a rejected
-- mention was indistinguishable from one never classified, was re-paid on every run, and the site counted it
-- as a neutral mention. This table is that record. It is empty until the new classifier writes to it; while
-- it is empty every number below equals the old build's.
create table if not exists public.mention_rejections (
  doc_id        text        not null,
  brand_id      bigint      not null,
  model_version text        not null,
  conf          real,
  reason        text,
  rejected_at   timestamptz not null default now(),
  primary key (doc_id, brand_id)
);
alter table public.mention_rejections enable row level security;
create index if not exists mention_rejections_brand on public.mention_rejections (brand_id);

-- ── 1. one row per company page ────────────────────────────────────────────────────────────────────────────
create table if not exists site.brand_stats (
  brand_id              bigint      primary key,
  slug                  text        not null unique,
  name                  text        not null,
  primary_category_id   bigint,
  primary_category_slug text,                       -- null when the category is not published: no board, no rank
  -- the dashboard tiles: everything collected for the brand, the newest label per document
  pos                   integer     not null default 0,
  neg                   integer     not null default 0,
  neu                   integer     not null default 0,   -- neutral + abstain + not yet classified
  unlabelled            integer     not null default 0,   -- the not-yet-classified part of `neu`
  posts                 integer     not null default 0,
  comments              integer     not null default 0,
  total_mentions        integer     not null default 0,
  oldest_mention        timestamptz,
  newest_mention        timestamptz,
  subreddit_stats       jsonb       not null default '[]'::jsonb,  -- [{subreddit,total,pos,neg,neu,newest}], total desc
  rail_size             integer     not null default 0,   -- cards the page shows (at most 80 comments + 40 posts)
  rail_hash             text        not null default '',
  stats_hash            text        not null default '',
  -- written by the scorer (worker/site_score.py): the estimator needs an inverse Beta CDF
  page_score            integer,
  page_n_op             integer     not null default 0,
  board_rank            integer,
  board_size            integer     not null default 0,
  scored_at             timestamptz,
  -- what the page should look like, and what was last PROVEN to be served (set only after fetching the page)
  page_hash             text generated always as (
    md5(stats_hash || '|' || rail_hash || '|' || coalesce(page_score::text, '') || '|' ||
        coalesce(board_rank::text, '') || '|' || board_size::text)) stored,
  served_hash           text,
  served_at             timestamptz,
  refreshed_at          timestamptz not null default now()
);
create index if not exists brand_stats_category on site.brand_stats (primary_category_slug);

-- ── 2. which documents each page shows ─────────────────────────────────────────────────────────────────────
create table if not exists site.rail_key (
  brand_id    bigint      not null,
  doc_id      text        not null,
  created_utc timestamptz not null,
  doc_type    smallint    not null,
  primary key (brand_id, doc_id, created_utc)
);
create index if not exists rail_key_doc on site.rail_key (doc_id);

-- The cards, looked up at read time. Same columns the old rail carried, plus the thread title for comments
-- (the build used to fetch every thread title to find these) and brand_id for the refresh.
create or replace view site.rail_card as
select k.brand_id,
       bs.slug  as brand_slug,
       bs.name  as brand_name,
       sr.name  as subreddit,
       m.doc_id,
       m.doc_type,
       m.thread_id,
       m.author,
       m.created_utc,
       m.permalink,
       m.body,
       m.matched_form,
       s.label,
       case when m.doc_type = 2 then null else t.link_title end as thread_title
from site.rail_key k
join site.brand_stats bs on bs.brand_id = k.brand_id
join public.mentions m
  on m.brand_id = k.brand_id and m.doc_id = k.doc_id and m.created_utc = k.created_utc
join public.subreddits sr on sr.id = m.subreddit_id
left join public.threads t on t.id = m.thread_id
left join lateral (
  select ms.label from public.mention_sentiment ms
   where ms.doc_id = m.doc_id and ms.brand_id = m.brand_id
   order by ms.scored_at desc nulls last, ms.model_version desc
   limit 1) s on true
where m.author <> '[deleted]'
  -- a takedown in flight (recorded, not yet purged) is already invisible
  and not exists (select 1 from public.removals r where r.doc_id = m.doc_id)
  -- the build used to throw on a permalink that is not Reddit's comment shape; a page render must not throw
  -- (a throw re-serves the old page), so the card is left out and site.bad_permalinks reports it
  and m.permalink ~ '^(https://www\.reddit\.com)?/r/[A-Za-z0-9_]+/comments/[a-z0-9]+';

create or replace view site.bad_permalinks as
select k.brand_id, k.doc_id, m.permalink
from site.rail_key k
join public.mentions m on m.brand_id = k.brand_id and m.doc_id = k.doc_id and m.created_utc = k.created_utc
where m.permalink !~ '^(https://www\.reddit\.com)?/r/[A-Za-z0-9_]+/comments/[a-z0-9]+';

-- ── 3. what changed ────────────────────────────────────────────────────────────────────────────────────────
create table if not exists site.dirty_brand (
  brand_id  bigint      primary key,
  marked_at timestamptz not null default now()
);

create or replace function site.mark_dirty() returns trigger
language plpgsql security definer set search_path = public, site, pg_temp as $$
begin
  if tg_table_name = 'removals' then
    insert into site.dirty_brand (brand_id)
    select distinct b from unnest(coalesce(new.brand_ids, '{}'::bigint[])) as b
    on conflict (brand_id) do nothing;
    return new;
  end if;
  if tg_table_name = 'brands' then
    if tg_op = 'DELETE' then
      insert into site.dirty_brand (brand_id) values (old.id) on conflict (brand_id) do nothing;
      return old;
    end if;
    insert into site.dirty_brand (brand_id) values (new.id) on conflict (brand_id) do nothing;
    return new;
  end if;
  if tg_op = 'DELETE' then
    insert into site.dirty_brand (brand_id) values (old.brand_id) on conflict (brand_id) do nothing;
    return old;
  end if;
  insert into site.dirty_brand (brand_id) values (new.brand_id) on conflict (brand_id) do nothing;
  return new;
end;
$$;

-- Row triggers, so EVERY writer is covered (the sweep, a manual purge, a backfill). On the partitioned
-- `mentions` the trigger is cloned onto every partition, including ones created later.
-- NOT on UPDATE of mentions: delete-sync stamps delete_checked_at on tens of thousands of rows a day.
drop trigger if exists site_dirty on public.mentions;
create trigger site_dirty after insert or delete on public.mentions
  for each row execute function site.mark_dirty();
drop trigger if exists site_dirty on public.mention_sentiment;
create trigger site_dirty after insert or update or delete on public.mention_sentiment
  for each row execute function site.mark_dirty();
drop trigger if exists site_dirty on public.mention_rejections;
create trigger site_dirty after insert or delete on public.mention_rejections
  for each row execute function site.mark_dirty();
drop trigger if exists site_dirty on public.removals;
create trigger site_dirty after insert on public.removals
  for each row execute function site.mark_dirty();
drop trigger if exists site_dirty on public.brands;
create trigger site_dirty after insert or delete or update of status, name, slug, primary_category_id on public.brands
  for each row execute function site.mark_dirty();

-- ── 4. recompute ONE brand from the truth ──────────────────────────────────────────────────────────────────
-- Recomputed, never incremented: a relabel (newest label wins), a purge and a status flip all land correctly
-- without anyone remembering to adjust a counter. One index-bound pass over the brand's own mentions.
create or replace function site.refresh_brand(p_brand bigint) returns boolean
language plpgsql security definer set search_path = public, site, pg_temp
set statement_timeout = '10min' as $$
declare
  v_b        record;
  v_a        record;
  v_hash     text;
  v_size     integer;
  v_rail     text;
begin
  -- Cleared FIRST. A mention that commits while this runs re-marks the brand (its insert waits on this
  -- delete and then succeeds), so the worst case is one extra refresh, never a lost change.
  delete from site.dirty_brand where brand_id = p_brand;

  select b.id, b.slug, b.name, b.status, b.primary_category_id, c.slug as cat_slug
    into v_b
    from public.brands b
    left join public.categories c
           on c.id = b.primary_category_id and c.status in ('published', 'unrankable')
   where b.id = p_brand;

  if not found or v_b.status <> 'published' then
    delete from site.rail_key where brand_id = p_brand;
    delete from site.brand_stats where brand_id = p_brand;
    return false;
  end if;

  -- The same reading as the old build's aggregate: the newest label per document; label 1 is positive,
  -- 2 negative, everything else (neutral, abstain, not classified yet) is shown as neutral.
  with lab as (
    select m.subreddit_id, m.doc_type, m.created_utc, s.label
      from public.mentions m
      left join lateral (
        select ms.label from public.mention_sentiment ms
         where ms.doc_id = m.doc_id and ms.brand_id = m.brand_id
         order by ms.scored_at desc nulls last, ms.model_version desc
         limit 1) s on true
     where m.brand_id = p_brand
       and not exists (select 1 from public.mention_rejections x
                        where x.doc_id = m.doc_id and x.brand_id = m.brand_id)),
  per_sub as (
    select sr.name as subreddit,
           count(*)                                                     as total,
           count(*) filter (where l.label = 1)                          as pos,
           count(*) filter (where l.label = 2)                          as neg,
           count(*) filter (where l.label is null or l.label not in (1, 2)) as neu,
           count(*) filter (where l.label is null)                      as unl,
           count(*) filter (where l.doc_type = 2)                       as posts,
           count(*) filter (where l.doc_type <> 2)                      as comments,
           max(l.created_utc)                                           as newest,
           min(l.created_utc)                                           as oldest
      from lab l join public.subreddits sr on sr.id = l.subreddit_id
     group by sr.name)
  select coalesce(sum(pos), 0)::int       as pos,
         coalesce(sum(neg), 0)::int       as neg,
         coalesce(sum(neu), 0)::int       as neu,
         coalesce(sum(unl), 0)::int       as unl,
         coalesce(sum(posts), 0)::int     as posts,
         coalesce(sum(comments), 0)::int  as comments,
         coalesce(sum(total), 0)::int     as total,
         min(oldest)                      as oldest,
         max(newest)                      as newest,
         coalesce(jsonb_agg(jsonb_build_object(
             'subreddit', subreddit, 'total', total, 'pos', pos, 'neg', neg, 'neu', neu,
             'newest', to_char(newest at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'))
           order by total desc, subreddit), '[]'::jsonb) as subs
    into v_a
    from per_sub;

  if v_a.total = 0 then
    -- A company page with nothing on it is not a page.
    delete from site.rail_key where brand_id = p_brand;
    delete from site.brand_stats where brand_id = p_brand;
    return false;
  end if;

  v_hash := md5(v_b.slug || '|' || v_b.name || '|' || coalesce(v_b.cat_slug, '') || '|' ||
                v_a.pos || '|' || v_a.neg || '|' || v_a.neu || '|' || v_a.unl || '|' ||
                v_a.posts || '|' || v_a.comments || '|' || coalesce(v_a.oldest::text, '') || '|' || v_a.subs::text);

  insert into site.brand_stats as s
         (brand_id, slug, name, primary_category_id, primary_category_slug, pos, neg, neu, unlabelled,
          posts, comments, total_mentions, oldest_mention, newest_mention, subreddit_stats, stats_hash, refreshed_at)
  values (p_brand, v_b.slug, v_b.name, v_b.primary_category_id, v_b.cat_slug, v_a.pos, v_a.neg, v_a.neu, v_a.unl,
          v_a.posts, v_a.comments, v_a.total, v_a.oldest, v_a.newest, v_a.subs, v_hash, now())
  on conflict (brand_id) do update
     set slug = excluded.slug, name = excluded.name,
         primary_category_id = excluded.primary_category_id,
         primary_category_slug = excluded.primary_category_slug,
         pos = excluded.pos, neg = excluded.neg, neu = excluded.neu, unlabelled = excluded.unlabelled,
         posts = excluded.posts, comments = excluded.comments, total_mentions = excluded.total_mentions,
         oldest_mention = excluded.oldest_mention, newest_mention = excluded.newest_mention,
         subreddit_stats = excluded.subreddit_stats, stats_hash = excluded.stats_hash, refreshed_at = now()
   -- an unchanged brand writes nothing: every write is shipped to backup storage and counted as egress
   where s.stats_hash is distinct from excluded.stats_hash
      or s.primary_category_id is distinct from excluded.primary_category_id;

  -- The page's documents: the newest 80 comments (doc_type 1) and 40 posts (doc_type 2). Only the difference
  -- is written: a brand that gained two comments deletes two keys and inserts two.
  with target as (
    (select m.doc_id, m.created_utc, m.doc_type
       from public.mentions m
      where m.brand_id = p_brand and m.doc_type = 1
        and not exists (select 1 from public.mention_rejections x where x.doc_id = m.doc_id and x.brand_id = m.brand_id)
      order by m.created_utc desc, m.doc_id desc
      limit 80)
    union all
    (select m.doc_id, m.created_utc, m.doc_type
       from public.mentions m
      where m.brand_id = p_brand and m.doc_type = 2
        and not exists (select 1 from public.mention_rejections x where x.doc_id = m.doc_id and x.brand_id = m.brand_id)
      order by m.created_utc desc, m.doc_id desc
      limit 40)),
  gone as (
    delete from site.rail_key k
     where k.brand_id = p_brand
       and not exists (select 1 from target t where t.doc_id = k.doc_id and t.created_utc = k.created_utc)
    returning 1)
  insert into site.rail_key (brand_id, doc_id, created_utc, doc_type)
  select p_brand, t.doc_id, t.created_utc, t.doc_type from target t
  on conflict (brand_id, doc_id, created_utc) do nothing;

  -- What the page will actually show (the view drops deleted authors, takedowns and bad permalinks), and a
  -- fingerprint of it: a relabel changes a card without changing which documents are shown.
  select count(*)::int,
         md5(coalesce(string_agg(c.doc_id || ':' || coalesce(c.label::text, '-'), ','
                                 order by c.created_utc desc, c.doc_id desc), ''))
    into v_size, v_rail
    from site.rail_card c
   where c.brand_id = p_brand;

  update site.brand_stats s
     set rail_size = v_size, rail_hash = v_rail
   where s.brand_id = p_brand
     and (s.rail_size is distinct from v_size or s.rail_hash is distinct from v_rail);

  return true;
end;
$$;

-- Refresh up to p_limit dirty brands, oldest mark first. Called in chunks so a run can stop and resume.
create or replace function site.refresh_dirty(p_limit integer default 200) returns integer
language plpgsql security definer set search_path = public, site, pg_temp
set statement_timeout = '30min' as $$
declare
  r record;
  n integer := 0;
begin
  for r in select brand_id from site.dirty_brand order by marked_at, brand_id limit p_limit loop
    perform site.refresh_brand(r.brand_id);
    n := n + 1;
  end loop;
  return n;
end;
$$;

-- ── 5. one row about the whole site ────────────────────────────────────────────────────────────────────────
create table if not exists site.meta (
  only_row            boolean     primary key default true check (only_row),
  last_success_at     timestamptz,          -- the freshness date the site shows
  last_run_id         uuid,
  newest_mention      timestamptz,
  boards_hash         text,                 -- every index page (home + each category) embeds the same boards
  served_boards_hash  text,
  slugs_hash          text,                 -- the set of pages: sitemap and llms.txt
  served_slugs_hash   text,
  updated_at          timestamptz not null default now()
);
insert into site.meta (only_row) values (true) on conflict (only_row) do nothing;

create or replace function site.compute_index_hashes() returns site.meta
language plpgsql security definer set search_path = public, site, pg_temp as $$
declare m site.meta;
begin
  update site.meta
     set boards_hash = (select md5(coalesce(string_agg(
                           slug || '|' || name || '|' || coalesce(primary_category_slug, '') || '|' ||
                           coalesce(page_score::text, '') || '|' || page_n_op || '|' || total_mentions, ','
                           order by slug), '')) from site.brand_stats),
         slugs_hash  = (select md5(coalesce(string_agg(slug, ',' order by slug), '')) from site.brand_stats),
         newest_mention = (select max(newest_mention) from site.brand_stats),
         updated_at = now()
   where only_row
  returning * into m;
  return m;
end;
$$;

-- The takedown ledger's marks, from `removals` alone (the old guard counted `mentions` to get these).
create or replace view site.ledger as
select (select count(*)         from public.removals)                        as removals_rows,
       (select max(detected_at) from public.removals)                        as removals_max,
       (select count(*)         from public.removals where purged_at is null) as removals_pending,
       -- keys that still point at a removed document; hidden by site.rail_card, cleaned by the next refresh
       (select count(*) from site.rail_key k
         where exists (select 1 from public.removals r where r.doc_id = k.doc_id)) as keys_awaiting_cleanup;

create or replace view site.methodology_params as
select version, scope, key, value, rationale, effective_from, git_commit, frozen_at
from public.methodology_params;

-- ── 6. the role the site connects as ───────────────────────────────────────────────────────────────────────
-- Created without a login; ops/site_role.py gives it a password and puts the connection string on Vercel.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'ri_site') then
    create role ri_site nologin;
  end if;
end $$;

-- The functions above run as their owner. Nobody but the owner may call them: the site role must not be
-- able to start a refresh.
revoke all on all functions in schema site from public;

grant usage on schema site to ri_site;
grant select on site.brand_stats, site.rail_card, site.meta, site.ledger, site.methodology_params to ri_site;
-- nothing in public, nothing in published: a corpus read from the site is a permission error
revoke all on schema public from ri_site;
alter role ri_site set statement_timeout = '5s';
alter role ri_site set search_path = site;
