/**
 * The canonical host lives in EXACTLY ONE config value.
 *
 * HANDOFF.md: the name breaches two Reddit clauses, enforcement is a UDRP
 * filing, and a loss costs the domain but not the project — "a forced move
 * should cost a day, not a quarter". That property is only real if no other
 * file hardcodes the host, which an ESLint rule enforces.
 */
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://redditindex.com";

/**
 * Fails loudly with the variable's name rather than building an empty site.
 */
export function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) {
    throw new Error(
      `Missing required environment variable ${name}. ` +
      `Set it on Vercel (Production, Preview, Development) — see 08-architecture.md §7.`,
    );
  }
  return v;
}
