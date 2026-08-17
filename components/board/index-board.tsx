"use client";

import { useState } from "react";
import {
  scopeToPath, splitScope,
  type BoardData, type Scope, type ScopeBoard,
} from "@/lib/data/board-shapes";
import { CategorySelect } from "./category-select";
import { ViewSwitcher, type BoardView } from "./view-switcher";
import { BoardTable } from "./board-table";
import { BrandSearch } from "./brand-search";
import type { SearchEntry } from "@/lib/data/search-index";
import { CATEGORY_BY_SLUG, type CategorySlug } from "@/lib/generated/categories";

/**
 * The whole index, one client component. Every scope's data arrives as props at
 * build time, so the default scope is in the prerendered HTML (this component
 * SSRs like any other) and switching is a setState — no navigation, no fetch.
 *
 * State comes ONLY from props, never from window.location: reading the URL
 * during render would tear hydration. The URL is written back on change via
 * history.replaceState, which Next keeps in sync with its router.
 */
export function IndexBoard({
  data,
  initialScope,
  search,
}: {
  data: BoardData;
  initialScope: Scope;
  search: SearchEntry[];
}) {
  const [scope, setScope] = useState<Scope>(initialScope);
  const [view, setView] = useState<BoardView>("boards");
  const [query, setQuery] = useState("");

  const full: ScopeBoard = data[scope] ?? { rows: [], total: 0 };
  // Typing filters the ranking in place. Ranks are NOT recomputed: a filtered
  // row keeps the position it holds on the real board, because a search that
  // renumbers its hits to 1..n is inventing a ranking nobody can check.
  const q = query.trim().toLowerCase();
  const hits = q
    ? full.rows
        .map((r, i) => ({ ...r, trueRank: i + 1 }))
        .filter((r) => r.brandName.toLowerCase().includes(q)
          || r.brandSlug.includes(q))
    : [];
  const board: ScopeBoard = q ? { rows: hits, total: full.total } : full;
  const showCategory = scope === "all";
  const scopeName = scope === "all"
    ? "All Categories"
    : CATEGORY_BY_SLUG[scope as CategorySlug].name;

  function changeScope(next: Scope) {
    setScope(next);
    window.history.replaceState(null, "", scopeToPath(next));
  }

  const { loved, hated } = splitScope(board.rows);

  return (
    <>
      <div className="bleed controls-band">
        <div className="board-controls">
          <BrandSearch index={search} query={query} onQueryChange={setQuery} />
          <CategorySelect value={scope} onChange={changeScope} />
          <ViewSwitcher value={view} onChange={setView} />
        </div>
      </div>

      {board.rows.length === 0 ? (
        <p className="mt-14 text-center" style={{ fontSize: "var(--fs-body)" }}>
          {q
            ? `No ranked company matches “${query.trim()}” in ${scopeName}.`
            : "No scored brands in this category yet."}
        </p>
      ) : q ? (
        /* A search shows ONE list of matches with their real board positions.
           Splitting a handful of hits into "most loved" and "most hated"
           halves would label a brand by where it fell among its own search
           results rather than on the board. */
        <div className="board-grid" data-view="list">
          <section className="board-card" data-tone="neutral"
                   aria-label={`Search results in ${scopeName}`}>
            <h2>
              {board.rows.length} {board.rows.length === 1 ? "match" : "matches"}
              {" in "}{scopeName}
            </h2>
            <BoardTable
              rows={board.rows}
              tone="neutral"
              showCategory={showCategory}
              caption={`Companies matching ${query.trim()} in ${scopeName}`}
            />
          </section>
        </div>
      ) : view === "boards" ? (
        <div className="board-bleed">
        <div className="board-grid">
          <section className="board-card" data-tone="loved" aria-label={`Most loved, ${scopeName}`}>
            <h2>Most Loved</h2>
            <BoardTable
              rows={loved}
              tone="loved"
              showCategory={showCategory}
              caption={`Most loved brands, ${scopeName}`}
            />
          </section>
          <section className="board-card" data-tone="hated" aria-label={`Most hated, ${scopeName}`}>
            <h2>Most Hated</h2>
            <BoardTable
              rows={hated}
              tone="hated"
              showCategory={showCategory}
              caption={`Most hated brands, ${scopeName}`}
            />
          </section>
        </div>
        </div>
      ) : (
        <div className="board-grid" data-view="list">
          <section className="board-card" data-tone="neutral" aria-label={`Full list, ${scopeName}`}>
            <h2>Most Loved to Most Hated</h2>
            <BoardTable
              rows={board.rows}
              tone="neutral"
              showCategory={showCategory}
              caption={`All ranked brands, ${scopeName}, most loved first`}
              total={board.total}
            />
          </section>
        </div>
      )}
    </>
  );
}
