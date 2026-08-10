import type { CategorySlug } from "@/lib/generated/categories";
import type { Mention } from "@/components/data/mention-card";

/**
 * The shapes the reader path works in. Everything here is DERIVED and computed
 * by the daily pass — nothing is calculated in a React component, and no rank
 * is ever derived on the client (16-design-system.md §5).
 */

/** Named exactly as the method names them, so a reader can follow one word from
 *  the page to /methodology to the SQL. */
export type FailedTest =
  | "n_eff"           // the category-scaled eligibility gate
  | "authors"         // >= 50 distinct authors
  | "subreddits"      // >= 5 distinct subreddits
  | "thread_share"    // <= 20% of n from one thread
  | "author_share";   // <= 5%  of n from one author

export const FAILED_TEST_LABEL: Record<FailedTest, string> = {
  n_eff: "effective sample size",
  authors: "distinct authors",
  subreddits: "distinct subreddits",
  thread_share: "share from a single thread",
  author_share: "share from a single author",
};

export type BrandScore = {
  brandSlug: string;
  brandName: string;
  categorySlug: CategorySlug;

  // The two headline metrics. Everything else is evidence.
  redditLoveScore: number | null;   // null while ineligible — a gate, not a flag
  n: number;                        // all eligible mentions

  // Evidence, all published, behind a disclosure.
  nOp: number;                      // pos + neg, the estimator's denominator
  nEff: number;
  deff: number;
  pos: number; neg: number; neu: number; abstain: number;
  neutralShare: number;
  abstainShare: number;
  polarization: number | null;
  ciLow: number | null;
  ciHigh: number | null;
  nAuthors: number;
  nSubreddits: number;
  nThreads: number;                 // published evidence, NOT a floor
  maxThreadShare: number;
  maxAuthorShare: number;
  maxSubredditShare: number;        // published evidence; see HANDOFF

  rankDesc: number | null;
  rankAsc: number | null;
  tiedWith: string[];

  eligible: boolean;
  /** Named, with both numbers, whenever eligible is false. A badge hiding its
   *  number is not shippable. */
  failedTest: FailedTest | null;
  failedObserved: string | null;
  failedRequired: string | null;

  windowStart: string;
  windowEnd: string;
};

export type CategoryView = {
  slug: CategorySlug;
  name: string;
  tier: "deep" | "standard" | "thin";
  precisionPp: number;
  nMin: number;
  /**
   * A category is rankable when its own viability test passes: at least five
   * SCORING subreddits. This is a different state from a brand being below
   * threshold, and the two never share wording.
   */
  rankable: boolean;
  scoringSubreddits: number;
  requiredSubreddits: number;
  baseRate: number | null;
  lastUpdated: string | null;
  scores: BrandScore[];
};

/** Per-subreddit sentiment breakdown — the dashboard's ledger rows. */
export type SubredditStat = {
  subreddit: string;
  total: number;
  pos: number;
  neg: number;
  neu: number;      // neu + abstain folded together for display
  newest: string;   // ISO date of the newest mention in this subreddit
};

export type CompanyView = {
  slug: string;
  name: string;
  primaryCategorySlug: CategorySlug | null;
  scores: BrandScore[];
  mentions: Mention[];
  /** TRUE full mention count from the aggregates, not the score-window n. */
  totalMentions: number;
  sentimentTotals: { pos: number; neg: number; neu: number };
  subredditStats: SubredditStat[];
};

export type Snapshot = {
  categories: CategoryView[];
  companies: Map<string, CompanyView>;
  methodologyVersion: string;
  generatedAt: string;
};
