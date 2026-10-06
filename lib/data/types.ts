import type { CategorySlug } from "@/lib/generated/categories";
import type { Mention } from "@/components/data/mention-card";

/**
 * The shapes the reader path works in. Everything here is computed by the daily sweep and stored in the
 * `site` schema (supabase/migrations/0007); nothing is calculated in a React component, and no rank is
 * ever derived on the client (16-design-system.md §5).
 */

/** Per-subreddit sentiment breakdown — the dashboard's ledger rows. */
export type SubredditStat = {
  subreddit: string;
  total: number;
  pos: number;
  neg: number;
  neu: number;      // neu + abstain + not yet classified, folded together for display
  newest: string;   // ISO date of the newest mention in this subreddit
};

export type CompanyView = {
  slug: string;
  name: string;
  primaryCategorySlug: CategorySlug | null;
  /** The Reddit love score: the estimator over ALL of the brand's collected opinionated mentions (the
   *  page's own Positive and Negative tiles), with a leave-one-out category prior (decisions/0011,
   *  worker/numerics.py). Null only when the brand has no mention at all. */
  pageScore: number | null;
  /** Opinionated mentions behind pageScore (positive + negative, all-time). The bar the pooled
   *  "All Categories" board applies. */
  pageNOp: number;
  mentions: Mention[];
  /** The full mention count, not the number of cards shown. */
  totalMentions: number;
  sentimentTotals: { pos: number; neg: number; neu: number };
  /** Post/comment split over everything collected — the numbers on the type filter. Never derived from
   *  `mentions`, which is a window. */
  docTypeTotals: { posts: number; comments: number };
  /** Mentions with no sentiment label yet. Folded into "neutral" for display, counted here so the page
   *  can say when that fold is large enough to distort the bar. */
  unlabelled: number;
  /** ISO date of the OLDEST mention held for this company. */
  oldestMention: string | null;
  /** How many cards the page carries (at most 80 comments + 40 posts, newest first). */
  railSize: number;
  /** decisions/0020: mentions found by the closer, real-time watch Empact runs for its Reddit clients (at most 60,
   *  newest first). Shown in their own section and counted in NOTHING above: not the score, the totals, the
   *  subreddit table or the rank. Empty for every company that is not watched. */
  watchMentions?: Mention[];
  subredditStats: SubredditStat[];
};

/** One company as the boards, the search box, the sitemap and llms.txt see it. */
export type IndexRow = {
  slug: string;
  name: string;
  /** Null when the brand's primary category is not published: it has a page and no board position. */
  categorySlug: CategorySlug | null;
  score: number | null;
  nOp: number;
  mentions: number;
};

export type SiteMeta = {
  /** When the last successful daily sweep finished: the freshness date the site shows. */
  lastSuccessAt: string | null;
  newestMention: string | null;
  boardsHash: string;
  slugsHash: string;
};
