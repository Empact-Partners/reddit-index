/**
 * The flat namespace, and the build gate that protects it.
 *
 * decisions/0007: categories and companies share ONE path segment, resolved in
 * a fixed precedence order, and "the union of all four tiers is asserted unique
 * at build time. A duplicate fails the build. It is never resolved at request
 * time and never resolved by whichever route the router happens to match first."
 *
 * Plain ESM with a .d.ts beside it, so the app and the gate scripts import the
 * SAME implementation — a gate that reimplements the thing it checks is a gate
 * that drifts away from it.
 */

/** Tier 1 — framework and file paths. */
export const FRAMEWORK_PATHS = [
  "_next", "api", "sitemap", "sitemap.xml", "robots.txt", "favicon.ico",
  "llms.txt",
  "icon", "apple-icon", "opengraph-image", "twitter-image", "manifest.webmanifest",
];

/** Tier 2 — site routes. */
export const SITE_ROUTES = ["methodology", "search"];

/**
 * Build the registry, or throw. The throw propagates out of
 * generateStaticParams and fails `next build`, which is the point: a build
 * failure is visible exactly once, to the person who caused it.
 */
export function buildRegistry(categorySlugs, companySlugs) {
  const bySlug = new Map();
  const dupes = [];

  const add = (slug, tier) => {
    const prev = bySlug.get(slug);
    if (prev) {
      dupes.push(`  "${slug}"  ${prev.tier} (wins)  x  ${tier} (shadowed)`);
      return;
    }
    bySlug.set(slug, { slug, tier });
  };

  for (const s of FRAMEWORK_PATHS) add(s, "framework");
  for (const s of SITE_ROUTES) add(s, "site");
  for (const s of categorySlugs) add(s, "category");
  for (const s of companySlugs) add(s, "company");

  if (dupes.length) {
    throw new Error(
      `SLUG REGISTRY COLLISION — ${dupes.length} duplicate(s) in the flat namespace.\n` +
      dupes.join("\n") +
      `\n\nResolve by giving the COMPANY a deterministic disambiguator derived from ` +
      `its primary category (decisions/0007). Never by renaming a published slug: ` +
      `a company page that moves after indexing loses the ranking that made it ` +
      `worth sending, which is the entire point of the asset.`,
    );
  }

  // Shape is asserted on the slugs WE mint. Framework paths are the
  // framework's own vocabulary (`_next`, `robots.txt`) and are not ours to
  // reshape — they are in the union to be collided against, nothing more.
  for (const [slug, entry] of bySlug) {
    if (entry.tier === "framework") continue;
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
      throw new Error(
        `SLUG SHAPE: "${slug}" (${entry.tier}) is not lowercase-kebab. ` +
        `Published slugs are frozen, so a malformed one is permanent.`,
      );
    }
    if (slug.normalize("NFC") !== slug) {
      throw new Error(`SLUG UNICODE: "${slug}" is not NFC-normalised`);
    }
  }

  return {
    bySlug,
    categories: [...categorySlugs],
    companies: [...companySlugs],
  };
}

/** Paths the site must never generate. decisions/0007 bans both shapes. */
export const BANNED_PATH_PREFIXES = ["/category/", "/brand/"];
