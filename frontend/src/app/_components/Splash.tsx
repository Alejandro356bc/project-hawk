"use client";

import { useEffect, useState } from "react";
import s from "./splash.module.css";

const MIN_VISIBLE_MS = 1250; // the hawk is fully drawn by then; never a flicker
const FADE_MS = 550;

// The hawk from the logo (icons.tsx HawkMark), drawn large for the loader.
const HAWK = "M1.5 12.2C5.4 10.6 9.3 11 12.4 13.6L14 15l1.6-1.4c3.1-2.6 7-3 10.9-1.4-3.4.5-6.4 2.3-8.3 5.1L15.6 21 14 25.5 12.4 21l-2.6-3.7C7.9 14.5 4.9 12.7 1.5 12.2Z";
const HEAD = "M12.6 13.9 14 12l1.4 1.9L14 15.2Z";

/**
 * Full-screen loader shown while the site loads. It is server-rendered, so it
 * covers the page from the first paint, then fades out once the page has
 * loaded (and at least MIN_VISIBLE_MS has passed). A CSS fallback hides it
 * after a few seconds even if scripts never run.
 */
export function Splash() {
  const [phase, setPhase] = useState<"shown" | "leaving" | "gone">("shown");

  useEffect(() => {
    const started = performance.now();
    const timers: number[] = [];
    const leave = () => {
      const wait = Math.max(0, MIN_VISIBLE_MS - (performance.now() - started));
      timers.push(window.setTimeout(() => setPhase("leaving"), wait));
      timers.push(window.setTimeout(() => setPhase("gone"), wait + FADE_MS));
    };
    if (document.readyState === "complete") leave();
    else window.addEventListener("load", leave, { once: true });
    return () => {
      window.removeEventListener("load", leave);
      timers.forEach(clearTimeout);
    };
  }, []);

  if (phase === "gone") return null;

  return (
    <div className={`${s.splash} ${phase === "leaving" ? s.leaving : ""}`} role="status" aria-live="polite" aria-label="Loading Hawk">
      <div className={s.stars} aria-hidden="true" />
      <div className={s.emblem} aria-hidden="true">
        <span className={s.orbit} />
        <span className={s.glow} />
        <span className={s.disc}>
          <svg className={s.hawk} viewBox="0 0 28 28" width="62" height="62">
            <circle className={s.sun} cx="21.5" cy="5.5" r="2.6" />
            <g className={s.wings}>
              <path className={s.body} d={HAWK} pathLength={1} />
              <path className={s.head} d={HEAD} pathLength={1} />
            </g>
          </svg>
        </span>
      </div>
      <span className={s.word} aria-hidden="true">
        Hawk
      </span>
      <span className={s.bar} aria-hidden="true">
        <span />
      </span>
    </div>
  );
}
