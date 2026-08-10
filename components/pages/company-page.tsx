import Link from "next/link";
import { num } from "@/lib/format";
import { CompanyDashboard } from "@/components/company/company-dashboard";
import { Breadcrumbs } from "@/components/site/breadcrumbs";
import { CATEGORY_BY_SLUG } from "@/lib/generated/categories";
import { CORRECTIONS_EMAIL } from "@/lib/env";
import { NON_AFFILIATION } from "@/lib/legal";
import type { CompanyView } from "@/lib/data/types";

/**
 * A company's page IS its Reddit analytics dashboard — the outreach asset.
 * Server-rendered stats up top (score, totals, the sentiment bar, per-category
 * tiles), then the client island: subreddit ledger + filters + the receipts.
 * data-category on the wrapper is what resolves --cat for the brand-mark
 * highlights and chips below.
 */
export function CompanyPage({ company }: { company: CompanyView }) {
  const primary = company.primaryCategorySlug
    ? CATEGORY_BY_SLUG[company.primaryCategorySlug]
    : null;
  const primaryScore = primary
    ? company.scores.find((s) => s.categorySlug === primary.slug)?.redditLoveScore ?? null
    : null;

  return (
    <div data-category={company.primaryCategorySlug ?? undefined}>
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
      <p className="mt-2" style={{ fontSize: "var(--fs-small)", color: "var(--sherpa-blue)" }}>
        What Reddit says about {company.name}, measured — every number below
        links back to real comments.
      </p>

      <CompanyDashboard
        mentions={company.mentions}
        subredditStats={company.subredditStats}
        totals={company.sentimentTotals}
        totalMentions={company.totalMentions}
        heroScore={primaryScore}
        heroLabel={`Reddit ❤️ Score${primary ? ` · ${primary.name}` : ""}`}
      />

      {/* Only when the brand genuinely scores in MORE than one category —
          a single-category repeat of the hero tile is noise (Vlad). */}
      {company.scores.length > 1 && (
        <section className="mt-[var(--section)]" aria-label="Scores by category">
          <h2 className="section-title">Scores by category</h2>
          <ul className="score-tiles mt-6">
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
                  {num(s.n)} scored {s.n === 1 ? "mention" : "mentions"}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

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
    </div>
  );
}
