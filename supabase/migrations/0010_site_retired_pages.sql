-- 0010 — remember a page that stopped existing, until the site has been seen to stop serving it.
--
-- site.refresh_brand deletes a company's row when the brand is unpublished or its last mention is purged.
-- The page is still in the site's cache at that moment. Without a record of it, nothing would ever expire
-- that path, and a company pulled for a legal reason would keep its page. The publisher expires every path
-- listed here, fetches it, and stamps gone_at only when the site answers 404.
create table if not exists site.retired_page (
  slug        text        primary key,
  retired_at  timestamptz not null default now(),
  gone_at     timestamptz            -- set only after the live site returned 404 for the path
);

create or replace function site.note_retired() returns trigger
language plpgsql security definer set search_path = site, pg_temp as $$
begin
  if tg_op = 'DELETE' then
    -- a page nobody was ever served needs no proof that it is gone
    if old.served_hash is not null then
      insert into site.retired_page (slug) values (old.slug)
      on conflict (slug) do update set retired_at = now(), gone_at = null;
    end if;
    return old;
  end if;
  -- the brand came back (or a new brand took the slug): it is a page again
  delete from site.retired_page where slug = new.slug;
  return new;
end;
$$;

drop trigger if exists site_retired on site.brand_stats;
create trigger site_retired after insert or delete on site.brand_stats
  for each row execute function site.note_retired();

revoke all on all functions in schema site from public;
