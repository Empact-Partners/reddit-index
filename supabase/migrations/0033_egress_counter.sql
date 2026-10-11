-- Readings of the database node's transmit counter, kept in the database (2026-10-11).
--
-- The counter (node_network_transmit_bytes_total) is the number the egress watchdog and the bill follow. Until now
-- only the laptop read it: the day guard that stops a daytime pass at the 1.9 GB line ran there, and on 11 Oct the
-- laptop slept on battery while a pass ran, the day went to 2.42 GB and the watchdog spoke. From this migration the
-- sweep reads the counter itself (worker/meter.py) and writes each reading here, so a pass can stop itself and the
-- usage of any 24 hours can be read back from two rows. The laptop writes its readings here too.
create table if not exists public.egress_counter (
  at      timestamptz primary key default now(),
  bytes   numeric     not null check (bytes > 0),
  source  text        not null default current_user
);
alter table public.egress_counter enable row level security;
grant select, insert, delete on public.egress_counter to ri_sweep;
drop policy if exists ri_sweep_egress_counter on public.egress_counter;
create policy ri_sweep_egress_counter on public.egress_counter for all to ri_sweep using (true) with check (true);

-- the readings already on record (docs/go-live/egress-2026-10-11.json and the 11 Oct investigation), so the first
-- 24-hour figure has something to stand on
insert into public.egress_counter (at, bytes, source) values
  ('2026-10-09 23:50:20+00', 1458941146284, 'gate meter (laptop)'),
  ('2026-10-10 04:51:54+00', 1459549715891, 'gate meter (laptop)'),
  ('2026-10-10 23:57:12+00', 1460633250325, 'gate meter (laptop)'),
  ('2026-10-11 05:09:12+00', 1461125561377, 'gate meter (laptop)'),
  ('2026-10-11 12:17:00+00', 1463055024361, 'investigation 11 Oct')
on conflict (at) do nothing;
