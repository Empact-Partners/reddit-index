import type { Metadata } from "next";
import Link from "next/link";
import { Calendar } from "lucide-react";
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
  // Vlad's copy, verbatim.
  description: "An index of the most loved and hated brands on Reddit.",
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
          {/* The one conversion path on the site — same Virtual Goal as the
              swash, straight to Vlad's calendar. */}
          <a
            className="masthead-cta"
            href="https://calendly.com/vlad-shvets"
            target="_blank"
            rel="noopener"
          >
            <span>Want to improve your reputation? Let&apos;s talk</span>
            <Calendar className="cta-cal" aria-hidden focusable="false" />
          </a>
        </header>
        <main className="container-site">{children}</main>
        <VentureFooter />
      </body>
    </html>
  );
}
