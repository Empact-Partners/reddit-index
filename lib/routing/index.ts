import "server-only";
import { buildRegistry } from "./registry.mjs";
import type { Registry } from "./registry.mjs";
import { getIndexRows } from "@/lib/data/site-db";
import { CATEGORIES } from "@/lib/generated/categories";

/**
 * The slug registry: every category and every company that has a page.
 *
 * If two slugs collide, buildRegistry throws. At build time the throw propagates out of
 * generateStaticParams and `next build` fails, which is the mechanism decisions/0007 asks for: a collision
 * is never resolved at request time and never by router match order. Company pages are now rendered on
 * first request (see app/[slug]/page.tsx), so a NEW company can appear between builds; the daily sweep runs
 * the same check before it publishes (worker/site_publish.py), and a category always wins the path.
 *
 * Not memoised here: getIndexRows remembers the rows per process under their content hash.
 */
export async function getRegistry(): Promise<Registry> {
  const rows = await getIndexRows();
  // Every category is a route whether or not it can be ranked. Hiding an unrankable category reads as
  // cherry-picking; it renders the insufficient-signal panel instead.
  const categorySlugs = CATEGORIES.map((c) => c.slug);
  // Only companies with at least one collected mention have a row, so every row is a page.
  const companySlugs = rows.map((r) => r.slug).sort();
  return buildRegistry(categorySlugs, companySlugs);
}
