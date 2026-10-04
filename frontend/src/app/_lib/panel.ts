// The visitor's debate panel: exactly 3 models picked in "Connect your models".

import type { Connections } from "./keyStore";
import { ALL_PROVIDERS } from "./providers";

export const PANEL_SIZE = 3;

export interface Seat {
  provider: string; // platform id, e.g. "groq"
  model: string; // model id on that platform
  name: string; // short display name
  platform: string; // platform display name
  logo: string;
}

/** A compact label from a model id: "openai/gpt-oss-20b" -> "GPT-OSS 20B". */
export function displayName(model: string): string {
  // "gpt-oss:120b" (Ollama) keeps its size tag; ":free" / ":latest" are dropped.
  const [base, tag] = model.split("/").pop()!.split(":");
  const core = tag && !/^(free|latest)$/i.test(tag) ? `${base}-${tag}` : base;
  const words: string[] = [];
  for (const w of core.replace(/_/g, "-").split("-")) {
    const lower = w.toLowerCase();
    if (!w || lower === "latest") continue;
    // "opus-5-5" -> "Opus 5.5"
    if (/^\d+$/.test(w) && /^\d+$/.test(words.at(-1) ?? "")) {
      words[words.length - 1] += `.${w}`;
      continue;
    }
    if (lower === "gpt" || lower === "oss" || lower === "glm") words.push(lower.toUpperCase());
    else if (/^\d+(\.\d+)?[bkm]$/.test(lower)) words.push(lower.toUpperCase()); // sizes: 20b -> 20B
    else if (/^[a-z]{1,2}[0-9.]+$/.test(lower)) words.push(lower.toUpperCase()); // o3, v4.1, k2.6
    else words.push(w.charAt(0).toUpperCase() + w.slice(1));
  }
  return words.join(" ").replace(/^GPT OSS/, "GPT-OSS");
}

/** Picked models the visitor can run (their key for that platform is added), in platform order. */
export function seatsFrom(c: Connections): Seat[] {
  const seats: Seat[] = [];
  for (const p of ALL_PROVIDERS) {
    if (!c.keys?.[p.id]?.trim()) continue; // debates run on the visitor's own key
    for (const model of c.models?.[p.id] ?? []) {
      seats.push({ provider: p.id, model, name: displayName(model), platform: p.name, logo: p.logo });
    }
  }
  return seats.slice(0, PANEL_SIZE);
}
