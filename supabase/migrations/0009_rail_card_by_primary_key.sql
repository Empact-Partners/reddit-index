-- 0009 — site.rail_card looks each card up by primary key, always.
--
-- 0007 joined rail_key to mentions and let the planner choose. It chose to read EVERY mention of the brand and
-- hash-join the 120 keys against them: fine for a brand with 900 mentions, 26 seconds of disk reads for the
-- brand "reddit" with 146,580, and the first fill died on a chunk of such brands at the 2 minute statement
-- timeout. The site role's timeout is 5 seconds, so the same plan would also have failed the largest pages.
--
-- A LATERAL subquery with LIMIT 1 cannot be flattened into a join, so it runs once per key as an index probe
-- on the mentions primary key (brand_id, doc_id, created_utc), pruned to the one monthly partition the key's
-- timestamp falls in. 120 probes a page, whatever the brand's size. Same columns, same rows.
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
cross join lateral (
  select mm.doc_id, mm.doc_type, mm.thread_id, mm.subreddit_id, mm.author, mm.created_utc, mm.permalink,
         mm.body, mm.matched_form, mm.brand_id
    from public.mentions mm
   where mm.brand_id = k.brand_id and mm.doc_id = k.doc_id and mm.created_utc = k.created_utc
   limit 1) m
join public.subreddits sr on sr.id = m.subreddit_id
left join public.threads t on t.id = m.thread_id
left join lateral (
  select ms.label from public.mention_sentiment ms
   where ms.doc_id = m.doc_id and ms.brand_id = m.brand_id
   order by ms.scored_at desc nulls last, ms.model_version desc
   limit 1) s on true
where m.author <> '[deleted]'
  and not exists (select 1 from public.removals r where r.doc_id = m.doc_id)
  and m.permalink ~ '^(https://www\.reddit\.com)?/r/[A-Za-z0-9_]+/comments/[a-z0-9]+';
