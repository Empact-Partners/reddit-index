-- 0014 — four holes an independent review found in the takedown chain of 0007 to 0011 (2026-10-02).
--
-- 1. A page can be in the site's cache without ever having been fetched by the publisher: a visitor opens it,
--    and the publisher proves only a sample. 0010 recorded a retired page only when served_hash was set, so
--    a visited-but-unproven page of a brand that was then pulled would never be expired. Every page that
--    stops existing is now recorded, and the publisher must see it answer 404.
-- 2. A slug rename updates the row in place, so the OLD path was never retired. (Slugs are frozen by the
--    trigger on `brands`; this closes the path anyway.)
-- 3. A takedown marked brands dirty only on INSERT and only through removals.brand_ids. It now fires on
--    INSERT or UPDATE and also finds the brands from the mentions and the page keys that hold the document.
-- 4. The site's role could still EXECUTE public.refresh_mention_rail(), a SECURITY DEFINER function that
--    rebuilds a 230 MB materialised view. Functions are executable by PUBLIC unless revoked.

create or replace function site.note_retired() returns trigger
language plpgsql security definer set search_path = site, pg_temp as $$
begin
  if tg_op = 'DELETE' then
    insert into site.retired_page (slug) values (old.slug)
    on conflict (slug) do update set retired_at = now(), gone_at = null;
    return old;
  end if;
  if tg_op = 'UPDATE' then
    if old.slug is distinct from new.slug then
      insert into site.retired_page (slug) values (old.slug)
      on conflict (slug) do update set retired_at = now(), gone_at = null;
    end if;
  end if;
  -- the brand came back (or a new brand took the slug): it is a page again
  delete from site.retired_page where slug = new.slug;
  return new;
end;
$$;

drop trigger if exists site_retired on site.brand_stats;
create trigger site_retired after insert or delete or update of slug on site.brand_stats
  for each row execute function site.note_retired();

create or replace function site.mark_dirty_removal() returns trigger
language plpgsql security definer set search_path = public, site, pg_temp as $$
begin
  insert into site.dirty_brand (brand_id)
  select b from (
    select unnest(coalesce(new.brand_ids, '{}'::bigint[])) as b
    union select m.brand_id from public.mentions m where m.doc_id = new.doc_id
    union select k.brand_id from site.rail_key k where k.doc_id = new.doc_id) x
  where b is not null
  on conflict (brand_id) do nothing;
  return new;
end;
$$;

drop trigger if exists site_dirty on public.removals;
create trigger site_dirty after insert or update on public.removals
  for each row execute function site.mark_dirty_removal();

revoke execute on function public.refresh_mention_rail(boolean) from public;
alter default privileges in schema public revoke execute on functions from public;
revoke all on all functions in schema site from public;
