-- The daytime passes are requested on Railway, by the index's own second service (ops/day_tick.py, decision 0026),
-- with the sweep's database login. Until now the request row was written from the laptop as postgres and the sweep
-- could only read and delete it.
grant insert on public.day_run_request to ri_sweep;
