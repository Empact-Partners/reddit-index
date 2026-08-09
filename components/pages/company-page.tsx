import Link from "next/link";
import { num } from "@/lib/format";
import { MentionList } from "@/components/data/mention-card";
import { Breadcrumbs } from "@/components/site/breadcrumbs";
import { CATEGORY_BY_SLUG } from "@/lib/generated/categories";
import { CORRECTIONS_EMAIL } from "@/lib/env";
import { NON_AFFILIATION } from "@/lib/legal";
import type { CompanyView } from "@/lib/data/types";

/**
 * ONE company, ONE page, under the persistent masthead: breadcrumb, the brand
 * name in Syne Bold, one score TILE per category (category chip, the big
 * centred score, the mention count), then the receipts — every collected
 * mention quoted in full with a link to its source. The quiet footer carries
 * the methodology link, correction path and non-affiliation notice.
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
      <h1 className="company-title mt-8">{company.name}</h1>

      <section className="mt-10" aria-label="Scores by category">
        {company.scores.length === 0 ? (
          <p style={{ fontSize: "var(--fs-body)", maxWidth: "66ch" }}>
            No score has been computed for this company yet. Its collected
            mentions are published below.
          </p>
        ) : (
          <ul className="score-tiles">
            {company.scores.map((s) => (
              <li key={s.categorySlug} className="score-tile">
                <Link href={`/${s.categorySlug}/`} className="score-tile-cat">
                  <span className="cat-chip" data-category={s.categorySlug}>
                    {CATEGORY_BY_SLUG[s.categorySlug].name}
                  </span>
                </Link>
                {s.redditLoveScore !== null ? (
                  <span className="score-tile-num">
                    {s.redditLoveScore}
                    <span className="score-tile-denom"> / 100</span>
                  </span>
                ) : (
                  <span className="score-tile-num score-tile-nonum">—</span>
                )}
                <span className="score-tile-mentions">
                  {num(s.n)} {s.n === 1 ? "mention" : "mentions"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-[var(--section)]">
        <h2 className="section-title">
          What Reddit says
          <span className="section-count">
            {num(company.mentions.length)} shown
            {company.totalMentions > company.mentions.length
              ? ` of ${num(company.totalMentions)}`
              : ""}
          </span>
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
