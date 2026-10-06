-- The organic mentions board's link into the index (decision 0019, 2026-10-06).
--
-- Vlad, 2026-10-06: the Reddit Index and the organic mentions board are "a super connected system ... establish a proper
-- relationship and proper links between" them. The Reddit mentions tracker (Empact-Partners/reddit-mentions) finds
-- every organic mention of the partners Empact runs Reddit for, in real time, across a partner-chosen watch list; the
-- Empact Ops board (Empact-Partners/empact-ops, reddit/partners/<p>/organic/) keeps each one and what Empact did about
-- it. This table keeps every one of them in the index's own database too, tied to the index's brand, so:
--   - nothing the tracker found is lost between the two systems, and each row points at its board record;
--   - the index's coverage of its own partners is measured: `watch.organic_coverage` says, per mention, whether the
--     index's uniform collection holds it (public.mentions, same brand, same document).
-- It is never read by the site (the site reads site.* only) and never scored: the public rankings count only the
-- index's own uniform collection (tracker decision D5; 0018), or partners would be measured on a closer watch than
-- their competitors. No persona name ever lands here: `replied` is a yes or no.
create schema if not exists watch;

create table if not exists watch.organic_mentions (
  board_id     text primary key,              -- the Empact Ops record id: om_<reddit id>_<partner>
  partner      text not null,                 -- the Empact Ops / tracker slug (clementineaba)
  brand_id     bigint references public.brands(id),   -- the index's brand (clementine-aba); null when it is not one
  reddit_id    text not null,                 -- t1_… or t3_…, as in public.mentions.doc_id
  doc_type     text,                          -- comment | post
  subreddit    text,
  url          text,
  written_at   timestamptz,
  found_at     timestamptz,
  sentiment    text,
  mention_type text,
  engagement   text,                          -- what Empact did: new, replying, replied, partner, no_reply, not_about_them
  replied      boolean not null default false,
  board_url    text,                          -- the record on GitHub
  mirrored_at  timestamptz not null default now()
);
create index if not exists organic_mentions_brand_idx on watch.organic_mentions (brand_id, written_at desc);
create index if not exists organic_mentions_reddit_idx on watch.organic_mentions (reddit_id);
alter table watch.organic_mentions enable row level security;   -- no policy: only the owner (postgres) reads or writes
revoke all on schema watch from public;

-- Per mention: does the index's own collection hold it? The primary key (brand_id, doc_id, created_utc) with the
-- written time narrows the lookup to one monthly partition.
create or replace view watch.organic_coverage as
select o.*,
       exists (select 1 from public.mentions m
               where m.brand_id = o.brand_id and m.doc_id = o.reddit_id
                 and m.created_utc between o.written_at - interval '1 minute' and o.written_at + interval '1 minute') as in_index
from watch.organic_mentions o;
revoke all on watch.organic_coverage from public;
