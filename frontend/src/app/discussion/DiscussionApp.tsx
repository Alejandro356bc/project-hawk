"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ModelLogo, PlusIcon, HawkMark, StopIcon } from "../_components/icons";
import { ParticleRing } from "../_components/ParticleRing";
import { applyEvent, newRound, streamRound, type RoundState } from "../_lib/debateClient";
import { connectedCount, useConnections } from "../_lib/keyStore";
import { PANEL_SIZE, seatsFrom, type Seat } from "../_lib/panel";
import { ConnectDialog } from "./ConnectDialog";
import { Debate } from "./Debate";
import { VotesPanel } from "./VotesPanel";
import s from "./discussion.module.css";

const MAX_ROUNDS = 3;

interface Conversation {
  id: number;
  title: string;
  when: string;
  question: string;
  seats: Seat[]; // the panel this debate was held with
  rounds: RoundState[];
}

let nextId = 1;

export function DiscussionApp() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [running, setRunning] = useState<number | null>(null); // conversation with a round in flight
  const [panel, setPanel] = useState<"history" | "votes" | null>(null);
  const connections = useConnections();
  const [keysOpen, setKeysOpen] = useState(false);
  const abort = useRef<AbortController | null>(null);

  // First visit: ask for API keys before anything else.
  const showConnect = !connections.onboarded || keysOpen;
  const connected = connectedCount(connections);
  const seats = seatsFrom(connections);
  const panelReady = seats.length === PANEL_SIZE;

  const active = conversations.find((c) => c.id === activeId) ?? null;
  const busy = running !== null;

  // Leaving the page stops any debate in flight.
  useEffect(() => () => abort.current?.abort(), []);

  const updateRound = (convoId: number, fn: (r: RoundState) => RoundState) =>
    setConversations((cs) =>
      cs.map((c) => (c.id === convoId ? { ...c, rounds: c.rounds.map((r, i) => (i === c.rounds.length - 1 ? fn(r) : r)) } : c)),
    );

  async function runRound(convo: Conversation, previous: RoundState[]) {
    const controller = new AbortController();
    abort.current = controller;
    setRunning(convo.id);
    try {
      await streamRound(
        { question: convo.question, seats: convo.seats, previous, userKeys: connections.keys },
        (event) => updateRound(convo.id, (r) => applyEvent(r, event)),
        controller.signal,
      );
      // A stream that ends early (engine restarted, network) still leaves a settled round.
      updateRound(convo.id, (r) => (r.status === "running" ? { ...r, status: "failed", failure: "The debate ended unexpectedly." } : r));
    } catch (e) {
      const stopped = controller.signal.aborted;
      updateRound(convo.id, (r) => ({
        ...r,
        status: stopped ? "stopped" : "failed",
        failure: stopped ? undefined : e instanceof Error ? e.message : "The debate failed.",
      }));
    } finally {
      if (abort.current === controller) abort.current = null;
      setRunning(null);
    }
  }

  function ask(question: string) {
    const q = question.trim();
    if (!q || busy || !panelReady) return;
    const convo: Conversation = {
      id: nextId++,
      title: q.length > 40 ? `${q.slice(0, 38)}…` : q,
      when: new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }),
      question: q,
      seats,
      rounds: [newRound(PANEL_SIZE)],
    };
    setConversations((cs) => [convo, ...cs]);
    setActiveId(convo.id);
    setDraft("");
    setPanel(null);
    runRound(convo, []);
  }

  function nextRound() {
    if (!active || busy || active.rounds.length >= MAX_ROUNDS) return;
    const previous = active.rounds;
    const updated = { ...active, rounds: [...previous, newRound(PANEL_SIZE)] };
    setConversations((cs) => cs.map((c) => (c.id === active.id ? updated : c)));
    runRound(updated, previous);
  }

  function stop() {
    abort.current?.abort();
  }

  function open(id: number | null) {
    if (busy) return;
    setActiveId(id);
    setPanel(null);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    ask(draft);
  }

  const placeholder = !panelReady
    ? "Pick 3 models to start a debate"
    : busy
      ? "The panel is debating…"
      : active
        ? "Ask the panel a new question…"
        : "Ask the panel anything…";

  const composer = (
    <form className={s.composer} onSubmit={submit}>
      <label htmlFor="ask" className="sr-only">
        Ask the panel
      </label>
      <input
        id="ask"
        className={s.input}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder={placeholder}
        autoComplete="off"
        maxLength={4000}
        disabled={busy || !panelReady}
      />
      {busy ? (
        <button type="button" aria-label="Stop the debate" className={s.send} onClick={stop}>
          <StopIcon size={12} />
        </button>
      ) : (
        <button type="submit" aria-label="Send to panel" className={s.send} disabled={!panelReady || !draft.trim()}>
          <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M8 5.5v13l11-6.5z" fill="currentColor" />
          </svg>
        </button>
      )}
    </form>
  );

  // The panel shown before a debate: who will answer.
  const panelLine = panelReady ? (
    <div className={s.panelLine}>
      <span className={s.panelLabel}>Your panel</span>
      {seats.map((seat, i) => (
        <span key={`${seat.provider}:${seat.model}:${i}`} className={s.panelChip} title={`${seat.platform} · ${seat.model}`}>
          <span className={s.panelChipLogo}>
            <ModelLogo src={seat.logo} size={12} />
          </span>
          {seat.name}
        </span>
      ))}
      <button type="button" className={s.panelChange} onClick={() => setKeysOpen(true)}>
        Change
      </button>
    </div>
  ) : (
    <button type="button" className={s.choosePanel} onClick={() => setKeysOpen(true)}>
      Choose your 3 models ({seats.length}/{PANEL_SIZE})
    </button>
  );

  return (
    <div className={s.shell}>
      <div className={s.toggles}>
        <button type="button" className={s.toggle} aria-expanded={panel === "history"} onClick={() => setPanel(panel === "history" ? null : "history")}>
          History
        </button>
        <button type="button" className={`${s.toggle} ${s.toggleBlue}`} aria-expanded={panel === "votes"} onClick={() => setPanel(panel === "votes" ? null : "votes")}>
          Votes
        </button>
      </div>

      {/* Left: floating history */}
      <aside className={`${s.float} ${s.floatLeft} ${panel === "history" ? s.floatShown : ""}`} aria-label="History">
        <Link href="/" className={s.brand}>
          <HawkMark size={22} sun="#FFFFFF" ink="#FFFFFF" />
          Hawk
        </Link>
        <button type="button" className={s.newChat} onClick={() => open(null)} disabled={busy}>
          <PlusIcon size={15} strokeWidth={2.2} />
          New discussion
        </button>
        <div className={s.floatHead}>
          <span>History</span>
        </div>
        <nav className={s.history} aria-label="Past discussions">
          {conversations.length === 0 && <p className={s.historyEmpty}>Your debates will appear here.</p>}
          {conversations.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => open(c.id)}
              disabled={busy && c.id !== activeId}
              aria-current={c.id === activeId ? "page" : undefined}
              className={`${s.historyItem} ${c.id === activeId ? s.historyActive : ""}`}
            >
              <span className={s.historyTitle}>{c.title}</span>
              <span className={s.historyWhen}>
                {c.when} · {c.rounds.length} {c.rounds.length === 1 ? "round" : "rounds"}
              </span>
            </button>
          ))}
        </nav>

        <button type="button" className={s.keysButton} onClick={() => setKeysOpen(true)}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="8" cy="15" r="4" />
            <path d="M10.8 12.2 20 3M16 7l3 3M14 9l2 2" />
          </svg>
          Models &amp; keys
          <span className={s.keysCount}>{connected ? `${connected} keys` : `${seats.length}/${PANEL_SIZE} models`}</span>
        </button>
      </aside>

      {/* Middle: the chat */}
      <main className={s.chat}>
        {active ? (
          <>
            <div className={s.scroll}>
              <Debate key={active.id} question={active.question} seats={active.seats} rounds={active.rounds} />
            </div>
            <div className={s.dock}>{composer}</div>
          </>
        ) : (
          <div className={s.hero}>
            <h1 className="sr-only">Ask the Hawk panel</h1>
            <div className={s.ring}>
              <ParticleRing className={s.ringCanvas} />
              <span className={s.ringLabel}>Hawk</span>
            </div>
            {composer}
            {panelLine}
          </div>
        )}
      </main>

      {/* Right: floating votes (blue) */}
      <VotesPanel
        seats={active ? active.seats : seats}
        rounds={active?.rounds ?? []}
        running={busy}
        onNextRound={nextRound}
        onChoose={() => setKeysOpen(true)}
        className={panel === "votes" ? s.floatShown : ""}
      />

      {showConnect && <ConnectDialog initial={connections} onClose={() => setKeysOpen(false)} />}
    </div>
  );
}
