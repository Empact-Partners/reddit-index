"use client";

import { useState } from "react";
import {
  scopeToPath, splitScope,
  type BoardData, type Scope, type ScopeBoard,
} from "@/lib/data/board-shapes";
import { CategorySelect } from "./category-select";
import { ViewSwitcher, type BoardView } from "./view-switcher";
import { BoardTable } from "./board-table";
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
}: {
  data: BoardData;
  initialScope: Scope;
}) {
  const [scope, setScope] = useState<Scope>(initialScope);
  const [view, setView] = useState<BoardView>("boards");

  const board: ScopeBoard = data[scope] ?? { rows: [], total: 0 };
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
    <div className="mt-10">
      <div className="board-controls">
        <CategorySelect value={scope} onChange={changeScope} />
        <ViewSwitcher value={view} onChange={setView} />
      </div>

      {board.rows.length === 0 ? (
        <p className="mt-12" style={{ fontSize: "var(--fs-body)" }}>
          No scored brands in this category yet.
        </p>
      ) : view === "boards" ? (
        <div className="mt-12 grid gap-12 md:grid-cols-2 items-start">
          <section className="board-col" data-tone="loved">
            <h2 className="board-head">Most Loved</h2>
            <BoardTable
              rows={loved}
              tone="loved"
              showCategory={showCategory}
              caption={`Most loved brands, ${scopeName}`}
            />
          </section>
          <section className="board-col" data-tone="hated">
            <h2 className="board-head">Most Hated</h2>
            <BoardTable
              rows={hated}
              tone="hated"
              showCategory={showCategory}
              caption={`Most hated brands, ${scopeName}`}
            />
          </section>
        </div>
      ) : (
        <div className="mt-12">
          <BoardTable
            rows={board.rows}
            tone="neutral"
            showCategory={showCategory}
            caption={`All ranked brands, ${scopeName}, most loved first`}
            total={board.total}
          />
        </div>
      )}
    </div>
  );
}
