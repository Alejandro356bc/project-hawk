// GET /api/models?provider=<id> — the models a platform offers.
//
// Lists are fetched with the *site's* keys (frontend/.env.local, server-only), so
// visitors can browse models without entering anything. A visitor's own key is
// only for spending their free tokens and is never needed here.
//
// Models are only returned when that key is present AND works, so an empty or
// broken key is visible as such ("missing" / "invalid") instead of being hidden
// behind a public catalogue.

import { createHash } from "node:crypto";
import type { ModelInfo } from "../../_lib/providers";

const TIMEOUT_MS = 12_000;
const CACHE_MS = 10 * 60_000; // catalogues change rarely; don't hit providers on every click

type Code = "missing" | "invalid" | "unreachable";

class UpstreamError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: Code = "unreachable",
  ) {
    super(message);
  }
}

async function getJson(url: string, headers: Record<string, string>) {
  const res = await fetch(url, { headers, signal: AbortSignal.timeout(TIMEOUT_MS), cache: "no-store" });
  const text = await res.text();
  // Gemini reports a bad key as 400 API_KEY_INVALID rather than 401.
  const badKey = res.status === 401 || res.status === 403 || (res.status === 400 && /api[ _]key/i.test(text));
  if (badKey) throw new UpstreamError("Key not working: the platform rejected it.", 502, "invalid");
  if (!res.ok) throw new UpstreamError(`The platform answered ${res.status}.`, 502);
  try {
    return JSON.parse(text);
  } catch {
    throw new UpstreamError("The platform sent an unexpected answer.", 502);
  }
}

const bearer = (key: string) => ({ Authorization: `Bearer ${key}` });

interface Lister {
  /** Server env var holding the site's key; omitted when no key is needed (Ollama). */
  env?: string;
  /** Proves the key works, for platforms whose model list is public. */
  verify?: (key: string) => Promise<void>;
  list: (key: string) => Promise<ModelInfo[]>;
}

/** OpenAI-compatible `GET /models` → `{ data: [{ id }] }`. */
const openAiCompatible = (env: string, base: string): Lister => ({
  env,
  async list(key) {
    const body = await getJson(`${base}/models`, bearer(key));
    return (body.data ?? []).map((m: { id: string }) => ({ id: m.id }));
  },
});

const LISTERS: Record<string, Lister> = {
  openrouter: {
    env: "OPENROUTER_API_KEY",
    // The catalogue is public, so check the key itself first.
    async verify(key) {
      await getJson("https://openrouter.ai/api/v1/key", bearer(key));
    },
    async list(key) {
      const body = await getJson("https://openrouter.ai/api/v1/models", bearer(key));
      return (body.data ?? []).map(
        (m: { id: string; name?: string; pricing?: { prompt?: string; completion?: string } }) => ({
          id: m.id,
          label: m.name,
          free: m.id.endsWith(":free") || (m.pricing?.prompt === "0" && m.pricing?.completion === "0"),
        }),
      );
    },
  },
  groq: openAiCompatible("GROQ_API_KEY", "https://api.groq.com/openai/v1"),
  mistral: openAiCompatible("MISTRAL_API_KEY", "https://api.mistral.ai/v1"),
  nvidia: {
    ...openAiCompatible("NVIDIA_API_KEY", "https://integrate.api.nvidia.com/v1"),
    // NVIDIA's model list is public and it has no key-check endpoint.
    async verify(key) {
      await gatewayCheck("https://integrate.api.nvidia.com/v1/chat/completions", key, {
        model: NVIDIA_PROBE_MODEL,
        messages: [{ role: "user", content: "OK" }],
        max_tokens: 1,
      });
    },
  },
  tokenharbor: openAiCompatible("TOKENHARBOR_API_KEY", "https://tokenharbor.ai/v1"),
  gemini: {
    env: "GEMINI_API_KEY",
    async list(key) {
      const body = await getJson("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000", {
        "x-goog-api-key": key,
      });
      return (body.models ?? [])
        .filter((m: { supportedGenerationMethods?: string[] }) => m.supportedGenerationMethods?.includes("generateContent"))
        .map((m: { name: string; displayName?: string }) => ({ id: m.name.replace(/^models\//, ""), label: m.displayName }));
    },
  },
  // Claude Code / Codex run on a subscription via their CLIs, or on a paid API key.
  // These lists need the key, so a list coming back also proves the key works.
  claude: {
    env: "ANTHROPIC_API_KEY",
    async list(key) {
      const body = await getJson("https://api.anthropic.com/v1/models?limit=1000", {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
      });
      return (body.data ?? []).map((m: { id: string; display_name?: string }) => ({ id: m.id, label: m.display_name }));
    },
  },
  codex: {
    env: "OPENAI_API_KEY",
    async list(key) {
      const body = await getJson("https://api.openai.com/v1/models", bearer(key));
      // Only models that can take part in a debate (chat/reasoning), not embeddings, audio, images…
      const chat = /^(gpt-|o\d|chatgpt|codex)/;
      const notChat = /(embedding|audio|realtime|transcribe|tts|whisper|dall-e|image|moderation|search)/;
      return (body.data ?? [])
        .filter((m: { id: string }) => chat.test(m.id) && !notChat.test(m.id))
        .map((m: { id: string }) => ({ id: m.id }));
    },
  },
  ollama: {
    // Ollama Cloud: hosted open models. The catalogue is public, so check the key first.
    env: "OLLAMA_API_KEY",
    async verify(key) {
      await gatewayCheck("https://ollama.com/api/chat", key, {
        model: OLLAMA_PROBE_MODEL,
        messages: [{ role: "user", content: "OK" }],
        stream: false,
        options: { num_predict: 1 },
      });
    },
    async list(key) {
      const body = await getJson("https://ollama.com/api/tags", bearer(key));
      return (body.models ?? []).map((m: { name: string }) => ({ id: m.name }));
    },
  },
};

const NVIDIA_PROBE_MODEL = "deepseek-ai/deepseek-v4.1-flash";
const OLLAMA_PROBE_MODEL = "gpt-oss:20b";
const AUTH_WINDOW_MS = 8_000;

/**
 * Key check for platforms whose model list is public and that have no key
 * endpoint (NVIDIA, Ollama Cloud). A wrong key is refused at the gateway within
 * a second (401/403), while a valid one queues for the model, which can take a
 * while to wake. So: a quick 401/403 means the key is bad; any other answer, or
 * none within the window, means it got past the gateway. The request is
 * cancelled before it costs anything.
 */
async function gatewayCheck(url: string, key: string, body: object) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), AUTH_WINDOW_MS);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { ...bearer(key), "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
      cache: "no-store",
    });
    if (res.status === 401 || res.status === 403) {
      throw new UpstreamError("Key not working: the platform rejected it.", 502, "invalid");
    }
  } catch (e) {
    if (e instanceof UpstreamError) throw e;
    if (controller.signal.aborted) return; // still waiting on the model: the key was accepted
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

// Keyed by provider + a fingerprint of the key, so editing .env.local takes effect at once.
const cache = new Map<string, { at: number; models: ModelInfo[] }>();

// Speech, image, embedding and safety-classifier models can't debate; don't offer them.
const NOT_CHAT = /(whisper|orpheus|tts|transcribe|audio|speech|embed|rerank|moderation|guard|imagen|image|dall-e|veo|lyria|aqa|ocr|vision-only)/i;
const canDebate = (m: ModelInfo) => !NOT_CHAT.test(m.id) && !NOT_CHAT.test(m.label ?? "");
const fingerprint = (key: string) => createHash("sha256").update(key).digest("hex").slice(0, 12);

export async function GET(request: Request) {
  const provider = new URL(request.url).searchParams.get("provider") ?? "";
  const lister = LISTERS[provider];
  if (!lister) return Response.json({ error: "Unknown platform." }, { status: 400 });

  const key = lister.env ? (process.env[lister.env] ?? "").trim() : "";
  if (lister.env && !key) {
    return Response.json(
      { error: "Not connected: no key set.", code: "missing", setup: lister.env },
      // Expected state (the platform just isn't set up), so not an HTTP error.
      { status: 200 },
    );
  }

  const cacheKey = `${provider}:${fingerprint(key)}`;
  const hit = cache.get(cacheKey);
  if (hit && Date.now() - hit.at < CACHE_MS) return Response.json({ models: hit.models });

  try {
    await lister.verify?.(key);
    const models = (await lister.list(key)).filter(canDebate).sort((a, b) => a.id.localeCompare(b.id));
    cache.set(cacheKey, { at: Date.now(), models });
    return Response.json({ models });
  } catch (e) {
    if (e instanceof UpstreamError) {
      return Response.json({ error: e.message, code: e.code, setup: lister.env }, { status: e.status });
    }
    const timedOut = e instanceof DOMException && e.name === "TimeoutError";
    return Response.json(
      {
        error: timedOut ? "Couldn't check the key: the platform took too long to answer." : "Couldn't reach the platform.",
        code: "unreachable",
      },
      { status: 502 },
    );
  }
}
