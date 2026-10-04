// Providers a user can connect, mirroring .env.example and the CLI setup wizard.

import { LOGOS } from "./data";

export type ProviderInput = "key" | "url";

/** One model a provider offers, as returned by /api/models. */
export interface ModelInfo {
  id: string;
  label?: string;
  free?: boolean;
}

export interface ProviderSpec {
  id: string;
  name: string;
  logo: string;
  input: ProviderInput;
  /** The .env variable the backend will read, shown so CLI users recognise it. */
  env: string;
  kind: "Free API" | "Local · no key" | "Paid API";
  placeholder?: string;
  /** Expected key prefixes; a mismatch shows a hint but never blocks saving. */
  prefixes?: string[];
  keyUrl?: string;
  note?: string;
}

export const FEATURED: ProviderSpec = {
  id: "openrouter",
  name: "OpenRouter",
  logo: LOGOS.openrouter,
  input: "key",
  env: "OPENROUTER_API_KEY",
  kind: "Free API",
  placeholder: "sk-or-…",
  prefixes: ["sk-or-"],
  keyUrl: "https://openrouter.ai/keys",
  note: "One free key gives you a full panel of free models.",
};

export const MORE_PROVIDERS: ProviderSpec[] = [
  { id: "groq", name: "Groq", logo: LOGOS.groq, input: "key", env: "GROQ_API_KEY", kind: "Free API", placeholder: "gsk_…", prefixes: ["gsk_"], keyUrl: "https://console.groq.com/keys" },
  { id: "gemini", name: "Gemini", logo: LOGOS.gemini, input: "key", env: "GEMINI_API_KEY", kind: "Free API", placeholder: "Paste your Gemini key", keyUrl: "https://aistudio.google.com/apikey" },
  { id: "mistral", name: "Mistral", logo: LOGOS.mistral, input: "key", env: "MISTRAL_API_KEY", kind: "Free API", placeholder: "Paste your Mistral key", keyUrl: "https://console.mistral.ai/api-keys" },
  { id: "nvidia", name: "NVIDIA NIM", logo: LOGOS.nvidia, input: "key", env: "NVIDIA_API_KEY", kind: "Free API", placeholder: "nvapi-…", prefixes: ["nvapi-"], keyUrl: "https://build.nvidia.com" },
  { id: "tokenharbor", name: "DeepSeek (Token Harbor)", logo: LOGOS.deepseek, input: "key", env: "TOKENHARBOR_API_KEY", kind: "Free API", placeholder: "Paste your Token Harbor key", keyUrl: "https://tokenharbor.ai" },
  { id: "ollama", name: "Ollama Cloud", logo: LOGOS.ollama, input: "key", env: "OLLAMA_API_KEY", kind: "Free API", placeholder: "Paste your Ollama API key", keyUrl: "https://ollama.com/settings/keys", note: "Hosted open models such as GPT-OSS, DeepSeek, Kimi and GLM." },
  {
    id: "claude",
    name: "Claude Code",
    logo: LOGOS.claude,
    input: "key",
    env: "ANTHROPIC_API_KEY",
    kind: "Paid API",
    placeholder: "sk-ant-…",
    prefixes: ["sk-ant-"],
    keyUrl: "https://console.anthropic.com/settings/keys",
    note: "Claude models on a paid Anthropic API key.",
  },
  {
    id: "codex",
    name: "Codex",
    logo: LOGOS.openai,
    input: "key",
    env: "OPENAI_API_KEY",
    kind: "Paid API",
    placeholder: "sk-…",
    prefixes: ["sk-"],
    keyUrl: "https://platform.openai.com/api-keys",
    note: "OpenAI models on a paid OpenAI API key.",
  },
];

export const ALL_PROVIDERS = [FEATURED, ...MORE_PROVIDERS];

export const prefixMismatch = (spec: ProviderSpec, value: string) =>
  !!value && !!spec.prefixes && !spec.prefixes.some((p) => value.startsWith(p));

export const GROUPS: { label: string; providers: ProviderSpec[] }[] = [
  { label: "Recommended", providers: [FEATURED] },
  { label: "Free APIs", providers: MORE_PROVIDERS.filter((p) => p.kind === "Free API") },
  { label: "Local", providers: MORE_PROVIDERS.filter((p) => p.kind === "Local · no key") },
  { label: "Paid APIs", providers: MORE_PROVIDERS.filter((p) => p.kind === "Paid API") },
].filter((g) => g.providers.length > 0);
