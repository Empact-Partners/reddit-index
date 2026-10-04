-- archive.mentions was created (0020) as a copy of public.mentions while body was still NOT NULL; 0021 dropped
-- it on public.mentions only. A row that keeps its text on another row (body NULL, body_from set) could then
-- never be archived: retention's `rejected` step would roll back on its first such row. Found by the independent
-- review of 2026-10-04 before that step ever ran (it first has work on 2026-11-01). archive.mentions is empty.
alter table archive.mentions alter column body drop not null;
