-- 0015 — the daily sweep's own database role, and a switch that stops it in one statement.
--
-- The old collector connected as `postgres` with the only copy of that password on Railway. When it had to
-- be stopped on 2026-10-02 the only certain way was to change the superuser's password. The sweep now
-- connects as `ri_sweep`, which can write the tables it maintains and nothing else, and two things stop it:
--
--   * public.sweep_control.enabled = false   the sweep reads it before every stage and every 25 subreddits
--                                            and stops clean (ops/ri.py stop does this);
--   * alter role ri_sweep nologin            the sweep cannot connect at all (ops/ri.py stop does this too).
--
-- `publish_enabled` keeps the site frozen while scheduled runs are proven: the sweep collects, classifies
-- and scores, and tells the site nothing until decision 0017 turns publishing on.

create table if not exists public.sweep_control (
  only_row        boolean     primary key default true check (only_row),
  enabled         boolean     not null default false,
  publish_enabled boolean     not null default false,
  reason          text,
  updated_at      timestamptz not null default now()
);
alter table public.sweep_control enable row level security;
insert into public.sweep_control (only_row, enabled, reason)
values (true, false, 'created by migration 0015; enabled only when the new sweep is deployed')
on conflict (only_row) do nothing;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'ri_sweep') then
    create role ri_sweep nologin;
  end if;
end $$;

grant usage on schema public, site to ri_sweep;
-- read: the gazetteer, the taxonomy, the switch
grant select on public.brands, public.brand_aliases, public.categories, public.subreddits,
                public.category_subreddits, public.methodology_params, public.sweep_control
  to ri_sweep;
-- collect
grant select, insert, update on public.threads, public.ingest_state to ri_sweep;
grant select, insert, delete on public.mentions to ri_sweep;
-- classify
grant select, insert, delete on public.mention_sentiment, public.mention_rejections to ri_sweep;
-- takedowns: the ledger is append-and-stamp, never delete
grant select, insert, update on public.removals to ri_sweep;
grant select, insert, update, delete on public.doc_probe to ri_sweep;
-- receipts
grant select, insert, update on public.pipeline_runs to ri_sweep;
grant select on public.brand_category_scores to ri_sweep;
-- the site tables and their functions
grant select, insert, update, delete on all tables in schema site to ri_sweep;
grant execute on function site.refresh_brand(bigint), site.refresh_dirty(integer), site.compute_index_hashes()
  to ri_sweep;
alter role ri_sweep set statement_timeout = '30min';
