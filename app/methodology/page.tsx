import type { Metadata } from "next";
import Link from "next/link";
import { getMethodologyParams } from "@/lib/data/methodology";
import { METHODOLOGY_VERSION } from "@/lib/format";

export const dynamic = "force-static";
export const revalidate = 86400;

export const metadata: Metadata = {
  title: "Methodology",
  description:
    "How the Reddit Love Score is computed, what qualifies a company for a position, and what this index gets wrong.",
  alternates: { canonical: "/methodology/" },
};

/**
 * ONE methodology page, one URL, one click from every ranking. It is the
 * footer's destination, the callout's destination, and there is no second
 * /about route.
 *
 * "Write it like ApeWisdom's, not like a vendor's: short, mechanical, and
 * openly self-incriminating about what the method gets wrong."
 *
 * Every frozen constant is rendered from the append-only methodology_params
 * table rather than retyped here, so the page cannot drift from the code that
 * actually ran.
 */
export default async function Methodology() {
  const params = await getMethodologyParams();
  const commit = params[0]?.gitCommit ?? "unrecorded";

  return (
    <article className="py-[var(--section)]" style={{ maxWidth: "72ch" }}>
      <h1 style={{ fontSize: "var(--fs-h1)" }}>Methodology</h1>
      <p className="mt-6" style={{ fontSize: "var(--fs-lead)" }}>
        Version {METHODOLOGY_VERSION}, frozen at commit{" "}
        <code>{commit.slice(0, 12)}</code> before the first collection run. That
        order matters: a method chosen after seeing where a named company landed
        is not a method.
      </p>

      <Section title="What is measured">
        <p>
          Reddit comments and post bodies that name a software product, in
          subreddits where product discussion is allowed and which are not run
          by a vendor. Each mention is resolved to one company, classified as
          positive, negative, neutral or unclassifiable about <em>that</em>{" "}
          company, and counted once. A comment naming three products produces
          three observations with three separate verdicts.
        </p>
        <p>
          A brand named in a post body and a brand named in a comment count
          identically. They differ only in the label on the card and which link
          they point at.
        </p>
      </Section>

      <Section title="The number">
        <Pre>{`N_op = pos + neg
p̃    = (x_pos + α₀) / (N_op + α₀ + β₀)
Reddit Love Score = round(100 · p̃)`}</Pre>
        <p>
          One published number per company per category, an integer from 0 to
          100. Neutral mentions are counted and published but are not in the
          denominator, because a company that is named constantly without
          opinion is not thereby liked.
        </p>
        <p>
          α₀ and β₀ shrink each company toward its category&apos;s own base
          rate, fitted across every <em>other</em> company in that category so
          the biggest name is not pinned to its own average. The practical
          effect: a company with six positive mentions does not outrank one with
          four thousand.
        </p>
        <p>
          Sorting that number descending <em>is</em> the consolidated view. Most
          Loved is the top of it, Most Hated is the bottom of it, and because
          both are positions in a single ordering, no company can appear on
          both.
        </p>
      </Section>

      <Section title="What has to be true before a company is ranked">
        <p>
          One gate that scales with the category, and four floors that never
          scale.
        </p>
        <p>
          The gate is <code>n_eff ≥ n_min</code>. <code>n_min</code> comes from
          a published precision target, not from taste:{" "}
          <code>n_min = 1.96² × 0.25 / h²</code>, giving 600 at ±4pp, 400 at
          ±5pp and 200 at ±7pp. <code>n_eff</code> is the opinionated mention
          count divided by a design effect, because a hundred replies inside one
          thread are not a hundred independent opinions. The design effect is
          computed twice — clustering by thread and by author — and the worse of
          the two is used.
        </p>
        <ul>
          <li>at least 50 distinct authors</li>
          <li>at least 5 distinct subreddits</li>
          <li>no more than 20% of mentions from any one thread</li>
          <li>no more than 5% of mentions from any one author</li>
        </ul>
        <p>
          A company that fails any of these is shown as{" "}
          <strong>below threshold</strong>, with the failing test named and both
          numbers printed. It is never quietly dropped. A category that cannot
          field five scoring subreddits is a different failure with different
          words: <strong>the category cannot be ranked</strong>, and no company
          inside it gets a position, including companies that pass every
          brand-level test.
        </p>
      </Section>

      <Section title="Uncertainty">
        <p>
          Every published score carries a 90% interval from a cluster bootstrap
          that resamples whole threads and whole authors rather than individual
          mentions. Companies whose intervals overlap are declared statistically
          tied and rendered as ties. The interval is printed beside the score,
          never behind a hover: an interval a reader cannot see is an interval
          that does not constrain the claim.
        </p>
      </Section>

      <Section title="What this gets wrong">
        <p>
          <strong>Exposure is confounded with sentiment and there is no fix.</strong>{" "}
          Software bought by a committee is discussed by the people who
          inherited it. Software chosen by its user is discussed by the person
          who picked it. That pushes enterprise incumbents down and self-serve
          tools up regardless of quality, and no statistical adjustment repairs
          it. It is disclosed on every ranked page for that reason.
        </p>
        <p>
          <strong>Precision has not been measured.</strong> No human-adjudicated
          audit has been run. The ≥0.97 mention-level precision figure in the
          specification is a design target, not a result, and no precision
          number is published here because none has been earned.
        </p>
        <p>
          <strong>Recall is deliberately reduced.</strong> Companies whose names
          collide with ordinary English — Close, Make, Front, Square, Render,
          Motion, Craft, Remote — are matched only through a qualified form such
          as a domain. They are excluded rather than guessed, so their counts
          are floors and their absence from a board is not evidence of anything.
        </p>
        <p>
          <strong>This corpus is a sample, not a census.</strong> Reddit&apos;s
          API reaches roughly the last few days of any listing, and the archive
          lane that would make it a census is not running. Every count on this
          site is a lower bound.
        </p>
        <p>
          <strong>Votes are ignored.</strong> Upvotes measure how many people
          saw a comment and agreed enough to click, in a ranking system that
          feeds back on itself. They do not enter the score at any weight.
        </p>
      </Section>

      <Section title="Corrections">
        <p>
          Write to{" "}
          <a href="mailto:corrections@redditindex.com" className="underline underline-offset-4">
            corrections@redditindex.com
          </a>
          . Corrections and removals are free, are never bundled with an offer
          of any kind, and do not require a call. A comment deleted on Reddit
          disappears from here on the next nightly sync.
        </p>
      </Section>

      <Section title="Every frozen parameter">
        <p>
          These were fixed before any data was collected. Changing one is a
          version bump with a dated entry, never an edit — the table they live
          in rejects updates.
        </p>
        <div className="table-scroll mt-6">
          <table className="rank-table">
            <caption>
              {params.length} parameters, methodology version {METHODOLOGY_VERSION}.
            </caption>
            <thead>
              <tr>
                <th scope="col">Parameter</th>
                <th scope="col">Value</th>
                <th scope="col">Why</th>
              </tr>
            </thead>
            <tbody>
              {params.map((p) => (
                <tr key={`${p.scope}:${p.key}`}>
                  <th scope="row" style={{ fontWeight: 400, whiteSpace: "nowrap" }}>
                    <code>{p.key}</code>
                  </th>
                  <td><code>{JSON.stringify(p.value)}</code></td>
                  <td style={{ fontSize: "var(--fs-small)", minWidth: "34ch" }}>{p.rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <p className="mt-[var(--section)]" style={{ fontSize: "var(--fs-small)" }}>
        <Link href="/" className="underline underline-offset-4">Back to the index</Link>
      </p>
    </article>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-[var(--section)]">
      <h2 style={{ fontSize: "var(--fs-h3)" }}>{title}</h2>
      <div className="mt-5 grid gap-5" style={{ fontSize: "var(--fs-body)" }}>
        {children}
      </div>
    </section>
  );
}

function Pre({ children }: { children: string }) {
  return (
    <pre
      style={{
        fontSize: "var(--fs-small)",
        borderLeft: "3px solid var(--rule)",
        paddingLeft: "16px",
        overflowX: "auto",
        margin: 0,
      }}
    >
      {children}
    </pre>
  );
}
