import type { CategorySlug } from "@/lib/generated/categories";

/**
 * The board's shapes and pure logic — importable from both the server build
 * step and the client component, so the two views can never disagree about
 * what a scope contains.
 *
 * ONE ordering per scope is shipped: the consolidated list, score descending,
 * capped at LIST_CAP. The two-table view is DERIVED from it by splitScope, so
 * "Most Loved" and "Most Hated" are provably opposite ends of the same list
 * and provably disjoint.
 */

export type Scope = "all" | CategorySlug;

export type BoardRow = {
  brandSlug: string;
  brandName: string;
  /** Reddit Love Score, integer 0-100. */
  score: number;
  /** Number of mentions (n) inside the scoring window. */
  mentions: number;
  categorySlug: CategorySlug;
};

export type ScopeBoard = {
  /** Consolidated ordering, score descending, capped (see consolidate). */
  rows: BoardRow[];
  /** How many brands the scope holds BEFORE the cap, so a truncated list can
   *  say what it dropped instead of implying completeness. */
  total: number;
};

export type BoardData = Record<string, ScopeBoard>;

export const PER_LIST = 100;
export const LIST_CAP = 200;

/** Score descending; mentions break ties; slug makes it deterministic. */
export function byBoardOrder(a: BoardRow, b: BoardRow): number {
  return (b.score - a.score) || (b.mentions - a.mentions)
    || a.brandSlug.localeCompare(b.brandSlug);
}

/**
 * The single-list view: everything when N <= 200, else the top 100 and the
 * bottom 100 — both ends survive truncation, because a list whose bottom is
 * "the 200th most loved" has no Most Hated end at all.
 */
export function consolidate(rows: BoardRow[]): BoardRow[] {
  const sorted = [...rows].sort(byBoardOrder);
  if (sorted.length <= LIST_CAP) return sorted;
  return [...sorted.slice(0, PER_LIST), ...sorted.slice(-PER_LIST)];
}

/**
 * The two-table view, derived from the consolidated ordering. Loved takes the
 * top, Hated takes the bottom reversed (rank 1 = most hated). ceil/floor keeps
 * the two lists disjoint for any N, so a 10-brand category shows 5 and 5 —
 * never the same brand on both sides.
 */
export function splitScope(rows: BoardRow[]): { loved: BoardRow[]; hated: BoardRow[] } {
  const lovedN = Math.min(PER_LIST, Math.ceil(rows.length / 2));
  const hatedN = Math.min(PER_LIST, Math.floor(rows.length / 2));
  return {
    loved: rows.slice(0, lovedN),
    hated: rows.slice(rows.length - hatedN).reverse(),
  };
}

/** The one place a scope becomes a URL. trailingSlash: true — the slash is
 *  load-bearing, a bare path 308s on the next hard navigation. */
export function scopeToPath(scope: Scope): string {
  return scope === "all" ? "/" : `/${scope}/`;
}
