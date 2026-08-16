import type { Snapshot } from "@/lib/data/types";
import { CATEGORY_BY_SLUG, type CategorySlug } from "@/lib/generated/categories";

/**
 * The searchable list of every company that HAS a page.
 *
 * Built from the same predicate as the route registry (a company with at
 * least one mention or score), so search can never offer a result that 404s.
 *
 * This is deliberately NOT the board data. The boards cap each scope at
 * LIST_CAP=200 rows, which is why only a few hundred of the ~3,000 ranked
 * companies were reachable by browsing at all — search is the only surface
 * that sees the whole index, so it is built from the snapshot directly.
 *
 * Kept to three short fields because it ships to the client on every page:
 * ~3,000 entries at roughly 45 bytes each, which gzips to a few tens of KB.
 */
export type SearchEntry = {
  /** slug — also the href, since companies live at "/<slug>" */
  s: string;
  /** display name */
  n: string;
  /** primary category name, for disambiguating same-named brands */
  c: string;
  /** the published score, null while below the category's threshold. The
   *  result line is "score · category" and nothing else — Vlad, 2026-08-16:
   *  a rank in the dropdown read as though it were the score. */
  v: number | null;
};

export function buildSearchIndex(snap: Snapshot): SearchEntry[] {
  const out: SearchEntry[] = [];
  for (const co of snap.companies.values()) {
    if (co.totalMentions <= 0 && co.scores.length === 0) continue;
    const cat = co.primaryCategorySlug
      ? CATEGORY_BY_SLUG[co.primaryCategorySlug as CategorySlug]?.name ?? ""
      : "";
    // The score is the PRIMARY category's — the one the company page leads
    // with — so search and the page always agree.
    const primary = co.primaryCategorySlug
      ? co.scores.find((sc) => sc.categorySlug === co.primaryCategorySlug)
      : undefined;
    const meetsBar = primary != null && primary.nOp >= co.primaryThreshold;
    out.push({
      s: co.slug, n: co.name, c: cat,
      v: meetsBar ? primary!.redditLoveScore : null,
    });
  }
  // Stable, alphabetical: the order is the tie-break when scores are equal,
  // and a deterministic index keeps the built HTML byte-identical run to run.
  out.sort((a, b) => a.n.localeCompare(b.n) || a.s.localeCompare(b.s));
  return out;
}

/**
 * Rank matches for a query. Prefix beats word-start beats substring, so
 * typing "note" puts Notion above Evernote, and shorter names win ties
 * because they are the more likely intent.
 */
export function searchCompanies(
  index: SearchEntry[],
  query: string,
  limit = 12,
): SearchEntry[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const scored: { e: SearchEntry; r: number }[] = [];
  for (const e of index) {
    const name = e.n.toLowerCase();
    let r = -1;
    if (name === q) r = 0;
    else if (name.startsWith(q)) r = 1;
    else if (name.includes(" " + q) || name.includes("-" + q)) r = 2;
    else if (name.includes(q)) r = 3;
    else if (e.s.includes(q)) r = 4;
    if (r >= 0) scored.push({ e, r });
    // no early break: a later exact match must still outrank an early
    // substring hit, and 3k entries is microseconds
  }
  scored.sort((a, b) => a.r - b.r || a.e.n.length - b.e.n.length
    || a.e.n.localeCompare(b.e.n));
  return scored.slice(0, limit).map((x) => x.e);
}
