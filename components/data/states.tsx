import Link from "next/link";
import { num, pct } from "@/lib/format";
import type { BrandScore, CategoryView, FailedTest } from "@/lib/data/types";
import { FAILED_TEST_LABEL } from "@/lib/data/types";

/**
 * "Category cannot be ranked" and "Brand is below threshold" are DIFFERENT
 * states with different wording, and naming the wrong one is worse than naming
 * neither. A brand can pass every brand-level test inside a category that fails
 * viability; that brand is not below threshold.
 */

/** The exact figures behind a failed brand-level test, observed beside required. */
function failureLine(s: BrandScore): string {
  if (!s.failedTest) return "";
  const label = FAILED_TEST_LABEL[s.failedTest as FailedTest];
  return `${label}: ${s.failedObserved} observed, ${s.failedRequired} required`;
}

/**
 * The qualification badge. Always paired with the number that failed —
 * "a badge hiding its number is not shippable".
 */
export function QualificationBadge({ s }: { s: BrandScore }) {
  if (!s.eligible) {
    return (
      <span className="badge" data-variant="below">
        Brand is below threshold — {failureLine(s)}
      </span>
    );
  }
  if (s.tiedWith.length > 0) {
    return (
      <span className="badge" data-variant="tied">
        Statistically tied with {s.tiedWith.join(", ")}
      </span>
    );
  }
  return (
    <span className="badge" data-variant="ranked">
      Ranked #{s.rankDesc}
    </span>
  );
}

/**
 * THE INSUFFICIENT-SIGNAL PANEL — the design's honesty valve.
 *
 * A full-width panel on the dotted field. Not a thin ranking, and not a 404.
 * It names the failed CATEGORY viability requirement with the observed number
 * beside the required one, lists every brand found anyway, and links onward.
 *
 * It uses NO accent hue at all: a category with no verdict must look different
 * from one with a verdict before a word is read.
 *
 * Lowering a threshold to make this panel go away is explicitly not a fix —
 * "a category that cannot be ranked honestly renders the insufficient-signal
 * panel, and that is a CORRECT outcome".
 */
export function InsufficientSignalPanel({
  category,
  alternatives,
}: {
  category: CategoryView;
  alternatives: { slug: string; name: string }[];
}) {
  return (
    <section className="signal-panel pattern-dotted">
      <h2 style={{ fontSize: "var(--fs-h2)" }}>
        Category cannot be ranked: {category.name}
      </h2>
      <p className="mt-5" style={{ fontSize: "var(--fs-lead)", maxWidth: "66ch" }}>
        This category does not clear its viability test, so no position is
        published for any company in it. The measurement that failed is the
        number of scoring subreddits: <b>{category.scoringSubreddits} found</b>,{" "}
        <b>{category.requiredSubreddits} required</b>. Ranking a category on
        fewer communities than that lets one captured community define an entire
        market.
      </p>
      <p className="mt-4" style={{ fontSize: "var(--fs-body)", maxWidth: "66ch" }}>
        Everything collected is still published below. A company here is not
        below threshold — that is a separate, brand-level test, and it is only
        named when a company fails it on its own numbers.
      </p>

      {category.scores.length > 0 && <EvidenceTable scores={category.scores} categoryUnrankable />}

      <p className="mt-8" style={{ fontSize: "var(--fs-body)" }}>
        <Link href="/methodology/" className="underline underline-offset-4">
          How a category qualifies
        </Link>
        {alternatives.length > 0 && (
          <>
            {" · Categories that do clear the bar: "}
            {alternatives.map((a, i) => (
              <span key={a.slug}>
                {i > 0 && ", "}
                <Link href={`/${a.slug}/`} className="underline underline-offset-4">
                  {a.name}
                </Link>
              </span>
            ))}
          </>
        )}
      </p>
    </section>
  );
}

/**
 * Below-threshold companies inside a RANKABLE category, in their own block,
 * labelled with the gate each one missed. Never mixed into the ranking, and
 * never silently omitted.
 */
export function BelowThresholdBlock({ scores }: { scores: BrandScore[] }) {
  if (scores.length === 0) return null;
  return (
    <section className="mt-[var(--section)]">
      <h2 style={{ fontSize: "var(--fs-h3)" }}>Below threshold</h2>
      <p className="mt-4" style={{ fontSize: "var(--fs-body)", maxWidth: "66ch" }}>
        These companies are tracked and their mentions are published, but none
        has enough independent evidence to carry a position. Each row names the
        test it missed and both numbers.
      </p>
      <div className="mt-6">
        <EvidenceTable scores={scores} />
      </div>
    </section>
  );
}

/**
 * The full evidence table. TEN columns, and none of them is dropped at narrow
 * widths — the dropped ones would be the diversity floors, which is the
 * evidence a reader needs most when a claim looks wrong. It scrolls inside its
 * own container instead; the page body never scrolls sideways.
 */
export function EvidenceTable({
  scores,
  categoryUnrankable = false,
}: {
  scores: BrandScore[];
  categoryUnrankable?: boolean;
}) {
  return (
    <div className="table-scroll mt-6">
      <table className="rank-table">
        <caption>
          Every company found, with the evidence behind it. Raw n is all eligible
          mentions; n_eff is n_op adjusted for how clustered those mentions are.
        </caption>
        <thead>
          <tr>
            <th scope="col">Company</th>
            <th scope="col">n</th>
            <th scope="col">n_eff</th>
            <th scope="col">Authors</th>
            <th scope="col">Subreddits</th>
            <th scope="col">Threads</th>
            <th scope="col">Top thread</th>
            <th scope="col">Top author</th>
            <th scope="col">Interval</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {scores.map((s) => (
            <tr key={s.brandSlug}>
              <th scope="row" style={{ fontWeight: 400 }}>
                <Link href={`/${s.brandSlug}/`} className="underline underline-offset-4">
                  {s.brandName}
                </Link>
              </th>
              <td>{num(s.n)}</td>
              <td>{num(Math.round(s.nEff))}</td>
              <td>{num(s.nAuthors)}</td>
              <td>{num(s.nSubreddits)}</td>
              <td>{num(s.nThreads)}</td>
              <td>{pct(s.maxThreadShare)}</td>
              <td>{pct(s.maxAuthorShare)}</td>
              <td>
                {s.ciLow !== null && s.ciHigh !== null ? `${s.ciLow}–${s.ciHigh}` : "—"}
              </td>
              <td style={{ fontSize: "var(--fs-small)" }}>
                {categoryUnrankable && s.eligible
                  ? "Category cannot be ranked"
                  : s.eligible
                    ? `Ranked #${s.rankDesc}`
                    : `Brand is below threshold — ${failureLine(s)}`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
