"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

/**
 * Where a question went, and who answered it.
 *
 * The client asked to see the journey rather than a spinner: which stages ran,
 * how long each took, and whether the reply came from our own hardware or from
 * Gemini. Two components, because there are two honest things to show.
 *
 * `JourneyPending` runs while the request is in flight. It names the stages and
 * moves through them, and it deliberately shows no numbers at all: nothing has
 * been measured yet, and a millisecond count invented in the browser to fill a
 * gap is a lie that looks like telemetry.
 *
 * `JourneyResult` replaces it once the answer lands, and every figure in it is
 * measured on the server and carried back on the reply.
 *
 * Both degrade to nothing. A backend that sends no trace, or an error that
 * sends none, leaves the chat exactly as it was.
 */

export interface TraceStage {
  name: string;
  label: string;
  ms: number;
  detail?: string;
}

export interface TraceEngine {
  /** What the platform switch was set to when the question arrived. */
  chosen: string;
  /** What actually wrote the reply. "none" when no model was called at all. */
  used: string;
  fell_back: boolean;
  reason: string;
  model: string;
}

export interface RequestTrace {
  id: string;
  agent: string;
  at: number;
  total_ms: number;
  engine: TraceEngine;
  stages: TraceStage[];
}

/** The stages a question goes through, in order. Named the same on the server. */
const STEPS = [
  { name: "understand", label: "Understanding" },
  { name: "retrieve", label: "Searching" },
  { name: "engine", label: "Asking the model" },
  { name: "compose", label: "Writing the reply" },
];

/** How long to dwell on each stage before moving the highlight along. This is a
 *  cadence, not a measurement: it is why nothing here prints a number. */
const DWELL_MS = 900;

function seconds(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Colour carries meaning here: green is hardware we control, blue is the cloud
 *  engine, grey is a reply that needed no model, amber is a fallback. */
function engineLook(engine: TraceEngine) {
  if (engine.fell_back) {
    return { tone: "bg-warn-soft text-warn border-warn/30", dot: "bg-warn" };
  }
  if (engine.used === "gpu") {
    return { tone: "bg-positive-soft text-positive border-positive/30", dot: "bg-positive" };
  }
  if (engine.used === "gemini") {
    return { tone: "bg-blue-50 text-blue-700 border-blue-200", dot: "bg-blue-500" };
  }
  return { tone: "bg-surface-sunken text-ink-muted border-line", dot: "bg-ink-faint" };
}

function engineName(engine: TraceEngine): string {
  if (engine.used === "gpu") return "our own GPU";
  if (engine.used === "gemini") return "Gemini";
  return "no model";
}

/** The one line somebody reads without expanding anything. */
function engineSummary(engine: TraceEngine): string {
  if (engine.fell_back) {
    return `Started on ${engineName({ ...engine, used: engine.chosen })}, answered by ${engineName(engine)}`;
  }
  if (engine.used === "none") return "Answered without calling a model";
  return `Answered by ${engineName(engine)}`;
}

// ── while the answer is still coming ────────────────────────────────────────

export function JourneyPending() {
  const [active, setActive] = useState(0);

  useEffect(() => {
    // Somebody who has asked for less motion still needs to know it is working,
    // so the stages are all shown at once rather than cycling.
    const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (still) {
      setActive(STEPS.length - 1);
      return;
    }

    // Stops on the last stage rather than looping back to the first. The reply
    // has not arrived, so claiming it has started over would be wrong.
    const tick = setInterval(() => {
      setActive((i) => (i < STEPS.length - 1 ? i + 1 : i));
    }, DWELL_MS);
    return () => clearInterval(tick);
  }, []);

  return (
    <div
      className="flex flex-wrap items-center gap-x-2 gap-y-1.5 rounded-card border border-line bg-surface px-3.5 py-2.5"
      role="status"
      aria-live="polite"
      aria-label={`Working: ${STEPS[active].label}`}
    >
      {STEPS.map((step, i) => {
        const done = i < active;
        const now = i === active;
        return (
          <span key={step.name} className="flex items-center gap-2">
            {i > 0 && <span aria-hidden className="text-ink-faint">&rsaquo;</span>}
            <span
              className={cn(
                "flex items-center gap-1.5 text-xs transition-colors",
                now ? "font-semibold text-ink" : done ? "text-ink-muted" : "text-ink-faint"
              )}
            >
              <span
                aria-hidden
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  now ? "animate-rise bg-brand-500" : done ? "bg-ink-faint" : "bg-line-strong"
                )}
              />
              {step.label}
            </span>
          </span>
        );
      })}
    </div>
  );
}

// ── once it has arrived ─────────────────────────────────────────────────────

export function JourneyResult({ trace }: { trace?: RequestTrace | null }) {
  const [open, setOpen] = useState(false);

  // No trace is not an error. An older backend, or a reply that never reached
  // the pipeline, simply has no journey to show.
  if (!trace || !trace.engine) return null;

  const look = engineLook(trace.engine);
  const stages = trace.stages ?? [];

  return (
    <div className="mt-2.5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 rounded-control px-1 py-1 text-left transition-colors hover:bg-surface-hover"
      >
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium",
            look.tone
          )}
        >
          <span aria-hidden className={cn("h-1.5 w-1.5 rounded-full", look.dot)} />
          {engineSummary(trace.engine)}
        </span>

        <span className="text-[11px] tabular-nums text-ink-faint">{seconds(trace.total_ms)}</span>

        <svg
          aria-hidden
          className={cn(
            "ml-auto h-3.5 w-3.5 flex-shrink-0 text-ink-faint transition-transform",
            open && "rotate-180"
          )}
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
        <span className="sr-only">{open ? "Hide the journey" : "Show the journey"}</span>
      </button>

      {open && (
        <div className="mt-1.5 rounded-card border border-line bg-surface-sunken px-3 py-2.5">
          <ol className="flex flex-col gap-1.5">
            {stages.map((stage) => (
              <li key={stage.name} className="flex items-baseline gap-2 text-[11.5px]">
                <span className="min-w-[7.5rem] font-medium text-ink">{stage.label}</span>
                <span className="tabular-nums text-ink-muted">{seconds(stage.ms)}</span>
                {stage.detail && <span className="text-ink-faint">{stage.detail}</span>}
              </li>
            ))}
          </ol>

          <p className="mt-2.5 border-t border-line pt-2 text-[11.5px] text-ink-muted">
            {trace.engine.used === "none" ? (
              <>
                No model was called. The answer came straight from what the search
                found, which is why it was quick and why it cannot have been
                invented.
              </>
            ) : (
              <>
                Written by <span className="font-medium text-ink">{engineName(trace.engine)}</span>
                {trace.engine.model && (
                  <>
                    {" "}
                    (<span className="font-mono text-[11px]">{trace.engine.model}</span>)
                  </>
                )}
                .
              </>
            )}
            {trace.engine.fell_back && trace.engine.reason && (
              <>
                {" "}
                <span className="text-warn">{trace.engine.reason}</span>
              </>
            )}
          </p>
        </div>
      )}
    </div>
  );
}
