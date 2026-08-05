/**
 * next/font/local only exists inside a Next build. Vitest renders the error
 * boundaries directly, and global-error.tsx imports the fonts because it
 * supplies its own <html> — so the mock stands in for the loader.
 */
export default function localFont(_opts: unknown) {
  return { className: "font-mock", variable: "--font-mock", style: { fontFamily: "mock" } };
}
