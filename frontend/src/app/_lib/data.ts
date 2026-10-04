// Static content for the marketing and discussion pages. Swap these for live
// data once the frontend talks to the Hawk backend.

// next.config.ts sets basePath "/hawk"; next/image needs it on `src`.
export const BASE_PATH = "/hawk";

const logo = (file: string) => `${BASE_PATH}/logos/${file}.svg`;

export const LOGOS = {
  openai: logo("openai"),
  qwen: logo("qwen-color"),
  meta: logo("meta-color"),
  claude: logo("claude-color"),
  gemini: logo("gemini-color"),
  mistral: logo("mistral-color"),
  deepseek: logo("deepseek-color"),
  nvidia: logo("nvidia-color"),
  groq: logo("groq"),
  ollama: logo("ollama"),
  openrouter: logo("openrouter"),
} as const;

export type Vote = "Approve" | "Reject" | "Abstain";

export interface Panelist {
  id: string;
  name: string;
  short: string;
  logo: string;
  color: string;
  provider: string;
  vote: Vote;
  reason: string;
}

export const PANEL: Panelist[] = [
  {
    id: "qwen3-coder",
    name: "Qwen3 Coder",
    short: "Qwen3",
    logo: LOGOS.qwen,
    color: "#5B4FE0",
    provider: "OpenRouter · free",
    vote: "Approve",
    reason: "Sessions match the existing middleware; least code to change.",
  },
  {
    id: "llama-3.3-70b",
    name: "Llama 3.3 70B",
    short: "Llama 3.3",
    logo: LOGOS.meta,
    color: "#0866FF",
    provider: "OpenRouter · free",
    vote: "Reject",
    reason: "A future mobile client may want tokens. Worth planning for now.",
  },
  {
    id: "gpt-oss-120b",
    name: "GPT-OSS 120B",
    short: "GPT-OSS",
    logo: LOGOS.openai,
    color: "#22262F",
    provider: "OpenRouter · free",
    vote: "Approve",
    reason: "Revocation is the deciding factor, and sessions get it for free.",
  },
];

export const QUESTION = "Should we refactor auth.py to use JWT or sessions?";

// --- Orbit -----------------------------------------------------------------

export interface OrbitBody {
  name: string;
  logo: string;
  left: string;
  top: string;
  deg: number;
}

function place(deg: number, radius: number) {
  const a = (deg * Math.PI) / 180;
  return {
    left: `${(50 + radius * Math.cos(a)).toFixed(2)}%`,
    top: `${(50 + radius * Math.sin(a)).toFixed(2)}%`,
    deg,
  };
}

export type SeatStatus = "speaking" | "approve" | "reject";

export const SEATED: (OrbitBody & { model: string; status: SeatStatus })[] = [
  { name: "GPT-OSS 120B", model: "gpt-oss-120b", logo: LOGOS.openai, status: "speaking", ...place(-90, 28) },
  { name: "Qwen3 Coder", model: "qwen3-coder", logo: LOGOS.qwen, status: "approve", ...place(30, 28) },
  { name: "Llama 3.3 70B", model: "llama-3.3-70b", logo: LOGOS.meta, status: "reject", ...place(150, 28) },
];

const ORBITING: [string, string][] = [
  ["Claude Code", LOGOS.claude],
  ["Gemini", LOGOS.gemini],
  ["Mistral", LOGOS.mistral],
  ["DeepSeek", LOGOS.deepseek],
  ["NVIDIA NIM", LOGOS.nvidia],
  ["Groq", LOGOS.groq],
  ["Ollama", LOGOS.ollama],
  ["OpenRouter", LOGOS.openrouter],
];

export const IN_ORBIT: OrbitBody[] = ORBITING.map(([name, src], i) => ({
  name,
  logo: src,
  ...place(-72 + (i * 360) / ORBITING.length, 45),
}));

// --- Demo window -----------------------------------------------------------

const HEIGHTS = [
  30, 45, 38, 60, 52, 70, 44, 36, 58, 80, 66, 48, 40, 62, 90, 74, 55, 42, 68, 84, 60, 46, 52, 76, 88, 64, 50, 40,
  58, 72, 94, 80, 62, 48, 56, 70, 86, 100, 78, 60, 52, 66, 82, 92, 70, 58, 64, 76, 90, 84, 68, 72, 88, 96, 80, 74,
];

export const ACTIVITY = HEIGHTS.map((h, i) => ({
  height: `${h}%`,
  recent: i >= 44,
  delay: `${((i % 7) * -0.23).toFixed(2)}s`,
}));

export interface FeedItem {
  time: string;
  event: string;
  meta?: string;
  tag?: "APPROVE" | "REJECT";
  text: string;
  color: string;
  opacity: number;
}

const C = { qwen: "#5B4FE0", meta: "#0866FF", openai: "#22262F", accent: "var(--accent)" };

export const FEED: FeedItem[] = [
  { time: "14:23:06", event: "gpt-oss.challenge", meta: "3.1s", text: "Short-lived tokens still leave a window after logout.", color: C.accent, opacity: 1 },
  { time: "14:22:58", event: "qwen3.rebuttal", meta: "2.4s", text: "Mobile is hypothetical; a token layer can sit in front later.", color: C.qwen, opacity: 1 },
  { time: "14:22:51", event: "llama.vote", tag: "REJECT", text: "A mobile client is on the roadmap. Avoid migrating twice.", color: C.meta, opacity: 1 },
  { time: "14:22:49", event: "qwen3.vote", tag: "APPROVE", text: "Sessions match the existing middleware.", color: C.qwen, opacity: 1 },
  { time: "14:22:40", event: "llama.challenge", meta: "2.9s", text: "Refresh tokens race a logout. Who handles that?", color: C.meta, opacity: 1 },
  { time: "14:22:31", event: "gpt-oss.answer", meta: "4.2s", text: "JWT means building revocation. That is real work.", color: "#A8A8B0", opacity: 0.85 },
  { time: "14:22:19", event: "llama.answer", meta: "3.6s", text: "JWT scales better if we add a mobile app.", color: C.meta, opacity: 0.7 },
  { time: "14:22:08", event: "qwen3.answer", meta: "2.2s", text: "Keep sessions. The middleware already handles them.", color: C.qwen, opacity: 0.55 },
];

// Deterministic starfield so server and client render the same markup.
export const STARS = Array.from({ length: 44 }, (_, i) => ({
  left: `${((i * 37.3) % 100).toFixed(1)}%`,
  top: `${((i * 17.9 + (i % 3) * 5) % 70).toFixed(1)}%`,
  size: i % 4 === 0 ? 3 : 2,
  opacity: 0.3 + (i % 5) * 0.12,
}));

// Who spoke in which turn, per panelist (how-it-works card).
export const SPEAKING_LANES = [
  [1, 1, 0, 0, 0, 1, 0, 0, 0],
  [0, 0, 1, 1, 0, 0, 1, 0, 0],
  [0, 0, 0, 0, 1, 0, 0, 1, 1],
];

export const TRANSCRIPT = [
  { name: "Qwen3 Coder", color: C.qwen, round: "Round 1", text: "Keep sessions. The middleware already handles them." },
  { name: "Llama 3.3 70B", color: C.meta, round: "Round 1", text: "JWT scales better if we add a mobile app." },
  { name: "GPT-OSS 120B", color: C.openai, round: "Round 1", text: "JWT means building revocation. That is real work." },
  { name: "Llama 3.3 70B", color: C.meta, round: "Round 2", text: "Fair. But refresh races a logout, which we must handle." },
  { name: "Qwen3 Coder", color: C.qwen, round: "Round 2", text: "Agreed. One more reason to stay with sessions." },
];

export const STATS = [
  { big: "3", title: "Panelists on one free key", text: "A single free OpenRouter key seats a full three-model panel from its free models." },
  { big: "9", title: "Providers", text: "Mix free APIs, Ollama's cloud models and paid Anthropic or OpenAI keys." },
  { big: "$0", title: "To get started", text: "Free-tier models and local Ollama mean a full debate never needs a paid subscription." },
];

export type ProviderKind = "free" | "local" | "cli";

export interface Provider {
  name: string;
  logo: string;
  kind: ProviderKind;
}

export const PROVIDER_ROWS: Provider[][] = [
  [
    { name: "OpenRouter", logo: LOGOS.openrouter, kind: "free" },
    { name: "Groq", logo: LOGOS.groq, kind: "free" },
    { name: "Gemini", logo: LOGOS.gemini, kind: "free" },
    { name: "Mistral", logo: LOGOS.mistral, kind: "free" },
  ],
  [
    { name: "NVIDIA NIM", logo: LOGOS.nvidia, kind: "free" },
    { name: "DeepSeek", logo: LOGOS.deepseek, kind: "free" },
    { name: "Ollama Cloud", logo: LOGOS.ollama, kind: "free" },
    { name: "Claude Code", logo: LOGOS.claude, kind: "cli" },
    { name: "Codex", logo: LOGOS.openai, kind: "cli" },
  ],
];

export const PROVIDER_KIND_LABEL: Record<ProviderKind, string> = {
  free: "Free API",
  local: "Local · no key",
  cli: "Paid API",
};

// --- Discussion page -------------------------------------------------------

const byId = Object.fromEntries(PANEL.map((p) => [p.id, p]));
export const panelist = (id: string) => byId[id];
