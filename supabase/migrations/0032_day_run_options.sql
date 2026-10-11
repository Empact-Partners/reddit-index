-- A daytime pass's request can carry options for that one pass (2026-10-11): today only
--   {"tree_workers": n}   comment trees in flight at once in the collect stage, 1 to 4
-- so two passes of one day can be compared without a redeploy between them. Null: the sweep's own settings
-- (ops/schedule.json). The sweep reads it as to_jsonb(row)->'options', so an image deployed before this migration
-- still runs.
alter table public.day_run_request
  add column if not exists options jsonb check (options is null or jsonb_typeof(options) = 'object');
