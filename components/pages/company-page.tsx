import Link from "next/link";
import { CompanyDashboard } from "@/components/company/company-dashboard";
import { MentionList } from "@/components/data/mention-card";
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

      {/* decisions/0020 (Vlad, 2026-10-06: "nothing private, all public"): the closer watch's mentions, shown in
          full with the same attribution as every card, counted in nothing above. */}
      {company.watchMentions && company.watchMentions.length > 0 && (
        <section id="closer-watch" className="mt-[var(--section)]" aria-labelledby="closer-watch-title">
          <h2 id="closer-watch-title" style={{ fontSize: "var(--fs-h3)" }}>
            More mentions, from a closer watch
          </h2>
          <p className="mt-3" style={{ fontSize: "var(--fs-body)", maxWidth: "72ch" }}>
            Empact Partners, which runs this index, also runs Reddit marketing for {company.name}, so {company.name}&apos;s
            name is watched in real time across more subreddits than the index reads for every company. These{" "}
            {company.watchMentions.length === 1 ? "mention comes" : `${company.watchMentions.length} mentions come`} from that
            watch, shown as found, newest first. They are not counted in the score, the totals, the subreddit table or the
            rank above, so every company is measured the same way, and their sentiment is the watch&apos;s own reading.{" "}
            <Link href="/methodology/#closer-watch" className="underline underline-offset-4">How this works</Link>
          </p>
          <div className="mt-6">
            <MentionList mentions={company.watchMentions} />
          </div>
        </section>
      )}


    </div>
  );
}
