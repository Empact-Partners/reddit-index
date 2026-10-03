-- One copy of each comment's text (docs/retention.md, step 3).
--
-- A comment that names three brands was stored three times: one mention row per brand, each with the whole body.
-- Measured 2026-10-02: 1,965 MB of mention text, of which one copy per comment is 828 MB. From this migration on,
-- the text lives on one of a comment's rows and the others carry NULL; readers take it from that row.
--
-- Every row of a comment has the same created_utc (it is the comment's own timestamp), so the lookup names the
-- partition and costs one index probe (public.mentions (doc_id), migration 0013).
--
-- Which copy: a cleared row records, in body_from, the brand id of the row that holds ITS text. A comment
-- edited between two brands' collections can hold two different texts, so a row is cleared only when its text
-- EQUALS the holder's, and readers follow the pointer, never "any row with text": each reader returns exactly
-- what it returned before. A holder that is deleted (retention) first copies its text back to the rows that
-- point at it; a takedown deletes every row of the comment at once.
--
-- What reads mention text, and how each keeps returning exactly what it returned before:
--   published.mentions   the lookup job's view: same columns, same rows, body coalesced from the comment's row
--   site.rail_card       the site's cards: the same
--   mention_rail_mv      the old site's materialised view: not refreshed any more, dropped at step 4
--   worker/classify_sweep.py and scripts that read text: coalesce the same way (changed in the same commit)
--
-- This migration changes no stored text. ops/retention.py clears the duplicates, one monthly partition at a time,
-- inside the budget docs/retention.md declares, checking the views' output before and after.

alter table public.mentions add column if not exists body_from bigint;

create or replace view published.mentions as
 select m.brand_id,
    m.doc_id,
    m.doc_type,
    m.thread_id,
    m.subreddit_id,
    m.author,
    m.created_utc,
    m.permalink,
    m.score,
    coalesce(m.body, (select k.body from public.mentions k
                       where k.doc_id = m.doc_id and k.created_utc = m.created_utc and k.brand_id = m.body_from)) as body,
    m.matched_form,
    s.label,
    s.intensity,
    s.stage
   from public.mentions m
     join public.brands b on b.id = m.brand_id and b.status = 'published'::text
     left join lateral ( select ms.label, ms.intensity, ms.stage
           from public.mention_sentiment ms
          where ms.doc_id = m.doc_id and ms.brand_id = m.brand_id
          order by ms.scored_at desc nulls last, ms.model_version desc
         limit 1) s on true;

create or replace view site.rail_card as
 select k.brand_id,
    bs.slug as brand_slug,
    bs.name as brand_name,
    sr.name as subreddit,
    m.doc_id,
    m.doc_type,
    m.thread_id,
    m.author,
    m.created_utc,
    m.permalink,
    coalesce(m.body, (select x.body from public.mentions x
                       where x.doc_id = m.doc_id and x.created_utc = m.created_utc and x.brand_id = m.body_from)) as body,
    m.matched_form,
    s.label,
        case
            when m.doc_type = 2 then null::text
            else t.link_title
        end as thread_title
   from site.rail_key k
     join site.brand_stats bs on bs.brand_id = k.brand_id
     cross join lateral ( select mm.doc_id, mm.doc_type, mm.thread_id, mm.subreddit_id, mm.author, mm.created_utc,
            mm.permalink, mm.body, mm.body_from, mm.matched_form, mm.brand_id
           from public.mentions mm
          where mm.brand_id = k.brand_id and mm.doc_id = k.doc_id and mm.created_utc = k.created_utc
         limit 1) m
     join public.subreddits sr on sr.id = m.subreddit_id
     left join public.threads t on t.id = m.thread_id
     left join lateral ( select ms.label
           from public.mention_sentiment ms
          where ms.doc_id = m.doc_id and ms.brand_id = m.brand_id
          order by ms.scored_at desc nulls last, ms.model_version desc
         limit 1) s on true
  where m.author <> '[deleted]'::text
    and not (exists ( select 1 from public.removals r where r.doc_id = m.doc_id))
    and m.permalink ~ '^(https://www\.reddit\.com)?/r/[A-Za-z0-9_]+/comments/[a-z0-9]+'::text;

-- New rows: a brand row whose text is already stored, word for word, on another row of the comment points at it.
create or replace function public.mentions_one_copy() returns trigger
language plpgsql set search_path = public as $$
declare holder bigint;
begin
  if new.body is not null then
    select m.brand_id into holder from public.mentions m
     where m.doc_id = new.doc_id and m.created_utc = new.created_utc and m.body = new.body
     order by m.brand_id limit 1;
    if holder is not null then
      new.body := null;
      new.body_from := holder;
    end if;
  end if;
  return new;
end $$;

drop trigger if exists mentions_one_copy on public.mentions;
create trigger mentions_one_copy before insert on public.mentions
  for each row execute function public.mentions_one_copy();
revoke execute on function public.mentions_one_copy() from public;
