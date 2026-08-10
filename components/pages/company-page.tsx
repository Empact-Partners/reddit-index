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
  const t = company.sentimentTotals;
  const opTotal = Math.max(1, company.totalMentions);
  const pct = (n: number) => Math.round((n / opTotal) * 100);

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

      <section className="mt-10" aria-label="Overview">
        <ul className="stat-tiles">
          <li className="stat-tile stat-tile-hero">
            <span className="stat-num">
              {primaryScore !== null ? primaryScore : "—"}
              {primaryScore !== null && <span className="stat-denom"> / 100</span>}
            </span>
            <span className="stat-label">Reddit ❤️ Score{primary ? ` · ${primary.name}` : ""}</span>
          </li>
          <li className="stat-tile">
            <span className="stat-num">{num(company.totalMentions)}</span>
            <span className="stat-label">Mentions collected</span>
          </li>
          <li className="stat-tile">
            <span className="stat-num pos-ink">{num(t.pos)}</span>
            <span className="stat-label">Positive</span>
          </li>
          <li className="stat-tile">
            <span className="stat-num neg-ink">{num(t.neg)}</span>
            <span className="stat-label">Negative</span>
          </li>
          <li className="stat-tile">
            <span className="stat-num">{num(t.neu)}</span>
            <span className="stat-label">Neutral / no verdict</span>
          </li>
          <li className="stat-tile">
            <span className="stat-num">{num(company.subredditStats.length)}</span>
            <span className="stat-label">Subreddits</span>
          </li>
        </ul>

        {company.totalMentions > 0 && (
          <div className="sentiment-band mt-6" role="img"
               aria-label={`Sentiment: ${pct(t.pos)}% positive, ${pct(t.neg)}% negative, ${pct(t.neu)}% neutral`}>
            <div className="sentiment-bar" aria-hidden="true">
              {t.pos > 0 && <span className="bar-pos" style={{ width: `${(t.pos / opTotal) * 100}%` }} />}
              {t.neg > 0 && <span className="bar-neg" style={{ width: `${(t.neg / opTotal) * 100}%` }} />}
              {t.neu > 0 && <span className="bar-neu" style={{ width: `${(t.neu / opTotal) * 100}%` }} />}
            </div>
            <p className="sentiment-bar-legend" aria-hidden="true">
              <span><i className="dot dot-pos" />{pct(t.pos)}% positive</span>
              <span><i className="dot dot-neg" />{pct(t.neg)}% negative</span>
              <span><i className="dot dot-neu" />{pct(t.neu)}% neutral</span>
            </p>
          </div>
        )}
      </section>

      {company.scores.length > 0 && (
        <section className="mt-12" aria-label="Scores by category">
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

      <CompanyDashboard
        mentions={company.mentions}
        subredditStats={company.subredditStats}
        totals={company.sentimentTotals}
        totalMentions={company.totalMentions}
      />

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
