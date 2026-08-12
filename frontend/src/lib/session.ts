"use client";

// A stable per-browser session id. The backend keys the conversation memory and
// the server-side cart on this, so it must persist across reloads.
const KEY = "ai_order_session_id";

export function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let id = window.localStorage.getItem(KEY);
  if (!id) {
    id = (crypto?.randomUUID?.() ?? `s_${Date.now()}_${Math.random().toString(36).slice(2)}`).replace(/-/g, "");
    window.localStorage.setItem(KEY, id);
  }
  return id;
}

export function resetSessionId(): void {
  if (typeof window !== "undefined") window.localStorage.removeItem(KEY);
}
