-- The two indexes and the one role setting that make the build's corpus read
-- survivable, applied to production on 2026-09-17 during the egress incident.
--
-- Recorded here so the schema is reproducible rather than invisible drift. They
-- were created CONCURRENTLY against live traffic, which cannot run inside a
-- transaction block, so this file deliberately has no begin/commit and uses
-- IF NOT EXISTS throughout: re-running it against production is a no-op.
--
-- WHY. `loadSnapshotOnce()` issues two queries that walk the whole corpus, and
-- both had degraded to the edge of the 2min statement timeout as the corpus
-- grew. A production build failed on exactly this (57014 at snapshot.ts:122,
-- deployment dpl_FZseUJVrFoZDRjrecHMNcTLB9VKM) — at which point the site could
-- no longer be rebuilt at all, and "publish = rebuild" is the ONLY way data
-- reaches redditindex.com.

-- 1. The sentiment lateral in published.mentions.
--
-- The view resolves each mention's newest sentiment row with a LEFT JOIN
-- LATERAL: filter on (doc_id, brand_id), then ORDER BY scored_at DESC NULLS
-- LAST, model_version DESC LIMIT 1. mention_sentiment_pkey covers the filter
-- but NOT the ordering and carries none of the output columns, so every one of
-- ~1.16M lookups fell back to a heap fetch — ~1.16M random reads per corpus
-- scan. The whole-table aggregate measured 119,053 ms against a 120,000 ms
-- timeout: one second from never completing again.
--
-- This index satisfies filter, ordering and output together, so the lateral
-- becomes an Index Only Scan at ~0.006 ms. Aggregate: 119,053 ms -> 14,633 ms.
create index concurrently if not exists mention_sentiment_latest_idx
  on public.mention_sentiment (doc_id, brand_id, scored_at desc nulls last, model_version desc)
  include (label, intensity, stage);

-- 2. The mention rail's per-brand, per-doc_type recency scan.
--
-- The rail takes the newest 80 posts and 40 comments PER BRAND. The only index
-- that fit was (brand_id, created_utc DESC), which does not carry doc_type, so
-- each branch read rows in recency order and threw away everything of the wrong
-- type — and paid the sentiment lateral on each one it discarded.
--
-- ON ONLY + per-partition CONCURRENTLY + ATTACH, because CREATE INDEX on a
-- partitioned parent takes an ACCESS EXCLUSIVE lock on all 49 partitions at
-- once. Rail: 93 s -> ~62 s measured on an unbiased brand sample.
--
-- This does NOT remove the real cost, which is partition fan-out: `ORDER BY
-- created_utc DESC LIMIT n` on a table partitioned BY MONTH on created_utc
-- makes a Merge Append across all 49 partitions, per brand, per doc_type —
-- ~945,000 index scans for one rail. The durable fix is a materialized view
-- refreshed by the pipeline; see the note in lib/data/snapshot.ts.
create index if not exists mentions_brand_doctype_created_idx
  on only public.mentions (brand_id, doc_type, created_utc desc);
-- then, per partition:
--   create index concurrently mentions_<YYYY_MM>_bdc_idx
--     on public.mentions_<YYYY_MM> (brand_id, doc_type, created_utc desc);
--   alter index public.mentions_brand_doctype_created_idx
--     attach partition public.mentions_<YYYY_MM>_bdc_idx;
-- The parent index reports indisvalid only once all 49 are attached.

-- 3. site_reader's statement timeout.
--
-- site_reader had no role setting and inherited the 2min default. After the ISR
-- path is gone (revalidate = false), site_reader is a BUILD-ONLY role: nothing
-- serves a user request through it, so a long ceiling costs nothing and a short
-- one costs the ability to publish. Raised so corpus growth cannot silently
-- make the site unbuildable again.
alter role site_reader set statement_timeout = '10min';
