-- 0008 — site.refresh_brand plans once, not once per brand.
--
-- `mentions` has 49 partitions and none of refresh_brand's queries can prune them (they filter on brand_id; the
-- partition key is created_utc). Under the default plan-cache mode Postgres keeps building a fresh plan for
-- every call, which costs more than running it. Measured 2026-10-02 on twelve mid-sized brands in one
-- statement: 89 ms a brand with the default, 43 ms with a generic plan. The plan is the same either way.
alter function site.refresh_brand(bigint) set plan_cache_mode = force_generic_plan;
