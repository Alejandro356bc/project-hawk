import Link from "next/link";
import { CopyButton } from "./CopyButton";
import { HawkMark } from "./icons";
import f from "./footer.module.css";

const REPO = "https://github.com/Alejandro356bc/projectx";
const INSTALL = "python -m pip install . && hawk";

const PRODUCT = [
  { label: "Live demo", href: "#demo" },
  { label: "How it works", href: "#how" },
  { label: "Providers", href: "#providers" },
  { label: "Discussions", href: "/discussion", internal: true },
];

const OPEN_SOURCE = [
  { label: "GitHub", href: REPO },
  { label: "Docs", href: `${REPO}#readme` },
  { label: "Changelog", href: `${REPO}/blob/main/CHANGELOG.md` },
  { label: "MIT License", href: `${REPO}/blob/main/LICENSE` },
  { label: "Contributing", href: `${REPO}/blob/main/CONTRIBUTING.md` },
  { label: "Security", href: `${REPO}/blob/main/SECURITY.md` },
];

function GitHubIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8a8 8 0 0 0 5.47 7.59c.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.5 7.5 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8 8 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  );
}

/** The landing page footer: brand, link columns, install command, and a giant "Hawk" to close the page. */
export function SiteFooter() {
  return (
    <footer className={f.footer}>
      <span aria-hidden="true" className={f.stars} />
      <span aria-hidden="true" className={f.glow} />

      <div className={f.inner}>
        <div className={f.top}>
          <div className={f.brandBlock}>
            <Link href="/" className={f.brand}>
              <span className={f.brandMark}>
                <HawkMark size={22} sun="#8FB0FF" ink="#FFFFFF" />
              </span>
              Hawk
            </Link>
            <p className={f.tagline}>
              A panel of AI models that debates your coding questions, votes, and hands you one clear verdict.
            </p>
            <div className={f.badges}>
              <span className={f.badge}>
                <span className={f.dot} />
                Open source
              </span>
              <span className={f.badge}>MIT licensed</span>
            </div>
          </div>

          <nav className={f.columns} aria-label="Footer">
            <div className={f.column}>
              <span className={f.heading}>Product</span>
              {PRODUCT.map((l) =>
                l.internal ? (
                  <Link key={l.label} href={l.href} className={f.link}>
                    {l.label}
                  </Link>
                ) : (
                  <a key={l.label} href={l.href} className={f.link}>
                    {l.label}
                  </a>
                ),
              )}
            </div>
            <div className={f.column}>
              <span className={f.heading}>Open source</span>
              {OPEN_SOURCE.map((l) => (
                <a key={l.label} href={l.href} className={f.link} target="_blank" rel="noreferrer">
                  {l.label === "GitHub" && <GitHubIcon />}
                  {l.label}
                  <span className={f.external} aria-hidden="true">
                    ↗
                  </span>
                </a>
              ))}
            </div>
            <div className={`${f.column} ${f.startColumn}`}>
              <span className={f.heading}>Get started</span>
              {/* the install command in a small macOS Terminal window */}
              <div className={f.terminal}>
                <div className={f.termBar}>
                  <span aria-hidden="true" className={f.lights}>
                    <span />
                    <span />
                    <span />
                  </span>
                  <span className={f.termTitle}>zsh</span>
                  <CopyButton text={INSTALL} label="Copy install command" className={f.copy} />
                </div>
                <code className={f.termBody}>
                  <span className={f.prompt}>~ %</span> {INSTALL}
                </code>
              </div>
            </div>
          </nav>
        </div>

        <div className={f.bottom}>
          <span>© 2026 Hawk · Released under the MIT License</span>
          <a href={REPO} className={f.bottomLink} target="_blank" rel="noreferrer">
            <GitHubIcon />
            Star us on GitHub
          </a>
        </div>
      </div>

      {/* the closing word: the name, huge, fading into the bottom edge */}
      <div className={f.wordmark} aria-hidden="true">
        Hawk
      </div>
    </footer>
  );
}
