-- Retention step 4 (docs/retention.md): published.mention_rail reads the site's cards, and the old site's
-- materialised view goes.
--
-- Nothing has refreshed public.mention_rail_mv since the read path went live (2026-10-06; only the retired
-- worker/publish.py did), so published.mention_rail served the cards of the last old-site build. site.rail_card is
-- what every page shows now, kept current by the nightly sweep, and it follows the one-copy text pointer
-- (migration 0019). Same twelve columns, same names and types, so the view keeps its grants (site_reader).
-- Frees about 220 MB.
create or replace view published.mention_rail as
 select brand_slug, brand_name, subreddit, doc_id, doc_type, thread_id, author, created_utc, permalink, body,
        matched_form, label
   from site.rail_card;

drop materialized view public.mention_rail_mv;

-- the function that rebuilt it (called only by the retired worker/publish.py) would now fail on every call
drop function public.refresh_mention_rail(boolean);
