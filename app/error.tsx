"use client";

/**
 * A route-level error boundary still renders inside the root layout, so the
 * footer and its slot 4 survive. What does NOT survive is global-error.tsx —
 * see the file beside this one.
 */
export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <section className="py-[var(--section)]">
      <h1 style={{ fontSize: "var(--fs-h1)" }}>Something broke on this page</h1>
      <p className="mt-6" style={{ fontSize: "var(--fs-lead)", maxWidth: "60ch" }}>
        The page could not be rendered. Nothing was changed by the attempt.
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
  );
}
