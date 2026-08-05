import type { Metadata } from "next";
import { syne, publicSans } from "./fonts";
import { SiteHeader } from "@/components/site/site-header";
import { SiteFooter } from "@/components/site/site-footer";
import { ProvisionalBanner } from "@/components/site/provisional-banner";
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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${syne.variable} ${publicSans.variable}`}>
      <body>
        <ProvisionalBanner />
        <SiteHeader />
        <main className="container-site">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
