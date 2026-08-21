"use client";

import type { ChatMessage as ChatMessageType } from "@/types";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  message: ChatMessageType;
  large?: boolean;
}

/**
 * Recognises the one line the backend really does append as a prompt to act:
 * `Just say "add item 2 to cart" (or any number) and I'll add it for you.`
 *
 * The old code styled whatever happened to be last in orange, on the assumption
 * that it was always a call to action. On a two line reply that meant the
 * second line was highlighted whatever it said, including apologies and error
 * messages, which read as though the assistant were selling the failure.
 */
function isPrompt(line: string): boolean {
  return /^(just say|say|tap|try saying|you can say)\b/i.test(line.trim());
}

/**
 * `**like this**` becomes bold.
 *
 * The greeting and the booking confirmation both emphasise a name or a
 * reference this way, and until now the asterisks were printed literally:
 * "Your reference is **BK-00011**". Nothing else in these replies is markdown,
 * so this handles the one mark that is actually used rather than pulling in a
 * parser for a syntax the backend never emits.
 */
function withEmphasis(text: string): React.ReactNode {
  const parts = text.split(/\*\*([^*]+)\*\*/g);
  // split() with one capture group alternates: plain, bold, plain, bold…
  return parts.map((part, i) =>
    i % 2 === 1
      ? <strong key={i} className="font-semibold text-ink">{part}</strong>
      : <span key={i}>{part}</span>
  );
}

function FormattedText({ text }: { text: string }) {
  const lines = text.split(/\n+/).filter((l) => l.trim() !== "");

  return (
    <div className="flex flex-col gap-1.5">
      {lines.map((line, i) => {
        const trimmed = line.trim();

        // A numbered product line: "1. Whole Milk: $1.80"
        const numbered = trimmed.match(/^(\d+)\.\s+(.+)$/);
        if (numbered) {
          return (
            <div
              key={i}
              className="flex items-start gap-2.5 rounded-control border border-line bg-surface-sunken px-3 py-2"
            >
              <span className="mt-px flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-brand-500 text-[11px] font-semibold text-white">
                {numbered[1]}
              </span>
              <span className="text-sm leading-snug text-ink">
                {formatProductLine(numbered[2])}
              </span>
            </div>
          );
        }

        if (isPrompt(trimmed)) {
          return (
            <p key={i} className="text-sm leading-relaxed text-ink-muted">
              {withEmphasis(trimmed)}
            </p>
          );
        }

        return (
          <p
            key={i}
            className={cn(
              "text-sm leading-relaxed",
              i === 0 ? "font-medium text-ink" : "text-ink-muted"
            )}
          >
            {withEmphasis(trimmed)}
          </p>
        );
      })}
    </div>
  );
}

/** Pick the price out of a product line so it can be read at a glance.
 *
 * `/unit` is dropped for the same reason the cards drop it: it is the catalog's
 * placeholder, not a real measure, and the reply saying "$4.85/unit" next to a
 * card saying "$4.85" looks like two different prices. A genuine unit such as
 * `/kg` or `/litre` is left alone. */
function formatProductLine(text: string): React.ReactNode {
  const cleaned = text.replace(/\/units?\b/gi, "");
  const parts = cleaned.split(/(\$[\d.]+(?:\/\w+)?)/g);
  return parts.map((part, i) =>
    /^\$[\d.]+(\/\w+)?$/.test(part) ? (
      <span key={i} className="font-semibold text-ink">
        {part}
      </span>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

export function ChatMessage({ message, large = false }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("group mb-4 flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
      <div
        className={cn(
          "flex flex-shrink-0 items-center justify-center rounded-full",
          large ? "h-8 w-8 text-base" : "h-7 w-7 text-sm",
          isUser ? "bg-surface-hover text-ink-muted" : "bg-brand-50"
        )}
        aria-hidden
      >
        {isUser ? (
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
        ) : (
          "📅"
        )}
      </div>

      <div
        className={cn(
          "flex min-w-0 flex-col gap-1",
          isUser ? "items-end" : "items-start",
          large ? "max-w-[78%]" : "max-w-[82%]"
        )}
      >
        <div
          className={cn(
            "rounded-card px-4 py-2.5",
            isUser
              ? "rounded-tr-sm bg-brand-500 text-white"
              : "w-full rounded-tl-sm border border-line bg-surface"
          )}
        >
          {isUser ? (
            <span className="text-sm leading-relaxed">{message.content}</span>
          ) : (
            <FormattedText text={message.content} />
          )}
        </div>

        {/* Where the answer came from. Only the community documents set this,
            and it is the document as well as the section on purpose: two of
            the Serenity rulebooks disagree with each other, so which one an
            answer came out of is the point rather than a footnote. */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {message.sources.map((s) => (
              <span
                key={`${s.document}-${s.section}`}
                className="rounded-full border border-line bg-surface-sunken px-2 py-0.5 text-[11px] text-ink-muted"
              >
                {/* Community first. With several associations loaded, whose
                    rules these are is the first thing a reader needs, and an
                    answer can draw on more than one document at a time. */}
                {s.community && (
                  <span className="font-semibold text-accent">{s.community}</span>
                )}
                {s.community && " \u00b7 "}
                <span className="font-medium text-ink">{s.document}</span>
                {" \u00b7 "}{s.section}
              </span>
            ))}
          </div>
        )}

        {/* Timestamps were under every bubble, including the greeting, which is
            a lot of noise for something nobody reads in a live conversation. */}
        <span className="px-1 text-[11px] text-ink-faint opacity-0 transition-opacity group-hover:opacity-100">
          {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
      </div>
    </div>
  );
}
