"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Lottie } from "lottie-react";

import { docsApi, type DocsSource } from "@/lib/api";
import { cn } from "@/lib/utils";
import handshake from "./handshake.json";

/**
 * The community documents assistant, as a floating panel.
 *
 * Mounted once in the layout, so it is on every page without any page knowing
 * about it. Everything it says comes from the association's own PDFs by way of
 * `/api/v1/docs/ask`; there is no client-side knowledge here at all, which is
 * why a refusal looks different from an answer rather than merely reading
 * differently.
 */

interface Turn {
  role: "user" | "bot";
  text: string;
  /** Undefined on a user turn. False marks a refusal or a failure. */
  grounded?: boolean;
  sources?: DocsSource[];
  failed?: boolean;
}

// Survives navigation between pages, and is deliberately session rather than
// local: a shared machine in a leasing office should not show the last
// person's questions tomorrow.
const HISTORY_KEY = "serenity_help_history";

function load<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function HelpWidget() {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [greeting, setGreeting] = useState("");
  const [starters, setStarters] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  /**
   * Earlier questions come back when the panel is opened, not when the page
   * mounts.
   *
   * Two reasons, and they point the same way. The pages are a static export, so
   * reading sessionStorage while rendering gives the server one answer and the
   * browser another, and React discards the hydration. And restoring in an
   * effect means calling setState from inside one, which the lint rule forbids
   * for good reason: it is a second render pass every visitor pays for, on
   * every page, to fill a panel most of them never open.
   *
   * Opening is a real user event, so it is the honest place for it.
   */
  const restored = useRef(false);
  const toggle = useCallback(() => {
    setOpen((wasOpen) => {
      if (!wasOpen && !restored.current) {
        restored.current = true;
        const saved = load<Turn[]>(HISTORY_KEY, []);
        if (saved.length) setTurns(saved);
      }
      return !wasOpen;
    });
  }, []);

  // Writing is safe in an effect: no state changes, so no extra render.
  useEffect(() => {
    if (turns.length) sessionStorage.setItem(HISTORY_KEY, JSON.stringify(turns));
  }, [turns]);

  // The starters are fetched on first open rather than on mount, so a visitor
  // who never opens the panel pays nothing for it.
  useEffect(() => {
    if (!open || starters.length || greeting) return;
    const abort = new AbortController();
    docsApi
      .suggestions(abort.signal)
      .then((s) => {
        setGreeting(s.greeting);
        setStarters(s.questions);
      })
      .catch(() => {
        // Losing the starters is not worth an error state: the panel is still
        // perfectly usable by typing, so it degrades to just the input.
        setGreeting("Ask me anything about the community rules or the application process.");
      });
    return () => abort.abort();
  }, [open, starters.length, greeting]);

  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  /**
   * Keep the newest turn in view.
   *
   * Two bugs live here, both found by watching it rather than by reading it.
   * Setting `scrollTop` straight from the effect runs before the browser has
   * laid the new bubble out, so the height is still the old one and the panel
   * stops short; hence the frame's wait. And `scrollIntoView` on a sentinel,
   * which was the first fix, scrolls the nearest scrollable ancestor, which
   * for a `position: fixed` panel can be the page behind it: restoring a
   * conversation left the panel showing its own top. Moving the container's
   * own `scrollTop` cannot pick the wrong element.
   */
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      const list = listRef.current;
      if (list) list.scrollTop = list.scrollHeight;
    });
    return () => cancelAnimationFrame(id);
  }, [turns, busy, open]);

  // Escape closes, matching every other dismissible layer in the app.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const send = useCallback(
    async (question: string) => {
      const text = question.trim();
      if (!text || busy) return;

      setDraft("");
      setTurns((t) => [...t, { role: "user", text }]);
      setBusy(true);
      try {
        const reply = await docsApi.ask(text);
        setTurns((t) => [
          ...t,
          {
            role: "bot",
            text: reply.answer,
            grounded: reply.grounded,
            sources: reply.sources,
          },
        ]);
      } catch {
        // A network failure is not "the documents do not say", and must never
        // be dressed up as one. It gets its own wording and its own styling.
        setTurns((t) => [
          ...t,
          {
            role: "bot",
            text: "Something went wrong reaching the assistant. Please try again.",
            grounded: false,
            failed: true,
          },
        ]);
      } finally {
        setBusy(false);
        requestAnimationFrame(() => inputRef.current?.focus());
      }
    },
    [busy]
  );

  const empty = turns.length === 0;

  return (
    <>
      {/* ── the launcher ────────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-controls="help-panel"
        aria-label={open ? "Close the help assistant" : "Ask about the community rules"}
        className={cn(
          "fixed bottom-5 right-5 z-50 flex h-14 w-14 items-center justify-center",
          "rounded-full bg-brand-500 shadow-pop transition-all duration-200",
          "hover:bg-brand-600 hover:scale-105 active:scale-95",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500",
          // Out of the way when the panel is up on a phone, where the panel
          // covers the screen and a button on top of it is just clutter.
          open && "max-sm:pointer-events-none max-sm:opacity-0"
        )}
      >
        {open ? (
          <svg className="h-6 w-6 text-white" fill="none" stroke="currentColor" strokeWidth={2.2} viewBox="0 0 24 24" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        ) : (
          <Lottie src={handshake} loop className="h-9 w-9" />
        )}
      </button>

      {/* ── the panel ───────────────────────────────────────────────────── */}
      {open && (
        <div
          id="help-panel"
          ref={panelRef}
          role="dialog"
          aria-label="Community rules assistant"
          className={cn(
            "fixed z-50 flex flex-col overflow-hidden border border-line bg-surface shadow-pop",
            // Phone: a full sheet, because a 380px card on a 360px screen is a
            // scrollbar with a chat in it.
            "max-sm:inset-0 max-sm:rounded-none",
            // Desktop: a card sitting above the launcher.
            "sm:bottom-24 sm:right-5 sm:h-[560px] sm:max-h-[calc(100dvh-8rem)] sm:w-[380px] sm:rounded-sheet"
          )}
        >
          <header className="flex items-center gap-3 border-b border-line bg-brand-50 px-4 py-3">
            <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-brand-500">
              <Lottie src={handshake} loop className="h-6 w-6" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-ink">Community assistant</p>
              <p className="truncate text-xs text-ink-muted">Answers from the Serenity documents</p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Minimise"
              className="flex h-8 w-8 items-center justify-center rounded-control text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2.2} viewBox="0 0 24 24" aria-hidden>
                <path strokeLinecap="round" d="M6 12h12" />
              </svg>
            </button>
            <button
              type="button"
              onClick={() => {
                setTurns([]);
                sessionStorage.removeItem(HISTORY_KEY);
                setOpen(false);
              }}
              aria-label="Close and clear the conversation"
              className="flex h-8 w-8 items-center justify-center rounded-control text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2.2} viewBox="0 0 24 24" aria-hidden>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </header>

          <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
            {empty && (
              <div className="space-y-3">
                <p className="rounded-card bg-surface-sunken px-3.5 py-2.5 text-sm leading-relaxed text-ink">
                  {greeting || "Loading…"}
                </p>
                {starters.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-ink-faint">Try one of these</p>
                    {starters.map((q) => (
                      <button
                        key={q}
                        type="button"
                        onClick={() => send(q)}
                        className="block w-full rounded-control border border-line px-3.5 py-2.5 text-left text-sm text-ink transition-colors hover:border-brand-300 hover:bg-brand-50"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {turns.map((turn, i) =>
              turn.role === "user" ? (
                <div key={i} className="flex justify-end">
                  <p className="max-w-[85%] rounded-card bg-brand-500 px-3.5 py-2.5 text-sm leading-relaxed text-white">
                    {turn.text}
                  </p>
                </div>
              ) : (
                <div key={i} className="space-y-1.5">
                  <p
                    className={cn(
                      "max-w-[92%] rounded-card px-3.5 py-2.5 text-sm leading-relaxed",
                      turn.failed
                        ? "border border-danger/25 bg-danger-soft text-ink"
                        : turn.grounded
                          ? "bg-surface-sunken text-ink"
                          : // Not an answer. Styled as a note so it cannot be
                            // mistaken for one at a glance.
                            "border border-line bg-warn-soft text-ink"
                    )}
                  >
                    {turn.text}
                  </p>
                  {turn.grounded && turn.sources && turn.sources.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {turn.sources.map((s) => (
                        <span
                          key={s.section}
                          title={s.document}
                          className="rounded-full border border-line bg-surface px-2 py-0.5 text-[11px] text-ink-muted"
                        >
                          {s.section}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )
            )}

            {busy && (
              <div className="flex items-center gap-1.5 rounded-card bg-surface-sunken px-3.5 py-3 w-fit" aria-label="Looking through the documents">
                {[0, 150, 300].map((delay) => (
                  <span
                    key={delay}
                    className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-faint"
                    style={{ animationDelay: `${delay}ms` }}
                  />
                ))}
              </div>
            )}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(draft);
            }}
            className="flex items-center gap-2 border-t border-line px-3 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]"
          >
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask about the rules…"
              maxLength={500}
              disabled={busy}
              aria-label="Your question"
              className="h-10 min-w-0 flex-1 rounded-control border border-line bg-surface px-3 text-sm text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-brand-400 disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={busy || !draft.trim()}
              aria-label="Send"
              className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-control bg-brand-500 text-white transition-colors hover:bg-brand-600 disabled:opacity-40"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2.2} viewBox="0 0 24 24" aria-hidden>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </button>
          </form>
        </div>
      )}
    </>
  );
}
