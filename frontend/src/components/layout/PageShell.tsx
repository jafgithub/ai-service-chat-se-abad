"use client";

import Link from "next/link";

import { BRAND_NAME } from "@/constants";
import { AccountMenu } from "@/components/layout/AccountMenu";

/**
 * The frame around every page that is not the assistant.
 *
 * The assistant keeps its own full-height chrome, because it is a conversation
 * and has to fill the viewport exactly. Everything else is an ordinary scrolling
 * page, and they should all agree on where the brand, the account menu and the
 * heading sit.
 */

interface PageShellProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  /** Right of the heading: the one action the page offers, if it has one. */
  action?: React.ReactNode;
  /** Narrow for forms, wide for lists. */
  width?: "narrow" | "wide";
}

export function PageShell({ title, subtitle, children, action, width = "wide" }: PageShellProps) {
  return (
    <div className="flex min-h-dvh flex-col bg-surface-sunken">
      <header className="sticky top-0 z-30 flex-shrink-0 border-b border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-5xl items-center gap-3 px-4">
          <Link href="/" className="flex items-center gap-2 font-extrabold text-ink">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-orange-500 to-rose-500 text-base text-white">
              📅
            </span>
            <span className="hidden sm:block">{BRAND_NAME}</span>
          </Link>

          <div className="flex-1" />

          <Link
            href="/chat"
            className="hidden h-10 items-center rounded-control px-3 text-sm font-semibold text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink sm:flex"
          >
            Assistant
          </Link>
          <AccountMenu />
        </div>
      </header>

      <main
        className={
          width === "narrow"
            ? "mx-auto w-full max-w-md flex-1 px-4 py-8"
            : "mx-auto w-full max-w-5xl flex-1 px-4 py-8"
        }
      >
        <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-ink">{title}</h1>
            {subtitle && <p className="mt-1 text-sm text-ink-muted">{subtitle}</p>}
          </div>
          {action}
        </div>

        {children}
      </main>
    </div>
  );
}
