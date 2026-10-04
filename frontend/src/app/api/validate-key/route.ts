// POST /api/validate-key — verify a visitor's key with its selected platform.
//
// The key exists only for this request: it is never logged, cached, or stored
// on the server. A successful response means the platform accepted the key;
// the browser remains responsible for storing it locally for a later debate.

const TIMEOUT_MS = 12_000;
const AUTH_FAILURE = /api[ _-]?key|invalid.*(key|credential)|unauthenticated|authentication|not authorized/i;

type Provider =
  | "openrouter"
  | "groq"
  | "gemini"
  | "mistral"
  | "nvidia"
  | "tokenharbor"
  | "ollama"
  | "claude"
  | "codex";

const PROVIDERS = new Set<Provider>([
  "openrouter",
  "groq",
  "gemini",
  "mistral",
  "nvidia",
  "tokenharbor",
  "ollama",
  "claude",
  "codex",
]);

class KeyRejected extends Error {}
class PlatformUnavailable extends Error {}

const bearer = (key: string) => ({ Authorization: `Bearer ${key}` });

function keyWasRejected(status: number, text: string) {
  return status === 401 || status === 403 || (status === 400 && AUTH_FAILURE.test(text));
}

/** A normal authenticated endpoint; any 2xx response proves the key works. */
async function authenticatedGet(url: string, headers: Record<string, string>) {
  const response = await fetch(url, {
    headers,
    signal: AbortSignal.timeout(TIMEOUT_MS),
    cache: "no-store",
  });
  const text = await response.text();
  if (keyWasRejected(response.status, text)) throw new KeyRejected();
  if (!response.ok) throw new PlatformUnavailable();
}

/**
 * NVIDIA and Ollama expose public model catalogues, so listing models cannot
 * prove a supplied key. Their gateway rejects an unknown model after checking
 * authentication; that failure is deliberately used as a no-cost auth probe.
 */
async function authenticatedGateway(url: string, key: string) {
  const response = await fetch(url, {
    method: "POST",
    headers: { ...bearer(key), "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "hawk-key-validation-model",
      messages: [{ role: "user", content: "Validate this API key." }],
      max_tokens: 1,
      stream: false,
    }),
    signal: AbortSignal.timeout(TIMEOUT_MS),
    cache: "no-store",
  });
  const text = await response.text();
  if (keyWasRejected(response.status, text)) throw new KeyRejected();
  // An authenticated gateway rejects this intentionally non-existent model.
  if (response.ok || response.status === 400 || response.status === 404) return;
  throw new PlatformUnavailable();
}

async function verify(provider: Provider, key: string) {
  switch (provider) {
    case "openrouter":
      return authenticatedGet("https://openrouter.ai/api/v1/key", bearer(key));
    case "groq":
      return authenticatedGet("https://api.groq.com/openai/v1/models", bearer(key));
    case "gemini":
      return authenticatedGet("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1", {
        "x-goog-api-key": key,
      });
    case "mistral":
      return authenticatedGet("https://api.mistral.ai/v1/models", bearer(key));
    case "nvidia":
      return authenticatedGateway("https://integrate.api.nvidia.com/v1/chat/completions", key);
    case "tokenharbor":
      return authenticatedGet("https://tokenharbor.ai/v1/models", bearer(key));
    case "ollama":
      return authenticatedGateway("https://ollama.com/api/chat", key);
    case "claude":
      return authenticatedGet("https://api.anthropic.com/v1/models?limit=1", {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
      });
    case "codex":
      return authenticatedGet("https://api.openai.com/v1/models", bearer(key));
  }
}

export async function POST(request: Request) {
  let body: { provider?: unknown; key?: unknown };
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid request." }, { status: 400 });
  }

  if (typeof body.provider !== "string" || !PROVIDERS.has(body.provider as Provider)) {
    return Response.json({ error: "Unknown platform." }, { status: 400 });
  }
  if (typeof body.key !== "string") {
    return Response.json({ error: "Enter an API key first." }, { status: 400 });
  }

  const key = body.key.trim();
  // API credentials are printable ASCII tokens. Reject malformed pasted input
  // locally instead of allowing header construction to fail ambiguously.
  if (!key || key.length > 512 || !/^[\x21-\x7e]+$/.test(key)) {
    return Response.json({ error: "Enter a valid API key without spaces or special characters." }, { status: 400 });
  }

  try {
    await verify(body.provider as Provider, key);
    return Response.json({ verified: true });
  } catch (error) {
    if (error instanceof KeyRejected) {
      return Response.json({ error: "This platform rejected the API key." }, { status: 401 });
    }
    return Response.json(
      { error: "Could not verify this key right now. Try again shortly." },
      { status: 502 },
    );
  }
}
