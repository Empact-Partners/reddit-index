import localFont from "next/font/local";

/**
 * Self-hosted, never a CDN. 09-design.md bans Reddit Sans "with any lookalike…
 * no substitution, no fallback stack that can land near it", so the fallback
 * chain deliberately stops at generic system faces.
 *
 * Files land in app/_fonts/ via scripts/fetch-fonts.mjs and are hash-pinned in
 * MANIFEST.json, which scripts/gates/fonts.mjs re-checks on every build.
 */
export const syne = localFont({
  src: [{ path: "./_fonts/Syne-Medium.woff2", weight: "500", style: "normal" }],
  variable: "--font-syne",
  display: "swap",
  preload: true,
  fallback: ["ui-sans-serif", "system-ui", "sans-serif"],
});

export const publicSans = localFont({
  src: [
    { path: "./_fonts/PublicSans-Regular.woff2", weight: "400", style: "normal" },
    { path: "./_fonts/PublicSans-SemiBold.woff2", weight: "600", style: "normal" },
  ],
  variable: "--font-public-sans",
  display: "swap",
  preload: true,
  fallback: ["ui-sans-serif", "system-ui", "sans-serif"],
});
