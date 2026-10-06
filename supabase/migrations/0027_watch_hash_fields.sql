-- 0026's watch fingerprint covers every field a card renders (Codex review of decision 0020, 2026-10-06): a changed
-- author, permalink, subreddit, title, form, type or time now changes the page's fingerprint, so the publisher re-renders it.
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

  -- every field a card renders, unambiguously joined (unit and record separators), in the page's order
  select count(*)::int,
         coalesce(md5(string_agg(concat_ws(chr(31), doc_id, created_utc::text, doc_type::text, subreddit, author, permalink,
                                           coalesce(thread_title, ''), md5(body), coalesce(sentiment, ''),
                                           coalesce(matched_form, '')),
                                 chr(30) order by created_utc desc, doc_id)), '')
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

