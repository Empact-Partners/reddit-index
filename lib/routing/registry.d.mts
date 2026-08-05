export type SlugTier = "framework" | "site" | "category" | "company";
export interface RegistryEntry { slug: string; tier: SlugTier }
export interface Registry {
  bySlug: Map<string, RegistryEntry>;
  categories: string[];
  companies: string[];
}
export declare const FRAMEWORK_PATHS: string[];
export declare const SITE_ROUTES: string[];
export declare const BANNED_PATH_PREFIXES: string[];
export declare function buildRegistry(
  categorySlugs: readonly string[],
  companySlugs: readonly string[],
): Registry;
