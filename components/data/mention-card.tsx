import Link from "next/link";
import { absoluteDate } from "@/lib/format";

export type Sentiment = "pos" | "neg" | "neu" | "abstain";

export type Mention = {
  brandName: string;
  brandSlug: string;
  subreddit: string;   // "sales", no r/ prefix
  author: string;      // "foo", no u/ prefix, never "[deleted]"
  createdUtc: string;  // ISO 8601
  sentiment: Sentiment;
  docType: "post_body" | "comment";
  body: string;        // FULL text
  permalink: string;   // absolute reddit.com URL, copied from the API
};

const SENTIMENT_WORD: Record<Sentiment, string> = {
  pos: "Positive",
  neg: "Negative",
  neu: "Neutral",
  abstain: "No verdict",
};

/**
 * "This is the component the whole product rests on." Seven fields, none
 * optional, none conditional on width, position or sentiment:
 *
 *   1 brand · 2 subreddit · 3 username · 4 timestamp · 5 sentiment label
 *   6 the full text · 7 the permalink
 *
 * The rules that are easiest to break, and why each one is here:
 *
 *  · The USERNAME is real text in the DOM. Never an avatar, never an initial,
 *    never abbreviated. A quote without its source is not shippable.
 *  · The BODY is never truncated. No "read more", no fade mask, no line clamp.
 *    decisions/0002 prices displaying full comment text as an accepted risk —
 *    a half-quote would carry the same exposure and less of the honesty.
 *  · The PERMALINK is the card's largest tap target, 44x44 minimum, labelled
 *    "View on Reddit". It is never demoted to an icon and the timestamp does
 *    not compete with it — a 13px Micro timestamp link cannot meet 44x44, so it
 *    is not a link at all.
 *  · `docType` changes ONLY the visible label and which permalink is used.
 *    Never the size, order, prominence or scoring weight. A brand named in a
 *    post body and a brand named in a comment are the same observation.
 *  · Nothing here may let a reader mistake a Reddit user's words for the site's
 *    own: the left rule and the quotation marks do that work, and the text
 *    takes no site-copy weight, colour, or pull-quote treatment.
 *  · There is no vote arrow, karma pill, award or reply rail in this markup at
 *    all — they cannot regress because there is nothing to remove.
 */
export function MentionCard({ m }: { m: Mention }) {
  const headingId = `m-${m.permalink.split("/").filter(Boolean).pop()}`;
  const typeLabel = m.docType === "post_body" ? "Post body" : "Comment";

  return (
    <article className="mention-card" data-sentiment={m.sentiment} aria-labelledby={headingId}>
      <h3 id={headingId} className="sr-only">
        {typeLabel} mentioning {m.brandName} in r/{m.subreddit} by u/{m.author},{" "}
        {absoluteDate(m.createdUtc)}
      </h3>

      {/* The header row: the verdict and WHERE the words came from — a post's
          own body or a comment — at equal size and equal prominence. */}
      <p className="mention-meta">
        <span className="sentiment-chip" data-sentiment={m.sentiment}>
          {SENTIMENT_WORD[m.sentiment]}
        </span>
        <span className="doc-type-tag" data-doc={m.docType}>
          {typeLabel}
        </span>
      </p>

      {/* Fields 1-4, one Micro row, this order, on every card. */}
      <p className="mention-attribution">
        <Link href={`/${m.brandSlug}/`} className="mention-brand">
          {m.brandName}
        </Link>
        <span aria-hidden="true"> · </span>
        <a
          className="mention-sub"
          href={`https://www.reddit.com/r/${m.subreddit}/`}
          rel="nofollow ugc noopener"
        >
          r/{m.subreddit}
        </a>
        <span aria-hidden="true"> · </span>
        <a
          className="mention-user"
          href={`https://www.reddit.com/user/${m.author}/`}
          rel="nofollow ugc noopener"
        >
          u/{m.author}
        </a>
        <span aria-hidden="true"> · </span>
        <time dateTime={m.createdUtc} title={m.createdUtc}>
          {absoluteDate(m.createdUtc)}
        </time>
        <span aria-hidden="true"> · </span>
        <span className="from-reddit">from Reddit</span>
      </p>

      {/* Field 6. Full text. */}
      <blockquote className="mention-body" cite={m.permalink}>
        {m.body.split(/\n{2,}/).map((para, i) => (
          <p key={i}>{para}</p>
        ))}
      </blockquote>

      {/* Field 7. The card's primary link and its largest tap target. */}
      <a className="mention-permalink" href={m.permalink} rel="nofollow ugc noopener">
        View on Reddit
        <span className="sr-only">
          {" "}
          — {typeLabel.toLowerCase()} by u/{m.author} in r/{m.subreddit}
        </span>
      </a>
    </article>
  );
}

/**
 * An ordered list so a screen reader announces position. Cards sort newest
 * first. A card whose source was deleted on Reddit simply is not in this list
 * after the next sync — no tombstone, no cached copy, no "[deleted]" holding
 * the slot.
 */
export function MentionList({ mentions }: { mentions: Mention[] }) {
  if (mentions.length === 0) {
    return (
      <p style={{ fontSize: "var(--fs-body)" }}>
        No mentions have been collected for this company yet.
      </p>
    );
  }
  return (
    <ol className="mention-list">
      {mentions.map((m) => (
        <li key={`${m.brandSlug}:${m.permalink}`}>
          <MentionCard m={m} />
        </li>
      ))}
    </ol>
  );
}
