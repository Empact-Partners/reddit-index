import "server-only";
import { buildRegistry } from "./registry.mjs";
import type { Registry } from "./registry.mjs";
import { getSnapshot } from "@/lib/data/snapshot";
import { CATEGORIES } from "@/lib/generated/categories";

/**
 * The build-time slug registry. Memoised for the life of the process, because
 * generateStaticParams and every page render ask for it.
 *
 * If two slugs collide, buildRegistry throws, the throw propagates out of
 * generateStaticParams, and `next build` fails. That is the whole mechanism:
 * decisions/0007 forbids resolving a collision at request time, and forbids
 * letting router match order decide.
 */
let registryPromise: Promise<Registry> | null = null;

export function getRegistry(): Promise<Registry> {
  return (registryPromise ??= build());
}

async function build(): Promise<Registry> {
  const snap = await getSnapshot();
  // Every category is a route whether or not it can be ranked. Hiding an
  // unrankable category reads as cherry-picking; it renders the
  // insufficient-signal panel instead.
  const categorySlugs = CATEGORIES.map((c) => c.slug);
  // Only companies with at least one collected mention get a page. A company
  // page with nothing on it is not a page, it is a claim of coverage.
  const companySlugs = [...snap.companies.values()]
    .filter((c) => c.totalMentions > 0 || c.scores.length > 0)
    .map((c) => c.slug)
    .sort();
  return buildRegistry(categorySlugs, companySlugs);
}
