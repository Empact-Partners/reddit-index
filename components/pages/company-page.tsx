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
export function CompanyPage({
  company,
  boardRank,
  boardSize,
}: {
  company: CompanyView;
  /** Position on the primary category's board — the same list the reader can
   *  open — or null when the brand is below that category's threshold. */
  boardRank: number | null;
  boardSize: number;
}) {
  const primary = company.primaryCategorySlug
    ? CATEGORY_BY_SLUG[company.primaryCategorySlug]
    : null;
  // decisions/0011 (2026-08-19): ONE number. The score is computed over every
  // opinionated mention collected for this brand — the same corpus as the
  // Positive and Negative tiles below it — and it is the number its category
  // board ranks it by, so the page and the board can never disagree. Null only
  // when the brand carries no opinionated mention at all.
  const primaryScore = company.pageScore;

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
        docTypeTotals={company.docTypeTotals}
        unlabelled={company.unlabelled}
        oldestMention={company.oldestMention}
        heroScore={primaryScore}
        heroLabel="Reddit ❤️ Score"
        rank={boardRank}
        rankLabel={primary
          ? `of ${boardSize} in ${primary.name}`
          : null}
      />


    </div>
  );
}
