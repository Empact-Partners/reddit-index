import { IS_PROVISIONAL, PROVISIONAL_NOTICE } from "@/lib/site-stage";

/**
 * Says out loud what the noindex headers say to a crawler. Sits above the
 * header and never adjacent to footer slot 4, so nothing about the legal
 * notice reads as promotional context.
 */
export function ProvisionalBanner() {
  if (!IS_PROVISIONAL) return null;
  return (
    <div
      className="on-dark"
      style={{ background: "var(--sherpa-blue)", color: "var(--snowbelt)" }}
    >
      <p className="container-site py-3" style={{ fontSize: "var(--fs-small)" }}>
        {PROVISIONAL_NOTICE}
      </p>
    </div>
  );
}
