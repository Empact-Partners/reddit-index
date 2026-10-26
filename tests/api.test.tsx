// @vitest-environment node
import { createHash } from "node:crypto";
import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * The read API (decision 0040). The database is mocked: these hold the rules the route enforces BEFORE it asks
 * the database anything (the key's shape, the filters, the page cap, the cursor) and how each of the database's
 * refusals becomes HTTP. The same rules inside api.threads (migration 0039) were proven against the live database
 * by a rolled-back dry run and by ops/api_role.py --check.
 */
vi.mock("@/lib/data/api-db", () => ({ threads: vi.fn(), brands: vi.fn() }));

import { threads, brands } from "@/lib/data/api-db";
import { GET as getThreads } from "@/app/api/v1/threads/route";
import { GET as getBrands } from "@/app/api/v1/brands/route";
import { decodeCursor, encodeCursor, MAX_LIMIT } from "@/lib/api/v1";

const KEY = "rik_" + "a".repeat(40);
const HASH = createHash("sha256").update(KEY).digest("hex");
const mThreads = vi.mocked(threads);
const mBrands = vi.mocked(brands);

const page = (over: Record<string, unknown> = {}) => ({
  brand: { slug: "contabo", name: "Contabo" }, sentiment: "negative", since: null, limit: 100,
  rows: [], next: null, scanned: 1023, complete: true, ...over,
});

function call(qs: string, auth: string | null = `Bearer ${KEY}`) {
  const headers = new Headers();
  if (auth !== null) headers.set("authorization", auth);
  return getThreads(new Request(`https://redditindex.com/api/v1/threads/?${qs}`, { headers }));
}

beforeEach(() => {
  mThreads.mockReset();
  mBrands.mockReset();
  mThreads.mockResolvedValue(page() as never);
  mBrands.mockResolvedValue({ brands: [{ slug: "contabo", name: "Contabo", mentions: 1023, negative: 397 }] } as never);
});

describe("auth", () => {
  it("401 without an Authorization header, and the database is not asked", async () => {
    const r = await call("brand=contabo", null);
    expect(r.status).toBe(401);
    expect(mThreads).not.toHaveBeenCalled();
  });

  it("401 on a header that is not a bearer key", async () => {
    for (const h of [`Basic ${KEY}`, "Bearer", "Bearer short", `Bearer ${KEY} extra`, `Bearer ${KEY.replace("a", "!")}`]) {
      expect((await call("brand=contabo", h)).status).toBe(401);
    }
    expect(mThreads).not.toHaveBeenCalled();
  });

  it("sends the sha256 of the key, never the key", async () => {
    await call("brand=contabo");
    expect(mThreads).toHaveBeenCalledTimes(1);
    expect(mThreads.mock.calls[0]![0]).toBe(HASH);
    expect(JSON.stringify(mThreads.mock.calls[0])).not.toContain(KEY);
  });

  it("401 when the database does not know the key, or it is revoked", async () => {
    mThreads.mockResolvedValue({ error: "unauthorized" });
    const r = await call("brand=contabo");
    expect(r.status).toBe(401);
    expect((await r.json()).error).toBe("unauthorized");
  });

  it("429 past the day's calls", async () => {
    mThreads.mockResolvedValue({ error: "rate_limited" });
    expect((await call("brand=contabo")).status).toBe(429);
  });

  it("the brands route checks the key the same way", async () => {
    const none = await getBrands(new Request("https://redditindex.com/api/v1/brands/"));
    expect(none.status).toBe(401);
    mBrands.mockResolvedValue({ error: "unauthorized" });
    const bad = await getBrands(new Request("https://redditindex.com/api/v1/brands/", { headers: { authorization: `Bearer ${KEY}` } }));
    expect(bad.status).toBe(401);
  });
});

describe("filters", () => {
  it("brand is required and must be a slug", async () => {
    expect((await call("")).status).toBe(400);
    expect((await call("brand=Contabo%20GmbH")).status).toBe(400);
    expect((await call("brand=../../etc")).status).toBe(400);
    expect(mThreads).not.toHaveBeenCalled();
  });

  it("defaults: negative, 100 rows, no since, first page", async () => {
    await call("brand=Contabo");
    expect(mThreads.mock.calls[0]![1]).toEqual({ brand: "contabo", sentiment: "negative", since: null, limit: 100, after: null });
  });

  it("sentiment takes negative, neutral, positive, all and nothing else", async () => {
    for (const s of ["negative", "neutral", "positive", "all", "ALL"]) {
      mThreads.mockClear();
      expect((await call(`brand=contabo&sentiment=${s}`)).status).toBe(200);
      expect(mThreads.mock.calls[0]![1].sentiment).toBe(s.toLowerCase());
    }
    expect((await call("brand=contabo&sentiment=angry")).status).toBe(400);
  });

  it("since is a date", async () => {
    await call("brand=contabo&since=2026-09-01");
    expect(mThreads.mock.calls[0]![1].since).toBe("2026-09-01T00:00:00.000Z");
    expect((await call("brand=contabo&since=last-week")).status).toBe(400);
    expect((await call("brand=contabo&since=2026-13-45")).status).toBe(400);
  });

  it("404 for a slug the index does not publish", async () => {
    mThreads.mockResolvedValue({ error: "unknown_brand" });
    const r = await call("brand=nope");
    expect(r.status).toBe(404);
    expect((await r.json()).message).toMatch(/\/api\/v1\/brands/);
  });

  it("the brands route passes q, and refuses a long one", async () => {
    const r = await getBrands(new Request("https://redditindex.com/api/v1/brands/?q=conta", { headers: { authorization: `Bearer ${KEY}` } }));
    expect(r.status).toBe(200);
    expect(mBrands).toHaveBeenCalledWith(HASH, "conta");
    const long = await getBrands(new Request(`https://redditindex.com/api/v1/brands/?q=${"x".repeat(101)}`, { headers: { authorization: `Bearer ${KEY}` } }));
    expect(long.status).toBe(400);
  });
});

describe("the page cap and the cursor", () => {
  it(`limit is capped at ${MAX_LIMIT}`, async () => {
    await call("brand=contabo&limit=10000");
    expect(mThreads.mock.calls[0]![1].limit).toBe(MAX_LIMIT);
    mThreads.mockClear();
    await call("brand=contabo&limit=250");
    expect(mThreads.mock.calls[0]![1].limit).toBe(250);
  });

  it("limit must be a whole number of at least 1", async () => {
    for (const l of ["0", "-5", "abc", "1.5", "9999999"]) {
      expect((await call(`brand=contabo&limit=${l}`)).status).toBe(400);
    }
    expect(mThreads).not.toHaveBeenCalled();
  });

  it("next comes back as an opaque cursor that, passed in, resumes after the last row", async () => {
    const last = { rank: 1, score: 23, created: "2026-09-21T21:56:52+00:00", doc: "t1_pb91ik7" };
    mThreads.mockResolvedValue(page({ next: last }) as never);
    const body = await (await call("brand=contabo&limit=2")).json();
    expect(typeof body.next).toBe("string");
    mThreads.mockClear();
    await call(`brand=contabo&limit=2&cursor=${body.next}`);
    expect(mThreads.mock.calls[0]![1].after).toEqual(last);
  });

  it("null next on the last page", async () => {
    expect((await (await call("brand=contabo")).json()).next).toBeNull();
  });

  it("a cursor this API did not give out is refused", async () => {
    const forged = [
      "garbage", Buffer.from('{"a":1}').toString("base64url"),
      encodeCursor({ rank: 1, score: 1, created: "2026-01-01T00:00:00Z", doc: "t1_x' or 1=1--" }),
      Buffer.from(JSON.stringify([5, 1, "2026-01-01", "t1_abc"])).toString("base64url"),
      Buffer.from(JSON.stringify([1, 2147483648, "2026-01-01T00:00:00Z", "t1_abc"])).toString("base64url"),
    ];
    for (const c of forged) expect((await call(`brand=contabo&cursor=${encodeURIComponent(c)}`)).status).toBe(400);
    expect(mThreads).not.toHaveBeenCalled();
    expect(decodeCursor(encodeCursor({ rank: 0, score: -3, created: "2026-01-01T00:00:00Z", doc: "t3_abc" })))
      .toEqual({ rank: 0, score: -3, created: "2026-01-01T00:00:00Z", doc: "t3_abc" });
  });
});

describe("answers", () => {
  it("never cached", async () => {
    expect((await call("brand=contabo")).headers.get("cache-control")).toBe("no-store");
    expect((await call("brand=contabo", null)).headers.get("cache-control")).toBe("no-store");
  });

  it("503 when the database does not answer, without its message", async () => {
    mThreads.mockRejectedValue(new Error("password authentication failed for user ri_api"));
    const r = await call("brand=contabo");
    expect(r.status).toBe(503);
    expect(JSON.stringify(await r.json())).not.toMatch(/password|ri_api/);
  });
});
