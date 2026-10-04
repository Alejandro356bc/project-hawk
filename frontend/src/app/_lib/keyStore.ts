// Connected-provider settings, kept in this browser's localStorage.
//
// The visitor's own API keys are kept in this browser. They are transiently
// sent to the selected platform to verify a connection and to run the visitor's
// debates; Hawk never stores them on its server. Model lists use site keys.

import { useSyncExternalStore } from "react";

export interface Connections {
  keys: Record<string, string>; // provider id -> key or URL
  enabled: Record<string, boolean>; // provider id -> on (CLIs)
  models: Record<string, string[]>; // provider id -> model ids picked for the panel
  onboarded: boolean; // the first-visit dialog has been answered
}

const STORAGE_KEY = "hawk.connections.v1";
const EMPTY: Connections = { keys: {}, enabled: {}, models: {}, onboarded: false };
// On the server nothing is known; report "onboarded" so the dialog never renders there.
const SERVER: Connections = { ...EMPTY, onboarded: true };

const listeners = new Set<() => void>();
let cachedRaw: string | null | undefined;
let cached: Connections = EMPTY;

function read(): Connections {
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    // Storage blocked (private mode, policy): behave as a first visit.
  }
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    try {
      cached = raw ? { ...EMPTY, ...JSON.parse(raw) } : EMPTY;
    } catch {
      cached = EMPTY;
    }
  }
  return cached;
}

function write(next: Connections) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Can't persist; keep it for this page view so the dialog still closes.
    cachedRaw = undefined;
    cached = next;
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const onStorage = (e: StorageEvent) => e.key === STORAGE_KEY && listener();
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export function useConnections(): Connections {
  return useSyncExternalStore(subscribe, read, () => SERVER);
}

export const saveConnections = (next: Omit<Connections, "onboarded">) => write({ ...next, onboarded: true });

export const markOnboarded = () => write({ ...read(), onboarded: true });

export const forgetConnections = () => write({ ...EMPTY, onboarded: true });

export const connectedCount = (c: Connections) => Object.values(c.keys).filter((v) => v.trim()).length;
