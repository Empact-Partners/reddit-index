// @vitest-environment node
import { describe, it, expect, vi } from "vitest";
import fs from "node:fs";
import path from "node:path";

vi.mock("server-only", () => ({}));

/**
 * THE CUTOVER PROOF: the precomputed `site` tables serve the same numbers the old build computed.
 *
 * This runs the OLD read path for real (lib/data/snapshot.ts against the production database, the whole
 * corpus, about 0.2 GB of egress) and compares every company it produced with the dump of the new tables
 * (ops/parity_dump.py). It is skipped unless RI_PARITY_DUMP points at that dump, so `pnpm test` never pays
 * for it. Run it with ops/parity_run.py, once, before the site is switched to the new path.
 *
 * What must match exactly: which companies have a page, every tile (positive, negative, neutral, not yet
 * classified, posts, comments, total), the oldest mention, the per-subreddit table, the score, the number
 * of opinionated mentions behind it, the category board's size, and the rank except where two brands tie
 * on score AND mention count (the old order broke that tie with a locale comparison, the new one with plain
 * character order). Cards are compared only for brands with no new mention since the old rail was built.
 */
const DUMP = process.env.RI_PARITY_DUMP;

type NewRow = {
  slug: string; name: string; primary_category_slug: string | null;
  pos: number; neg: number; neu: number; unlabelled: number; posts: number; comments: number;
  total_mentions: number; oldest_mention: string | null;
  subreddit_stats: Array<{ subreddit: string; total: number; pos: number; neg: number; neu: number; newest: string }>;
  page_score: number | null; page_n_op: number; board_rank: number | null; board_size: number;
  rail_size: number; card_ids: string[]; changed_since_rail: boolean;
};

describe.skipIf(!DUMP)("site tables equal the old build's snapshot", () => {
  it("every company page, every number", async () => {
    const { getSnapshot } = await import("@/lib/data/snapshot");
    const { buildBoards } = await import("@/lib/data/boards");
    const snap = await getSnapshot();
    const boards = buildBoards(snap);
    const fresh = new Map((JSON.parse(fs.readFileSync(DUMP as string, "utf8")) as NewRow[]).map((r) => [r.slug, r]));

    const oldPages = [...snap.companies.values()].filter((c) => c.totalMentions > 0 || c.scores.length > 0);
    const problems: Record<string, string[]> = {
      missing_in_new: [], extra_in_new: [], tiles: [], oldest: [], subreddits: [], score: [], board_size: [],
      rank_unexplained: [], rank_tie_order: [], category: [], cards_unchanged_brand: [], cards_checked: [],
    };
    const oldSlugs = new Set(oldPages.map((c) => c.slug));
    for (const s of fresh.keys()) if (!oldSlugs.has(s)) problems.extra_in_new.push(s);

    for (const co of oldPages) {
      const n = fresh.get(co.slug);
      if (!n) { problems.missing_in_new.push(co.slug); continue; }
      const t = co.sentimentTotals;
      if (t.pos !== n.pos || t.neg !== n.neg || t.neu !== n.neu || co.unlabelled !== n.unlabelled
          || co.docTypeTotals.posts !== n.posts || co.docTypeTotals.comments !== n.comments
          || co.totalMentions !== n.total_mentions || co.pageNOp !== n.page_n_op) {
        problems.tiles.push(co.slug);
      }
      if ((co.oldestMention ?? null) !== (n.oldest_mention ?? null)) problems.oldest.push(co.slug);
      if ((co.primaryCategorySlug ?? null) !== (n.primary_category_slug ?? null)) problems.category.push(co.slug);
      const key = (s: { subreddit: string; total: number; pos: number; neg: number; neu: number; newest: string }) =>
        `${s.subreddit}|${s.total}|${s.pos}|${s.neg}|${s.neu}|${s.newest}`;
      const a = co.subredditStats.map(key).sort().join("\n");
      const b = n.subreddit_stats.map(key).sort().join("\n");
      if (a !== b) problems.subreddits.push(co.slug);
      if ((co.pageScore ?? null) !== (n.page_score ?? null)) problems.score.push(`${co.slug}: ${co.pageScore} vs ${n.page_score}`);

      const rows = co.primaryCategorySlug ? boards[co.primaryCategorySlug]?.rows ?? [] : [];
      const idx = rows.findIndex((r) => r.brandSlug === co.slug);
      const oldRank = idx >= 0 ? idx + 1 : null;
      if (rows.length !== n.board_size) problems.board_size.push(`${co.slug}: ${rows.length} vs ${n.board_size}`);
      if (oldRank !== n.board_rank) {
        const me = idx >= 0 ? rows[idx] : null;
        const tied = me ? rows.filter((r) => r.score === me.score && r.mentions === me.mentions).length : 0;
        const explained = me !== null && n.board_rank !== null && tied > 1 && Math.abs(oldRank! - n.board_rank) < tied;
        (explained ? problems.rank_tie_order : problems.rank_unexplained).push(`${co.slug}: ${oldRank} vs ${n.board_rank}`);
      }
      if (!n.changed_since_rail) {
        problems.cards_checked.push(co.slug);
        const oldIds = co.mentions.map((m) => m.permalink).length;
        if (oldIds !== n.rail_size) problems.cards_unchanged_brand.push(`${co.slug}: ${oldIds} vs ${n.rail_size}`);
      }
    }

    const summary = Object.fromEntries(Object.entries(problems).map(([k, v]) => [k, v.length]));
    const report = { old_pages: oldPages.length, new_pages: fresh.size, summary,
      examples: Object.fromEntries(Object.entries(problems).filter(([k]) => k !== "cards_checked").map(([k, v]) => [k, v.slice(0, 25)])) };
    const out = path.join(path.dirname(DUMP as string), "report.json");
    fs.writeFileSync(out, JSON.stringify(report, null, 1));
    console.log(JSON.stringify(report.summary), "->", out);

    for (const k of ["missing_in_new", "extra_in_new", "tiles", "oldest", "subreddits", "score", "board_size",
                     "rank_unexplained", "category", "cards_unchanged_brand"]) {
      expect(problems[k], k).toEqual([]);
    }
  }, 900_000);
});
