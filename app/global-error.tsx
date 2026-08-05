"use client";

import { syne, publicSans } from "./fonts";
import { SiteFooter } from "@/components/site/site-footer";
import "./globals.css";

/**
 * THE TRAP.
 *
 * global-error.tsx replaces the ROOT LAYOUT entirely — it supplies its own
 * <html> and <body>, so nothing from app/layout.tsx reaches it. That includes
 * the footer, and with it slot 4.
 *
 * 09-design.md requires the non-affiliation notice on every route "without
 * exception, including error pages", and rates its absence as severe as a wrong
 * score. This file is also invisible to scripts/gates/footer-slot4.mjs, which
 * walks prerendered HTML — an error boundary never prerenders. So the footer is
 * mounted here explicitly and a Vitest case in tests/ asserts it, because that
 * is the only mechanism that can.
 */
export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <html lang="en" className={`${syne.variable} ${publicSans.variable}`}>
      <body>
        <main className="container-site">
          <section className="py-[var(--section)]">
            <h1 style={{ fontSize: "var(--fs-h1)" }}>Something broke</h1>
            <p className="mt-6" style={{ fontSize: "var(--fs-lead)", maxWidth: "60ch" }}>
              The site could not be rendered. Nothing was changed by the attempt.
            </p>
            <button
              type="button"
              onClick={reset}
              className="mt-6 underline underline-offset-4"
              style={{ fontSize: "var(--fs-body)" }}
            >
              Try again
            </button>
          </section>
        </main>
        <SiteFooter />
      </body>
    </html>
  );
}
