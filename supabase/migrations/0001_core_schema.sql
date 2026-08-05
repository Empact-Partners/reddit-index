-- Reddit Index — core schema.
-- Contract: 08-architecture.md §3. Every table here appears there, except three
-- noted below that the spec needs and does not have.
--
-- Two deviations from §3, both forced, both recorded in HANDOFF.md:
--
--  1. §3 specifies `mentions PARTITION BY RANGE(created_utc)` AND
--     `UNIQUE(brand_id, doc_id)`. Postgres rejects that combination outright:
--     a unique constraint on a partitioned table must include every partition
--     key column. The natural key becomes (brand_id, doc_id, created_utc).
--     `created_utc` is a fixed property of a Reddit fullname, so the same
--     (brand, document) pair cannot legitimately appear under two timestamps —
--     and a nightly assertion in gate_checks.sql proves it never does.
--
--  2. §3 keys `mention_sentiment` on `mention_id`. A foreign key into a
--     partitioned table has to carry the whole partition key, so sentiment is
--     keyed on (doc_id, brand_id, model_version) instead — which is the
--     resolution unit 05-entity-resolution.md §3 already defines:
--     "(document × brand × category), where a document is either a comment or
--     a post."
--
-- Everything in Postgres is DERIVED. Parquet in Storage is the corpus.

begin;

-- ───────────────────────────────────────────────────────────── reference data

create table categories (
  id                   bigserial primary key,
  slug                 text not null unique,
  name                 text not null,
  parent_id            bigint references categories(id),
  icon                 text not null,
  hex                  text not null,
  base_rate_c          numeric,               -- fitted category prior mean
  threshold_tier       text not null check (threshold_tier in ('deep','standard','thin')),
  precision_target_pp  int  not null,
  n_min                int  not null,
  status               text not null default 'draft'
                       check (status in ('draft','published','unrankable')),
  frozen_at            timestamptz,           -- slug freeze, see trigger below
  created_at           timestamptz not null default now()
);

create table subreddits (
  id                  bigserial primary key,
  name                text not null unique,   -- bare, no r/ prefix
  rule_posture        text check (rule_posture in ('permissive','capped','hostile','unknown')),
  posture_source      text,
  is_vendor_sub       bool not null default false,
  subscribers         bigint,
  comments_per_hour   numeric,
  poll_interval_h     numeric,
  rules_hash          text,
  checked_at          timestamptz
);

-- Which subreddits feed which category, and which of those may SCORE.
-- 13-algorithm.md §2: scorable = status ok AND rule_posture <> hostile AND NOT
-- is_vendor_sub, capped at 8 scoring subreddits per category chosen by measured
-- yield per call — never by subscriber count.
create table category_subreddits (
  category_id   bigint not null references categories(id) on delete cascade,
  subreddit_id  bigint not null references subreddits(id) on delete cascade,
  is_scoring    bool   not null default false,
  worth         numeric,
  bb_per_hour   numeric,
  primary key (category_id, subreddit_id)
);
create index on category_subreddits (category_id) where is_scoring;

create table brands (
  id                   bigserial primary key,
  slug                 text not null unique,
  name                 text not null,
  primary_category_id  bigint references categories(id),
  ambiguity_class      text not null check (ambiguity_class in ('low','medium','high')),
  surface_class        text not null check (surface_class in ('SAFE','AMBIGUOUS','HOSTILE')),
  require_context      bool not null default false,
  min_corroborating    smallint not null default 0,
  domains              text[] not null default '{}',
  stop_contexts        text[] not null default '{}',
  ambiguity_note       text,
  status               text not null default 'draft'
                       check (status in ('draft','published','excluded')),
  excluded_reason      text,
  frozen_at            timestamptz,
  created_at           timestamptz not null default now()
);
create index on brands using gin (domains);

-- Service-role only. 08-architecture.md §3: "the alias, stop-context and
-- ambiguity table is a working recipe for gaming the index."
create table brand_aliases (
  brand_id           bigint not null references brands(id) on delete cascade,
  alias              text   not null,
  alias_type         text   not null check (alias_type in ('canonical','alias','domain')),
  surface_class      text   not null check (surface_class in ('SAFE','AMBIGUOUS','HOSTILE')),
  min_corroborating  smallint not null default 0,
  -- A bare token no stop-context list can rescue: `close`, `make`, `square`.
  -- Never matchable at any score; the brand resolves only through a qualified
  -- form. 05-entity-resolution.md §9 — excluded, not guessed.
  bare_disabled      bool not null default false,
  primary key (alias, brand_id)
);

-- ────────────────────────────────────────────────────────────────── the corpus

create table threads (
  id            text primary key,             -- t3 fullname
  subreddit_id  bigint not null references subreddits(id),
  link_title    text,
  permalink     text not null,
  created_utc   timestamptz not null,
  num_comments  int,
  archived      bool not null default false,
  score         int,
  first_seen_at timestamptz not null default now()
);
create index on threads (subreddit_id, created_utc desc);

create table mentions (
  brand_id      bigint      not null references brands(id),
  doc_id        text        not null,         -- t1_ or t3_ fullname
  created_utc   timestamptz not null,
  doc_type      smallint    not null,         -- 1 = comment, 2 = post_body
  thread_id     text        not null,
  subreddit_id  bigint      not null references subreddits(id),
  author        text        not null,
  permalink     text        not null,         -- copied from the API, never built
  score         int,
  body          text        not null,         -- full matched text; decisions/0002
  match_conf    real        not null,
  matched_form  text        not null,
  rule_fired    text,
  run_id        uuid        not null,
  loaded_at     timestamptz not null default now(),
  primary key (brand_id, doc_id, created_utc)
) partition by range (created_utc);

create index on mentions (brand_id, created_utc desc);
create index on mentions (thread_id);
create index on mentions (brand_id, author);
create index on mentions (subreddit_id);

-- 36 trailing + 12 forward monthly partitions, plus a catch-all so a stray
-- timestamp can never fail an insert mid-load.
do $$
declare m date := date_trunc('month', now())::date - interval '36 months';
begin
  for i in 0..47 loop
    execute format(
      'create table if not exists mentions_%s partition of mentions for values from (%L) to (%L)',
      to_char(m, 'YYYY_MM'), m, (m + interval '1 month')::date);
    m := (m + interval '1 month')::date;
  end loop;
end $$;
create table mentions_default partition of mentions default;

create table mention_sentiment (
  doc_id             text   not null,
  brand_id           bigint not null references brands(id),
  model_version      text   not null,
  -- Frozen encoding. 06-sentiment.md §3 is authoritative over 07 §3's five-value
  -- list: the set is four-way and `recommendation` is a FLAG, because collapsing
  -- it into a polarity would change the denominator and therefore the rank.
  label              smallint not null check (label between 0 and 3),  -- 0 neu 1 pos 2 neg 3 abstain
  intensity          real,
  conf               real,
  stage              smallint not null check (stage between 1 and 4),  -- 1 rules 2 encoder 3 llm 4 human
  is_comparative     bool not null default false,
  is_recommendation  bool not null default false,
  is_category_gripe  bool not null default false,
  evidence_span      text,
  scored_at          timestamptz not null default now(),
  primary key (doc_id, brand_id, model_version)
);

-- ─────────────────────────────────────────────────────────────────── the index

create table brand_category_scores (
  brand_id           bigint not null references brands(id),
  category_id        bigint not null references categories(id),
  week_start         date   not null,
  pos int not null, neg int not null, neu int not null, abstain int not null,
  n                  int not null,             -- all eligible mentions
  n_op               int not null,             -- pos + neg, the estimator denominator
  n_eff              numeric,
  deff               numeric,
  deff_thread        numeric,
  deff_author        numeric,
  icc_thread         numeric,
  icc_author         numeric,
  icc_estimated      bool not null default true,
  alpha0             numeric,
  beta0              numeric,
  reddit_love_score  int,
  polarization       numeric,
  neutral_share      numeric,
  abstain_share      numeric,
  ci_low             numeric,
  ci_high            numeric,
  n_authors          int,
  n_subreddits       int,
  n_threads          int,
  max_thread_share   numeric,
  max_author_share   numeric,
  max_subreddit_share numeric,               -- published evidence, not a floor
  rank_desc          int,
  rank_asc           int,
  eligible           bool not null default false,
  failed_test        text,
  failed_observed    text,
  failed_required    text,
  window_start       date,
  window_end         date,
  methodology_version text,
  run_id             uuid,
  computed_at        timestamptz not null default now(),
  primary key (brand_id, category_id, week_start)
);
create index on brand_category_scores (category_id, week_start, reddit_love_score desc);

create table leaderboards (
  category_id        bigint references categories(id),  -- null = the pooled board
  week_start         date not null,
  board              text not null check (board in ('most_loved','most_hated')),
  brand_id           bigint not null references brands(id),
  rank               int not null,
  tied_with          int[] not null default '{}',
  reddit_love_score  int not null,
  n                  int not null,
  rank_delta         int
);
create unique index on leaderboards (coalesce(category_id, -1), week_start, board, brand_id);

create table brand_pages (
  brand_id      bigint primary key references brands(id),
  payload       jsonb not null,
  content_hash  text  not null,
  updated_at    timestamptz not null default now()
);

-- ───────────────────────────────────────────────────────────────── operational

-- A tombstone ledger, not an audit trail. Its job is to stop a purged doc_id
-- being re-ingested from a stale archive shard, and to carry revalidated_at as
-- the receipt that the cached page was invalidated. 08 §8: a row with purged_at
-- set and revalidated_at null is an open defect.
create table removals (
  doc_id          text primary key,
  doc_type        smallint,
  brand_ids       bigint[],
  reason          text,
  detected_at     timestamptz not null default now(),
  purged_at       timestamptz,
  revalidated_at  timestamptz
);
create index on removals (detected_at);
create index on removals (revalidated_at) where revalidated_at is null;

create table ingest_state (
  scope         text not null,       -- subreddit, or a lane-scoped key
  ym            text not null,
  stage         text not null,
  code_version  text not null,
  watermark     text,
  file_hash     text,
  rows          int,
  status        text,
  finished_at   timestamptz,
  primary key (scope, ym, stage, code_version)
);

create table pipeline_runs (
  run_id       uuid primary key,
  stage        text not null,
  code_version text,
  started_at   timestamptz not null default now(),
  finished_at  timestamptz,
  status       text,
  notes        jsonb
);

-- ── Three tables 08 §3 does not have and the method cannot work without ──────

-- 1. The frozen-constants register. 07-index-methodology.md §9 requires the
--    method tagged and its commit hash recorded BEFORE the first production
--    crawl, and forbids changing a parameter after seeing where a named brand
--    landed. This table is that guarantee, in the database rather than in prose.
create table methodology_params (
  version         text not null,
  scope           text not null,      -- 'global' | a category slug | a brand slug
  key             text not null,
  value           jsonb not null,
  rationale       text not null,
  effective_from  timestamptz not null,
  git_commit      text not null,
  frozen_at       timestamptz not null default now(),
  primary key (version, scope, key)
);

create or replace function methodology_params_is_append_only() returns trigger
language plpgsql as $$
begin
  raise exception
    'methodology_params is append-only. Changing a frozen parameter is a methodology change: bump the version and add a dated changelog entry (07-index-methodology.md §9), never an UPDATE.';
end $$;

create trigger methodology_params_no_mutation
  before update or delete on methodology_params
  for each row execute function methodology_params_is_append_only();

-- 2. The adjudication ledger. Without it the precision claim is unfalsifiable.
create table mention_audit (
  id             bigserial primary key,
  sample_id      text   not null,
  doc_id         text   not null,
  brand_id       bigint not null references brands(id),
  stratum        text   not null check (stratum in ('SAFE','AMBIGUOUS','HOSTILE')),
  verdict        smallint,             -- 1 correct brand, 0 false positive, null pending
  adjudicator    text,
  adjudicated_at timestamptz,
  note           text,
  unique (sample_id, doc_id, brand_id, adjudicator)
);

-- 3. Lane D reproducibility. Yield per query is what sizes the next harvest.
create table lane_d_queries (
  id            bigserial primary key,
  category_id   bigint references categories(id),
  subreddit     text not null,
  q             text not null,
  sort          text not null,
  time_window   text not null,     -- `window` is a reserved word in Postgres
  page          int  not null default 1,
  results_n     int,
  unique_new_n  int,
  qualifying_n  int,
  run_id        uuid not null,
  fetched_at    timestamptz not null default now(),
  unique (subreddit, q, sort, time_window, page, run_id)
);

-- ─────────────────────────────────────────────────── slugs are frozen for good
-- decisions/0007: "A published slug is persisted and never regenerated from the
-- display name." A company URL that moves after indexing loses the ranking that
-- made it worth sending, so this is enforced by the database, not a comment.
create or replace function slug_is_frozen() returns trigger
language plpgsql as $$
begin
  if old.frozen_at is not null and new.slug is distinct from old.slug then
    raise exception
      'slug % is frozen (since %). Renames update the display name only; a slug change needs a permanent redirect and a recorded pair (decisions/0007).',
      old.slug, old.frozen_at;
  end if;
  return new;
end $$;

create trigger brands_slug_frozen     before update on brands
  for each row execute function slug_is_frozen();
create trigger categories_slug_frozen before update on categories
  for each row execute function slug_is_frozen();

-- ──────────────────────────────────── vendor subreddits can never score, ever
-- BUILD-PROMPT.md's gate: "Vendor-named subreddits contributed zero scoring
-- mentions." An assertion that passes because the data never arrived is not a
-- proof, so the exclusion is structural: the row cannot be inserted.
create or replace function reject_vendor_sub_mention() returns trigger
language plpgsql as $$
declare vend bool;
begin
  select is_vendor_sub into vend from subreddits where id = new.subreddit_id;
  if vend then
    raise exception
      'r/% is a vendor-named subreddit and may not contribute a scoring mention (13-algorithm.md §2). Vendor communities are ingested as evidence and excluded from every ranking.',
      (select name from subreddits where id = new.subreddit_id);
  end if;
  return new;
end $$;

create trigger mentions_no_vendor_subs before insert on mentions
  for each row execute function reject_vendor_sub_mention();

commit;
