-- While GLM is out (its plan allowance used up, 2026-10-07), Jev settles 35-50% of the queue and the rest waits. Without a
-- mark, every run re-read that residue first and stalled on it. jev_checked_at says Jev looked and could not settle the
-- item; a run with GLM off skips such rows, a run with GLM on takes them as usual. Nullable, no default: no table rewrite.
alter table public.classify_queue add column if not exists jev_checked_at timestamptz;
