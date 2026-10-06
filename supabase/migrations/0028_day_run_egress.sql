-- A daytime pass can be given less database egress than a night run (2026-10-06): the pass is requested with the room
-- the day still has under the 2 GB line, measured on the node counter by whoever requests it (the run itself cannot read
-- that counter). Null keeps the run's own cap (ops/schedule.json caps.egress_gb).
alter table public.day_run_request
  add column if not exists max_egress_gb numeric check (max_egress_gb is null or (max_egress_gb > 0 and max_egress_gb <= 0.7));
