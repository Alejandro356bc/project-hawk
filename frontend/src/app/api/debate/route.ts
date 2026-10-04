// POST /api/debate — run one debate round on the Hawk engine (src/backend).
//
// The browser sends the question, the 3 picked models and the visitor's own API
// keys. Debates always run on the VISITOR'S keys: the site's keys in
// frontend/.env.local only list models (see /api/models) and are never used to
// answer anyone's question.

import { ALL_PROVIDERS } from "../../_lib/providers";

const nameOf = Object.fromEntries(ALL_PROVIDERS.map((p) => [p.id, p.name]));

const ENGINE_URL = process.env.HAWK_ENGINE_URL || "http://127.0.0.1:8787";
const PANEL_SIZE = 3;

interface Body {
  question?: string;
  seats?: { provider?: string; model?: string }[];
  previous?: unknown[];
  userKeys?: Record<string, string>;
}

const known = new Set(ALL_PROVIDERS.map((p) => p.id));

export async function POST(request: Request) {
  let body: Body;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid request." }, { status: 400 });
  }

  const question = (body.question ?? "").trim();
  if (!question) return Response.json({ error: "Ask a question first." }, { status: 400 });
  if (!Array.isArray(body.seats) || body.seats.length !== PANEL_SIZE) {
    return Response.json({ error: `A debate needs exactly ${PANEL_SIZE} models.` }, { status: 400 });
  }

  const seats = [];
  for (const seat of body.seats) {
    const provider = seat.provider ?? "";
    if (!known.has(provider) || !seat.model) return Response.json({ error: "Unknown model or platform." }, { status: 400 });
    const key = (body.userKeys?.[provider] ?? "").trim();
    if (!key) {
      return Response.json(
        { error: `Add your own ${nameOf[provider]} API key in "Models & keys" to use this model.`, code: "needs_key", provider },
        { status: 400 },
      );
    }
    seats.push({ provider, model: seat.model, key });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${ENGINE_URL}/debate/round`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, seats, previous: body.previous ?? [] }),
      signal: request.signal, // stop the debate if the visitor leaves or presses Stop
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { error: "The Hawk engine isn't running. Start it with: python -m uvicorn backend.main:app --port 8787" },
      { status: 503 },
    );
  }

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text().catch(() => "");
    return Response.json(
      { error: upstream.status === 422 ? "The engine rejected the request." : "The Hawk engine failed.", detail: detail.slice(0, 300) },
      { status: 502 },
    );
  }

  return new Response(upstream.body, {
    headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-store" },
  });
}
