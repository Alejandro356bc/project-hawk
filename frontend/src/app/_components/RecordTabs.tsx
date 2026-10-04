"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { PANEL, TRANSCRIPT } from "../_lib/data";
import s from "../landing.module.css";

const TABS = ["Verdict", "Transcript", "Votes"] as const;

/** Each line fades and rises in, a beat after the one above it. */
const enter = (i: number) => ({
  className: `${s.line} ${s.lineIn}`,
  style: { animationDelay: `${i * 55}ms` },
});
type Tab = (typeof TABS)[number];

export function RecordTabs() {
  const [active, setActive] = useState<Tab>("Transcript");
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const id = useId();

  // The panel's height follows its content smoothly instead of snapping when the
  // tab changes: measure the content, and animate the frame to that height.
  const content = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState<number | null>(null);
  useEffect(() => {
    const el = content.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) =>
      setHeight(entry.contentRect.height),
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Arrow keys move between tabs, per the WAI-ARIA tabs pattern.
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const i = TABS.indexOf(active);
    const delta =
      event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!delta) return;
    event.preventDefault();
    const next = (i + delta + TABS.length) % TABS.length;
    setActive(TABS[next]);
    refs.current[next]?.focus();
  }

  return (
    <>
      <div
        role="tablist"
        aria-label="Transcript view"
        className={s.tabs}
        onKeyDown={onKeyDown}
      >
        {/* The white pill slides under whichever tab is active. */}
        <span
          aria-hidden="true"
          className={s.tabPill}
          style={{ transform: `translateX(${TABS.indexOf(active) * 100}%)` }}
        />
        {TABS.map((tab, i) => (
          <button
            key={tab}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="tab"
            id={`${id}-tab-${tab}`}
            aria-selected={active === tab}
            aria-controls={`${id}-panel`}
            tabIndex={active === tab ? 0 : -1}
            onClick={() => setActive(tab)}
            className={`${s.tab} ${active === tab ? s.tabActive : ""}`}
          >
            {tab}
          </button>
        ))}
      </div>

      <div
        className={s.panelFrame}
        style={height === null ? undefined : { height }}
      >
        <div ref={content}>
          <div
            key={active}
            role="tabpanel"
            id={`${id}-panel`}
            aria-labelledby={`${id}-tab-${active}`}
            className={s.lines}
          >
            {active === "Transcript" &&
              TRANSCRIPT.map((line, i) => (
                <div key={i} {...enter(i)}>
                  <div className={s.lineWho} style={{ color: line.color }}>
                    {line.name}
                    <span>{line.round}</span>
                  </div>
                  <span className={s.lineText}>{line.text}</span>
                </div>
              ))}

            {active === "Votes" &&
              PANEL.map((p) => (
                <div key={p.id} {...enter(PANEL.indexOf(p))}>
                  <div className={s.lineWho} style={{ color: p.color }}>
                    {p.name}
                    <span
                      style={{
                        color:
                          p.vote === "Approve"
                            ? "var(--approve)"
                            : "var(--reject)",
                        fontWeight: 600,
                      }}
                    >
                      {p.vote}
                    </span>
                  </div>
                  <span className={s.lineText}>{p.reason}</span>
                </div>
              ))}

            {active === "Verdict" && (
              <>
                <div {...enter(0)}>
                  <div className={s.lineWho}>
                    Keep sessions. Harden them.
                    <span style={{ color: "var(--approve)", fontWeight: 600 }}>
                      Approved 2–1
                    </span>
                  </div>
                  <span className={s.lineText}>
                    auth.py already stores state server-side; JWT would add
                    revocation work for no clear gain.
                  </span>
                </div>
                <div {...enter(1)}>
                  <div className={s.lineWho}>Next steps</div>
                  <span className={s.lineText}>
                    Set Secure, HttpOnly and SameSite on the cookie; rotate the
                    session ID on login.
                  </span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
