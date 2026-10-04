// Talks to /api/debate and turns its event stream into round state.
// Event shapes are produced by src/backend/debate.py (run_round).

import { BASE_PATH } from "./data";
import type { Seat } from "./panel";

export type Ballot = "Approve" | "Reject" | "Abstain" | "No Vote";

export interface SeatAnswer {
  text: string;
  vote?: Ballot; // set once the model has finished (or failed)
  error?: string;
  notice?: string; // e.g. "rate limited, retrying in 4s"
}

export interface Decision {
  outcome: "APPROVED" | "REJECTED" | "NO CONSENSUS";
  headline: string;
  reason: string;
  provisional: boolean;
  counts: Record<Ballot, number>;
}

export interface RoundState {
  answers: SeatAnswer[];
  decision?: Decision;
  verdict?: { seat: number; text: string; error?: string };
  status: "running" | "done" | "failed" | "stopped";
  failure?: string;
}

type RoundEvent =
  | { type: "start"; round: number }
  | { type: "delta"; seat: number; text: string }
  | { type: "wait"; seat: number; text: string }
  | { type: "error"; seat: number; message: string }
  | { type: "vote"; seat: number; vote: Ballot }
  | ({ type: "decision" } & Decision)
  | { type: "verdict_start"; seat: number }
  | { type: "verdict_delta"; text: string }
  | { type: "verdict_error"; message: string }
  | { type: "done" };

export const newRound = (size: number): RoundState => ({
  answers: Array.from({ length: size }, () => ({ text: "" })),
  status: "running",
});

const patchAnswer = (r: RoundState, i: number, patch: Partial<SeatAnswer>): RoundState => ({
  ...r,
  answers: r.answers.map((a, j) => (j === i ? { ...a, ...patch } : a)),
});

/** Apply one engine event to a round (pure). */
export function applyEvent(r: RoundState, e: RoundEvent): RoundState {
  switch (e.type) {
    case "delta":
      return patchAnswer(r, e.seat, { text: r.answers[e.seat].text + e.text, notice: undefined });
    case "wait":
      return patchAnswer(r, e.seat, { notice: e.text.trim() });
    case "error":
      return patchAnswer(r, e.seat, { error: e.message, notice: undefined });
    case "vote":
      return patchAnswer(r, e.seat, { vote: e.vote });
    case "decision": {
      const { outcome, headline, reason, provisional, counts } = e;
      return { ...r, decision: { outcome, headline, reason, provisional, counts } };
    }
    case "verdict_start":
      return { ...r, verdict: { seat: e.seat, text: "" } };
    case "verdict_delta":
      return r.verdict ? { ...r, verdict: { ...r.verdict, text: r.verdict.text + e.text } } : r;
    case "verdict_error":
      return { ...r, verdict: { seat: r.verdict?.seat ?? -1, text: r.verdict?.text ?? "", error: e.message } };
    case "done":
      return { ...r, status: "done" };
    default:
      return r;
  }
}

/** What the engine needs from earlier rounds to build the next one's transcript. */
export const toPrevious = (rounds: RoundState[]) =>
  rounds.map((r) => ({ responses: r.answers.map((a) => ({ text: a.text || a.error || "", vote: a.vote ?? "No Vote" })) }));

/** Run one round, calling onEvent for each event. Throws a readable Error on failure. */
export async function streamRound(
  args: { question: string; seats: Seat[]; previous: RoundState[]; userKeys: Record<string, string> },
  onEvent: (e: RoundEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const providers = new Set(args.seats.map((s) => s.provider));
  const res = await fetch(`${BASE_PATH}/api/debate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: args.question,
      seats: args.seats.map(({ provider, model }) => ({ provider, model })),
      previous: toPrevious(args.previous),
      // Only the keys this panel needs; the server fills in the site's keys otherwise.
      userKeys: Object.fromEntries(Object.entries(args.userKeys).filter(([p, k]) => providers.has(p) && k)),
    }),
    signal,
  });
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? "The debate couldn't start.");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)) as RoundEvent);
      }
    }
  }
}
