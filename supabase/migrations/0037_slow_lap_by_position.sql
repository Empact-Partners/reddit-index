-- The takedown check's slow lap keeps a position, not a stamp on every document (2026-10-11, decision 0028).
--
-- public.doc_probe.checked_at is written once, at a document's first check; after that the lap walks the checked
-- documents in id order from a position kept in public.ingest_state (scope '_takedown'). The index that ordered
-- the old lap by stamp is unread; a small partial index finds the documents never checked yet.
set lock_timeout = '5s';
drop index if exists public.doc_probe_checked_at;
create index if not exists doc_probe_never_checked on public.doc_probe (doc_id) where checked_at is null;
