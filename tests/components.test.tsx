import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { MentionCard, type Mention } from "@/components/data/mention-card";

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
    // prominence, only the visible label, the data-doc value and the permalink.
    const norm = (h: string) =>
      h.replace(/post_body/g, "X").replace(/post body/gi, "X").replace(/comment/gi, "X");
    expect(norm(c)).toBe(norm(p));
  });
});
