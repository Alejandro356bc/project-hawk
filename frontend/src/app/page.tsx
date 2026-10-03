"use client";

import type { FormEvent, KeyboardEvent } from "react";
import { useState } from "react";

const models = [
  { value: "quorum", label: "Quorum panel", detail: "3 voices · balanced" },
  { value: "deep", label: "Deep reasoning", detail: "2 voices · thorough" },
  { value: "quick", label: "Quick answer", detail: "1 voice · fast" },
];

const suggestions = [
  "Compare two approaches",
  "Review this error",
  "Map the tradeoffs",
];

function ArrowUpIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none">
      <path d="M10 15V5m0 0L5.8 9.2M10 5l4.2 4.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SparkIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none">
      <path d="M12 2.75l1.35 5.9a3.6 3.6 0 002.68 2.68L21.93 12l-5.9 1.35a3.6 3.6 0 00-2.68 2.68L12 21.93l-1.35-5.9a3.6 3.6 0 00-2.68-2.68L2.07 12l5.9-1.35a3.6 3.6 0 00-2.68-2.68L12 2.75z" stroke="currentColor" strokeWidth="1.45" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 16 16" fill="none">
      <path d="M4.25 6.25L8 10l3.75-3.75" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 16 16" fill="none">
      <rect x="3.25" y="7" width="9.5" height="6.25" rx="1.6" stroke="currentColor" strokeWidth="1.25" />
      <path d="M5.25 7V5.35a2.75 2.75 0 115.5 0V7" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 16 16" fill="none">
      <path d="M8 3.25v9.5M3.25 8h9.5" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  );
}

export default function Home() {
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState("quorum");
  const [submittedPrompt, setSubmittedPrompt] = useState("");
  const [isFocused, setIsFocused] = useState(false);

  const selectedModel = models.find((item) => item.value === model) ?? models[0];
  const canSubmit = prompt.trim().length > 0;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!canSubmit) return;

    setSubmittedPrompt(prompt.trim());
    setPrompt("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  function applySuggestion(suggestion: string) {
    setPrompt(`${suggestion}: `);
    setSubmittedPrompt("");
  }

  return (
    <div className="quorum-shell">
      <div className="shell-grid" aria-hidden="true" />

      <header className="shell-nav">
        <a className="brand" href="#top" aria-label="Quorum home">
          <span className="brand-mark">Q</span>
          <span className="brand-copy">
            <span className="brand-name">quorum</span>
            <span className="brand-caption">the thinking room</span>
          </span>
        </a>

        <div className="nav-actions">
          <span className="nav-status">
            <span className="status-dot" />
            All systems clear
          </span>
          <button className="avatar-button" type="button" aria-label="Open account menu">
            LS
          </button>
        </div>
      </header>

      <main id="top" className="workspace">
        <section className="hero" aria-labelledby="hero-title">
          <div className="eyebrow">
            <span className="eyebrow-line" />
            <span>Multi-model workspace</span>
          </div>

          <h1 id="hero-title" className="hero-title">
            One question.
            <span className="hero-title-accent">Multiple good answers.</span>
          </h1>

          <p className="hero-intro">
            Bring the hard one. Quorum gathers a panel of models, weighs the
            tradeoffs, and gives you a direction you can trust.
          </p>

          <form
            className={`composer ${isFocused ? "is-focused" : ""}`}
            onSubmit={handleSubmit}
          >
            <div className="composer-main">
              <span className="composer-icon">
                <SparkIcon />
              </span>
              <textarea
                aria-label="Ask Quorum a question"
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                onFocus={() => setIsFocused(true)}
                onBlur={() => setIsFocused(false)}
                onKeyDown={handleKeyDown}
                placeholder="Ask the room anything..."
                rows={3}
              />
            </div>

            <div className="composer-footer">
              <div className="composer-tools">
                <label className="model-picker">
                  <span className="model-picker-icon"><SparkIcon /></span>
                  <select
                    aria-label="Choose a panel mode"
                    value={model}
                    onChange={(event) => setModel(event.target.value)}
                  >
                    {models.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label} · {item.detail}
                      </option>
                    ))}
                  </select>
                  <span className="chevron"><ChevronIcon /></span>
                </label>
                <span className="composer-hint">
                  <kbd>⌘</kbd><kbd>↵</kbd> to run
                </span>
              </div>

              <button className="run-button" type="submit" disabled={!canSubmit} aria-label="Run panel">
                <ArrowUpIcon />
              </button>
            </div>
          </form>

          <div className="suggestions" aria-label="Prompt starters">
            <span className="suggestions-label">Try asking</span>
            {suggestions.map((suggestion) => (
              <button
                className="suggestion-chip"
                type="button"
                key={suggestion}
                onClick={() => applySuggestion(suggestion)}
              >
                <PlusIcon />
                {suggestion}
              </button>
            ))}
          </div>

          {submittedPrompt && (
            <div className="submission-note" role="status">
              <span className="submission-pulse" />
              <span>Panel brief queued with {selectedModel.label.toLowerCase()}.</span>
              <span className="submission-question">“{submittedPrompt}”</span>
            </div>
          )}
        </section>

        <aside className="panel-preview" aria-label="Quorum panel preview">
          <div className="panel-preview-top">
            <span className="panel-kicker">The room</span>
            <span className="live-badge"><span /> Live</span>
          </div>

          <div className="panel-heading">
            <h2>Three ways in.</h2>
            <p>Every perspective earns its seat at the table.</p>
          </div>

          <div className="voice-list">
            <div className="voice-row">
              <span className="voice-avatar voice-avatar-one">O</span>
              <span className="voice-copy"><strong>OpenAI</strong><small>structured thinking</small></span>
              <span className="voice-state">ready</span>
            </div>
            <div className="voice-row">
              <span className="voice-avatar voice-avatar-two">A</span>
              <span className="voice-copy"><strong>Anthropic</strong><small>careful context</small></span>
              <span className="voice-state">ready</span>
            </div>
            <div className="voice-row">
              <span className="voice-avatar voice-avatar-three">G</span>
              <span className="voice-copy"><strong>Gemini</strong><small>wide-angle view</small></span>
              <span className="voice-state">ready</span>
            </div>
          </div>

          <div className="synthesis-card">
            <div className="synthesis-icon"><SparkIcon /></div>
            <div>
              <span className="synthesis-label">Then, one clear direction</span>
              <p>Consensus without the groupthink.</p>
            </div>
            <div className="signal-bars" aria-hidden="true"><i /><i /><i /><i /><i /></div>
          </div>

          <div className="panel-footnote">
            <LockIcon /> Your prompts stay in your workspace.
          </div>
        </aside>
      </main>

      <section className="proof-row" aria-label="How Quorum works">
        <div className="proof-item">
          <span className="proof-number">03</span>
          <span><strong>perspectives</strong><small>on every hard question</small></span>
        </div>
        <div className="proof-divider" />
        <div className="proof-item">
          <span className="proof-number">01</span>
          <span><strong>shared signal</strong><small>after the noise clears</small></span>
        </div>
        <div className="proof-divider" />
        <div className="proof-item">
          <span className="proof-number proof-number-accent">∞</span>
          <span><strong>better questions</strong><small>the more you use it</small></span>
        </div>
      </section>

      <footer className="shell-footer">
        <span>Built for questions that deserve a room.</span>
        <span>Private by default <span className="footer-dot">·</span> <span className="footer-accent">Quorum 01</span></span>
      </footer>
    </div>
  );
}
