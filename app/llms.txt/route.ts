import { getRegistry } from "@/lib/routing";
import { getSnapshot } from "@/lib/data/snapshot";
import { buildBoards } from "@/lib/data/boards";
import { SITE_URL } from "@/lib/env";
import { CATEGORY_BY_SLUG, type CategorySlug } from "@/lib/generated/categories";

export const dynamic = "force-static";

/**
 * /llms.txt — the llmstxt.org convention: one plain-text file that tells an
 * AI agent what this site is, how the numbers are made, and where the data
 * lives, without making it infer any of that from rendered HTML.
 *
 * It is generated from the SAME registry and snapshot the pages are built
 * from, so it cannot drift from what is actually published: the category
 * list, the counts and the method version are all read at build time.
 */
export async function GET() {
  const [reg, snap] = await Promise.all([getRegistry(), getSnapshot()]);
  const boards = buildBoards(snap);
  const totalMentions = [...snap.companies.values()]
    .reduce((a, c) => a + c.totalMentions, 0);
  // Ranked = what is actually ON a board. Reading brand_category_scores undercounts by
  // every brand in a category with no mapped scoring subreddits, and post-0011 the boards
  // are built from pageScore rather than those rows.
  const ranked = new Set(
    Object.values(boards).flatMap((b) => b.rows.map((r) => r.brandSlug)),
  ).size;

  const categories = reg.categories
    .map((slug) => {
      const c = CATEGORY_BY_SLUG[slug as CategorySlug];
      // Count what the board SHOWS. cat.scores (brand_category_scores) is empty for any
      // category whose scoring subreddits are not mapped yet, so this shipped
      // "0 companies scored" to LLM crawlers for categories with populated boards.
      const n = boards[slug]?.rows.length ?? 0;
      return `- [${c.name}](${SITE_URL}/${slug}/): ${n} companies scored`;
    })
    .join("\n");

  const body = `# Reddit Brand Index

> An index of the most loved and hated brands on Reddit. Every company is
> scored from real Reddit comments and post bodies — no surveys, no vendor
> submissions, no votes. ${totalMentions.toLocaleString("en-US")} mentions across
> ${reg.categories.length} software categories, ${ranked.toLocaleString("en-US")} companies scored.

## What the score means

The Reddit Love Score is an integer 0-100, published per company per
category. It is the 10th-percentile posterior quantile of a beta-binomial
model over that company's opinionated (positive or negative) mentions,
shrunk toward the category's pooled positive rate computed leave-one-out over
every other company. It is a LOWER BOUND, not a best guess: a company with
little evidence scores low until it earns more, so thin data cannot outrank a
well-measured competitor. Neutral mentions are counted and published but are
not in the denominator. Methodology version ${snap.methodologyVersion}.

A company is ranked in a category once it carries at least ONE opinionated
mention. There is no separate visibility threshold: thin evidence is handled
by the estimator, which shrinks a company with little evidence toward its
category's baseline rather than hiding it. The pooled all-categories board
additionally requires 10 opinionated mentions.

## Key pages

- [Methodology](${SITE_URL}/methodology/): the full method, every parameter, frozen and versioned
- [Index](${SITE_URL}/): most loved and most hated across all categories

## Categories

${categories}

## Notes for agents

- Every company page lists its individual mentions with permalinks to the
  original Reddit comments. Numbers on this site are checkable at the source.
- Reddit vote counts are deliberately ignored; a mention is one observation
  regardless of its score.
- Sentiment is assigned per (mention, company) pair: one comment naming three
  products yields three independent observations.
`;
  return new Response(body, {
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "public, max-age=3600",
    },
  });
}
