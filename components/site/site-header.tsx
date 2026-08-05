import { Wordmark } from "./wordmark";

export function SiteHeader() {
  return (
    <header style={{ borderBottom: "1px solid var(--rule)" }}>
      <div className="container-site py-5 flex items-center justify-between">
        <Wordmark />
      </div>
    </header>
  );
}
