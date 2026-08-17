/**
 * Display formatting. Everything a reader is entitled to check is text in the
 * DOM, at Small or larger, never truncated (09-design.md).
 */

/** 07-index-methodology.md §6: a trailing 12-month window, uniform weight. */
export const SCORING_WINDOW_MONTHS = 12;

/** The published method version. Frozen before the first production crawl. */
export const METHODOLOGY_VERSION = "2.2.0";

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
] as const;

const LONG_MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
] as const;

/** "Jan–Jun 2026" · "Sep 2025–Aug 2026". The window is never implied. */
export function formatWindow(startIso: string, endIso: string): string {
  const s = new Date(startIso), e = new Date(endIso);
  const sm = MONTHS[s.getUTCMonth()], em = MONTHS[e.getUTCMonth()];
  return s.getUTCFullYear() === e.getUTCFullYear()
    ? `${sm}–${em} ${e.getUTCFullYear()}`
    : `${sm} ${s.getUTCFullYear()}–${em} ${e.getUTCFullYear()}`;
}

/** Thousands-separated, tabular. */
export const num = (n: number): string => n.toLocaleString("en-US");

/** "3 March 2026" — absolute, never "2 days ago". */
export function absoluteDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getUTCDate()} ${LONG_MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** A percentage a reader can check, not a bar they have to eyeball. */
export const pct = (x: number, dp = 1): string => `${(x * 100).toFixed(dp)}%`;

/**
 * The collection window shown in footer slot 3. Sourced from the corpus at
 * build time where one exists; this is the fallback label used before the
 * first ingest, and it says so rather than inventing dates.
 */
export const COLLECTION_WINDOW_LABEL = "see the methodology page";
