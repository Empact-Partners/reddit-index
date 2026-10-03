-- 0012 — "told the site" and "saw the site serve it" are two facts.
--
-- Measured on a preview, 2026-10-02: making the site re-render one company page costs about 0.2 MB of
-- database egress (its 120 cards), and Vercel renders a page two or three times after an expiry before it
-- settles. Fetching every changed page every night to prove it would be 0.5 to 0.8 GB a day, most of the
-- 1 GB ceiling, to refresh pages nobody may open.
--
-- So the publisher expires every changed path (free) and fetches only the ones that must be proven: every
-- page that lost a card to a takedown, every retired page, the index pages, and a sample. A page that was
-- expired and not fetched re-renders, from current data, the first time someone asks for it.
--
--   expired_hash  the page_hash at which the path was last expired on the site
--   served_hash   the page_hash last SEEN in the served page (unchanged meaning)
alter table site.brand_stats add column if not exists expired_hash text;
alter table site.brand_stats add column if not exists expired_at   timestamptz;
