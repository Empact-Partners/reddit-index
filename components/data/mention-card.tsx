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
  /** The surface form the matcher fired on ("HubSpot", "hubspot.com") —
   *  highlighted in the body alongside the display name. */
  matchedForm: string;
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
 * Wrap every occurrence of the brand's surface forms in <mark class="brand-mark">.
 *
 * React nodes, never injected HTML. Word-boundary, case-insensitive, longer
 * forms matched first so "hubspot.com" never splits into a "hubspot" match
 * plus a stray ".com". Pure and exported for tests.
 */
export function highlight(text: string, forms: string[]): React.ReactNode[] {
  const clean = [...new Set(forms.map((f) => f.trim()).filter(Boolean))]
    .sort((a, b) => b.length - a.length);
  if (!clean.length || !text) return [text];
  const pat = clean.map((f) => f.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
  const re = new RegExp(`(?<![a-z0-9])(${pat})(?![a-z0-9])`, "gi");
  const out: React.ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(re)) {
    const i = m.index ?? 0;
    if (i > last) out.push(text.slice(last, i));
    out.push(<mark className="brand-mark" key={`${i}`}>{m[0]}</mark>);
    last = i + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out.length ? out : [text];
}

/**
 * "This is the component the whole product rests on." The seven mandatory
 * fields stay: brand, subreddit, username, timestamp, sentiment, the FULL
 * text, the permalink. v2 reorganises them for scanning:
 *
 *   header:  [sentiment pill] [Comment|Post]        [r/subreddit] [date]
 *   body:    full text, brand highlighted in the brand's colour
 *   footer:  u/author · from Reddit                 [View on Reddit]
 *
 * Unchanged laws: the username is real text, the body is never truncated,
 * the permalink is the biggest tap target, docType changes only its label.
 */
export function MentionCard({ m }: { m: Mention }) {
  const headingId = `m-${m.permalink.split("/").filter(Boolean).pop()}`;
  const typeLabel = m.docType === "post_body" ? "Post" : "Comment";

  return (
    <article className="mention-card" data-sentiment={m.sentiment} aria-labelledby={headingId}>
      <h3 id={headingId} className="sr-only">
        {typeLabel} mentioning {m.brandName} in r/{m.subreddit} by u/{m.author},{" "}
        {absoluteDate(m.createdUtc)}
      </h3>

      <p className="mention-meta">
        <span className="sentiment-chip" data-sentiment={m.sentiment}>
          {SENTIMENT_WORD[m.sentiment]}
        </span>
        <span className="doc-type-tag" data-doc={m.docType}>
          {typeLabel}
        </span>
        <span className="mention-meta-right">
          <a
            className="mention-sub"
            href={`https://www.reddit.com/r/${m.subreddit}/`}
            rel="nofollow ugc noopener"
          >
            r/{m.subreddit}
          </a>
          <time dateTime={m.createdUtc} title={m.createdUtc}>
            {absoluteDate(m.createdUtc)}
          </time>
        </span>
      </p>

      <blockquote className="mention-body" cite={m.permalink}>
        {m.body.split(/\n{2,}/).map((para, i) => (
          <p key={i}>{highlight(para, [m.brandName, m.matchedForm])}</p>
        ))}
      </blockquote>

      {/* The permalink is the card's PRIMARY action: Sherpa-filled, bottom
          LEFT, biggest tap target. Attribution keeps its place quietly right. */}
      <p className="mention-foot">
        <a className="mention-permalink" href={m.permalink} rel="nofollow ugc noopener">
          View on Reddit
          <span className="sr-only">
            {" "}
            — {typeLabel.toLowerCase()} by u/{m.author} in r/{m.subreddit}
          </span>
        </a>
        <span className="mention-attribution">
          <Link href={`/${m.brandSlug}/`} className="mention-brand">
            {m.brandName}
          </Link>
          <span aria-hidden="true"> · </span>
          <a
            className="mention-user"
            href={`https://www.reddit.com/user/${m.author}/`}
            rel="nofollow ugc noopener"
          >
            u/{m.author}
          </a>
          <span aria-hidden="true"> · </span>
          <span className="from-reddit">from Reddit</span>
        </span>
      </p>
    </article>
  );
}

/**
 * An ordered list so a screen reader announces position. The caller controls
 * order (the dashboard sorts). A card whose source was deleted on Reddit is
 * simply absent after the next sync — no tombstone.
 */
export function MentionList({ mentions }: { mentions: Mention[] }) {
  if (mentions.length === 0) {
    return (
      <p style={{ fontSize: "var(--fs-body)" }}>
        No mentions match these filters.
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
