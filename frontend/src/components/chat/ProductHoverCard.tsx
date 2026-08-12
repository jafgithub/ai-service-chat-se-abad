"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { cn } from "@/lib/utils";

/**
 * Details shown by pointing at a product, without clicking.
 *
 * Two things it deliberately does not do:
 *
 *   • It never appears on a touch screen. A phone has no hover; browsers fake
 *     one on first tap, which would put a panel over the product the shopper
 *     was trying to press. Gated on a pointer that can actually hover.
 *
 *   • It does not fetch anything. Everything shown is already on the page,
 *     read from our own products table with the search results, so pointing at
 *     twenty cards in a row costs nothing and cannot be slow.
 *
 * The open delay stops the panel flickering as the pointer crosses a grid on
 * its way somewhere else.
 */

const OPEN_DELAY_MS = 350;

/** Whether this device has a pointer that can genuinely hover.
 *
 * `useSyncExternalStore` rather than an effect: matchMedia is exactly the
 * external store it exists for, and it gives a correct value on the first
 * render instead of flipping after mount. The server snapshot is `false`,
 * because the pages are prerendered at build time where no device exists, and
 * assuming no hover is the safe default. */
function subscribeToHover(onChange: () => void) {
  const q = window.matchMedia("(hover: hover) and (pointer: fine)");
  q.addEventListener("change", onChange);
  return () => q.removeEventListener("change", onChange);
}

function useCanHover(): boolean {
  return useSyncExternalStore(
    subscribeToHover,
    () => window.matchMedia("(hover: hover) and (pointer: fine)").matches,
    () => false,
  );
}

interface ProductHoverCardProps {
  /** Rendered inside the trigger: the card itself. */
  children: React.ReactNode;
  /** What to show in the panel. */
  panel: React.ReactNode;
  className?: string;
}

export function ProductHoverCard({ children, panel, className }: ProductHoverCardProps) {
  const [open, setOpen] = useState(false);
  // Which side to open on, so a card at the right edge does not push a panel
  // off the screen.
  const [side, setSide] = useState<"right" | "left">("right");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hostRef = useRef<HTMLDivElement>(null);

  // Pointer capability, not screen width: a small window on a laptop still has
  // a mouse, and a large tablet still does not.
  const canHover = useCanHover();

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const show = () => {
    if (!canHover) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const box = hostRef.current?.getBoundingClientRect();
      if (box) setSide(box.right + 300 > window.innerWidth ? "left" : "right");
      setOpen(true);
    }, OPEN_DELAY_MS);
  };

  const hide = () => {
    if (timer.current) clearTimeout(timer.current);
    setOpen(false);
  };

  return (
    <div
      ref={hostRef}
      className={cn("relative", className)}
      onMouseEnter={show}
      onMouseLeave={hide}
      // Keyboard users get the same information by moving through the cards.
      onFocus={show}
      onBlur={hide}
    >
      {children}

      {open && (
        <div
          // pointer-events-none: the panel must never sit between the pointer
          // and the button underneath it.
          className={cn(
            "pointer-events-none absolute top-0 z-50 w-72 rounded-card border border-line bg-surface p-4 shadow-pop",
            side === "right" ? "left-full ml-2" : "right-full mr-2"
          )}
          role="tooltip"
        >
          {panel}
        </div>
      )}
    </div>
  );
}
