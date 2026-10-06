-- A daytime pass of the sweep, on Railway, on request (2026-10-06).
--
-- Vlad, 2026-10-05: "move on with the data collection". Daytime passes ran from the laptop and died twice when it
-- slept, and on 6 Oct the laptop's network blocked the database port altogether. The sweep's Railway service can be
-- started on demand, but its start command is fixed, and a start outside the night window is refused (that refusal
-- is what keeps a stray deployment from collecting, decision 0016). A row here, younger than 20 minutes, is the only
-- thing that turns an out-of-window start into a daytime pass: the sweep deletes it and runs one by-hand pass
-- (manual on its receipt, so the go-live gate never counts it), ending by end_by_utc.
create table if not exists public.day_run_request (
  requested_at  timestamptz primary key default now(),
  requested_by  text        not null default current_user,
  stages        text        not null default 'collect,classify,refresh,score,publish',
  max_calls     integer     not null default 10000 check (max_calls between 0 and 15000),
  end_by_utc    time        not null default '21:30'
);
alter table public.day_run_request enable row level security;
grant select, delete on public.day_run_request to ri_sweep;
drop policy if exists ri_sweep_day_run on public.day_run_request;
create policy ri_sweep_day_run on public.day_run_request for all to ri_sweep using (true) with check (true);
