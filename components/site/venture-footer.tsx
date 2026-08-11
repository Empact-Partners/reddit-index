/**
 * The thin venture bar — mirrored from MarketSplash's footer bottom bar,
 * verbatim copy and the same traced Empact logomark (six offset bars,
 * currentColor, decorative). One line, one link, nothing else.
 */
export function VentureFooter() {
  return (
    <footer className="venture-foot">
      <p>
        A venture by{" "}
        <a href="https://empact.partners" rel="noopener">
          Empact Partners
          <svg
            className="empact-mark"
            viewBox="0 0 638 590"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
            focusable="false"
          >
            <g fill="currentColor">
              <rect x="319" y="0" width="319" height="98.333" />
              <rect x="0" y="98.333" width="319" height="98.333" />
              <rect x="319" y="196.667" width="319" height="98.333" />
              <rect x="0" y="295" width="319" height="98.333" />
              <rect x="319" y="393.333" width="319" height="98.333" />
              <rect x="0" y="491.667" width="319" height="98.333" />
            </g>
          </svg>
        </a>
      </p>
    </footer>
  );
}
