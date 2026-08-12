"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

/**
 * The four things a screen backed by an API can be showing.
 *
 * They are together in one file because the difference between them is the
 * whole point, and keeping them apart is how a "no results" ends up looking
 * like a failure. In particular nothing here ever invents content: when a call
 * fails the screen says so and offers to try again. Filling the gap with
 * plausible-looking providers would be worse than an empty screen, because the
 * customer would ring one.
 */

export function Loading({ label = "Loading", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="rounded-card border border-line bg-surface p-4">
          <div className="h-3.5 w-1/3 animate-pulse rounded bg-surface-hover" />
          <div className="mt-2.5 h-3 w-2/3 animate-pulse rounded bg-surface-hover" />
          <div className="mt-4 h-9 w-28 animate-pulse rounded-control bg-surface-hover" />
        </div>
      ))}
    </div>
  );
}

interface MessageProps {
  title: string;
  body?: string;
  icon?: string;
  action?: { label: string; onClick: () => void };
  secondary?: { label: string; href: string };
  tone?: "neutral" | "bad";
  className?: string;
}

function Message({ title, body, icon, action, secondary, tone = "neutral", className }: MessageProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center rounded-card border px-6 py-10 text-center",
        tone === "bad" ? "border-danger/30 bg-danger-soft" : "border-line bg-surface",
        className
      )}
    >
      {icon && <span className="mb-3 text-3xl" aria-hidden>{icon}</span>}
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      {body && <p className="mt-1.5 max-w-md text-sm leading-relaxed text-ink-muted">{body}</p>}

      {(action || secondary) && (
        <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
          {action && <Button onClick={action.onClick}>{action.label}</Button>}
          {secondary && (
            <Link
              href={secondary.href}
              className="inline-flex h-11 items-center rounded-control border border-line bg-surface px-5 text-sm font-semibold text-ink transition-colors hover:bg-surface-hover"
            >
              {secondary.label}
            </Link>
          )}
        </div>
      )}
    </div>
  );
}

export function Empty(props: Omit<MessageProps, "tone">) {
  return <Message {...props} tone="neutral" />;
}

/** Something went wrong at the server or on the wire. Always offers a retry:
 *  most of these are transient, and a dead end for a blip is a bad trade. */
export function Failed({
  detail,
  onRetry,
  title = "That did not load",
}: {
  detail?: string;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <Message
      tone="bad"
      icon="⚠️"
      title={title}
      body={detail || "Something went wrong at our end. Nothing has been booked or changed."}
      action={onRetry ? { label: "Try again", onClick: onRetry } : undefined}
    />
  );
}

/** For a page that needs an account. Says which kind, because sending a
 *  provider to the customer sign-in is a dead end they cannot see the end of. */
export function SignInRequired({
  what,
  expired = false,
  provider = false,
}: {
  what: string;
  expired?: boolean;
  provider?: boolean;
}) {
  return (
    <Message
      icon={expired ? "🔒" : "👋"}
      title={expired ? "Please sign in again" : `Sign in to see ${what}`}
      body={
        expired
          ? "Your session ended, so we signed you out. Nothing has been lost."
          : `You need an account to see ${what}.`
      }
      secondary={
        provider
          ? { label: "Provider sign in", href: "/provider/login" }
          : { label: "Sign in", href: "/login" }
      }
    />
  );
}
