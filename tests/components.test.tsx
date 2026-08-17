import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { MentionCard, highlight, type Mention } from "@/components/data/mention-card";

describe("mention card", () => {
  const long = "x".repeat(4000) + " HubSpot helped. ";
  const m: Mention = {
    brandName: "HubSpot", brandSlug: "hubspot", subreddit: "sales", author: "someone",
    createdUtc: "2026-03-03T14:22:11.000Z", sentiment: "pos", docType: "comment",
    matchedForm: "hubspot",
    threadTitle: "Which CRM do you actually like?",
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

  it("quotes the body in full, with no read-more, brand marked", () => {
    const { container } = render(<MentionCard m={m} />);
    expect(container.querySelector(".mention-body")?.textContent).toContain("x".repeat(4000));
    expect(container.textContent).not.toMatch(/read more|show more/i);
    const marks = container.querySelectorAll(".mention-body mark.brand-mark");
    expect(marks.length).toBeGreaterThan(0);
    expect(marks[0]?.textContent).toBe("HubSpot");
  });

  it("carries no Reddit UI furniture", () => {
    const { container } = render(<MentionCard m={m} />);
    const html = container.innerHTML.toLowerCase();
    for (const banned of ["upvote", "downvote", "karma", "award", "arrow"]) {
      expect(html).not.toContain(banned);
    }
  });

  it("changes only the label and the context line for a post body", () => {
    const c = render(<MentionCard m={m} />).container.innerHTML;
    const p = render(<MentionCard m={{ ...m, docType: "post_body" }} />).container.innerHTML;
    expect(c).toContain("Comment");
    expect(p).toContain("Post");

    // A COMMENT carries the thread title above the quote: without it a reply
    // is unjudgeable, because the question it answers is on Reddit and not
    // here. A POST does not — worker/harvest.py::post_doc stores title +
    // selftext as ONE document, so the title is already the first line of the
    // body and printing it again would double it.
    expect(c).toContain("mention-context");
    expect(p).not.toContain("mention-context");

    // Everything else is identical treatment: same chips, same blockquote,
    // same permalink, same attribution.
    const strip = (h: string) => h.replace(/<p class="mention-context">.*?<\/p>/s, "");
    const norm = (h: string) =>
      strip(h).replace(/post_body/g, "X").replace(/post/gi, "X").replace(/comment/gi, "X");
    expect(norm(c)).toBe(norm(p));
  });

  it("a post with no stored thread title still renders", () => {
    const { container } = render(
      <MentionCard m={{ ...m, docType: "post_body", threadTitle: null }} />);
    expect(container.textContent).toContain("Post");
    expect(container.innerHTML).not.toContain("mention-context");
  });
});

describe("highlight", () => {
  it("wraps word-boundary matches case-insensitively", () => {
    const nodes = highlight("I love hubspot and HubSpot CRM.", ["HubSpot"]);
    const marks = nodes.filter((n) => typeof n !== "string");
    expect(marks).toHaveLength(2);
  });

  it("never matches inside a longer token", () => {
    const nodes = highlight("pinstripe is not stripe adjacent", ["Stripe"]);
    const marks = nodes.filter((n) => typeof n !== "string");
    expect(marks).toHaveLength(1); // only the bare "stripe"
  });

  it("prefers the longer form over its substring", () => {
    const nodes = highlight("see hubspot.com for hubspot", ["hubspot", "hubspot.com"]);
    const marks = nodes.filter((n) => typeof n !== "string") as { props: { children: string } }[];
    expect(marks.map((x) => x.props.children)).toEqual(["hubspot.com", "hubspot"]);
  });

  it("passes text through untouched when nothing matches", () => {
    expect(highlight("nothing here", ["HubSpot"])).toEqual(["nothing here"]);
  });

  it("survives empty forms", () => {
    expect(highlight("text", ["", "  "])).toEqual(["text"]);
  });
});
