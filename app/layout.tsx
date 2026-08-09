import type { Metadata } from "next";
import { syne, publicSans } from "./fonts";
import { IS_PROVISIONAL } from "@/lib/site-stage";
import { SITE_URL } from "@/lib/env";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Reddit Index",
    template: "%s · Reddit Index",
  },
  description:
    "What Reddit actually says about software brands, measured and published with its method.",
  // One of three independent noindex layers while the site is provisional; the
  // others are app/robots.ts and the X-Robots-Tag header in next.config.ts.
  // They fail differently, and all three read lib/site-stage.ts.
  ...(IS_PROVISIONAL ? { robots: { index: false, follow: false, nocache: true } } : {}),
};

/**
 * No banner, no header bar, no footer. The homepage is title + controls +
 * boards by explicit instruction; the pages that still owe a disclosure
 * (/methodology, company pages) carry it in their own content instead.
 */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${syne.variable} ${publicSans.variable}`}>
      <body>
        <main className="container-site">{children}</main>
      </body>
    </html>
  );
}
