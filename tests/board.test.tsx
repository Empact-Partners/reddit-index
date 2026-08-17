import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  consolidate, splitScope, scopeToPath, LIST_CAP, PER_LIST,
  type BoardRow,
} from "@/lib/data/board-shapes";
import { IndexBoard } from "@/components/board/index-board";
import type { CategorySlug } from "@/lib/generated/categories";

const row = (i: number, score: number, mentions = 10): BoardRow => ({
  brandSlug: `brand-${String(i).padStart(3, "0")}`,
  brandName: `Brand ${i}`,
  score,
  mentions,
  categorySlug: "crm" as CategorySlug,
});

describe("consolidate", () => {
  it("sorts score descending, mentions breaking ties, deterministically", () => {
    const rows = [row(1, 40, 5), row(2, 80), row(3, 40, 9)];
    expect(consolidate(rows).map((r) => r.brandSlug)).toEqual([
      "brand-002", "brand-003", "brand-001",
    ]);
  });

  // Owner's call 2026-08-16: the full list hides nothing. LIST_CAP is
  // Infinity, so consolidate returns every row in scope, ordered.
  it("returns EVERY row, most loved first — the list is uncapped", () => {
    const rows = Array.from({ length: 3000 }, (_, i) => row(i, 3000 - i));
    const out = consolidate(rows);
    expect(out).toHaveLength(3000);
    expect(out[0]?.score).toBe(3000);          // most loved first
    expect(out[out.length - 1]?.score).toBe(1); // most hated last
  });

  it("keeps both ends if a cap is ever reintroduced", () => {
    expect(LIST_CAP).toBe(Number.POSITIVE_INFINITY);
  });

  it("returns everything for a small scope", () => {
    const rows = Array.from({ length: 150 }, (_, i) => row(i, i));
    expect(consolidate(rows)).toHaveLength(150);
  });
});

describe("splitScope", () => {
  it("splits 1000 rows into disjoint 500/500 with hated reversed", () => {
    const rows = Array.from({ length: 2 * PER_LIST }, (_, i) => row(i, 2 * PER_LIST - i));
    const { loved, hated } = splitScope(rows);
    expect(loved).toHaveLength(PER_LIST);
    expect(hated).toHaveLength(PER_LIST);
    expect(hated[0]?.score).toBe(1); // rank 1 = most hated
    const overlap = new Set(loved.map((r) => r.brandSlug));
    expect(hated.some((r) => overlap.has(r.brandSlug))).toBe(false);
  });

  it("keeps small scopes disjoint via ceil/floor", () => {
    const rows = Array.from({ length: 7 }, (_, i) => row(i, 7 - i));
    const { loved, hated } = splitScope(rows);
    expect(loved).toHaveLength(4);
    expect(hated).toHaveLength(3);
    const overlap = new Set(loved.map((r) => r.brandSlug));
    expect(hated.some((r) => overlap.has(r.brandSlug))).toBe(false);
  });

  it("survives a one-row scope", () => {
    const { loved, hated } = splitScope([row(1, 50)]);
    expect(loved).toHaveLength(1);
    expect(hated).toHaveLength(0);
  });
});

describe("scopeToPath", () => {
  it("always carries the trailing slash", () => {
    expect(scopeToPath("all")).toBe("/");
    expect(scopeToPath("crm" as CategorySlug)).toBe("/crm/");
  });
});

describe("IndexBoard", () => {
  const data = {
    all: { rows: consolidate([row(1, 80), row(2, 60), row(3, 20)]), total: 3 },
    crm: { rows: consolidate([row(4, 90)]), total: 1 },
  };

  it("renders the initial scope's rows synchronously — no effect needed", () => {
    // "use client" still SSRs: what this render shows without any effect
    // running is exactly what the prerendered HTML carries.
    const { container } = render(<IndexBoard data={data} initialScope="all" search={[]} />);
    const t = container.textContent ?? "";
    expect(t).toContain("Most Loved");
    expect(t).toContain("Most Hated");
    expect(t).toContain("Brand 1");
    expect(t).toContain("Brand 3");
  });

  it("links brands to /{slug}/", () => {
    const { container } = render(<IndexBoard data={data} initialScope="all" search={[]} />);
    // Unit renders bypass next.config's trailingSlash rewrite, so accept both
    // forms here; the slugs gate asserts the built shape.
    const hrefs = [...container.querySelectorAll("tbody a")].map((a) => a.getAttribute("href"));
    expect(hrefs.some((h) => h === "/brand-001/" || h === "/brand-001")).toBe(true);
  });

  it("renders a category page's scope preselected", () => {
    const { container } = render(
      <IndexBoard data={data} initialScope={"crm" as CategorySlug} search={[]} />,
    );
    expect(container.textContent).toContain("Brand 4");
    expect(container.textContent).not.toContain("Brand 1");
  });

  it("shows the quiet empty state for a scope with no rows", () => {
    const { container } = render(
      <IndexBoard data={{ all: { rows: [], total: 0 } }} initialScope="all" search={[]} />,
    );
    expect(container.textContent).toContain("No scored brands");
  });
});

describe("search filtering", () => {
  it("keeps a hit's TRUE board position — never renumbers matches 1..n", () => {
    const rows = Array.from({ length: 30 }, (_, i) =>
      ({ ...row(i, 30 - i), brandName: `Brand ${i}` }));
    render(<IndexBoard data={{ all: { rows, total: 30 } }} initialScope="all" search={[]} />);
    const input = screen.getByPlaceholderText("Search companies");
    fireEvent.change(input, { target: { value: "Brand 12" } });
    // Brand 12 is the 13th row of the board; the filtered list must say 13,
    // not 1 — a search that renumbers its hits invents a ranking.
    expect(screen.getByText("13")).toBeTruthy();
  });

  it("restores the full board when the query is cleared", () => {
    const rows = Array.from({ length: 8 }, (_, i) =>
      ({ ...row(i, 8 - i), brandName: `Brand ${i}` }));
    render(<IndexBoard data={{ all: { rows, total: 8 } }} initialScope="all" search={[]} />);
    const input = screen.getByPlaceholderText("Search companies");
    fireEvent.change(input, { target: { value: "Brand 3" } });
    expect(screen.queryByText("Brand 0")).toBeNull();
    fireEvent.change(input, { target: { value: "" } });
    expect(screen.getByText("Brand 0")).toBeTruthy();
  });
});
