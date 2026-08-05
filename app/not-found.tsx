import Link from "next/link";

/**
 * The footer is rendered by the root layout, which not-found.tsx inherits — so
 * slot 4 is present here without anything extra. scripts/gates/footer-slot4.mjs
 * proves it on the built HTML rather than trusting that sentence.
 */
export default function NotFound() {
  return (
    <section className="py-[var(--section)]">
      <h1 style={{ fontSize: "var(--fs-h1)" }}>Page not found</h1>
      <p className="mt-6" style={{ fontSize: "var(--fs-lead)", maxWidth: "60ch" }}>
        There is no page at this address. Every category and every company on
        this site sits one segment deep, so a link with more than one slash in
        it was never one of ours.
      </p>
      <p className="mt-6">
        <Link href="/" className="underline underline-offset-4">Back to the index</Link>
      </p>
    </section>
  );
}
