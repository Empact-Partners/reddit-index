-- The sweep's role sees the rows its grants cover. Found by the first scheduled run (2026-10-03 00:01 UTC):
-- every public table has row-level security on and no policy, which shows a role without BYPASSRLS zero rows
-- and refuses its writes. The old collector logged in as the owner, which bypasses row-level security, so this
-- never showed. The stop switch read as empty ("cannot unpack NoneType") and the run's receipt was refused.
--
-- One policy per table, for ri_sweep only, allowing every row. What ri_sweep may DO stays decided by its grants
-- (migrations 0015, 0016): a policy cannot widen a grant. The site's role (ri_site) reads schema site, which has
-- no row-level security, and is untouched.
do $$
declare t text;
begin
  foreach t in array array[
    'brands', 'brand_aliases', 'categories', 'subreddits', 'category_subreddits', 'methodology_params',
    'sweep_control', 'brand_category_scores', 'threads', 'ingest_state', 'mentions', 'mention_sentiment',
    'mention_rejections', 'removals', 'doc_probe', 'pipeline_runs', 'classify_queue']
  loop
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = 'ri_sweep_rows') then
      execute format('create policy ri_sweep_rows on public.%I for all to ri_sweep using (true) with check (true)', t);
    end if;
  end loop;
end $$;
