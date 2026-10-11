# 0028 — The takedown check remembers a position, not a stamp on every document

Date: 2026-10-11. Status: accepted (the commission: full speed under the egress line; decision 0002's condition kept).

## Context

Every night the takedown check asks Reddit about every document shown on a page (about 115,000) and, with the calls
left, about 85,000 of the documents shown nowhere, longest unchecked first. To keep that order it stamped each one
it had checked (`public.doc_probe.checked_at`): 85,000 scattered row updates a night, none of them a HOT update
because the stamp was indexed. Read from the statement statistics: 1,696,458 stamps since 3 Oct wrote 817 MB of
write-ahead log (41 MB a night), and they rewrite most of the table's 130 MB every night, which the 11:15 UTC
backup ships again (decision 0025).

## Decision

1. Documents on a page: unchanged, every night, first.
2. **Documents never checked before** (stored since the last run, shown nowhere): next, all of them up to the
   night's room, as before. A comment is likeliest to be deleted in its first days. Each is stamped once, at this
   first check.
3. **The slow lap**: the documents already checked at least once, in document-id order from a saved position, round
   and round. Nothing is stamped; the position is one row (`public.ingest_state`, scope `_takedown`) and moves
   only after the night's purge, to the last document of the unbroken run Reddit answered. A batch Reddit did not
   answer stops the position there, so its documents are asked again the next night, not a lap later.

Migration 0037 drops the index on the stamp and adds a small partial index over the never-checked documents.

## Not changed

What counts as gone or edited, the purge, the ledger, the brake, the proof on the served page before a takedown's
receipt is stamped. The lap covers the same documents at the same rate: 896,704 documents shown nowhere on 11 Oct,
85,000 a night less the night's new ones.

## Checked before it runs

Read-only against the database on 11 Oct: 69,877 documents never checked and off every page (1.6 s to list),
then 15,123 from the lap (0.2 s), no document in both; from the last document the lap wraps to the first.

## How it is judged

The first night on it: `never_checked_before`, `first_checks_stamped` and `slow_lap` (from, to, documents) on the
receipt; the takedown stage's log against 121.7 MB on 11 Oct; the same documents checked (200,000).
