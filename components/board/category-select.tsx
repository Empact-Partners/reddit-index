"use client";

import { useEffect, useId, useRef, useState } from "react";
import { CATEGORIES, CATEGORY_BY_SLUG } from "@/lib/generated/categories";
import type { Scope } from "@/lib/data/board-shapes";

/**
 * The category dropdown. Hand-rolled listbox rather than a native <select>,
 * because a native option cannot carry the category swatch — and rather than a
 * dependency, because this is eighty lines.
 *
 * Elevation is a border on an opaque white panel: box-shadow is banned by the
 * CSS gate, and Empact's own guide bans drop shadows anyway. The swatch is the
 * existing .cat-chip class, which keeps var(--cat) inside the gate's allowlist.
 */
export function CategorySelect({
  value,
  onChange,
}: {
  value: Scope;
  onChange: (next: Scope) => void;
}) {
  const options: { value: Scope; label: string }[] = [
    { value: "all", label: "All Categories" },
    ...CATEGORIES.map((c) => ({ value: c.slug as Scope, label: c.name })),
  ];
  const selectedIdx = Math.max(0, options.findIndex((o) => o.value === value));

  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(selectedIdx);
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const listboxId = useId();

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  useEffect(() => {
    if (open) {
      setActive(selectedIdx);
      listRef.current?.focus();
    }
  }, [open, selectedIdx]);

  function pick(i: number) {
    const opt = options[i];
    if (opt) onChange(opt.value);
    setOpen(false);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(options.length - 1, a + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(0, a - 1));
    } else if (e.key === "Home") {
      e.preventDefault();
      setActive(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setActive(options.length - 1);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      pick(active);
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
    }
  }

  const current = options[selectedIdx];

  return (
    <div className="listbox" ref={rootRef}>
      <button
        type="button"
        className="listbox-btn"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        onClick={() => setOpen((o) => !o)}
      >
        {current && current.value !== "all" ? (
          <span className="cat-chip" data-category={current.value}>{current.label}</span>
        ) : (
          <span>{current?.label ?? "All Categories"}</span>
        )}
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" focusable="false">
          <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      </button>
      {open && (
        <ul
          id={listboxId}
          className="listbox-pop"
          role="listbox"
          aria-label="Category"
          tabIndex={-1}
          ref={listRef}
          aria-activedescendant={`${listboxId}-${active}`}
          onKeyDown={onKeyDown}
        >
          {options.map((o, i) => (
            <li
              key={o.value}
              id={`${listboxId}-${i}`}
              role="option"
              aria-selected={o.value === value}
              className="listbox-opt"
              data-active={i === active || undefined}
              onPointerMove={() => setActive(i)}
              onClick={() => pick(i)}
            >
              {o.value === "all" ? (
                <span>{o.label}</span>
              ) : (
                <span className="cat-chip" data-category={o.value}>
                  {CATEGORY_BY_SLUG[o.value].name}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
