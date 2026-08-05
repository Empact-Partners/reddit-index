-- Reddit Index — RLS, the published read surface, and the site_reader role.
--
-- 08-architecture.md §5's preferred posture, taken literally: "the site does not
-- ship the anon key at all. Build and revalidate read through a dedicated
-- site_reader Postgres role holding SELECT on published views only."
--
-- So RLS is on everywhere, `anon` gets no policy at all, and the entire reader
-- path is the `published` schema. Views are owned by postgres and left at the
-- default security_invoker = false, so they run with the owner's privileges and
-- the caller never touches a base table.

begin;

alter table categories          enable row level security;
alter table subreddits          enable row level security;
alter table category_subreddits enable row level security;
alter table brands              enable row level security;
alter table brand_aliases       enable row level security;
alter table threads             enable row level security;
alter table mentions            enable row level security;
alter table mention_sentiment   enable row level security;
alter table brand_category_scores enable row level security;
alter table leaderboards        enable row level security;
alter table brand_pages         enable row level security;
alter table removals            enable row level security;
alter table ingest_state        enable row level security;
alter table pipeline_runs       enable row level security;
alter table methodology_params  enable row level security;
alter table mention_audit       enable row level security;
alter table lane_d_queries      enable row level security;

create schema if not exists published;

create view published.categories as
  select id, slug, name, icon, hex, threshold_tier, precision_target_pp, n_min,
         base_rate_c, status
  from categories where status in ('published','unrankable');

create view published.brands as
  select b.id, b.slug, b.name, b.primary_category_id, b.ambiguity_class, b.status
  from brands b where b.status = 'published';

create view published.subreddits as
  select id, name, rule_posture, is_vendor_sub, subscribers from subreddits;

create view published.category_subreddits as
  select category_id, subreddit_id, is_scoring, bb_per_hour from category_subreddits;

create view published.threads as
  select id, subreddit_id, link_title, permalink, created_utc, num_comments, archived
  from threads;

-- run_id and match_conf are deliberately absent: 08 §5 exposes mentions "only
-- through a view that omits them". A mention is visible only when its brand is
-- published — a brand pulled for a failed precision certification takes its
-- evidence with it.
create view published.mentions as
  select m.brand_id, m.doc_id, m.doc_type, m.thread_id, m.subreddit_id,
         m.author, m.created_utc, m.permalink, m.score, m.body, m.matched_form,
         s.label, s.intensity, s.stage
  from mentions m
  join brands b on b.id = m.brand_id and b.status = 'published'
  left join mention_sentiment s
    on s.doc_id = m.doc_id and s.brand_id = m.brand_id
   and s.model_version = (select value #>> '{}' from methodology_params
                          where key = 'sentiment_model_version'
                          order by frozen_at desc limit 1);

create view published.brand_category_scores as
  select * from brand_category_scores;

create view published.leaderboards as
  select * from leaderboards;

create view published.brand_pages as
  select bp.brand_id, b.slug, bp.payload, bp.updated_at
  from brand_pages bp join brands b on b.id = bp.brand_id
  where b.status = 'published';

-- The frozen method is public by design: 07 §9's audit trail is only an audit
-- trail if a reader can see it.
create view published.methodology_params as
  select version, scope, key, value, rationale, effective_from, git_commit, frozen_at
  from methodology_params;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'site_reader') then
    create role site_reader nologin;
  end if;
end $$;

revoke all on schema public from site_reader;
grant usage on schema published to site_reader;
grant select on all tables in schema published to site_reader;
alter default privileges in schema published grant select on tables to site_reader;

-- Views execute as their owner, which needs the underlying grants.
grant usage on schema public to site_reader;
grant select on categories, subreddits, category_subreddits, brands, threads,
                mentions, mention_sentiment, brand_category_scores, leaderboards,
                brand_pages, methodology_params
  to site_reader;

-- No policy exists for anon on any table, and none is created here. Service
-- role bypasses RLS for pipeline writes. brand_aliases, ingest_state, removals,
-- mention_audit and lane_d_queries are reachable by the service role only.

commit;
