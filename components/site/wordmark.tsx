import Link from "next/link";

/**
 * The identity is the two words, set in Syne Medium, Sherpa Blue on Snowbelt.
 * No glyph, no lockup, no icon beside it — 09-design.md bans any mark that
 * survives a squint test against Reddit's, and a wordmark is also the portable
 * option: `brandsonreddit.com` is the documented migration target and a bespoke
 * glyph would be thrown away on a rename.
 */
export function Wordmark({ asLink = true }: { asLink?: boolean }) {
  const inner = (
    <span
      className="tracking-tight"
      style={{
        fontFamily: "var(--font-syne)",
        fontWeight: 500,
        fontSize: "var(--fs-h4)",
        color: "var(--sherpa-blue)",
      }}
    >
      Reddit Index
    </span>
  );
  return asLink ? (
    <Link href="/" aria-label="Reddit Index — home">
      {inner}
    </Link>
  ) : (
    inner
  );
}
