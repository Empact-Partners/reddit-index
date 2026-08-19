import "server-only";
import type { Snapshot, CompanyView } from "./types";
import { consolidate, type BoardData, type BoardRow, type Scope } from "./board-shapes";

/**
 * Snapshot -> the board dataset: one ordered list per scope ("all" + each
 * category).
 *
 * EVERY SCORED BRAND IS RANKED IN ITS CATEGORY (Vlad, 2026-08-19,
 * decisions/0011). A company page that publishes a Reddit love score and no
 * position was half an answer: "your score, and where you sit in your
 * category" is one sentence, not two. So a brand appears on its primary
 * category's board whenever it has a score, and its score is the one its own
 * page shows — computed over every opinionated mention collected for it, the
 * same corpus as the Positive and Negative tiles beside it.
 *
 * Thin evidence is handled by the estimator, not by a visibility gate. The
 * published number is the 0.10 posterior quantile under a leave-one-out
 * category prior, so one positive comment buys a brand a mid-table position
 * near its category's baseline, never the top: sparse evidence costs position
 * instead of buying it (score.py, methodology 2.2.0). That is what makes it
 * safe to rank everyone here, where a raw mean would not have been.
 *
 * The pooled "All Categories" board is NOT everyone. Vlad retracted a
 * show-everyone experiment there on 2026-08-16 in his own words ("I shouldn't
 * have told it to display all the companies -- that is wrong") after seeing
 * one-mention brands ranked beside 800-mention brands. Claiming a brand is the
 * most loved on Reddit OVERALL is a different claim from placing it inside its
 * own category, so the pooled board keeps its bar.
 */

/** The pooled board's bar: opinionated mentions before a brand can be called
 *  most-loved or most-hated across the whole index. */
const MIN_N_OP_POOLED = 10;

/**
 * The Mentions column shows the brand's TOTAL collected mentions -- the same
 * number its company page headlines. Vlad's ruling (2026-08-16), after
 * catching Raklet showing 3 in the list and 6 on its page: "total collected
 * everywhere; the mentions used for the calculation are behind the scenes."
 */
function toRow(c: CompanyView): BoardRow {
  return {
    brandSlug: c.slug,
    brandName: c.name,
    score: c.pageScore as number,
    mentions: c.totalMentions,
    categorySlug: c.primaryCategorySlug as BoardRow["categorySlug"],
  };
}

export function buildBoards(snap: Snapshot): BoardData {
  const scored = [...snap.companies.values()]
    .filter((c) => c.pageScore !== null && c.primaryCategorySlug !== null);

  const data: BoardData = {};
  for (const c of snap.categories) {
    // A brand is ranked in its PRIMARY category: the one its own page names in
    // its breadcrumb and its rank tile. One brand, one position, one number a
    // reader can check on both pages.
    const mine = scored.filter((x) => x.primaryCategorySlug === c.slug);
    data[c.slug satisfies Scope] = {
      rows: consolidate(mine.map(toRow)),
      total: mine.length,
    };
  }

  const pooled = scored.filter((c) => c.pageNOp >= MIN_N_OP_POOLED);
  data["all" satisfies Scope] = {
    rows: consolidate(pooled.map(toRow)),
    total: pooled.length,
  };

  return data;
}
