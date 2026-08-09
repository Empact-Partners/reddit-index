import Link from "next/link";
import { num } from "@/lib/format";
import { MentionList } from "@/components/data/mention-card";
import { CategoryChip } from "@/components/category/category-identity";
import { Breadcrumbs } from "@/components/site/breadcrumbs";
import { CATEGORY_BY_SLUG } from "@/lib/generated/categories";
import { CORRECTIONS_EMAIL } from "@/lib/env";
import { NON_AFFILIATION } from "@/lib/legal";
import type { CompanyView } from "@/lib/data/types";

/**
 * ONE company, ONE page: breadcrumb, name, the two headline numbers per
 * category, and the receipts — every collected mention, quoted in full, each
 * with a link to the original. The quiet footer here carries the methodology
 * link, the correction path and the non-affiliation notice, because the
 * homepage no longer has a footer to carry them.
 */
export function CompanyPage({ company }: { company: CompanyView }) {
  const primary = company.primaryCategorySlug
    ? CATEGORY_BY_SLUG[company.primaryCategorySlug]
    : null;

  return (
    <>
      <Breadcrumbs
        trail={[
          { href: "/", label: "Home" },
          ...(primary ? [{ href: `/${primary.slug}/`, label: primary.name }] : []),
        ]}
        current={company.name}
        categorySlug={company.primaryCategorySlug}
      />

      {/* No logo — a company's own mark never sits under a claim it did not make. */}
      <h1 className="mt-8" style={{ fontSize: "var(--fs-h1)" }}>{company.name}</h1>

      <section className="mt-12">
        {company.scores.length === 0 ? (
          <p style={{ fontSize: "var(--fs-body)", maxWidth: "66ch" }}>
            No score has been computed for this company yet. Its collected
            mentions are published below.
          </p>
        ) : (
          <ul className="list-none p-0 m-0 grid gap-6">
            {company.scores.map((s) => (
              <li key={s.categorySlug} className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
                <CategoryChip slug={s.categorySlug} />
                {s.redditLoveScore !== null && (
                  <span style={{ fontSize: "var(--fs-h3)", fontFamily: "var(--font-syne)" }}>
                    {s.redditLoveScore}
                    <span style={{ fontSize: "var(--fs-small)", fontFamily: "var(--font-sans)" }}>
                      {" "}/ 100
                    </span>
                  </span>
                )}
                <span style={{ fontSize: "var(--fs-small)" }}>
                  {num(s.n)} mentions
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-[var(--section)]">
        <h2 style={{ fontSize: "var(--fs-h3)" }}>
          What people said ({num(company.mentions.length)} shown
          {company.totalMentions > company.mentions.length
            ? ` of ${num(company.totalMentions)}`
            : ""}
          )
        </h2>
        <div className="mt-8">
          <MentionList mentions={company.mentions} />
        </div>
      </section>

      <footer
        className="mt-[var(--section)] pt-8 pb-12"
        style={{ borderTop: "1px solid var(--rule)", fontSize: "var(--fs-small)" }}
      >
        <p>
          <Link href="/" className="underline underline-offset-4">Back to the index</Link>
          {" · "}
          <Link href="/methodology/" className="underline underline-offset-4">
            How this is measured
          </Link>
          {" · "}
          Corrections and removals are free and unconditional:{" "}
          <a href={`mailto:${CORRECTIONS_EMAIL}`} className="underline underline-offset-4">
            {CORRECTIONS_EMAIL}
          </a>
        </p>
        <p className="mt-3">{NON_AFFILIATION}</p>
      </footer>
    </>
  );
}
