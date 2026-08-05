import Link from "next/link";
import { COLLECTION_WINDOW_LABEL } from "@/lib/format";

/**
 * SLOT 4. Ships exactly as written — no rewording, no shortening, no softening.
 * Anything that changes this string is a defect.
 */
export const NON_AFFILIATION =
  "Not affiliated with, endorsed by, or sponsored by Reddit, Inc. 'Reddit' is a trademark of Reddit, Inc., used here descriptively.";

/**
 * Four slots, fixed order, identical on every route — including 404, the error
 * boundaries, and every paginated page.
 *
 * 09-design.md rates a page rendering without slot 4 as a bug of the same
 * severity as a page rendering the wrong score, and 01-legal.md explains why:
 * implied affiliation is the theory a UDRP panel actually runs on, and a
 * product with "Reddit" in its name invites exactly that reading.
 *
 * Binding rules for slot 4, all enforced by scripts/gates/footer-slot4.mjs:
 *   · Small size, never Micro
 *   · Snowbelt at full opacity, never dimmed and never a muted grey
 *   · real text in the DOM — never an image, never title-only, never aria-hidden
 *   · never inside <details>, a "legal" drawer, or a modal
 *   · never adjacent to a call to action or anything commercial
 *
 * There are no props. A footer that can be configured is a footer that can be
 * configured wrong.
 */
export function SiteFooter() {
  return (
    <footer
      className="on-dark mt-[var(--section)]"
      style={{ background: "var(--sherpa-blue)", color: "var(--snowbelt)" }}
    >
      <div className="container-site py-12 flex flex-col gap-4">
        {/* Slot 1 — methodology. Never nested inside a menu. */}
        <p style={{ fontSize: "var(--fs-body)" }}>
          <Link href="/methodology/" className="underline underline-offset-4">
            How this is measured
          </Link>
        </p>

        {/* Slot 2 — attribution, at reading size. Never a micro credit line. */}
        <p style={{ fontSize: "var(--fs-body)" }}>
          Created by{" "}
          <a
            href="https://empact.partners"
            className="underline underline-offset-4"
            rel="noopener"
          >
            Empact Partners
          </a>
        </p>

        {/* Slot 3 — the source, named once, with the collection window. */}
        <p style={{ fontSize: "var(--fs-small)" }}>
          Every quotation on this site was written by a Reddit user and is
          reproduced with a link to its source. Collection window:{" "}
          {COLLECTION_WINDOW_LABEL}.{" "}
          <Link href="/methodology/" className="underline underline-offset-4">
            Method and limitations
          </Link>
          .
        </p>

        {/* Slot 4 — verbatim. */}
        <p style={{ fontSize: "var(--fs-small)", opacity: 1 }}>{NON_AFFILIATION}</p>
      </div>
    </footer>
  );
}
