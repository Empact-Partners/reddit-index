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
/** The pooled boards call a brand most-loved/most-hated ACROSS the whole
 *  index — that claim needs more than a handful of comments. Vlad revisited
 *  this on 2026-08-16 after seeing 1-mention brands ranked beside 800-mention
 *  brands and retracted the show-everyone experiment in his own words ("I
 *  shouldn't have told it to display all the companies — that is wrong"):
 *  strict thresholds everywhere. A brand below the bar appears on NO board;
 *  it stays reachable through search and its own page. */
const MIN_N_OP_POOLED = 10;

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

/**
 * The Mentions column shows the brand's TOTAL collected mentions — the same
 * number its company page headlines — not the scoring-window count. Vlad's
 * ruling (2026-08-16), after catching Raklet showing 3 in the list and 6 on
 * its page: "total collected everywhere; the mentions used for the
 * calculation are behind the scenes — viewers don't need to know."
 */
function toRow(s: BrandScore, totalOf: Map<string, number>): BoardRow {
  return {
    brandSlug: s.brandSlug,
    brandName: s.brandName,
    score: s.redditLoveScore as number,
    mentions: totalOf.get(s.brandSlug) ?? s.n,
    categorySlug: s.categorySlug,
  };
}

export function buildBoards(snap: Snapshot): BoardData {
  const thresholds = buildThresholds(snap);
  const totalOf = new Map<string, number>(
    [...snap.companies.values()].map((c) => [c.slug, c.totalMentions]));
  const floored = snap.categories
    .flatMap((c) => c.scores)
    // A brand must carry at least as much opinionated evidence as the TYPICAL
    // brand in its category (the median, clamped [3,30]) to be ranked there.
    .filter((s) => s.redditLoveScore !== null
      && s.nOp >= (thresholds.get(s.categorySlug) ?? THRESHOLD_FLOOR));

  const data: BoardData = {};

  for (const c of snap.categories) {
    const mine = floored.filter((s) => s.categorySlug === c.slug);
    data[c.slug satisfies Scope] = {
      rows: consolidate(mine.map((r) => toRow(r, totalOf))),
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
    rows: consolidate(pooled.map((r) => toRow(r, totalOf))),
    total: pooled.length,
  };

  return data;
}
