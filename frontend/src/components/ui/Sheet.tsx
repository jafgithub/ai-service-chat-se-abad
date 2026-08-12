"use client";

import { useEffect } from "react";
import { cn } from "@/lib/utils";

/**
 * The dismissible layer, extracted from the product sheet the shop used so the
 * booking flow inherits its behaviour rather than a lookalike: bottom sheet on
 * a phone, centred card above `sm`, escape to close, and a backdrop click that
 * does not fire when the click started inside the panel.
 */

interface SheetProps {
  title: string;
  /** Under the title. The step of the flow, usually. */
  subtitle?: string;
  onClose: () => void;
  /** A back arrow instead of nothing, when there is somewhere to go back to. */
  onBack?: () => void;
  children: React.ReactNode;
  /** Pinned under the content: the one action this step is asking for. */
  footer?: React.ReactNode;
  width?: "md" | "lg";
}

export function Sheet({
  title, subtitle, onClose, onBack, children, footer, width = "md",
}: SheetProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // The page behind must not scroll while a sheet is open, or a phone scrolls
  // the page instead of the slot list.
  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, []);

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-center bg-ink/50 p-0 backdrop-blur-sm sm:items-center sm:p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className={cn(
          "flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-sheet bg-surface shadow-pop sm:rounded-sheet",
          width === "lg" ? "sm:max-w-2xl" : "sm:max-w-md"
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-shrink-0 items-center gap-3 border-b border-line px-4 py-3.5">
          {onBack && (
            <button
              onClick={onBack}
              aria-label="Back"
              className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
          )}

          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-ink">{title}</p>
            {subtitle && <p className="truncate text-xs text-ink-muted">{subtitle}</p>}
          </div>

          <button
            onClick={onClose}
            aria-label="Close"
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="chat-scroll flex-1 overflow-y-auto px-4 py-4">{children}</div>

        {footer && (
          <div className="flex-shrink-0 border-t border-line bg-surface px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
