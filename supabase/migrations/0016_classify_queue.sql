-- 0016 — the mentions waiting for a sentiment label, as a queue.
--
-- Until now "unclassified" was computed: a mention with no mention_sentiment row. Finding the next batch
-- meant an anti-join over 1.4 million rows each time, and a mention the classifier had judged "not this
-- product" was never written down, so it looked unclassified forever and was paid for again on every pass.
-- The queue holds exactly what is waiting; a verdict (a label, or a rejection) removes the row; a failed
-- attempt leaves it with attempts + 1, and after five it is left for a person to look at.
create table if not exists public.classify_queue (
  brand_id    bigint      not null,
  doc_id      text        not null,
  created_utc timestamptz not null,
  enqueued_at timestamptz not null default now(),
  attempts    smallint    not null default 0,
  primary key (brand_id, doc_id, created_utc)
);
alter table public.classify_queue enable row level security;
create index if not exists classify_queue_order on public.classify_queue (enqueued_at desc);

create or replace function public.enqueue_mention() returns trigger
language plpgsql as $$
begin
  insert into public.classify_queue (brand_id, doc_id, created_utc)
  values (new.brand_id, new.doc_id, new.created_utc) on conflict do nothing;
  return new;
end;
$$;
drop trigger if exists mentions_enqueue on public.mentions;
create trigger mentions_enqueue after insert on public.mentions
  for each row execute function public.enqueue_mention();

-- the backlog: every mention with no label and no rejection, newest collected first in line
insert into public.classify_queue (brand_id, doc_id, created_utc, enqueued_at)
select m.brand_id, m.doc_id, m.created_utc, m.loaded_at
  from public.mentions m
 where not exists (select 1 from public.mention_sentiment s where s.doc_id = m.doc_id and s.brand_id = m.brand_id)
   and not exists (select 1 from public.mention_rejections x where x.doc_id = m.doc_id and x.brand_id = m.brand_id)
on conflict do nothing;

grant select, insert, update, delete on public.classify_queue to ri_sweep;
