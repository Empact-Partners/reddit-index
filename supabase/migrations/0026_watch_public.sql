-- The organic mentions the Reddit mentions tracker found, shown on the company page (decision 0020, 2026-10-06).
--
-- Vlad, 2026-10-06, on keeping the tracker's mentions off the public pages: "nothing private, all public". So every
-- organic mention on the Empact Ops board (watch.organic_mentions, 0024) is shown on its company's page, in its own
-- section, marked as what it is: found by a closer, real-time watch, read by a different method, and counted in
-- nothing (not the score, the totals, the subreddit table or the rank). The index's own collection stays the only
-- thing any number is computed from (tracker D5, 0018, 0019).
--
-- The same legal rules as every other card (01-legal.md, decision 0002): username, permalink and "from Reddit" on
-- each; checked against Reddit by the nightly takedown with the cards in the counted section; a document deleted,
-- removed or edited on Reddit is ledgered in public.removals and gone from the page; a ledgered document is never
-- shown again. A page with no watch cards keeps exactly the fingerprint it had.

-- ── 1. what a card needs, on the mirror ────────────────────────────────────────────────────────────────────────
alter table watch.organic_mentions
  add column if not exists author       text,
  add column if not exists body         text,
  add column if not exists thread_title text,
  add column if not exists score        integer,
  add column if not exists matched_form text,
  add column if not exists public       boolean not null default false,   -- on the board and not "not about them"
  add column if not exists purged_at    timestamptz;                      -- gone on Reddit: body dropped, never shown

-- ── 2. the cards a page shows ──────────────────────────────────────────────────────────────────────────────────
create table if not exists site.watch_card (
  brand_id     bigint      not null,
  doc_id       text        not null,
  created_utc  timestamptz not null,
  doc_type     smallint    not null,              -- 1 comment, 2 post (public.mentions' codes)
  subreddit    text        not null,
  author       text        not null,
  permalink    text        not null,
  thread_title text,
  body         text        not null,
  score        integer,
  sentiment    text,                              -- the tracker's reading (Claude), not the index's labels
  matched_form text,
  stored_at    timestamptz not null,              -- when the tracker stored it: the takedown's "edited after" line
  primary key (brand_id, doc_id)
);
create index if not exists watch_card_doc on site.watch_card (doc_id);

-- What the site reads: the cards, never a ledgered document (as site.rail_card hides a key awaiting cleanup).
create or replace view site.watch_shown as
select w.*, bs.slug as brand_slug
  from site.watch_card w
  join site.brand_stats bs on bs.brand_id = w.brand_id
 where not exists (select 1 from public.removals r where r.doc_id = w.doc_id);

-- The companies watched, for the disclosure on /methodology (01-legal.md 4.1: partners disclosed).
create table if not exists site.watched_brand (
  brand_id  bigint primary key,
  slug      text   not null,
  name      text   not null,
  since     date   not null default current_date
);

alter table site.brand_stats
  add column if not exists watch_size integer not null default 0,
  add column if not exists watch_hash text    not null default '';
-- A page with no watch cards hashes exactly as before: no page is re-rendered by this migration.
alter table site.brand_stats alter column page_hash set expression as (
  md5(stats_hash || '|' || rail_hash || '|' || coalesce(page_score::text, '') || '|' ||
      coalesce(board_rank::text, '') || '|' || board_size::text ||
      case when watch_hash <> '' then '|' || watch_hash else '' end));

-- ── 3. rebuilding one company's watch cards ────────────────────────────────────────────────────────────────────
create or replace function site.refresh_watch(p_brand bigint) returns integer
language plpgsql security definer set search_path = public, site, watch, pg_temp
set statement_timeout = '2min' as $$
declare
  v_b    record;
  v_size integer;
  v_hash text;
begin
  select b.id, b.slug, b.name, b.status, c.slug as cat_slug, b.primary_category_id
    into v_b
    from public.brands b
    left join public.categories c on c.id = b.primary_category_id and c.status in ('published', 'unrankable')
   where b.id = p_brand;

  delete from site.watch_card where brand_id = p_brand;
  if v_b.id is not null and v_b.status = 'published' then
    insert into site.watch_card (brand_id, doc_id, created_utc, doc_type, subreddit, author, permalink, thread_title,
                                 body, score, sentiment, matched_form, stored_at)
    select o.brand_id, o.reddit_id, o.written_at, case when o.doc_type = 'post' then 2 else 1 end, o.subreddit,
           o.author, o.url, case when o.doc_type = 'post' then null else o.thread_title end, o.body, o.score,
           o.sentiment, o.matched_form, coalesce(o.found_at, o.mirrored_at)
      from watch.organic_mentions o
     where o.brand_id = p_brand
       and o.public and o.purged_at is null
       and o.body is not null and o.body <> '' and o.author is not null and o.author not in ('[deleted]', '')
       and o.written_at is not null and o.subreddit is not null
       and o.url ~ '^https://www\.reddit\.com/r/[A-Za-z0-9_]+/comments/[a-z0-9]+/'
       and not exists (select 1 from public.removals r where r.doc_id = o.reddit_id)
       -- counted already: a document the index's own collection holds for this company is in the counted section
       and not exists (select 1 from public.mentions m where m.brand_id = p_brand and m.doc_id = o.reddit_id)
     order by o.written_at desc, o.reddit_id
     limit 60;
  end if;

  select count(*)::int,
         coalesce(md5(string_agg(doc_id || ':' || coalesce(score::text, '') || ':' || coalesce(sentiment, '') || ':' ||
                                 md5(body), ',' order by created_utc desc, doc_id)), '')
    into v_size, v_hash
    from site.watch_card where brand_id = p_brand;
  if v_size = 0 then
    v_hash := '';
  end if;

  -- a company the index has not collected yet still gets its page when it has watch cards (all public)
  if v_size > 0 and not exists (select 1 from site.brand_stats where brand_id = p_brand) then
    insert into site.brand_stats (brand_id, slug, name, primary_category_id, primary_category_slug, stats_hash)
    values (p_brand, v_b.slug, v_b.name, v_b.primary_category_id, v_b.cat_slug, md5(v_b.slug || '|' || v_b.name || '|watch-only'));
  elsif v_size = 0 then
    delete from site.brand_stats where brand_id = p_brand and total_mentions = 0;
  end if;

  update site.brand_stats
     set watch_size = v_size, watch_hash = v_hash
   where brand_id = p_brand and (watch_size is distinct from v_size or watch_hash is distinct from v_hash);
  return v_size;
end;
$$;

-- Every refresh of a company also rebuilds its watch cards (refresh_brand drops a row with no counted mention;
-- refresh_watch puts it back when the company has watch cards).
create or replace function site.refresh_dirty(p_limit integer default 200) returns integer
language plpgsql security definer set search_path = public, site, pg_temp
set statement_timeout = '30min' as $$
declare
  r record;
  n integer := 0;
begin
  for r in select brand_id from site.dirty_brand order by marked_at, brand_id limit p_limit loop
    perform site.refresh_brand(r.brand_id);
    perform site.refresh_watch(r.brand_id);
    n := n + 1;
  end loop;
  return n;
end;
$$;

-- ── 4. the takedown for watch cards ────────────────────────────────────────────────────────────────────────────
-- worker/takedown.py checks every watch card with the counted ones; what came back gone or edited lands here, in
-- one transaction: the ledger (which marks the brands dirty, so their pages are rebuilt and re-proven), the body
-- dropped from the mirror, the card deleted.
create or replace function site.purge_watch(p_ids text[], p_reasons text[]) returns integer
language plpgsql security definer set search_path = public, site, watch, pg_temp as $$
declare
  n integer;
begin
  insert into public.removals (doc_id, doc_type, brand_ids, reason, detected_at, purged_at)
  select o.reddit_id, min(case when o.doc_type = 'post' then 2 else 1 end), array_agg(distinct o.brand_id), v.reason,
         now(), now()
    from unnest(p_ids, p_reasons) as v(doc_id, reason)
    join watch.organic_mentions o on o.reddit_id = v.doc_id and o.brand_id is not null
   group by o.reddit_id, v.reason
  on conflict (doc_id) do update set purged_at = coalesce(public.removals.purged_at, now());
  insert into site.dirty_brand (brand_id)
  select distinct brand_id from site.watch_card where doc_id = any (p_ids)
  on conflict (brand_id) do nothing;
  update watch.organic_mentions set body = null, public = false, purged_at = now() where reddit_id = any (p_ids);
  delete from site.watch_card where doc_id = any (p_ids);
  get diagnostics n = row_count;
  return n;
end;
$$;

revoke all on function site.refresh_watch(bigint), site.purge_watch(text[], text[]) from public;
grant execute on function site.refresh_watch(bigint), site.purge_watch(text[], text[]), site.refresh_dirty(integer) to ri_sweep;
grant select on site.watch_shown, site.watched_brand to ri_site;
grant select, insert, update, delete on site.watch_card, site.watched_brand to ri_sweep;
