"use client";

import { useState } from "react";
import type { CommunityOption } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

/**
 * Which association a resident is asking as, shown and changed in one place.
 *
 * Not a dropdown that interrupts each question. It sits in view, says which
 * community the answers are coming from, and opens a short list when tapped.
 * With one community loaded it renders nothing at all: a choice of one is not a
 * choice, it is furniture.
 */
export function CommunityPicker({
  options,
  current,
  onChoose,
  align = "left",
  /** Open upwards. For a control that sits at the foot of the screen, where a
   *  list dropping down runs off the bottom on a phone. */
  openUp = false,
  className,
}: {
  options: CommunityOption[];
  current?: CommunityOption;
  onChoose: (key: string) => void;
  align?: "left" | "right";
  openUp?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  if (options.length < 2) return null;

  return (
    <div className={cn("relative", className)}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="listbox"
        className="flex max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-1 text-xs font-medium text-ink transition-colors hover:border-brand-500 hover:text-brand-600"
      >
        <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-brand-500" />
        <span className="truncate">{current?.label ?? "Choose your community"}</span>
        <svg viewBox="0 0 12 12" className="h-3 w-3 flex-shrink-0 text-ink-muted" aria-hidden>
          <path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.5"
                strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <>
          {/* Tapping anywhere else closes it, which on a phone is most of the
              screen and is what people try first. */}
          <button
            type="button"
            aria-hidden
            tabIndex={-1}
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-40 cursor-default"
          />
          <ul
            role="listbox"
            className={cn(
              "absolute z-50 min-w-[190px] overflow-hidden rounded-control border border-line bg-surface py-1 shadow-lg",
              openUp ? "bottom-full mb-1" : "mt-1",
              align === "right" ? "right-0" : "left-0"
            )}
          >
            {options.map((option) => {
              const active = option.key === current?.key;
              return (
                <li key={option.key}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={active}
                    onClick={() => {
                      onChoose(option.key);
                      setOpen(false);
                    }}
                    className={cn(
                      "flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left text-sm transition-colors hover:bg-surface-hover",
                      active ? "font-semibold text-brand-600" : "text-ink"
                    )}
                  >
                    <span className="truncate">{option.label}</span>
                    <span className="flex-shrink-0 text-[11px] text-ink-faint">
                      {option.documents} doc{option.documents === 1 ? "" : "s"}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
