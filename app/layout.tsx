import type { Metadata } from "next";
import Link from "next/link";
import { syne, publicSans } from "./fonts";
import { VentureFooter } from "@/components/site/venture-footer";
import { IS_PROVISIONAL } from "@/lib/site-stage";
import { SITE_URL } from "@/lib/env";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    // Vlad's exact homepage meta title, verbatim.
    default: "Reddit Brand Index: Most Loved & Hated Brands On Reddit",
    template: "%s · Reddit Brand Index",
  },
  description:
    "The most loved and most hated software brands, ranked by what Reddit " +
    "actually says. Real comments, classified one mention at a time into a " +
    "Reddit ❤️ Score across 100 software categories.",
  // One of three independent noindex layers while the site is provisional; the
  // others are app/robots.ts and the X-Robots-Tag header in next.config.ts.
  // They fail differently, and all three read lib/site-stage.ts.
  ...(IS_PROVISIONAL ? { robots: { index: false, follow: false, nocache: true } } : {}),
};

/**
 * The masthead is PERSISTENT chrome — the same bold Sherpa band on every
 * route, so opening a company page never feels like leaving the site. It is
 * a link, not a heading: each page owns its own h1 (the homepage's is
 * sr-only, a company page's is the brand name). No banner, no footer —
 * the pages that owe a disclosure carry it in their own content.
 */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${syne.variable} ${publicSans.variable}`}>
      <body>
        <header className="masthead">
          <Link href="/" className="masthead-link">
            <span className="masthead-title">
              <span className="swash">Reddit</span> Brand Index
            </span>
          </Link>
        </header>
        <main className="container-site">{children}</main>
        <VentureFooter />
      </body>
    </html>
  );
}
