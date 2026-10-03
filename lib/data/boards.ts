import type { IndexRow } from "./types";
import { CATEGORIES } from "@/lib/generated/categories";
import { consolidate, type BoardData, type BoardRow, type Scope } from "./board-shapes";

/**
 * Index rows -> the board dataset: one ordered list per scope ("all" + each category).
 *
 * EVERY SCORED BRAND IS RANKED IN ITS CATEGORY (Vlad, 2026-08-19, decisions/0011). A company page that
 * publishes a Reddit love score and no position was half an answer: "your score, and where you sit in your
 * category" is one sentence, not two. So a brand appears on its primary category's board whenever it has a
 * score, and its score is the one its own page shows — computed over every opinionated mention collected
 * for it, the same corpus as the Positive and Negative tiles beside it.
 *
 * Thin evidence is handled by the estimator, not by a visibility gate. The published number is the 0.10
 * posterior quantile under a leave-one-out category prior, so one positive comment buys a brand a mid-table
 * position near its category's baseline, never the top (worker/numerics.py).
 *
 * The pooled "All Categories" board is NOT everyone. Vlad retracted a show-everyone experiment there on
 * 2026-08-16 in his own words ("I shouldn't have told it to display all the companies -- that is wrong")
 * after seeing one-mention brands ranked beside 800-mention brands. So the pooled board keeps its bar.
 *
 * The order is board-shapes.ts's byBoardOrder, and it is the SAME order worker/site_score.py uses to store
 * each company's rank, so a company page and the board it points at cannot disagree.
 */

/** The pooled board's bar: opinionated mentions before a brand can be called most-loved or most-hated
 *  across the whole index. */
const MIN_N_OP_POOLED = 10;

/**
 * The Mentions column shows the brand's TOTAL collected mentions -- the same number its company page
 * headlines. Vlad's ruling (2026-08-16), after catching Raklet showing 3 in the list and 6 on its page:
 * "total collected everywhere; the mentions used for the calculation are behind the scenes."
 */
function toRow(r: IndexRow): BoardRow {
  return {
    brandSlug: r.slug,
    brandName: r.name,
    score: r.score as number,
    mentions: r.mentions,
    categorySlug: r.categorySlug as BoardRow["categorySlug"],
  };
}

export function buildBoards(rows: IndexRow[]): BoardData {
  const scored = rows.filter((r) => r.score !== null && r.categorySlug !== null);

  const byCategory = new Map<string, IndexRow[]>();
  for (const r of scored) {
    const list = byCategory.get(r.categorySlug as string);
    if (list) list.push(r); else byCategory.set(r.categorySlug as string, [r]);
  }

  const data: BoardData = {};
  for (const c of CATEGORIES) {
    // A brand is ranked in its PRIMARY category: the one its own page names in its breadcrumb and its
    // rank tile. One brand, one position, one number a reader can check on both pages.
    const mine = byCategory.get(c.slug) ?? [];
    data[c.slug satisfies Scope] = { rows: consolidate(mine.map(toRow)), total: mine.length };
  }

  const pooled = scored.filter((r) => r.nOp >= MIN_N_OP_POOLED);
  data["all" satisfies Scope] = { rows: consolidate(pooled.map(toRow)), total: pooled.length };

  return data;
}
