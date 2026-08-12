import "server-only";
import postgres from "postgres";
import { METHODOLOGY_VERSION } from "@/lib/format";

export type MethodologyParam = {
  version: string;
  scope: string;
  key: string;
  value: unknown;
  rationale: string;
  gitCommit: string;
};

/**
 * Read the frozen constants straight from the append-only table, so
 * /methodology cannot drift from the code that actually ran. 07 §9's audit
 * trail is only an audit trail if a reader can see it.
 */
export async function getMethodologyParams(): Promise<MethodologyParam[]> {
  const url = process.env.DATABASE_URL_READONLY;
  if (!url) return [];
  const sql = postgres(url, { prepare: false, max: 4, ssl: "require", onnotice: () => {} });
  try {
    // The table is append-only across versions; the page renders exactly the
    // set the running code uses.
    const rows = await sql`
      select version, scope, key, value, rationale, git_commit
      from published.methodology_params
      where version = ${METHODOLOGY_VERSION}
      order by scope, key`;
    return rows.map((r) => ({
      version: String(r.version),
      scope: String(r.scope),
      key: String(r.key),
      value: r.value,
      rationale: String(r.rationale),
      gitCommit: String(r.git_commit),
    }));
  } finally {
    await sql.end({ timeout: 5 });
  }
}
