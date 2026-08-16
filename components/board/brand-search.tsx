"use client";

import { useId, useMemo, useRef, useState } from "react";
import { searchCompanies, type SearchEntry } from "@/lib/data/search-index";

/**
 * Find any company in the index by name.
 *
 * This sits in the controls band beside the category select because the
 * boards cap every scope at 200 rows: browsing reaches a few hundred of the
 * ~3,000 ranked companies, and search is the only way to the rest. It
 * therefore searches the WHOLE index, never the current scope.
 *
 * Navigation is a router push to "/<slug>" — the same route the boards link
 * to — and the list is built from the route registry's own predicate, so a
 * result can never 404.
 *
 * Keyboard: ArrowUp/Down move, Enter opens, Escape closes. The input owns
 * aria-activedescendant so a screen reader announces the highlighted row
 * rather than silently moving focus.
 */
export function BrandSearch({
  index,
  query: q,
  onQueryChange: setQ,
}: {
  index: SearchEntry[];
  /** Lifted to IndexBoard: the same query filters the visible board, so
   *  typing narrows the ranking in place instead of only offering a jump. */
  query: string;
  onQueryChange: (q: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const results = useMemo(() => searchCompanies(index, q), [index, q]);
  const show = open && q.trim().length > 0;

  // A real anchor, not a router push: the results are <a href> so middle
  // click and "open in new tab" work, the static export needs no router
  // context, and Enter just follows the same href.
  function href(e: SearchEntry) {
    return `/${e.s}/`;
  }

  function go(e: SearchEntry) {
    setOpen(false);
    setQ("");
    window.location.href = href(e);
  }

  function onKeyDown(ev: React.KeyboardEvent<HTMLInputElement>) {
    if (ev.key === "Escape") {
      setOpen(false);
      return;
    }
    if (!show || results.length === 0) return;
    if (ev.key === "ArrowDown") {
      ev.preventDefault();
      setActive((i) => (i + 1) % results.length);
    } else if (ev.key === "ArrowUp") {
      ev.preventDefault();
      setActive((i) => (i - 1 + results.length) % results.length);
    } else if (ev.key === "Enter") {
      ev.preventDefault();
      const hit = results[Math.min(active, results.length - 1)];
      if (hit) go(hit);
    }
  }

  return (
    <div className="brand-search">
      <label className="sr-only" htmlFor={`${listId}-input`}>
        Search {index.length.toLocaleString("en-US")} companies by name
      </label>
      <input
        id={`${listId}-input`}
        type="search"
        role="combobox"
        autoComplete="off"
        aria-expanded={show}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={
          show && results.length ? `${listId}-${Math.min(active, results.length - 1)}` : undefined
        }
        placeholder="Search companies"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setActive(0);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => {
          // let a click on a result land before the list unmounts
          blurTimer.current = setTimeout(() => setOpen(false), 120);
        }}
        onKeyDown={onKeyDown}
      />
      {show && (
        <ul className="brand-search-results" id={listId} role="listbox">
          {results.length === 0 ? (
            <li className="brand-search-empty" role="presentation">
              No company matches “{q.trim()}”
            </li>
          ) : (
            results.map((e, i) => (
              <li
                key={e.s}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === Math.min(active, results.length - 1)}
                data-active={i === Math.min(active, results.length - 1) || undefined}
                onMouseEnter={() => setActive(i)}
              >
                <a
                  href={href(e)}
                  onMouseDown={() => {
                    // keep the list alive long enough for the click to land
                    if (blurTimer.current) clearTimeout(blurTimer.current);
                  }}
                >
                <span className="brand-search-name">{e.n}</span>
                <span className="brand-search-cat">
                  {e.v != null ? `${e.v} · ${e.c}` : e.c}
                </span>
                </a>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
