"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { cn } from "@/lib/utils";

/**
 * Who you are, and the few places that belong to you.
 *
 * This sits where the shop's cart button was. That is the single clearest sign
 * that the product changed: the loudest control in the header used to be a
 * basket, and now it is your own bookings.
 *
 * A provider gets a different menu, because the customer pages would all be
 * empty for them: a provider account has no bookings of its own and no
 * requests, and offering the links anyway would look broken.
 */

interface AccountMenuProps {
  /** On the brand bar, where everything is white on orange. */
  onBrand?: boolean;
}

export function AccountMenu({ onBrand }: AccountMenuProps) {
  const { status, account, signOut } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!host.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Nothing at all while the token is being checked. A "Sign in" button that
  // turns into somebody's initials a moment later reads as a glitch, and worse,
  // invites a click that was never needed.
  if (status === "loading") {
    return <span className="h-10 w-10" aria-hidden />;
  }

  if (status === "signed-out") {
    return (
      <Link
        href="/login"
        className={cn(
          "flex h-10 items-center rounded-control px-3 text-sm font-semibold transition-colors",
          onBrand
            ? "text-white/90 hover:bg-white/15 hover:text-white"
            : "border border-line bg-surface text-ink hover:bg-surface-hover"
        )}
      >
        Sign in
      </Link>
    );
  }

  const provider = account?.role === "provider";
  const initial = (account?.name || account?.email || "?").trim().charAt(0).toUpperCase();

  const links = provider
    ? [
        { href: "/provider/dashboard", label: "Dashboard" },
        { href: "/provider/appointments", label: "My diary" },
        { href: "/provider/services", label: "My services" },
        { href: "/provider/availability", label: "My hours" },
        { href: "/provider/profile", label: "My business" },
      ]
    : [
        { href: "/bookings", label: "My bookings" },
        { href: "/requests", label: "My requests" },
        { href: "/chat", label: "Book something else" },
      ];

  return (
    <div ref={host} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Account menu for ${account?.name || "your account"}`}
        className={cn(
          "flex h-10 items-center gap-2 rounded-control px-2 text-sm font-semibold transition-colors",
          onBrand
            ? "text-white hover:bg-white/15"
            : "border border-line bg-surface text-ink hover:bg-surface-hover"
        )}
      >
        <span
          className={cn(
            "flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold",
            onBrand ? "bg-white text-brand-600" : "bg-brand-50 text-brand-700"
          )}
        >
          {initial}
        </span>
        <span className="hidden max-w-28 truncate sm:block">{account?.name}</span>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-1.5 w-56 overflow-hidden rounded-card border border-line bg-surface py-1 shadow-pop"
        >
          <div className="border-b border-line px-3 py-2">
            <p className="truncate text-sm font-semibold text-ink">{account?.name}</p>
            <p className="truncate text-xs text-ink-muted">{account?.email}</p>
            {provider && account?.provider_status && account.provider_status !== "active" && (
              /* A pending provider must not be left wondering. The same words
                 appear on their dashboard. */
              <p className="mt-1 inline-block rounded-full bg-warn-soft px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-warn">
                {account.provider_status}
              </p>
            )}
          </div>

          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              role="menuitem"
              onClick={() => setOpen(false)}
              className="block px-3 py-2 text-sm text-ink transition-colors hover:bg-surface-hover"
            >
              {link.label}
            </Link>
          ))}

          <button
            role="menuitem"
            onClick={async () => {
              setOpen(false);
              await signOut();
              router.push("/");
            }}
            className="block w-full border-t border-line px-3 py-2 text-left text-sm text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
