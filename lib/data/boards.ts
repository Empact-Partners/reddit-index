import "server-only";
import type { Snapshot, BrandScore } from "./types";
import { consolidate, type BoardData, type BoardRow, type Scope } from "./board-shapes";

/**
 * Snapshot -> the board dataset the homepage ships: one capped, ordered list
 * per scope ("all" + each category).
 *
 * Display floor: a computed score and at least MIN_N_OP opinionated mentions.
 * The n_eff eligibility gates stay in the database and on company pages; they
 * no longer decide whether a brand APPEARS — an index that renders empty
 * because its own bar is set at 600 shows nothing to anyone.
 */

const MIN_N_OP = 3;
/** The pooled boards call a brand most-loved/most-hated ACROSS the whole
 *  index — that claim needs more than three annoyed comments
 *  (docs/methodology-review.md §2). */
const MIN_N_OP_POOLED = 10;

function toRow(s: BrandScore): BoardRow {
  return {
    brandSlug: s.brandSlug,
    brandName: s.brandName,
    score: s.redditLoveScore as number,
    mentions: s.n,
    categorySlug: s.categorySlug,
  };
}

export function buildBoards(snap: Snapshot): BoardData {
  const floored = snap.categories
    .flatMap((c) => c.scores)
    .filter((s) => s.redditLoveScore !== null && s.nOp >= MIN_N_OP);

  const data: BoardData = {};

  for (const c of snap.categories) {
    const mine = floored.filter((s) => s.categorySlug === c.slug);
    data[c.slug satisfies Scope] = {
      rows: consolidate(mine.map(toRow)),
      total: mine.length,
    };
  }

  // "All Categories" ranks BRANDS, not (brand x category) rows: a brand scored
  // in two categories appears once, through the row with the most opinionated
  // mentions — its home turf, not its best look.
  const best = new Map<string, BrandScore>();
  for (const s of floored.filter((x) => x.nOp >= MIN_N_OP_POOLED)) {
    const prev = best.get(s.brandSlug);
    if (
      !prev
      || s.nOp > prev.nOp
      || (s.nOp === prev.nOp && (s.redditLoveScore ?? 0) > (prev.redditLoveScore ?? 0))
      || (s.nOp === prev.nOp && s.redditLoveScore === prev.redditLoveScore
          && s.categorySlug.localeCompare(prev.categorySlug) < 0)
    ) {
      best.set(s.brandSlug, s);
    }
  }
  const pooled = [...best.values()];
  data["all" satisfies Scope] = {
    rows: consolidate(pooled.map(toRow)),
    total: pooled.length,
  };

  return data;
}
