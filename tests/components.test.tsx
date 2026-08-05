import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ScoreChip } from "@/components/data/score-chip";
import { MentionCard, type Mention } from "@/components/data/mention-card";

describe("score chip", () => {
  const props = {
    score: 21, ciLow: 18, ciHigh: 24, opinionatedMentions: 1240, nEff: 412,
    windowStart: "2026-01-01", windowEnd: "2026-06-30",
  };

  it("renders all five fields as text", () => {
    const { container } = render(<ScoreChip {...props} />);
    const t = container.textContent ?? "";
    expect(t).toContain("21");
    expect(t).toContain("90% CI");
    expect(t).toContain("1,240 opinionated mentions");
    expect(t).toContain("n_eff 412");
    expect(t).toContain("Jan–Jun 2026");
  });

  it("refuses to render with a missing field", () => {
    // decisions/0005 condition 1: the measured variable appears beside the
    // superlative on every surface. A chip missing a field breaks the condition
    // the whole naming decision ships under, so it fails loudly instead.
    expect(() =>
      render(<ScoreChip {...props} nEff={NaN as unknown as number} />),
    ).toThrow(/nEff/);
  });

  it("never carries a category colour", () => {
    const { container } = render(<ScoreChip {...props} tone="loved" />);
    expect(container.querySelector("[data-category]")).toBeNull();
  });
});

describe("mention card", () => {
  const long = "x".repeat(4000);
  const m: Mention = {
    brandName: "HubSpot", brandSlug: "hubspot", subreddit: "sales", author: "someone",
    createdUtc: "2026-03-03T14:22:11.000Z", sentiment: "pos", docType: "comment",
    body: long,
    permalink: "https://www.reddit.com/r/sales/comments/abc123/thread/def456/",
  };

  it("renders all seven fields", () => {
    const { container } = render(<MentionCard m={m} />);
    const t = container.textContent ?? "";
    expect(t).toContain("HubSpot");
    expect(t).toContain("r/sales");
    expect(t).toContain("u/someone");   // real text, never an avatar or initial
    expect(t).toContain("3 March 2026");
    expect(t).toContain("Positive");    // the word first
    expect(t).toContain("View on Reddit");
    expect(container.querySelector("time")?.getAttribute("title")).toBe(m.createdUtc);
  });

  it("quotes the body in full, with no read-more", () => {
    const { container } = render(<MentionCard m={m} />);
    expect(container.querySelector(".mention-body")?.textContent).toContain(long);
    expect(container.textContent).not.toMatch(/read more|show more/i);
  });

  it("carries no Reddit UI furniture", () => {
    const { container } = render(<MentionCard m={m} />);
    const html = container.innerHTML.toLowerCase();
    for (const banned of ["upvote", "downvote", "karma", "award", "arrow"]) {
      expect(html).not.toContain(banned);
    }
  });

  it("changes only the label for a post body, never the treatment", () => {
    const c = render(<MentionCard m={m} />).container.innerHTML;
    const p = render(<MentionCard m={{ ...m, docType: "post_body" }} />).container.innerHTML;
    expect(c).toContain("Comment");
    expect(p).toContain("Post body");
    // Identical structure and classes: doc_type never changes size, order or
    // prominence, only the visible label and the permalink target.
    expect(c.replace(/comment/gi, "X")).toBe(p.replace(/post body/gi, "X").replace(/comment/gi, "X"));
  });
});
