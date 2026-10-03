-- Migration 0019 stores a comment's text once: a second brand row of the same comment carries body NULL and
-- body_from. public.mentions.body was NOT NULL, so every such insert failed and the collector dropped the row.
-- Found by the sweep pilot on 2026-10-03 within its first minute of collection; repaired by
-- ops/repair_dropped_rows.py from the pilot's log.
alter table public.mentions alter column body drop not null;
