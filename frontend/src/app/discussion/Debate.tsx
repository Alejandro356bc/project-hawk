"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import { CheckIcon, ModelLogo, HawkMark, XIcon } from "../_components/icons";
import { Markdown } from "../_components/Markdown";
import type { Ballot, RoundState } from "../_lib/debateClient";
import type { Seat } from "../_lib/panel";
import s from "./discussion.module.css";

const VOTE_CLASS: Record<Ballot, string> = {
  Approve: s.vApprove,
  Reject: s.vReject,
  Abstain: s.vAbstain,
  "No Vote": s.vAbstain,
};

const WIRE_H = 64;
const GRID_GAP = 14; // keep in sync with .terminals gap

/** Curves from the hub (top center) down to the center of each of the three columns. */
function wirePaths(width: number) {
  const col = (width - 2 * GRID_GAP) / 3;
  const mid = width / 2;
  return [col / 2, mid, width - col / 2].map((x) =>
    x === mid
      ? `M${mid} 0 L${mid} ${WIRE_H}`
      : `M${mid} 0 C${mid} ${WIRE_H * 0.55} ${x} ${WIRE_H * 0.35} ${x} ${WIRE_H}`,
  );
}

function useWidth(ref: RefObject<HTMLElement | null>) {
  const [width, setWidth] = useState(820);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}

/** What the hub says about the latest round. */
function phase(round: RoundState | undefined, number: number) {
  if (!round) return { label: "", busy: false, thinking: false };
  if (round.status === "failed") return { label: round.failure ?? "The debate failed.", busy: false, thinking: false };
  if (round.status === "stopped") return { label: `Round ${number} stopped`, busy: false, thinking: false };
  if (round.status === "done") return { label: `Conclusion after round ${number}`, busy: false, thinking: false };
  const started = round.answers.some((a) => a.text || a.error);
  const voted = round.answers.every((a) => a.vote);
  if (!started) return { label: number === 1 ? "Connecting the panel" : `Starting round ${number}`, busy: true, thinking: true };
  if (!voted) return { label: `Round ${number} · the panel is thinking`, busy: true, thinking: true };
  if (!round.decision) return { label: "Counting votes", busy: true, thinking: false };
  return { label: "Writing the conclusion", busy: true, thinking: false };
}

/**
 * One question being debated live: the Hawk hub, wires to each panelist's
 * terminal, their answers round by round, and the conclusion.
 */
export function Debate({ question, seats, rounds }: { question: string; seats: Seat[]; rounds: RoundState[] }) {
  const current = rounds.at(-1);
  const number = rounds.length;
  const { label, busy, thinking } = phase(current, number);

  const grid = useRef<HTMLDivElement>(null);
  const width = useWidth(grid);

  // Keep the newest part in view while a round plays out.
  const end = useRef<HTMLDivElement>(null);
  const stage = current ? `${current.answers.filter((a) => a.vote).length}-${!!current.decision}-${!!current.verdict}-${current.status}` : "";
  useEffect(() => {
    if (busy) end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [busy, stage]);

  const writer = current?.verdict ? seats[current.verdict.seat] : undefined;

  return (
    <div className={s.debate}>
      <div className={s.userRow}>
        <p className={s.userBubble}>{question}</p>
      </div>

      <div className={s.hub} aria-live="polite" aria-busy={busy}>
        <span className={`${s.hubNode} ${busy ? s.hubNodeLive : ""}`}>
          <HawkMark size={22} sun="#FFFFFF" ink="#FFFFFF" />
        </span>
        <span className={s.hubName}>Hawk</span>
        <span className={`${s.hubStatus} ${current?.status === "failed" ? s.hubStatusError : ""}`}>{label}</span>
      </div>

      <svg
        className={`${s.wires} ${number === 1 && busy ? s.wiresDraw : ""} ${thinking ? s.wiresFlow : ""}`}
        viewBox={`0 0 ${width} ${WIRE_H}`}
        aria-hidden="true"
      >
        {wirePaths(width).map((d) => (
          <g key={d}>
            <path d={d} pathLength={1} className={s.wire} />
            <path d={d} pathLength={1} className={s.wirePulse} />
          </g>
        ))}
      </svg>

      <div className={s.terminals} ref={grid}>
        {seats.map((seat, i) => (
          <Terminal key={`${seat.provider}:${seat.model}:${i}`} seat={seat} index={i} rounds={rounds} />
        ))}
      </div>

      {current?.decision && (
        <section className={s.conclusion} aria-label="Conclusion">
          <span aria-hidden="true" className={s.conclusionGlow} />
          <div className={s.conclusionHead}>
            <span>
              CONCLUSION · ROUND {number}
              {writer && <> · WRITTEN BY {writer.name.toUpperCase()}</>}
            </span>
            <span className={`${s.approvedTag} ${current.decision.outcome !== "APPROVED" ? s.approvedTagOff : ""}`}>
              {current.decision.outcome === "APPROVED" ? <CheckIcon size={10} strokeWidth={3} /> : current.decision.outcome === "REJECTED" ? <XIcon size={10} strokeWidth={3} /> : null}
              {current.decision.headline} {current.decision.counts.Approve}–{current.decision.counts.Reject}
            </span>
          </div>
          <p className={s.decisionReason}>{current.decision.reason}</p>
          {current.verdict?.error ? (
            <p className={s.verdictError}>{current.verdict.error}</p>
          ) : (
            <div className={s.conclusionBody}>
              {current.verdict?.text ? (
                <Markdown text={current.verdict.text} className={s.markdown} />
              ) : (
                <p className={s.verdictWaiting}>Writing the conclusion…</p>
              )}
              {current.status === "running" && current.verdict && <span aria-hidden="true" className={s.caretLight} />}
            </div>
          )}
        </section>
      )}
      <div ref={end} />
    </div>
  );
}

function Terminal({ seat, index, rounds }: { seat: Seat; index: number; rounds: RoundState[] }) {
  const body = useRef<HTMLDivElement>(null);
  const live = rounds.at(-1);
  const streaming = live?.status === "running" && !live.answers[index].vote;
  const length = rounds.reduce((n, r) => n + r.answers[index].text.length, 0);

  // Follow the text as it streams in, like a real terminal.
  useEffect(() => {
    if (streaming && body.current) body.current.scrollTop = body.current.scrollHeight;
  }, [streaming, length]);

  return (
    <section className={s.terminal} style={{ animationDelay: `${index * 140}ms` }} aria-label={`${seat.name} answer`}>
      <div className={s.termBar}>
        <span aria-hidden="true" className={s.macLights}>
          <span style={{ background: "#FF5F57" }} />
          <span style={{ background: "#FEBC2E" }} />
          <span style={{ background: "#28C840" }} />
        </span>
        <span className={s.termTitle}>
          <span className={s.termLogo}>
            <ModelLogo src={seat.logo} size={11} />
          </span>
          <span className={s.termTitleText}>{seat.model} — zsh</span>
        </span>
      </div>
      <div className={s.termBody} ref={body} tabIndex={0}>
        {rounds.map((round, r) => {
          const answer = round.answers[index];
          const isLive = r === rounds.length - 1 && round.status === "running" && !answer.vote;
          return (
            <div key={r} className={s.termBlock}>
              <div>
                <span className={s.termPrompt}>{seat.provider}@hawk ~ %</span> <span className={s.termCmd}>answer #{r + 1}</span>
              </div>
              {answer.text && (
                <div className={s.termText}>
                  {answer.text}
                  {isLive && <span aria-hidden="true" className={s.termCursor} />}
                </div>
              )}
              {!answer.text && isLive && (
                <div className={s.termDim}>
                  {answer.notice ?? "thinking"}
                  <span aria-hidden="true" className={s.termCursor} />
                </div>
              )}
              {answer.error && <div className={s.termError}>✕ {answer.error}</div>}
              {answer.vote && <div className={`${s.termVote} ${VOTE_CLASS[answer.vote]}`}>→ vote: {answer.vote.toUpperCase()}</div>}
              {!answer.vote && round.status !== "running" && <div className={s.termDim}>(stopped)</div>}
            </div>
          );
        })}
        {!streaming && (
          <div>
            <span className={s.termPrompt}>{seat.provider}@hawk ~ %</span> <span aria-hidden="true" className={s.termCursor} />
          </div>
        )}
      </div>
    </section>
  );
}
