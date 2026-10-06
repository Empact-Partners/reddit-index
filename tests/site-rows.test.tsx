import { describe, it, expect } from "vitest";
import fixture from "./fixtures-board-rank.json";
import { buildBoards } from "@/lib/data/boards";
import { buildSearchIndex } from "@/lib/data/search-index";
import { byBoardOrder, type BoardRow } from "@/lib/data/board-shapes";
import type { IndexRow } from "@/lib/data/types";
import type { CategorySlug } from "@/lib/generated/categories";

/**
 * The rank on a company page is computed in Python (worker/site_score.py) and stored. The board it points
 * at is ordered here, in TypeScript. The fixture is three real categories with the ranks Python stored
 * (2026-10-02): every company's position on the board built here must be that rank. If the two orderings
 * ever drift (a different tie-break, a different filter), this fails before a reader sees a page that says
 * "#11" beside a board that shows it twelfth.
 */
type Fx = {
  slug: string; name: string; primary_category_slug: string; page_score: number | null;
  page_n_op: number; total_mentions: number; board_rank: number | null; board_size: number;
};
const rows: IndexRow[] = (fixture as Fx[]).map((r) => ({
  slug: r.slug, name: r.name, categorySlug: r.primary_category_slug as CategorySlug,
  score: r.page_score, nOp: r.page_n_op, mentions: r.total_mentions,
}));

describe("boards built from index rows agree with the ranks the sweep stored", () => {
  const boards = buildBoards(rows);
  for (const cat of ["crm", "password-managers", "project-management"]) {
    it(`${cat}: every company sits at its stored rank`, () => {
      const board = boards[cat]?.rows ?? [];
      const mine = (fixture as Fx[]).filter((r) => r.primary_category_slug === cat);
      expect(mine.length).toBeGreaterThan(0);
      expect(board.length).toBe(mine[0]?.board_size);
      for (const r of mine) {
        expect(board.findIndex((b) => b.brandSlug === r.slug) + 1, r.slug).toBe(r.board_rank);
        expect(r.board_size).toBe(board.length);
      }
    });
  }

  it("the pooled board keeps its bar of ten opinionated mentions", () => {
    const all = boards.all ?? { rows: [], total: -1 };
    const pooled = all.rows.map((r) => r.brandSlug);
    const eligible = rows.filter((r) => r.score !== null && r.nOp >= 10).map((r) => r.slug);
    expect(pooled.slice().sort()).toEqual(eligible.slice().sort());
    expect(all.total).toBe(eligible.length);
  });

  it("a company whose category is not published has a page and no board position", () => {
    const stray: IndexRow = { slug: "stray", name: "Stray", categorySlug: null, score: 55, nOp: 40, mentions: 90 };
    const b = buildBoards([...rows, stray]);
    expect(Object.values(b).some((s) => s.rows.some((r) => r.brandSlug === "stray"))).toBe(false);
    expect(buildSearchIndex([stray])).toEqual([{ s: "stray", n: "Stray", c: "", v: 55 }]);
  });
});

describe("byBoardOrder", () => {
  const row = (brandSlug: string, score: number, mentions: number): BoardRow =>
    ({ brandSlug, brandName: brandSlug, score, mentions, categorySlug: "crm" as CategorySlug });

  it("breaks a full tie by plain character order, the order Python's sort uses", () => {
    // '-' (0x2d) sorts before digits and letters in character order; a locale comparison ignores it.
    const tied = [row("ab", 50, 7), row("a-c", 50, 7), row("a1", 50, 7), row("a-b", 50, 7)];
    expect(tied.sort(byBoardOrder).map((r) => r.brandSlug)).toEqual(["a-b", "a-c", "a1", "ab"]);
  });

  it("score first, then mentions", () => {
    const out = [row("low", 40, 900), row("high-few", 60, 3), row("high-many", 60, 30)].sort(byBoardOrder);
    expect(out.map((r) => r.brandSlug)).toEqual(["high-many", "high-few", "low"]);
  });
});
