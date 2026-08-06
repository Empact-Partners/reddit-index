import Link from "next/link";
import { CORRECTIONS_EMAIL } from "@/lib/env";
import { METHODOLOGY_VERSION } from "@/lib/format";
import type { CategoryView } from "@/lib/data/types";

/**
 * THE EXPOSURE CONFOUND LINE.
 *
 * A distinct component from the methodology callout, and both appear. It is
 * persistent, above the first board, on every ranked surface — 07-index
 * -methodology.md §8 is blunt that no post-hoc statistical fix exists for this,
 * so disclosure is the only honest treatment, and burying it in the methodology
 * page does not count.
 */
export function ExposureConfoundLine() {
  return (
    <p
      className="mt-6"
      style={{ fontSize: "var(--fs-body)", maxWidth: "70ch" }}
    >
      A position here reflects what Reddit says, not product quality. Software
      sold through a sales team is discussed by the people who inherited it,
      software chosen by its user is discussed by the person who picked it, and
      that difference pushes enterprise incumbents down and self-serve tools up
      regardless of how good either is.
    </p>
  );
}

/**
 * The methodology callout. Once per ranked surface, directly above the first
 * score, carrying the method version and the collection window.
 *
 * decisions/0005 condition 2 makes this a CONDITION of using the words "Most
 * Loved" and "Most Hated" at all: the methodology is one click from every
 * ranking. It is never a substitute for the confound line above.
 */
export function MethodologyCallout({
  window,
  tier,
  precisionPp,
}: {
  window?: string;
  tier?: string;
  precisionPp?: number;
}) {
  return (
    <p
      className="mt-6"
      style={{
        fontSize: "var(--fs-small)",
        maxWidth: "70ch",
        borderLeft: "3px solid var(--rule)",
        paddingLeft: "16px",
      }}
    >
      One published number per company: the Reddit Love Score, an integer from 0
      to 100, computed only over mentions that carry an opinion and shrunk
      toward its category&apos;s own base rate so a company with six mentions
      cannot outrank one with four thousand. Method version{" "}
      {METHODOLOGY_VERSION}
      {window ? `, collection window ${window}` : ""}
      {tier ? `, ${tier} tier at ±${precisionPp}pp` : ""}.{" "}
      <Link href="/methodology/" className="underline underline-offset-4">
        Read the method
      </Link>
      .
    </p>
  );
}

/**
 * The category page states its own tier and precision target. decisions/0009:
 * "every tier's h is printed on the methodology page and on each category page"
 * — because the threshold is never picked, it is computed from a stated
 * half-width, and a reader who cannot see the half-width cannot check that.
 */
export function CategoryTierLine({ category }: { category: CategoryView }) {
  const tierWord = category.tier.charAt(0).toUpperCase() + category.tier.slice(1);
  return (
    <p className="mt-4" style={{ fontSize: "var(--fs-small)", maxWidth: "70ch" }}>
      {tierWord} tier: a company needs {category.nMin} effective mentions to
      carry a position here, which is the sample size a ±{category.precisionPp}
      pp precision target requires. Four diversity floors apply on top and do
      not scale with the tier: at least 50 distinct authors, at least 5 distinct
      subreddits, no more than 20% of mentions from one thread, and no more than
      5% from one author.
    </p>
  );
}

/**
 * The correction path. A plain link, at Body size, offering correction or
 * removal at no cost — never a form behind a contact step, and never adjacent
 * to anything commercial. It is a condition of both priced decisions
 * (0002 mitigation 4 and 0005 condition 5), not a feature.
 */
export function CorrectionPath() {
  return (
    <p className="mt-[var(--section)]" style={{ fontSize: "var(--fs-body)", maxWidth: "70ch" }}>
      If anything on this page is wrong, or you want it removed, write to{" "}
      <a href={`mailto:${CORRECTIONS_EMAIL}`} className="underline underline-offset-4">
        {CORRECTIONS_EMAIL}
      </a>
      . Corrections and removals are free, are never bundled with an offer of
      any kind, and do not require you to talk to anyone first.
    </p>
  );
}
