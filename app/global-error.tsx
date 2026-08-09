"use client";

import { syne, publicSans } from "./fonts";
import "./globals.css";

/**
 * global-error.tsx replaces the ROOT LAYOUT entirely — it supplies its own
 * <html> and <body>, so nothing from app/layout.tsx reaches it.
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
      </body>
    </html>
  );
}
