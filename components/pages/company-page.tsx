import Link from "next/link";
import { num, pct } from "@/lib/format";
import { ScoreChip } from "@/components/data/score-chip";
import { MentionList } from "@/components/data/mention-card";
import { QualificationBadge, EvidenceTable } from "@/components/data/states";
import {
  ExposureConfoundLine, MethodologyCallout, CorrectionPath,
} from "@/components/data/disclosures";
import { CategoryChip } from "@/components/category/category-identity";
import { Breadcrumbs } from "@/components/site/breadcrumbs";
import { CATEGORY_BY_SLUG } from "@/lib/generated/categories";
import type { CompanyView, Snapshot } from "@/lib/data/types";

/**
 * ONE company, ONE page, listing every category it qualifies in.
 *
 * decisions/0007: the breadcrumb shows its PRIMARY category — the one where its
 * opinionated mention volume is highest — as navigation, never as a claim of
 * exclusivity.
 *
 * The score chip on this page carries tone="neutral". There is no Most Loved /
 * Most Hated heading above it here, so a green or grape fill would imply a
 * verdict the surrounding page never made.
 */
export function CompanyPage({
  company, snapshot,
}: {
  company: CompanyView;
  snapshot: Snapshot;
}) {
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

      {/* No logo. 09-design.md bans brand logos on any ranking surface: it puts
          a company's own mark under a claim it did not make. */}
      <h1 className="mt-8" style={{ fontSize: "var(--fs-h1)" }}>{company.name}</h1>

      <MethodologyCallout />
      <ExposureConfoundLine />

      <section className="mt-[var(--section)]">
        <h2 style={{ fontSize: "var(--fs-h3)" }}>Where this company is measured</h2>
        {company.scores.length === 0 ? (
          <p className="mt-4" style={{ fontSize: "var(--fs-body)", maxWidth: "66ch" }}>
            No score has been computed for this company yet. Its collected
            mentions are published below.
          </p>
        ) : (
          <ul className="mt-6 list-none p-0 m-0 grid gap-10">
            {company.scores.map((s) => {
              const cat = snapshot.categories.find((c) => c.slug === s.categorySlug);
              return (
                <li key={s.categorySlug} className="grid gap-3">
                  <p className="flex flex-wrap items-baseline gap-3">
                    <CategoryChip slug={s.categorySlug} />
                    <span style={{ fontSize: "var(--fs-small)" }}>
                      {num(s.n)} mentions collected
                    </span>
                  </p>

                  {s.eligible && s.redditLoveScore !== null ? (
                    <ScoreChip
                      score={s.redditLoveScore}
                      ciLow={s.ciLow as number}
                      ciHigh={s.ciHigh as number}
                      opinionatedMentions={s.nOp}
                      nEff={s.nEff}
                      windowStart={s.windowStart}
                      windowEnd={s.windowEnd}
                      tone="neutral"
                    />
                  ) : null}

                  {/* neutral_share and abstain_share sit DIRECTLY under the chip,
                      at the same size — not buried in the methodology. The score
                      runs over a subset of n, and a reader is entitled to see how
                      big that subset is. */}
                  <p style={{ fontSize: "var(--fs-small)" }}>
                    {pct(s.neutralShare)} of mentions name this company without an
                    opinion about it, and {pct(s.abstainShare)} could not be
                    classified. Neither enters the score.
                  </p>

                  <p>
                    {cat && !cat.rankable ? (
                      <span className="badge">
                        Category cannot be ranked — {cat.scoringSubreddits} scoring
                        subreddits found, {cat.requiredSubreddits} required
                      </span>
                    ) : (
                      <QualificationBadge s={s} />
                    )}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {company.scores.length > 0 && (
        <section className="mt-[var(--section)]">
          <h2 style={{ fontSize: "var(--fs-h3)" }}>The evidence behind those numbers</h2>
          <EvidenceTable scores={company.scores} />
        </section>
      )}

      <section className="mt-[var(--section)]">
        <h2 style={{ fontSize: "var(--fs-h3)" }}>
          What people said ({num(company.mentions.length)} shown
          {company.totalMentions > company.mentions.length
            ? ` of ${num(company.totalMentions)}`
            : ""}
          )
        </h2>
        <p className="mt-4" style={{ fontSize: "var(--fs-body)", maxWidth: "66ch" }}>
          Newest first, quoted in full, each with a link to the original. A
          comment deleted on Reddit disappears from here on the next nightly
          sync — no placeholder holds its slot.
        </p>
        <div className="mt-8">
          <MentionList mentions={company.mentions} />
        </div>
      </section>

      <CorrectionPath />

      <p className="mt-8" style={{ fontSize: "var(--fs-small)" }}>
        <Link href="/" className="underline underline-offset-4">
          Back to the index
        </Link>
      </p>
    </>
  );
}
