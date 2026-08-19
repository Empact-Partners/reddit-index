import type { Metadata } from "next";
import Link from "next/link";
import { NON_AFFILIATION } from "@/lib/legal";
import { getMethodologyParams } from "@/lib/data/methodology";
import { METHODOLOGY_VERSION } from "@/lib/format";

export const dynamic = "force-static";
export const revalidate = 86400;

export const metadata: Metadata = {
  title: "How The Reddit ❤️ Score Is Measured",
  description:
    "How the Reddit ❤️ Score is calculated, what counts as a mention, " +
    "and what the method gets wrong. Every constant published.",
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
        <code>{commit.slice(0, 12)}</code>. Version 1 was frozen before the
        first collection run. Version 2 corrected a mis-specified prior;
        version 2.2 changed the published number from the posterior mean to a
        posterior lower bound. Each change, the reason for it, and the numbers
        that forced it are documented below, because a method quietly edited
        after the fact is not a method.
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
p₀   = (pooled_pos + 5) / (pooled_op + 10)   over every OTHER company
α₀   = 10·p₀        β₀ = 10·(1−p₀)
posterior = Beta(x_pos + α₀,  x_neg + β₀)
Reddit Love Score = round(100 · Q₀.₁₀(posterior))`}</Pre>
        <p>
          One published number per company per category, an integer from 0 to
          100: the <strong>10th percentile of the posterior</strong> — the
          rate the evidence can stand behind, not the best guess. Neutral
          mentions are counted and published but are not in the denominator,
          because a company that is named constantly without opinion is not
          thereby liked.
        </p>
        <p>
          The lower bound, and not the posterior mean, because the mean
          rewards thin evidence: shrinkage pulls a barely-observed company
          toward the category average, so a company with zero positives out
          of four opinions once published <em>above</em> one with 25% positive
          over seventy-two. Under a lower bound, uncertainty costs a company
          position instead of buying it one — the score rises with the
          positive rate <em>and</em> with the amount of evidence behind it,
          so a thin newcomer cannot leapfrog a well-measured incumbent. It is
          the same reason Reddit&apos;s own comment ranking uses a confidence
          bound rather than a raw average.
        </p>
        <p>
          The prior shrinks each company toward its category&apos;s pooled
          positive rate, computed over every <em>other</em> company&apos;s
          opinionated mentions, at a fixed weight of ten pseudo-observations.
          Ten, so that a company with forty real opinions is about eighty
          percent its own data — and a company with three is mostly the
          category&apos;s base rate until it earns more.
        </p>
        <p>
          Version 1 fitted the prior&apos;s weight from the data and let it
          reach two hundred pseudo-observations. In a category with exactly two
          well-covered companies, each was scored as the <em>other</em>: a
          registrar with 41 positive and 1 negative mention published 20/100
          while one with 4 positive and 111 negative published 63/100. That is
          why version 2 exists. Version 2.2 replaced the published mean with
          the lower bound after the same class of failure reappeared at the
          thin end of sparse categories. Both changes were caught by a
          calibration gate that refuses any scoring run whose ordering
          contradicts its own raw counts, and that gate still runs on every
          publish.
        </p>
        <p>
          Sorting that number descending <em>is</em> the consolidated view. Most
          Loved is the top of it, Most Hated is the bottom of it, and because
          both are positions in a single ordering, no company can appear on
          both. The two home boards show at most 100 a side; the single-list
          view is the same ordering in full. On the pooled all-categories
          board a company additionally needs at least ten opinionated
          mentions — calling something the most loved or most hated product
          on Reddit demands more than a handful of comments.
        </p>
        <p>
          The Mentions column, everywhere it appears, is the company&apos;s
          <em> total collected mentions</em> — the same figure its own page
          headlines. The opinionated subset that actually enters the estimator
          is published on the company page as evidence.
        </p>
      </Section>

      <Section title="What has to be true before a company is ranked">
        <p>
          One gate that scales with the category, and four floors that never
          scale.
        </p>
        <p>
          A company is ranked in a category once it carries at least that
          category&apos;s <strong>threshold</strong> of opinionated mentions.
          The threshold is the category&apos;s own median: a company must hold
          at least as much evidence as the typical brand it is being ranked
          against, never fewer than 3 and never more than 30. A category where
          the typical brand has four opinions asks for four; one where the
          typical brand has twenty asks for twenty. Nothing about the bar is
          chosen by hand, and it moves as the corpus grows.
        </p>
        <p>
          Separately, <code>n_eff ≥ n_min</code> decides whether a published
          score may also claim a <em>precision</em>. <code>n_min</code> comes
          from a published precision target:{" "}
          <code>n_min = 1.96² × 0.25 / h²</code>, giving 600 at ±4pp, 400 at
          ±5pp and 200 at ±7pp. <code>n_eff</code> is the opinionated mention
          count divided by a design effect, because a hundred replies inside one
          thread are not a hundred independent opinions. The design effect is
          computed twice — clustering by thread and by author — and the worse of
          the two is used. A company can be ranked without clearing it; it then
          carries a rank and no precision claim.
        </p>
        <ul>
          <li>at least 50 distinct authors</li>
          <li>at least 5 distinct subreddits</li>
          <li>no more than 20% of mentions from any one thread</li>
          <li>no more than 5% of mentions from any one author</li>
        </ul>
        <p>
          Every company carrying at least one positive or negative mention is
          scored and ranked in its category. The published number is computed
          over every opinionated mention collected for that company, which is
          the same corpus as the Positive and Negative counts printed beside
          it, and it is the number its category board ranks it by, so a page
          and a board can never disagree. Thin evidence is handled by the
          estimator rather than by hiding the company: because the published
          score is the lower bound and not the mean, a company with one
          opinion lands near its category&apos;s baseline, never at the top.
          A company with no opinionated mention at all is not scored and not
          ranked. A category that cannot
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
          A comment deleted on Reddit disappears from here on the next nightly
          sync. Corrections and removals are free and unconditional.
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
        {NON_AFFILIATION}
      </p>
      <p className="mt-6 pb-12" style={{ fontSize: "var(--fs-small)" }}>
        <Link href="/" className="underline underline-offset-4">Back to the index</Link>
        {" · "}Created by{" "}
        <a href="https://empact.partners" rel="noopener" className="underline underline-offset-4">
          Empact Partners
        </a>
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
