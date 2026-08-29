"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { aiRuntimeApi, type AiStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Which engine answers, and the GPU behind it.
 *
 * Two facts sit side by side here on purpose. The switch says which engine
 * should answer; the line beneath it says which one actually answered the last
 * question. They disagree whenever the GPU is off, and hiding that is how a
 * demonstration ends up claiming credit for Gemini's work.
 *
 * The polling is not decoration. The server's health reading is what
 * llm.generate consults without blocking, and this panel refreshing it is what
 * keeps a resident's question off the slow path while the machine boots.
 */

const gpuState = {
  "not-configured": { label: "Not set up", tone: "bg-surface-sunken text-ink-muted" },
  stopped: { label: "Off", tone: "bg-surface-sunken text-ink-muted" },
  pending: { label: "Starting", tone: "bg-warn-soft text-warn" },
  running: { label: "Running", tone: "bg-positive-soft text-positive" },
  stopping: { label: "Stopping", tone: "bg-warn-soft text-warn" },
  "shutting-down": { label: "Shutting down", tone: "bg-warn-soft text-warn" },
  terminated: { label: "Terminated", tone: "bg-danger-soft text-danger" },
  unknown: { label: "Unknown", tone: "bg-danger-soft text-danger" },
} as const;

/** Fast while something is changing, slow when it is not. */
const BUSY_MS = 4000;
const IDLE_MS = 30000;
const BUSY_STATES = ["pending", "stopping", "shutting-down"];

const upFor = (since: string | null | undefined) => {
  if (!since) return "";
  const mins = Math.floor((Date.now() - new Date(since).getTime()) / 60000);
  if (mins < 1) return "just started";
  if (mins < 60) return `up ${mins} minute${mins === 1 ? "" : "s"}`;
  return `up ${Math.floor(mins / 60)}h ${mins % 60}m`;
};

export function AiRuntime({ token }: { token: string }) {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  // So the interval can read the current state without being torn down and
  // rebuilt on every poll.
  const stateRef = useRef("");

  const headers = { "X-Admin-Token": token };

  const load = useCallback(async () => {
    try {
      const next = await aiRuntimeApi.status({ "X-Admin-Token": token });
      setStatus(next);
      stateRef.current = next.gpu.state;
      setError("");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not read the AI settings.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (!cancelled) await load();
    })();
    return () => { cancelled = true; };
  }, [load]);

  /* Hand rolled, because there is no polling anywhere else in this application
     and useResource has no interval. Paused when the tab is hidden: nobody is
     watching a background tab, and this costs an AWS call every time. */
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;

    const tick = () => {
      const wait = BUSY_STATES.includes(stateRef.current) ? BUSY_MS : IDLE_MS;
      timer = setTimeout(async () => {
        if (typeof document === "undefined" || !document.hidden) await load();
        tick();
      }, wait);
    };

    tick();
    return () => clearTimeout(timer);
  }, [load]);

  const act = useCallback(async (what: "gemini" | "gpu" | "start" | "stop") => {
    setBusy(what);
    setError("");
    try {
      const next =
        what === "start" ? await aiRuntimeApi.start(headers)
        : what === "stop" ? await aiRuntimeApi.stop(headers)
        : await aiRuntimeApi.setProvider(what, headers);
      setStatus(next);
      stateRef.current = next.gpu.state;
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "We could not change that just now.");
    } finally {
      setBusy("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const gpu = status?.gpu;
  const pill = gpuState[(gpu?.state ?? "unknown") as keyof typeof gpuState] ?? gpuState.unknown;
  const onGpu = status?.provider === "gpu";
  const fellBack = Boolean(status?.serving.fell_back);

  return (
    <section className="rounded-card border border-line bg-surface">
      <header className="border-b border-line px-5 py-4">
        <h2 className="text-base font-semibold text-ink">AI engine</h2>
        <p className="mt-0.5 text-sm text-ink-muted">
          {loading
            ? "Loading..."
            : onGpu
              ? `Set to our own GPU, running ${status?.model}.`
              : "Set to Gemini, which is Google's hosted model."}
        </p>
      </header>

      {error && (
        <p className="m-5 rounded-control bg-danger-soft px-4 py-3 text-sm text-danger">{error}</p>
      )}

      {!loading && status && (
        <div className="space-y-4 p-5">
          {/* The disagreement, when there is one. This is the honest bit. */}
          {onGpu && fellBack && (
            <div className="rounded-control bg-warn-soft px-4 py-3 text-sm text-warn">
              <strong className="font-semibold">
                Switched to our GPU, but Gemini is answering.
              </strong>{" "}
              {status.serving.reason} Residents still get answers, so nothing is
              broken. Start the GPU below to serve them from it.
            </div>
          )}

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
              Which engine answers
            </p>
            <div className="flex flex-wrap gap-2">
              <Choice
                label="Gemini"
                sub="Google's hosted model"
                chosen={!onGpu}
                busy={busy === "gemini"}
                onClick={() => act("gemini")}
              />
              <Choice
                label="Our own GPU"
                sub={gpu?.configured ? status.model : "not set up yet"}
                chosen={onGpu}
                disabled={!gpu?.configured}
                busy={busy === "gpu"}
                onClick={() => act("gpu")}
              />
            </div>
          </div>

          <div className="rounded-control border border-line p-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", pill.tone)}>
                {pill.label}
              </span>
              <span className="text-sm text-ink-muted">
                {gpu?.configured
                  ? gpu.state === "running"
                    ? `${upFor(gpu.since)}, switching itself off after ${status.idle_minutes} idle minutes`
                    : gpu.error || gpu.reason
                  : "Add GPU_INSTANCE_ID and the AWS keys to .env to switch this on."}
              </span>
            </div>

            {gpu?.configured && (
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => act("start")}
                  disabled={busy !== "" || gpu.state === "running" || BUSY_STATES.includes(gpu.state)}
                  className="h-10 rounded-control bg-brand-500 px-5 text-sm font-semibold text-white transition-colors hover:bg-brand-600 disabled:opacity-40"
                >
                  {busy === "start" ? "Starting..." : "Start the GPU"}
                </button>
                <button
                  type="button"
                  onClick={() => act("stop")}
                  disabled={busy !== "" || gpu.state !== "running"}
                  className="h-10 rounded-control border border-line px-5 text-sm font-semibold text-ink transition-colors hover:bg-surface-hover disabled:opacity-40"
                >
                  {busy === "stop" ? "Stopping..." : "Stop the GPU"}
                </button>
              </div>
            )}

            <p className="mt-3 text-xs text-ink-muted">
              It takes 2 to 4 minutes to start. Questions asked meanwhile are
              answered by Gemini, so nobody waits.
            </p>
          </div>

          <p className="text-xs text-ink-faint">
            Last question answered by{" "}
            <strong className="font-semibold text-ink-muted">
              {status.serving.served_by === "gpu"
                ? "our own GPU"
                : status.serving.served_by === "gemini"
                  ? "Gemini"
                  : "nothing yet"}
            </strong>
            {gpu?.configured ? ` · ${status.region}` : ""}
          </p>
        </div>
      )}
    </section>
  );
}

function Choice({
  label, sub, chosen, busy, disabled, onClick,
}: {
  label: string;
  sub: string;
  chosen: boolean;
  busy?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || busy}
      aria-pressed={chosen}
      className={cn(
        "min-w-[150px] rounded-control border px-4 py-2.5 text-left transition-colors disabled:opacity-40",
        chosen ? "border-brand-500 bg-brand-50" : "border-line bg-surface hover:bg-surface-hover"
      )}
    >
      <span className="block text-sm font-semibold text-ink">
        {busy ? "Switching..." : label}
      </span>
      <span className="block text-xs text-ink-muted">{sub}</span>
    </button>
  );
}
