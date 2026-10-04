"use client";

import { useEffect, useRef, useState } from "react";
import { CheckIcon, ModelLogo, HawkMark } from "../_components/icons";
import { BASE_PATH } from "../_lib/data";
import { forgetConnections, markOnboarded, saveConnections, type Connections } from "../_lib/keyStore";
import { ALL_PROVIDERS, GROUPS, prefixMismatch, type ModelInfo, type ProviderSpec } from "../_lib/providers";
import s from "./connect.module.css";

/** A panel is exactly this many models. */
const PANEL_SIZE = 3;

type Fetched =
  | { status: "loading" }
  | { status: "ok"; models: ModelInfo[] }
  | { status: "error"; error: string; code?: "missing" | "invalid" | "unreachable"; setup?: string };

type KeyStatus = "idle" | "checking" | "connected" | { error: string };

async function validateKey(provider: string, key: string): Promise<{ error?: string }> {
  try {
    const res = await fetch(`${BASE_PATH}/api/validate-key`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, key }),
    });
    const body: unknown = await res.json().catch(() => ({}));
    if (res.ok && typeof body === "object" && body !== null && "verified" in body && body.verified === true) return {};
    if (typeof body === "object" && body !== null && "error" in body && typeof body.error === "string") {
      return { error: body.error };
    }
    return { error: "Could not verify this key." };
  } catch {
    return { error: "Could not verify this key." };
  }
}

// Model lists come from the site's own keys on the server; visitors don't need one to browse.
async function requestModels(provider: string): Promise<Fetched> {
  try {
    const res = await fetch(`${BASE_PATH}/api/models?provider=${encodeURIComponent(provider)}`);
    const body = await res.json();
    return res.ok && body.models
      ? { status: "ok", models: body.models as ModelInfo[] }
      : { status: "error", error: body.error ?? "Couldn't load models.", code: body.code, setup: body.setup };
  } catch {
    return { status: "error", error: "Couldn't load models." };
  }
}

/**
 * "Connect your models": platforms on the left, the selected one on the right,
 * where a key can be checked and the platform's models picked. Shown on a first
 * visit and from the history panel's API keys button.
 */
export function ConnectDialog({ initial, onClose }: { initial: Connections; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const validationAttempt = useRef<Record<string, number>>({});
  const [keys, setKeys] = useState<Record<string, string>>(initial.keys);
  // Stored keys must be verified again: previous versions only marked a key as
  // connected based on text being present, not on the platform accepting it.
  const [keyStatus, setKeyStatus] = useState<Record<string, KeyStatus>>({});
  const [picked, setPicked] = useState<Record<string, string[]>>(initial.models ?? {});
  const [fetched, setFetched] = useState<Record<string, Fetched>>(() =>
    Object.fromEntries(ALL_PROVIDERS.map((p) => [p.id, { status: "loading" } as Fetched])),
  );
  const [activeId, setActiveId] = useState(ALL_PROVIDERS[0].id);

  const active = ALL_PROVIDERS.find((p) => p.id === activeId) ?? ALL_PROVIDERS[0];
  // A platform is connected only after its provider accepts the entered key.
  const isConnected = (p: ProviderSpec) => keyStatus[p.id] === "connected" || (p.input === "url" && !!picked[p.id]?.length);
  // The panel is the models picked on platforms that are listing right now AND
  // for which the visitor added their own key (debates run on the visitor's key).
  const pickedTotal = ALL_PROVIDERS.reduce((sum, p) => {
    const f = fetched[p.id];
    if (f?.status !== "ok" || !isConnected(p)) return sum;
    const available = new Set(f.models.map((m) => m.id));
    return sum + (picked[p.id] ?? []).filter((id) => available.has(id)).length;
  }, 0);
  const ready = pickedTotal === PANEL_SIZE;
  const hadAny = Object.values(initial.keys).some(Boolean);

  // Nothing is pre-picked: the visitor chooses their own panel.
  function applyModels(p: ProviderSpec, next: Fetched) {
    setFetched((f) => ({ ...f, [p.id]: next }));
  }

  function reload(p: ProviderSpec) {
    setFetched((f) => ({ ...f, [p.id]: { status: "loading" } }));
    requestModels(p.id).then((next) => applyModels(p, next));
  }

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
    // Check every platform up front so each one's status shows in the list.
    for (const p of ALL_PROVIDERS) requestModels(p.id).then((next) => applyModels(p, next));
  }, []);

  function select(p: ProviderSpec) {
    setActiveId(p.id);
    if (!fetched[p.id]) reload(p);
  }

  function close() {
    ref.current?.close();
    onClose();
  }

  function save() {
    const trimmed = Object.fromEntries(
      Object.entries(keys)
        .map(([k, v]) => [k, v.trim()])
        .filter(([id, v]) => {
          const provider = ALL_PROVIDERS.find((p) => p.id === id);
          return !!v && !!provider && isConnected(provider);
        }),
    );
    saveConnections({ keys: trimmed, enabled: {}, models: picked });
    close();
  }

  // Skipping still counts as answering, so the dialog won't reopen on every visit.
  function skip() {
    markOnboarded();
    close();
  }

  function forget() {
    forgetConnections();
    close();
  }

  function updateKey(provider: string, value: string) {
    validationAttempt.current[provider] = (validationAttempt.current[provider] ?? 0) + 1;
    setKeys((current) => ({ ...current, [provider]: value }));
    setKeyStatus((current) => ({ ...current, [provider]: "idle" }));
  }

  async function connect(provider: ProviderSpec) {
    const key = keys[provider.id]?.trim() ?? "";
    if (!key) return;

    const attempt = (validationAttempt.current[provider.id] ?? 0) + 1;
    validationAttempt.current[provider.id] = attempt;
    setKeyStatus((current) => ({ ...current, [provider.id]: "checking" }));
    const result = await validateKey(provider.id, key);
    // Ignore a response for a key that was edited while the request was active.
    if (validationAttempt.current[provider.id] !== attempt) return;
    setKeyStatus((current) => ({ ...current, [provider.id]: result.error ? { error: result.error } : "connected" }));
  }

  return (
    <dialog
      ref={ref}
      className={s.dialog}
      aria-labelledby="connect-title"
      onCancel={(e) => {
        // Esc behaves like "Skip for now".
        e.preventDefault();
        skip();
      }}
    >
      <header className={s.head}>
        <span className={s.mark}>
          <HawkMark size={20} sun="#FFFFFF" ink="#FFFFFF" />
        </span>
        <div>
          <h2 id="connect-title" className={s.title}>
            Connect your models
          </h2>
          <p className={s.desc}>Browse each platform&apos;s models, add your API key, and pick 3 models. Debates run on your own keys.</p>
        </div>
      </header>

      <div className={s.main}>
        <nav className={s.side} aria-label="Platforms">
          {GROUPS.map((group) => (
            <div key={group.label} className={s.group}>
              <span className={s.groupLabel}>{group.label}</span>
              {group.providers.map((p) => {
                const on = isConnected(p);
                const n = picked[p.id]?.length ?? 0;
                const health = statusOf(fetched[p.id]);
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => select(p)}
                    aria-current={p.id === active.id ? "true" : undefined}
                    className={`${s.item} ${p.id === active.id ? s.itemActive : ""}`}
                  >
                    <span className={s.itemLogo}>
                      <ModelLogo src={p.logo} size={14} />
                      {health && <span className={`${s.dot} ${s[health.tone]}`} aria-hidden="true" />}
                    </span>
                    <span className={s.itemName}>
                      {p.name}
                      {health && <span className="sr-only">, {health.label}</span>}
                    </span>
                    {(n > 0 || on) && (
                      <span className={s.itemStatus} aria-label={n ? `${n} ${n === 1 ? "model" : "models"} picked` : "Connected"}>
                        {n ? n : <CheckIcon size={10} strokeWidth={3} />}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        <section className={s.detail} aria-labelledby="detail-title" key={active.id}>
          <ProviderDetail
            spec={active}
            value={keys[active.id] ?? ""}
            onValue={(v) => updateKey(active.id, v)}
            connected={isConnected(active)}
            status={keyStatus[active.id] ?? "idle"}
            onConnect={() => void connect(active)}
            fetched={fetched[active.id]}
            picked={picked[active.id] ?? []}
            onPick={(ids) => setPicked((cur) => ({ ...cur, [active.id]: ids }))}
            canPickMore={pickedTotal < PANEL_SIZE}
            hasKey={isConnected(active)}
          />
        </section>
      </div>

      <footer className={s.foot}>
        <p className={s.privacy}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="5" y="11" width="14" height="9" rx="2" />
            <path d="M8 11V8a4 4 0 0 1 8 0v3" />
          </svg>
          <span className={s.privacyText}>
            Keys are stored in this browser. Connecting verifies a key only with its selected platform; Hawk never saves it on the server.
          </span>
          {hadAny && (
            <button type="button" className={s.forget} onClick={forget}>
              Forget all keys
            </button>
          )}
        </p>
        <div className={s.actions}>
          <button type="button" className={s.skip} onClick={skip}>
            Skip for now
          </button>
          <button type="button" className={s.save} onClick={save} disabled={!ready}>
            <CheckIcon size={14} strokeWidth={2.6} />
            {ready
              ? `Continue with these ${PANEL_SIZE} models`
              : pickedTotal > PANEL_SIZE
                ? `Too many: unpick ${pickedTotal - PANEL_SIZE} (${pickedTotal}/${PANEL_SIZE})`
                : `Pick ${PANEL_SIZE} models (${pickedTotal}/${PANEL_SIZE})`}
          </button>
        </div>
      </footer>
    </dialog>
  );
}

/** A dot in the platform list while checking and once the site key works; nothing otherwise. */
function statusOf(f?: Fetched): { tone: "dotOk" | "dotWait"; label: string } | null {
  if (!f) return null;
  if (f.status === "loading") return { tone: "dotWait", label: "checking" };
  if (f.status === "ok") return { tone: "dotOk", label: "working" };
  return null;
}

function ProviderDetail({
  spec,
  value,
  onValue,
  connected,
  status,
  onConnect,
  fetched,
  picked,
  onPick,
  canPickMore,
  hasKey,
}: {
  spec: ProviderSpec;
  value: string;
  onValue: (v: string) => void;
  connected: boolean;
  status: KeyStatus;
  onConnect: () => void;
  fetched?: Fetched;
  picked: string[];
  onPick: (ids: string[]) => void;
  canPickMore: boolean;
  hasKey: boolean;
}) {
  const [visible, setVisible] = useState(false);
  const isUrl = spec.input === "url";
  const paid = spec.kind === "Paid API";
  const id = `key-${spec.id}`;
  const mismatch = prefixMismatch(spec, value.trim());
  const checking = status === "checking";
  const hasError = typeof status === "object";
  const statusClass = checking ? s.statusChecking : connected ? s.statusConnected : hasError ? s.statusError : "";

  return (
    <>
      <div className={s.detailHead}>
        <span className={s.detailLogo}>
          <ModelLogo src={spec.logo} size={24} />
        </span>
        <div className={s.detailWho}>
          <h3 id="detail-title" className={s.detailName}>
            {spec.name}
            {spec.id === "openrouter" && <span className={s.badge}>Recommended</span>}
          </h3>
          <span className={s.kind}>{spec.kind}</span>
        </div>
        {spec.keyUrl && (
          <a href={spec.keyUrl} target="_blank" rel="noreferrer" className={s.getKey}>
            Get a key ↗
          </a>
        )}
      </div>

      {spec.note && <p className={s.detailNote}>{spec.note}</p>}

      {isUrl && <p className={s.hint}>Shows the models installed in Ollama on the machine running Hawk.</p>}

      {spec.input === "key" && (
        <div className={s.field}>
          <label htmlFor={id} className={s.label}>
            Your API key{" "}
            <span className={s.optional}>{paid ? "required to use these models · paid, billed to your account" : "required to use these models · runs on your free tokens"}</span>
          </label>
          <div className={s.keyControlRow}>
            <div className={`${s.inputRow} ${mismatch ? s.inputWarn : ""}`}>
              <input
                id={id}
                type={visible ? "text" : "password"}
                value={value}
                onChange={(e) => onValue(e.target.value)}
                placeholder={spec.placeholder}
                autoComplete="off"
                spellCheck={false}
                aria-describedby={`${id}-hint`}
                className={s.input}
              />
              <button
                type="button"
                className={s.inline}
                onClick={() => setVisible((v) => !v)}
                aria-label={visible ? `Hide ${spec.name} key` : `Show ${spec.name} key`}
              >
                {visible ? "Hide" : "Show"}
              </button>
            </div>
            <button
              type="button"
              className={`${s.connectButton} ${checking ? s.connectionChecking : ""} ${connected ? s.connectionActive : ""} ${hasError ? s.connectionFailed : ""}`}
              onClick={onConnect}
              disabled={!value.trim() || checking || connected}
              aria-busy={checking}
              aria-label={connected ? `${spec.name} key connected` : checking ? `Verifying ${spec.name} key` : `Connect ${spec.name} key`}
            >
              {checking ? (
                <>
                  <span className={s.connectionSpinner} aria-hidden="true" />
                  Verifying
                </>
              ) : connected ? (
                <>
                  <CheckIcon size={14} strokeWidth={3} aria-hidden="true" />
                  Connected
                </>
              ) : (
                "Connect"
              )}
            </button>
          </div>
          <span
            id={`${id}-hint`}
            className={`${s.hint} ${mismatch ? s.hintWarn : ""} ${hasError ? s.hintError : ""} ${statusClass}`}
            aria-live="polite"
          >
            {connected
              ? "Connected. This key was accepted by the platform."
              : checking
                ? `Verifying your ${spec.name} key…`
                : hasError
                  ? status.error
              : mismatch
                    ? `${spec.name} keys usually start with ${spec.prefixes?.join(" or ")}.`
                    : paid
                      ? "Verify your key before using these paid models."
                      : "Verify your key before using these models."}
          </span>
        </div>
      )}

      {/* Only a working key shows anything here; a missing or broken one shows nothing. */}
      {(fetched?.status === "loading" || fetched?.status === "ok") && (
        <h4 className={s.sectionTitle}>Available models</h4>
      )}
      {fetched?.status === "loading" && (
        <>
          <p className={s.checking}>Checking the key…</p>
          <ModelSkeleton />
        </>
      )}
      {fetched?.status === "ok" && (
        <ModelPicker
          models={fetched.models}
          picked={picked}
          onPick={onPick}
          canPickMore={canPickMore}
          hasKey={hasKey}
          platform={spec.name}
          freeFilter={spec.id === "openrouter"}
        />
      )}
    </>
  );
}

function ModelPicker({
  models,
  picked,
  onPick,
  freeFilter,
  canPickMore,
  hasKey,
  platform,
}: {
  models: ModelInfo[];
  picked: string[];
  onPick: (ids: string[]) => void;
  freeFilter: boolean;
  canPickMore: boolean;
  hasKey: boolean;
  platform: string;
}) {
  const [query, setQuery] = useState("");
  const [freeOnly, setFreeOnly] = useState(freeFilter);
  const pickedSet = new Set(picked);
  const q = query.trim().toLowerCase();
  // Picked models first so choices stay visible.
  const shown = models
    .filter((m) => (!freeOnly || m.free) && (!q || m.id.toLowerCase().includes(q) || m.label?.toLowerCase().includes(q)))
    .sort((a, b) => Number(pickedSet.has(b.id)) - Number(pickedSet.has(a.id)));

  const togglePick = (id: string) => onPick(pickedSet.has(id) ? picked.filter((p) => p !== id) : [...picked, id]);

  return (
    <div className={s.picker}>
      <div className={s.pickerBar}>
        <span className={s.ok}>
          <CheckIcon size={12} strokeWidth={3} />
          {models.length} models available
        </span>
        <span className={s.pickedCount}>{picked.length} picked</span>
      </div>
      <div className={s.pickerHint} aria-live="polite">
        {!hasKey
          ? `Add your ${platform} API key above to use these models.`
          : canPickMore
            ? "Your panel debates with exactly 3 models, from any platforms."
            : "Your panel is full (3 models). Unpick one to choose another."}
      </div>
      <div className={s.pickerTools}>
        <label htmlFor="model-search" className="sr-only">
          Search models
        </label>
        <input
          id="model-search"
          className={s.search}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search models…"
          autoComplete="off"
        />
        {freeFilter && (
          <label className={s.freeToggle}>
            <input type="checkbox" checked={freeOnly} onChange={(e) => setFreeOnly(e.target.checked)} />
            Free only
          </label>
        )}
      </div>
      <ul className={s.models}>
        {shown.slice(0, 200).map((m) => (
          <li key={m.id}>
            <label className={`${s.model} ${pickedSet.has(m.id) ? s.modelOn : ""}`}>
              <input
                type="checkbox"
                checked={pickedSet.has(m.id)}
                disabled={!pickedSet.has(m.id) && (!hasKey || !canPickMore)}
                onChange={() => togglePick(m.id)}
              />
              <span className={s.modelText}>
                {m.label && m.label !== m.id && <span className={s.modelLabel}>{m.label}</span>}
                <span className={s.modelId}>{m.id}</span>
              </span>
              {m.free && <span className={s.free}>FREE</span>}
            </label>
          </li>
        ))}
        {shown.length === 0 && <li className={s.empty}>No models match.</li>}
        {shown.length > 200 && <li className={s.empty}>Showing 200 of {shown.length}. Search to narrow down.</li>}
      </ul>
    </div>
  );
}

function ModelSkeleton() {
  return (
    <div className={s.skeleton} role="status" aria-label="Loading models">
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} style={{ width: `${88 - i * 9}%` }} />
      ))}
    </div>
  );
}
