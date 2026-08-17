"use client";

import { useRef, useState } from "react";
import { num } from "@/lib/format";
import { MentionList, type Mention, type Sentiment } from "@/components/data/mention-card";
import type { SubredditStat } from "@/lib/data/types";

/**
 * The dashboard. THE STAT TILES ARE THE NAVIGATION: "Mentions collected" is
 * the default view (all mentions); Positive / Negative / Neutral are the
 * same view filtered; "Subreddits" is a DIFFERENT view — the ledger replaces
 * the cards, and clicking a subreddit drills back into mentions filtered to
 * it. One island, props-only state (the board contract), no fetch.
 *
 * Pagination: everything is loaded, 10 cards per page.
 */

type SentimentFilter = "all" | "pos" | "neg" | "neu";
type DocFilter = "all" | "post_body" | "comment";
type View = "mentions" | "subreddits";
const PAGE_SIZE = 10;

function bucket(s: Sentiment): Exclude<SentimentFilter, "all"> {
  return s === "pos" ? "pos" : s === "neg" ? "neg" : "neu";
}

export function CompanyDashboard({
  mentions,
  subredditStats,
  totals,
  totalMentions,
  docTypeTotals,
  unlabelled,
  oldestMention,
  heroScore,
  heroLabel,
  rank,
  rankLabel,
}: {
  mentions: Mention[];
  subredditStats: SubredditStat[];
  totals: { pos: number; neg: number; neu: number };
  totalMentions: number;
  /** TRUE corpus split, not the rail's. The filter counts what exists. */
  docTypeTotals: { posts: number; comments: number };
  /** Collected but not classified yet. Counted as neutral everywhere, which is
   *  only honest while the number is small — so the page says it. */
  unlabelled: number;
  /** How far back collection reaches, so "oldest shown" can say what it is. */
  oldestMention: string | null;
  heroScore: number | null;
  heroLabel: string;
  /** "#12 in Social Media Management" — the brand's standing in the category
   *  it is ranked in. Null when it is below that category's threshold, which
   *  is the same bar that suppresses the score itself. */
  rank: number | null;
  rankLabel: string | null;
}) {
  const [view, setView] = useState<View>("mentions");
  const [sentiment, setSentiment] = useState<SentimentFilter>("all");
  const [docType, setDocType] = useState<DocFilter>("all");
  const [subreddit, setSubreddit] = useState<string>("all");
  const [order, setOrder] = useState<"newest" | "oldest">("newest");
  const [page, setPage] = useState(1);
  const listTop = useRef<HTMLDivElement>(null);

  const filtered = mentions
    .filter((m) => sentiment === "all" || bucket(m.sentiment) === sentiment)
    .filter((m) => docType === "all" || m.docType === docType)
    .filter((m) => subreddit === "all" || m.subreddit === subreddit)
    .sort((a, b) => order === "newest"
      ? b.createdUtc.localeCompare(a.createdUtc)
      : a.createdUtc.localeCompare(b.createdUtc));

  // Posts and comments are collected and shown separately, so say which is
  // which with the real corpus totals — the list is a window, these are not.
  const railPosts = mentions.filter((m) => m.docType === "post_body").length;
  const railComments = mentions.length - railPosts;
  const windowed = mentions.length < totalMentions;

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  const visible = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);

  function pickMentions(f: SentimentFilter) {
    setView("mentions");
    setSentiment(f);
    setPage(1);
  }
  function pickSubreddits() {
    setView("subreddits");
  }
  function drillIntoSub(name: string) {
    setSubreddit(name);
    setView("mentions");
    setPage(1);
  }
  function goto(p: number) {
    setPage(p);
    if (typeof listTop.current?.scrollIntoView === "function") {
      listTop.current.scrollIntoView({ block: "start" });
    }
  }

  const opTotal = Math.max(1, totalMentions);
  const pct = (n: number) => Math.round((n / opTotal) * 100);
  const t = totals;

  const tiles: { key: string; num: string; label: string; ink?: string;
                 active: boolean; onClick: () => void }[] = [
    { key: "all", num: num(totalMentions), label: "Mentions collected",
      active: view === "mentions" && sentiment === "all",
      onClick: () => pickMentions("all") },
    { key: "pos", num: num(t.pos), label: "Positive", ink: "pos-ink",
      active: view === "mentions" && sentiment === "pos",
      onClick: () => pickMentions("pos") },
    { key: "neg", num: num(t.neg), label: "Negative", ink: "neg-ink",
      active: view === "mentions" && sentiment === "neg",
      onClick: () => pickMentions("neg") },
    { key: "neu", num: num(t.neu), label: "Neutral",
      active: view === "mentions" && sentiment === "neu",
      onClick: () => pickMentions("neu") },
    { key: "subs", num: num(subredditStats.length), label: "Subreddits",
      active: view === "subreddits",
      onClick: pickSubreddits },
  ];

  // Windowed page numbers: 1 … around-current … last.
  const pageNums: number[] = [];
  for (let p = 1; p <= pages; p++) {
    if (p === 1 || p === pages || Math.abs(p - current) <= 2) pageNums.push(p);
  }

  return (
    <>
      <section className="mt-10" aria-label="Overview">
        <ul className="stat-tiles">
          <li className="stat-tile stat-tile-hero">
            <span className="stat-num">
              {heroScore !== null ? heroScore : "—"}
              {heroScore !== null && <span className="stat-denom"> / 100</span>}
            </span>
            <span className="stat-label">{heroLabel}</span>
          </li>
          {rank !== null && (
            <li className="stat-tile stat-tile-rank">
              <span className="stat-num">
                <span className="stat-hash" aria-hidden="true">#</span>{rank}
              </span>
              <span className="stat-label">
                {/* The visible label already reads "of 24 in CRM"; the
                    sr-only prefix supplies only the word the "#" glyph
                    stands for, so a screen reader hears one sentence. */}
                <span className="sr-only">Ranked number </span>
                {rankLabel}
              </span>
            </li>
          )}
          {tiles.map(({ key, num: n2, label, ink, active, onClick }) => (
            <li key={key}>
              <button
                type="button"
                className="stat-tile stat-tile-btn"
                aria-pressed={active}
                onClick={onClick}
              >
                <span className={`stat-num${ink ? ` ${ink}` : ""}`}>{n2}</span>
                <span className="stat-label">{label}</span>
              </button>
            </li>
          ))}
        </ul>

        {totalMentions > 0 && (
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
            {/* The classifier trails the collector, and an unclassified
                mention is counted as neutral. That is fine at 2% and a
                distortion at 40%, so the page states the number whenever it is
                big enough to move the bar. */}
            {unlabelled / opTotal > 0.1 && (
              <p className="rail-note">
                {num(unlabelled)} of these ({pct(unlabelled)}%) were collected
                recently and are still being classified. They count as neutral
                until they are.
              </p>
            )}
          </div>
        )}
      </section>

      <div ref={listTop} />

      {view === "subreddits" ? (
        <section className="mt-12" aria-label="Subreddits">
          <h2 className="section-title">Where the mentions live</h2>
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
                    <tr key={s.subreddit} onClick={() => drillIntoSub(s.subreddit)}>
                      <td className="col-brand">
                        <button
                          type="button"
                          className="sub-ledger-btn"
                          onClick={(e) => { e.stopPropagation(); drillIntoSub(s.subreddit); }}
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
      ) : (
        <section className="mt-12" aria-label="Mentions">
          <div className="filter-bar">
            <h2 className="section-title" style={{ marginRight: "auto" }}>What people said</h2>
            {subreddit !== "all" && (
              <button type="button" className="filter-clear"
                      onClick={() => { setSubreddit("all"); setPage(1); }}>
                r/{subreddit} ✕
              </button>
            )}
            {/* Posts and comments are different evidence — a post is someone
                raising the subject, a comment is someone answering. The counts
                are the whole corpus, not the window below. */}
            <div className="seg" role="group" aria-label="Document type">
              {([
                ["all", "All", docTypeTotals.posts + docTypeTotals.comments],
                ["comment", "Comments", docTypeTotals.comments],
                ["post_body", "Posts", docTypeTotals.posts],
              ] as [DocFilter, string, number][]).map(([key, label, count]) => (
                <button key={key} type="button" aria-pressed={docType === key}
                        onClick={() => { setDocType(key); setPage(1); }}>
                  {label}<span className="seg-count"> {num(count)}</span>
                </button>
              ))}
            </div>
            <div className="seg" role="group" aria-label="Sort order">
              <button type="button" aria-pressed={order === "newest"}
                      onClick={() => { setOrder("newest"); setPage(1); }}>
                Newest
              </button>
              <button type="button" aria-pressed={order === "oldest"}
                      onClick={() => { setOrder("oldest"); setPage(1); }}>
                {/* "Oldest" sorts the WINDOW, and saying so is the difference
                    between a sort and a lie: the oldest mention held can be
                    years older than the oldest card here. */}
                {windowed ? "Oldest shown" : "Oldest"}
              </button>
            </div>
          </div>

          {windowed && (
            <p className="rail-note">
              Showing the {num(mentions.length)} most recent of{" "}
              {num(totalMentions)} mentions ({num(railComments)} comments,{" "}
              {num(railPosts)} posts).
              {oldestMention && (
                <> Collection reaches back to {oldestMention.slice(0, 10)}.</>
              )}
            </p>
          )}

          <div className="mt-8">
            <MentionList mentions={visible} />
          </div>

          {pages > 1 && (
            <nav className="pager mt-10" aria-label="Mention pages">
              <button type="button" disabled={current === 1} onClick={() => goto(current - 1)}>
                Previous
              </button>
              {pageNums.map((p, i) => (
                <span key={p} className="pager-slot">
                  {i > 0 && pageNums[i - 1] !== p - 1 && <span className="pager-gap">…</span>}
                  <button type="button" aria-current={p === current ? "page" : undefined}
                          onClick={() => goto(p)}>
                    {p}
                  </button>
                </span>
              ))}
              <button type="button" disabled={current === pages} onClick={() => goto(current + 1)}>
                Next
              </button>
            </nav>
          )}
        </section>
      )}
    </>
  );
}
