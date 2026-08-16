import Link from "next/link";
import { num } from "@/lib/format";
import { CompanyDashboard } from "@/components/company/company-dashboard";
import { Breadcrumbs } from "@/components/site/breadcrumbs";
import { CATEGORY_BY_SLUG } from "@/lib/generated/categories";
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
  // Apply the SAME bar the boards apply. Without it a company page published
  // a Reddit Love Score off one or two opinionated mentions — 507 brands were
  // doing so, and a page whose single opinion is negative outranked nothing
  // while still showing a number a reader would take at face value.
  const primaryRow = primary
    ? company.scores.find((s) => s.categorySlug === primary.slug)
    : undefined;
  const primaryScore = primaryRow && primaryRow.nOp >= company.primaryThreshold
    ? primaryRow.redditLoveScore
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

    </div>
  );
}
