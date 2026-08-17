-- 0003 — two repairs the live database already carries, written down so a
-- replay of the migration chain reproduces the database that exists.
--
-- 1. UNPIN published.mentions FROM ONE model_version.
--    0002 joined mention_sentiment on
--        s.model_version = (select value from methodology_params
--                           where key = 'sentiment_model_version' …)
--    That was true when one engine labelled everything. It is not true now:
--    the corpus carries claude-cli-absa-1, deepseek-v4-flash-absa-1 and
--    haiku-4.5-absa-1, and the frozen parameter reads 'multi-lane', which
--    matches NO row. The pin has already cost this project once — 115,820
--    labels were invisible to the site until it was lifted by hand on
--    2026-08-16 (commit 74923ce), and that hand-edit existed in no file, so
--    the next `supabase db push` onto a fresh database would have silently
--    blanked every sentiment on the site again.
--
--    The replacement takes the MOST RECENTLY SCORED label per (doc, brand),
--    with model_version as a deterministic tiebreak when two labels share a
--    timestamp. One row per mention, engine-agnostic, and a re-label wins by
--    being newer rather than by matching a string.
--
-- 2. threads.tree_fetched_at — the revisit queue's memory.
--    The daily lane fetched comment trees with
--        ORDER BY num_comments DESC LIMIT 12
--    over a 72-hour window and recorded nothing. num_comments is refreshed on
--    every pass, so the ordering is stable: the same twelve threads were
--    re-read for three days while the thirteenth aged out of the window
--    unread. Measured over 2026-08-10..15: 48,171 of 75,511 threads (64%) sat
--    outside the top twelve of their own subreddit-day, and only 12% ever
--    acquired a single comment mention. Comments are 80% of the corpus, so
--    this was the largest ongoing loss in the pipeline.

begin;

create or replace view published.mentions as
  select m.brand_id, m.doc_id, m.doc_type, m.thread_id, m.subreddit_id,
         m.author, m.created_utc, m.permalink, m.score, m.body, m.matched_form,
         s.label, s.intensity, s.stage
  from mentions m
  join brands b on b.id = m.brand_id and b.status = 'published'
  left join lateral (
    select ms.label, ms.intensity, ms.stage
    from mention_sentiment ms
    where ms.doc_id = m.doc_id and ms.brand_id = m.brand_id
    order by ms.scored_at desc nulls last, ms.model_version desc
    limit 1
  ) s on true;

grant select on published.mentions to site_reader;

alter table threads add column if not exists tree_fetched_at timestamptz;

comment on column threads.tree_fetched_at is
  'When this thread''s comment tree was last fetched. NULLS FIRST ordering in '
  'the daily revisit query is what guarantees every thread in the window is '
  'read once before any thread is read twice.';

-- Supports the revisit query exactly: subreddit, inside the window, unread first.
create index if not exists threads_revisit_idx
  on threads (subreddit_id, first_seen_at, tree_fetched_at nulls first);

commit;
