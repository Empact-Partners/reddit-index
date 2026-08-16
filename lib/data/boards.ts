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

/** No category ever ranks a company on fewer than this many opinions. */
export const THRESHOLD_FLOOR = 3;
/** …nor demands more than this, however loud the category is. */
export const THRESHOLD_CEIL = 30;
/**
 * Owner's call, 2026-08-16: every scored company appears, on every board.
 *
 * This bar was 10 opinionated mentions for the pooled board, and the
 * per-category median for the category boards. Together they hid most of the
 * index: 793 of ~3,000 companies on the home list, 34 of 67 on /web-hosting.
 *
 * They are safe to drop BECAUSE of methodology 2.2.0. The bars existed to
 * stop thin evidence ranking high — under the old posterior MEAN a brand
 * with four opinions was pulled up toward the category average (shift4, 0
 * positives out of 4, published 40 above PayPal). The published score is now
 * the posterior LOWER BOUND, which moves the other way: thin evidence lands
 * low on its own, so a company can be listed without being flattered. The
 * threshold is still computed and still published as evidence on the page.
 */
const MIN_N_OP_POOLED = 1;

/**
 * Each category's own bar, derived from its own evidence.
 *
 * The published threshold is the MEDIAN opinionated-mention count across the
 * brands tracked in that category, clamped to [3, 30]: a company must carry at
 * least as much evidence as the typical brand it is being ranked against.
 *
 * This replaces two broken things. The `n_eff` gate that /methodology
 * described admitted 10 of 2,056 rows and was never consulted by any
 * component, and the 86-of-100 category tiers behind it were a hardcoded
 * default derived from three-year CATEGORY comment flow, never from per-brand
 * evidence. A median is self-calibrating: a category whose typical brand has
 * forty opinions demands more than one whose typical brand has four, and the
 * floor keeps thin categories publishable rather than empty.
 *
 * n_eff is not deleted — it stops deciding visibility and becomes what it is
 * actually good for, the precision claim attached to a published number.
 */
export function buildThresholds(snap: Snapshot): Map<string, number> {
  return new Map(snap.categories.map((c) => [c.slug, c.threshold]));
}

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
  const thresholds = buildThresholds(snap);
  const floored = snap.categories
    .flatMap((c) => c.scores)
    // one opinionated mention is enough to be LISTED; the lower-bound score
    // decides where. See MIN_N_OP_POOLED above for why this is no longer the
    // safety mechanism it once was.
    .filter((s) => s.redditLoveScore !== null && s.nOp >= 1);

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
