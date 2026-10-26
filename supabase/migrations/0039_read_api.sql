-- The read API (decision 0040, 2026-10-26): GET /api/v1/threads and GET /api/v1/brands on redditindex.com.
--
-- Vlad promised it to Heather at the Reddit weekly jam of 5 Oct: the team pulls a partner's negative threads into
-- the partner's GitHub repo instead of reading them off the page. The site's own role (`ri_site`, 0007) reads
-- schema `site` only, and that must stay true, so the API gets its own role and its own schema:
--
--   api.api_keys     one row per key: the sha256 of the key, never the key. Revoked by a timestamp, never deleted.
--   api.threads()    one brand's mentions with a sentiment, newest 20,000 of the window considered, at most 500
--                    returned, each with a 280-character excerpt cut inside Postgres: the body never leaves it.
--   api.brands()     the slugs, from the precomputed site.brand_stats counts.
--   ri_api           EXECUTE on those two functions and nothing else. Both check the key themselves, so the
--                    role's password alone reads nothing: a caller also needs a key's hash, which only the
--                    functions can see.
--
-- THE EGRESS LINE (README "Cost"): 2 GB a day for every job together. One call returns at most 500 rows of about
-- 0.8 kB (about 0.4 MB) and a key makes at most 300 calls a UTC day (about 0.12 GB at the very worst); a real pull
-- of one partner is one or two calls of a few kilobytes.

set lock_timeout = '5s';

create schema if not exists api;
revoke all on schema api from public;

create table if not exists api.api_keys (
  id            text        primary key,                -- kid_xxxxxxxx: shown and printed, not a secret
  name          text        not null,                   -- who holds it: "heather"
  key_hash      text        not null unique check (key_hash ~ '^[0-9a-f]{64}$'),   -- sha256 hex of the key
  created_at    timestamptz not null default now(),
  last_used_at  timestamptz,
  revoked_at    timestamptz,                             -- set by ops/api_keys.py revoke; a revoked key never returns
  day           date,                                    -- the UTC day day_calls counts
  day_calls     integer     not null default 0
);
alter table api.api_keys enable row level security;    -- no policy: only the owner (postgres) reads or writes

-- ── the key check, inside every call ────────────────────────────────────────────────────────────────────────────
-- 'ok', 'unauthorized' (unknown, malformed or revoked) or 'rate_limited' (past 300 calls this UTC day). A call
-- with a good key is counted and stamps last_used_at whatever it then returns.
create or replace function api._use_key(p_key_hash text) returns text
language plpgsql security definer set search_path = pg_catalog, public as $$
declare
  today date := (now() at time zone 'utc')::date;
  calls integer;
begin
  if p_key_hash is null or p_key_hash !~ '^[0-9a-f]{64}$' then
    return 'unauthorized';
  end if;
  update api.api_keys
     set last_used_at = now(),
         day_calls = case when day = today then day_calls + 1 else 1 end,
         day = today
   where key_hash = p_key_hash and revoked_at is null
  returning day_calls into calls;
  if not found then
    return 'unauthorized';
  end if;
  if calls > 300 then
    return 'rate_limited';
  end if;
  return 'ok';
end $$;

-- A stored permalink is a path or a full URL; the API always gives a full URL.
create or replace function api._reddit_url(p text) returns text
language sql immutable set search_path = pg_catalog as $$
  select case when p is null then null when p ~ '^https?://' then p else 'https://www.reddit.com' || p end
$$;

-- ── GET /api/v1/threads ────────────────────────────────────────────────────────────────────────────────────────
-- Order: negative first, then the Reddit score (the index stores no citation weight; the score is the weight it
-- has), then newest, then doc_id, all descending, so the cursor is the last row's four values and a page is
-- "everything after it in that order". The sentiment is the newest label per mention, the same rule as
-- published.mentions and site.rail_card (0003). Rows the site would not show are not returned either: a deleted
-- author, a document in public.removals.
--
-- Bounded work: the brand's newest 20,000 mentions in the window are the candidates (every partner brand has
-- fewer than 1,100; github has 137,000 and takes 39 s to label in full). `complete` says whether the window held
-- more; a caller narrows it with p_since.
create or replace function api.threads(
  p_key_hash      text,
  p_brand         text,
  p_sentiment     text        default 'negative',
  p_since         timestamptz default null,
  p_limit         integer     default 100,
  p_after_rank    integer     default null,
  p_after_score   integer     default null,
  p_after_created timestamptz default null,
  p_after_doc     text        default null
) returns json
language plpgsql security definer set search_path = pg_catalog, public as $$
declare
  auth      text := api._use_key(p_key_hash);
  b         record;
  want      smallint;
  lim       integer := least(greatest(coalesce(p_limit, 100), 1), 500);
  cap       constant integer := 20000;
  scanned   integer;
  more      boolean;
  rows_json json;
  last_row  json;
begin
  if auth <> 'ok' then
    return json_build_object('error', auth);
  end if;
  if p_sentiment is null or p_sentiment not in ('negative', 'neutral', 'positive', 'all') then
    return json_build_object('error', 'bad_sentiment');
  end if;
  if p_after_rank is not null and (p_after_score is null or p_after_created is null or p_after_doc is null) then
    return json_build_object('error', 'bad_cursor');
  end if;
  select id, slug, name into b from public.brands where slug = p_brand and status = 'published';
  if not found then
    return json_build_object('error', 'unknown_brand');
  end if;
  want := case p_sentiment when 'negative' then 2 when 'positive' then 1 when 'neutral' then 0 end;

  with scan as (
    -- the brand's newest mentions in the window, one more than the cap so `complete` can be told
    select m.doc_id, m.created_utc, m.doc_type, m.thread_id, m.subreddit_id, m.author, m.permalink, m.score,
           m.matched_form, m.body, m.body_from,
           row_number() over (order by m.created_utc desc) as rn
      from public.mentions m
     where m.brand_id = b.id
       and m.created_utc >= coalesce(p_since, '-infinity'::timestamptz)
     order by m.created_utc desc
     limit cap + 1
  ), candidates as (
    select s.*, l.label,
           case when l.label = 2 then 1 else 0 end as rk,
           coalesce(s.score, 0) as w
      from scan s
      left join lateral (
        select ms.label from public.mention_sentiment ms
         where ms.doc_id = s.doc_id and ms.brand_id = b.id
         order by ms.scored_at desc nulls last, ms.model_version desc
         limit 1) l on true
     where s.rn <= cap
  ), hits as (
    -- one more than the page, so `next` is given only when a row follows
    select c.* from candidates c
     where (want is null or c.label = want)
       and c.author <> '[deleted]'
       and not exists (select 1 from public.removals r where r.doc_id = c.doc_id)
       and (p_after_rank is null
            or (c.rk, c.w, c.created_utc, c.doc_id) < (p_after_rank, p_after_score, p_after_created, p_after_doc))
     order by c.rk desc, c.w desc, c.created_utc desc, c.doc_id desc
     limit lim + 1
  ), numbered as (
    select h.*, row_number() over (order by h.rk desc, h.w desc, h.created_utc desc, h.doc_id desc) as pos
      from hits h
  ), shown as (
    -- the text of a comment is stored once (0019): a row without it points at the row that holds it
    select n.*,
           btrim(regexp_replace(coalesce(n.body,
             (select k.body from public.mentions k
               where k.doc_id = n.doc_id and k.created_utc = n.created_utc and k.brand_id = n.body_from)),
             '\s+', ' ', 'g')) as txt
      from numbered n
     where n.pos <= lim
  ), cut as (
    -- the excerpt opens up to 80 characters before the brand's name and runs 280 characters, word for word
    select s.*, greatest(1, strpos(lower(s.txt), lower(s.matched_form)) - 80) as st from shown s
  )
  select (select count(*)::int from scan),
         (select count(*) from hits) > lim,
         (select coalesce(json_agg(json_build_object(
                   'doc_id', c.doc_id,
                   'brand', b.slug,
                   'sentiment', case c.label when 2 then 'negative' when 1 then 'positive' when 0 then 'neutral'
                                             when 3 then 'abstain' else 'unlabelled' end,
                   'subreddit', sr.name,
                   'thread_url', api._reddit_url(coalesce(t.permalink,
                                   substring(c.permalink from '^(?:https://www\.reddit\.com)?(/r/[^/]+/comments/[^/]+/[^/]*/?)'))),
                   'thread_title', t.link_title,
                   'doc_type', case when c.doc_type = 2 then 'post' else 'comment' end,
                   'permalink', api._reddit_url(c.permalink),
                   'excerpt', case when c.st > 1 then '…' else '' end
                              || substr(c.txt, c.st, 280)
                              || case when length(c.txt) >= c.st + 280 then '…' else '' end,
                   'reddit_score', c.score,
                   'posted_at', c.created_utc) order by c.pos), '[]'::json)
            from cut c
            left join public.subreddits sr on sr.id = c.subreddit_id
            left join public.threads t on t.id = c.thread_id),
         (select json_build_object('rank', c2.rk, 'score', c2.w, 'created', c2.created_utc, 'doc', c2.doc_id)
            from cut c2 where c2.pos = lim)
    into scanned, more, rows_json, last_row;

  return json_build_object(
    'brand', json_build_object('slug', b.slug, 'name', b.name),
    'sentiment', p_sentiment,
    'since', p_since,
    'limit', lim,
    'rows', rows_json,
    'next', case when more then last_row end,
    'scanned', least(scanned, cap),
    'complete', scanned <= cap);
end $$;

-- ── GET /api/v1/brands ─────────────────────────────────────────────────────────────────────────────────────────
-- Every published brand, with the counts the site already computed (site.brand_stats; null for a brand with no
-- page yet). p_q narrows it to slugs or names containing the text. About 0.7 MB unnarrowed.
create or replace function api.brands(p_key_hash text, p_q text default null) returns json
language plpgsql security definer set search_path = pg_catalog, public as $$
declare
  auth text := api._use_key(p_key_hash);
  q    text := nullif(lower(btrim(coalesce(p_q, ''))), '');
  out  json;
begin
  if auth <> 'ok' then
    return json_build_object('error', auth);
  end if;
  select coalesce(json_agg(json_build_object(
           'slug', b.slug, 'name', b.name, 'mentions', s.total_mentions, 'negative', s.neg) order by b.slug), '[]'::json)
    into out
    from public.brands b
    left join site.brand_stats s on s.brand_id = b.id
   where b.status = 'published'
     and (q is null or strpos(b.slug, q) > 0 or strpos(lower(b.name), q) > 0);
  return json_build_object('brands', out);
end $$;

-- ── the role the API connects as ───────────────────────────────────────────────────────────────────────────────
-- Created without a login; ops/api_role.py gives it a password and puts the connection string on Vercel.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'ri_api') then
    create role ri_api nologin;
  end if;
end $$;

revoke all on all functions in schema api from public, anon, authenticated, service_role;
revoke all on all tables in schema api from public, anon, authenticated, service_role;
grant usage on schema api to ri_api;
grant execute on function api.threads(text, text, text, timestamptz, integer, integer, integer, timestamptz, text) to ri_api;
grant execute on function api.brands(text, text) to ri_api;
revoke all on schema public from ri_api;
revoke all on schema site from ri_api;
alter role ri_api set statement_timeout = '15s';
alter role ri_api set search_path = api;
