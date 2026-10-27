-- RLS on every monthly partition of mentions and on mention_rail_meta (2026-10-27, applied live the same day).
--
-- Supabase's security advisor (rls_disabled_in_public, ERROR) flagged 51 tables: mention_rail_meta (0005) and every
-- mentions_YYYY_MM partition plus mentions_default. 0002 enabled RLS on the parent `mentions`, but RLS is not
-- inherited: a partition is its own table, PostgREST exposes it under its own name, and the default grants gave
-- `anon` SELECT/INSERT/UPDATE/DELETE on each one. Anyone holding the project URL and the anon key could read and
-- write the raw corpus partition by partition.
--
-- No policy is added, as everywhere since 0002: `anon` and `authenticated` see nothing, postgres (the owner) and
-- service_role bypass RLS, and the readers keep working because they read through postgres-owned views
-- (published.*, site.*) or functions, never a base table. A query on the parent applies the parent's policies
-- only, so ri_sweep's `ri_sweep_rows` policy on `mentions` is unaffected.
--
-- worker/daily.py's ensure_partitions() now enables RLS on each partition it creates, so a new month is never
-- born open. This file is idempotent: it enables RLS on any public table that still lacks it.

set lock_timeout = '3s';

do $$
declare r record;
begin
  for r in select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
           where n.nspname = 'public' and c.relkind in ('r','p') and not c.relrowsecurity order by 1 loop
    execute format('alter table public.%I enable row level security', r.relname);
  end loop;
end $$;
