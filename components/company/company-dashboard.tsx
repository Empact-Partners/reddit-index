"use client";

import { useId, useState } from "react";
import { num } from "@/lib/format";
import { MentionList, type Mention, type Sentiment } from "@/components/data/mention-card";
import type { SubredditStat } from "@/lib/data/types";

/**
 * The interactive half of a company's dashboard: the subreddit ledger, the
 * filter bar, and the filtered mention cards.
 *
 * Same island contract as the boards (components/board/index-board.tsx):
 * every card arrives as props at build time, the default view is in the
 * prerendered HTML, state comes only from props/defaults — filtering is a
 * setState, no fetch, no URL reads.
 */

type SentimentFilter = "all" | "pos" | "neg" | "neu";
const SENTIMENT_LABEL: Record<SentimentFilter, string> = {
  all: "All", pos: "Positive", neg: "Negative", neu: "Neutral",
};

function bucket(s: Sentiment): Exclude<SentimentFilter, "all"> {
  return s === "pos" ? "pos" : s === "neg" ? "neg" : "neu";
}

export function CompanyDashboard({
  mentions,
  subredditStats,
  totals,
  totalMentions,
}: {
  mentions: Mention[];
  subredditStats: SubredditStat[];
  totals: { pos: number; neg: number; neu: number };
  totalMentions: number;
}) {
  const [sentiment, setSentiment] = useState<SentimentFilter>("all");
  const [subreddit, setSubreddit] = useState<string>("all");
  const [order, setOrder] = useState<"newest" | "oldest">("newest");
  const ledgerId = useId();

  const filtered = mentions
    .filter((m) => sentiment === "all" || bucket(m.sentiment) === sentiment)
    .filter((m) => subreddit === "all" || m.subreddit === subreddit)
    .sort((a, b) => order === "newest"
      ? b.createdUtc.localeCompare(a.createdUtc)
      : a.createdUtc.localeCompare(b.createdUtc));

  const counts: Record<SentimentFilter, number> = {
    all: totalMentions, pos: totals.pos, neg: totals.neg, neu: totals.neu,
  };

  function toggleSub(name: string) {
    setSubreddit((cur) => (cur === name ? "all" : name));
  }

  return (
    <>
      <section className="mt-[var(--section)]" aria-labelledby={`${ledgerId}-h`}>
        <h2 id={`${ledgerId}-h`} className="section-title">
          Where the mentions live
          <span className="section-count">
            {subredditStats.length} subreddit{subredditStats.length === 1 ? "" : "s"} —
            click one to filter
          </span>
        </h2>
        <div className="table-scroll mt-6">
          <table className="rank-table sub-ledger">
            <caption className="sr-only">Mentions per subreddit with sentiment split</caption>
            <thead>
              <tr>
                <th scope="col">Subreddit</th>
                <th scope="col" className="col-mentions">Mentions</th>
                <th scope="col">Sentiment</th>
                <th scope="col">Newest</th>
              </tr>
            </thead>
            <tbody>
              {subredditStats.map((s) => {
                const total = Math.max(1, s.total);
                return (
                  <tr
                    key={s.subreddit}
                    data-active={subreddit === s.subreddit || undefined}
                    onClick={() => toggleSub(s.subreddit)}
                  >
                    <td className="col-brand">
                      <button
                        type="button"
                        className="sub-ledger-btn"
                        aria-pressed={subreddit === s.subreddit}
                        onClick={(e) => { e.stopPropagation(); toggleSub(s.subreddit); }}
                      >
                        r/{s.subreddit}
                      </button>
                    </td>
                    <td className="col-mentions">{num(s.total)}</td>
                    <td className="col-split">
                      <span className="mini-bar" aria-hidden="true">
                        {s.pos > 0 && <span className="mini-bar-pos" style={{ width: `${(s.pos / total) * 100}%` }} />}
                        {s.neg > 0 && <span className="mini-bar-neg" style={{ width: `${(s.neg / total) * 100}%` }} />}
                        {s.neu > 0 && <span className="mini-bar-neu" style={{ width: `${(s.neu / total) * 100}%` }} />}
                      </span>
                      <span className="mini-bar-nums">
                        <b className="pos-ink">{num(s.pos)}</b> / <b className="neg-ink">{num(s.neg)}</b> / {num(s.neu)}
                      </span>
                    </td>
                    <td className="col-newest">{s.newest.slice(0, 10)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-[var(--section)]">
        <h2 className="section-title">
          What people said
          <span className="section-count">
            showing {num(filtered.length)} of {num(mentions.length)} loaded
            {totalMentions > mentions.length ? ` (${num(totalMentions)} collected)` : ""}
          </span>
        </h2>

        <div className="filter-bar mt-6">
          <div className="seg" role="group" aria-label="Filter by sentiment">
            {(Object.keys(SENTIMENT_LABEL) as SentimentFilter[]).map((k) => (
              <button
                key={k}
                type="button"
                aria-pressed={sentiment === k}
                onClick={() => setSentiment(k)}
              >
                {SENTIMENT_LABEL[k]} <span className="seg-count">{num(counts[k])}</span>
              </button>
            ))}
          </div>
          <div className="seg" role="group" aria-label="Sort order">
            <button type="button" aria-pressed={order === "newest"} onClick={() => setOrder("newest")}>
              Newest
            </button>
            <button type="button" aria-pressed={order === "oldest"} onClick={() => setOrder("oldest")}>
              Oldest
            </button>
          </div>
          {subreddit !== "all" && (
            <button type="button" className="filter-clear" onClick={() => setSubreddit("all")}>
              r/{subreddit} ✕
            </button>
          )}
        </div>

        <div className="mt-8">
          <MentionList mentions={filtered} />
        </div>
      </section>
    </>
  );
}
