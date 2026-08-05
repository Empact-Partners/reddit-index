-- Assertions that must return ZERO rows. Run after every load.
-- BUILD-PROMPT's gates, plus the ones the specification implies and never names.

-- 1. Vendor-named subreddits contributed zero SCORING mentions.
--    The insert trigger already makes this structurally impossible; this is the
--    data-level proof, and __selftest__ proves the trigger fires.
select 'vendor sub in scoring mentions' as assertion, s.name, count(*) as n
from mentions m join subreddits s on s.id = m.subreddit_id
where s.is_vendor_sub group by 1, 2

union all
-- 2. Hostile-rule subreddits contributed zero scoring mentions.
select 'hostile sub in scoring mentions', s.name, count(*)
from mentions m join subreddits s on s.id = m.subreddit_id
where s.rule_posture = 'hostile' group by 1, 2

union all
-- 3. No (brand, document) pair appears twice. The partition key forces a
--    three-column primary key, so the two-column uniqueness the spec asked for
--    is asserted rather than enforced.
-- Group by BOTH columns. Grouping by doc_id alone fires on the correct case:
-- one comment naming three products is three mentions with three brand_ids,
-- which is the whole point of targeted ABSA. An assertion that fires on good
-- data gets muted, and a muted assertion protects nothing.
select 'duplicate (brand_id, doc_id)', m.doc_id || ':' || m.brand_id, count(*)
from mentions m group by 1, 2 having count(*) > 1

union all
-- 4. A purged row whose page was never revalidated is an open defect: the
--    cached page keeps serving a comment its author deleted.
select 'purged but not revalidated', doc_id, 1
from removals where purged_at is not null and revalidated_at is null

union all
-- 5. Every permalink is a real Reddit URL, copied from the API rather than
--    reconstructed from a title slug.
select 'malformed permalink', permalink, 1
from mentions
where permalink !~ '^https://www\.reddit\.com/r/[A-Za-z0-9_]+/comments/[a-z0-9]+'

union all
-- 6. No mention is attributed to a deleted author. A quote needs its source.
select 'deleted author', doc_id, 1 from mentions where author in ('[deleted]', '')

union all
-- 7. An eligible score must carry an interval. decisions/0005 ships the
--    superlative on the condition that the measured variable appears with it.
select 'eligible score with no interval', b.slug, 1
from brand_category_scores s join brands b on b.id = s.brand_id
where s.eligible and (s.ci_low is null or s.ci_high is null or s.reddit_love_score is null)

union all
-- 8. An ineligible score must name the test it failed, with both numbers.
select 'ineligible score with no named test', b.slug, 1
from brand_category_scores s join brands b on b.id = s.brand_id
where not s.eligible
  and (s.failed_test is null or s.failed_observed is null or s.failed_required is null)

union all
-- 9. A published score must never come from a category below its own viability
--    test. That state has different wording and a different page.
select 'ranked brand in an unrankable category', c.slug, 1
from brand_category_scores s
join categories c on c.id = s.category_id
where s.eligible and (
  select count(*) from category_subreddits cs
  where cs.category_id = c.id and cs.is_scoring) < 5;
