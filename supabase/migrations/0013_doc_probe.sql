-- 0013 — what the takedown check needs: find a document's rows fast, and remember when it was last checked.
--
-- 1. An index on mentions(doc_id). There was none: delete-sync's `delete from mentions where doc_id in (...)`
--    read every partition. A document can be stored under several brands, so the purge needs all of them.
--
-- 2. public.doc_probe: one narrow row per document, when Reddit was last asked about it. The old script
--    stamped mentions.delete_checked_at instead: that column is indexed on every partition, so each stamp
--    rewrote a wide row and seven index entries, and all of it is shipped to backup storage and counted as
--    egress. (The column and its index existed in the database and in no migration; this file is where they
--    are finally written down. They are left in place and no longer written.)
--
-- 3. Every document on a page is checked every night without needing this table. The table drives the slow
--    lap through everything else.

create index if not exists mentions_doc_id_idx on public.mentions (doc_id);

-- recorded here because it was created by hand on 2026-08-17 and never in a migration
alter table public.mentions add column if not exists delete_checked_at timestamptz;

create table if not exists public.doc_probe (
  doc_id     text        primary key,
  checked_at timestamptz             -- null: never checked
);
alter table public.doc_probe enable row level security;
create index if not exists doc_probe_checked_at on public.doc_probe (checked_at nulls first);

insert into public.doc_probe (doc_id, checked_at)
select m.doc_id, max(m.delete_checked_at)
  from public.mentions m
 group by m.doc_id
on conflict (doc_id) do nothing;

create or replace function public.note_doc() returns trigger
language plpgsql as $$
begin
  insert into public.doc_probe (doc_id) values (new.doc_id) on conflict (doc_id) do nothing;
  return new;
end;
$$;

drop trigger if exists mentions_note_doc on public.mentions;
create trigger mentions_note_doc after insert on public.mentions
  for each row execute function public.note_doc();
