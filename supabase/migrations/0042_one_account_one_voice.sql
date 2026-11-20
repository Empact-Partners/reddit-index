-- One account, one voice (2026-11-20, decision 0044, issue 107).
--
-- The score counted every opinionated mention, so one account posting about a product 170 times counted 170
-- times: PHPRunner ranked #1 on Most Loved from one account, its own author ("Full disclosure: I'm an author of
-- PHPRunner"), and about twenty brands near the top of the board drew most of their mentions from one account.
-- site.refresh_brand now also counts the distinct accounts with an opinion (voice_pos, voice_neg), and
-- worker/site_score.py scores and ranks on those. The tiles (pos, neg, neu, mention counts) are unchanged.
-- Every brand is re-marked dirty so the next refresh fills the two columns.
begin;
alter table site.brand_stats add column if not exists voice_pos integer, add column if not exists voice_neg integer;

CREATE OR REPLACE FUNCTION site.refresh_brand(p_brand bigint)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'site', 'pg_temp'
 SET statement_timeout TO '10min'
 SET plan_cache_mode TO 'force_generic_plan'
AS $function$
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

  -- The newest label per document; label 1 is positive, 2 negative, everything else (neutral, abstain, not
  -- classified yet) is shown as neutral. Left out: documents judged "not this product", and documents in
  -- the takedown ledger.
  with lab as (
    select m.subreddit_id, m.doc_type, m.created_utc, s.label,
           coalesce(nullif(lower(m.author), '[deleted]'), 'doc:' || m.doc_id) as voice
      from public.mentions m
      left join lateral (
        select ms.label from public.mention_sentiment ms
         where ms.doc_id = m.doc_id and ms.brand_id = m.brand_id
         order by ms.scored_at desc nulls last, ms.model_version desc
         limit 1) s on true
     where m.brand_id = p_brand
       and not exists (select 1 from public.mention_rejections x
                        where x.doc_id = m.doc_id and x.brand_id = m.brand_id)
       and not exists (select 1 from public.removals r where r.doc_id = m.doc_id)),
  -- One account, one voice (decision 0044, issue 107): an account's opinionated mentions of this brand count
  -- once, as positive when most of them are positive and negative when most are negative (a tie counts neither).
  -- A mention whose author is gone counts as its own voice.
  voices as (
    select l.voice,
           count(*) filter (where l.label = 1) as p,
           count(*) filter (where l.label = 2) as n
      from lab l
     where l.label in (1, 2)
     group by l.voice),
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
         (select count(*) from voices v where v.p > v.n)::int as voice_pos,
         (select count(*) from voices v where v.n > v.p)::int as voice_neg,
         min(oldest)                      as oldest,
         max(newest)                      as newest,
         coalesce(jsonb_agg(jsonb_build_object(
             'subreddit', subreddit, 'total', total, 'pos', pos, 'neg', neg, 'neu', neu,
             'newest', to_char(newest at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'))
           order by total desc, subreddit), '[]'::jsonb) as subs
    into v_a
    from per_sub;

  if v_a.total = 0 then
    delete from site.rail_key where brand_id = p_brand;
    delete from site.brand_stats where brand_id = p_brand;
    return false;
  end if;

  v_hash := md5(v_b.slug || '|' || v_b.name || '|' || coalesce(v_b.cat_slug, '') || '|' ||
                v_a.pos || '|' || v_a.neg || '|' || v_a.neu || '|' || v_a.unl || '|' ||
                v_a.posts || '|' || v_a.comments || '|' || coalesce(v_a.oldest::text, '') || '|' || v_a.subs::text || '|' ||
                v_a.voice_pos || '|' || v_a.voice_neg);

  insert into site.brand_stats as s
         (brand_id, slug, name, primary_category_id, primary_category_slug, pos, neg, neu, unlabelled,
          posts, comments, total_mentions, oldest_mention, newest_mention, subreddit_stats, stats_hash, refreshed_at,
          voice_pos, voice_neg)
  values (p_brand, v_b.slug, v_b.name, v_b.primary_category_id, v_b.cat_slug, v_a.pos, v_a.neg, v_a.neu, v_a.unl,
          v_a.posts, v_a.comments, v_a.total, v_a.oldest, v_a.newest, v_a.subs, v_hash, now(),
          v_a.voice_pos, v_a.voice_neg)
  on conflict (brand_id) do update
     set slug = excluded.slug, name = excluded.name,
         primary_category_id = excluded.primary_category_id,
         primary_category_slug = excluded.primary_category_slug,
         pos = excluded.pos, neg = excluded.neg, neu = excluded.neu, unlabelled = excluded.unlabelled,
         posts = excluded.posts, comments = excluded.comments, total_mentions = excluded.total_mentions,
         oldest_mention = excluded.oldest_mention, newest_mention = excluded.newest_mention,
         subreddit_stats = excluded.subreddit_stats, stats_hash = excluded.stats_hash, refreshed_at = now(),
         voice_pos = excluded.voice_pos, voice_neg = excluded.voice_neg
   where s.stats_hash is distinct from excluded.stats_hash
      or s.voice_pos is distinct from excluded.voice_pos
      or s.primary_category_id is distinct from excluded.primary_category_id;

  -- The page's documents: the newest 80 comments (doc_type 1) and 40 posts (doc_type 2). Only the difference
  -- is written.
  with target as (
    (select m.doc_id, m.created_utc, m.doc_type
       from public.mentions m
      where m.brand_id = p_brand and m.doc_type = 1
        and not exists (select 1 from public.mention_rejections x where x.doc_id = m.doc_id and x.brand_id = m.brand_id)
        and not exists (select 1 from public.removals r where r.doc_id = m.doc_id)
      order by m.created_utc desc, m.doc_id desc
      limit 80)
    union all
    (select m.doc_id, m.created_utc, m.doc_type
       from public.mentions m
      where m.brand_id = p_brand and m.doc_type = 2
        and not exists (select 1 from public.mention_rejections x where x.doc_id = m.doc_id and x.brand_id = m.brand_id)
        and not exists (select 1 from public.removals r where r.doc_id = m.doc_id)
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
$function$
;
insert into site.dirty_brand (brand_id) select brand_id from site.brand_stats on conflict do nothing;
commit;
