import Link from "next/link";
import type { CategorySlug } from "@/lib/generated/categories";

/**
 * Home > Category > Company. An ordered list with aria-label="Breadcrumb", so
 * the trail is announced as a trail. "No page is a dead end, and no page is
 * reachable only from search."
 *
 * Every href resolves inside the flat namespace — `/`, `/{category}/`,
 * `/{company}/`. There is no `/category/…` or `/brand/…` to link to.
 */
export function Breadcrumbs({
  trail,
  current,
  categorySlug,
}: {
  trail: { href: string; label: string }[];
  current: string;
  categorySlug?: CategorySlug | null;
}) {
  return (
    <nav aria-label="Breadcrumb" className="pt-8">
      <ol
        className="list-none p-0 m-0 flex flex-wrap items-center gap-2"
        style={{ fontSize: "var(--fs-small)" }}
      >
        {trail.map((t, i) => (
          <li key={t.href} className="flex items-center gap-2">
            <Link
              href={t.href as "/"}
              className={i > 0 && categorySlug ? "breadcrumb-cat underline underline-offset-4" : "underline underline-offset-4"}
              {...(i > 0 && categorySlug ? { "data-category": categorySlug } : {})}
            >
              {t.label}
            </Link>
            <span aria-hidden="true">›</span>
          </li>
        ))}
        <li aria-current="page">{current}</li>
      </ol>
    </nav>
  );
}
