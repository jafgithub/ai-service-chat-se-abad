"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageShell } from "@/components/layout/PageShell";
import { Empty, Loading, SignInRequired } from "@/components/ui/States";
import { cn } from "@/lib/utils";

/**
 * The provider's half of the application.
 *
 * Three things this does that each page would otherwise repeat, and get subtly
 * different:
 *
 *   • It waits. "Not signed in yet" and "signed out" look identical in state for
 *     the moment it takes to check the token, and a page that treats them the
 *     same throws a signed-in provider back to the sign-in screen.
 *   • It keeps customers out of the provider area and vice versa. Not as
 *     security, which is the API's job and is enforced there, but because every
 *     one of these pages would be empty for the wrong role and would look
 *     broken rather than forbidden.
 *   • It says, once and on every page, when an application has not been
 *     approved yet. A provider who does not know that is a provider waiting for
 *     bookings that cannot arrive.
 */

const TABS = [
  { href: "/provider/dashboard", label: "Overview" },
  { href: "/provider/appointments", label: "Diary" },
  { href: "/provider/services", label: "Services" },
  { href: "/provider/availability", label: "Hours" },
  { href: "/provider/profile", label: "Business" },
];

interface ProviderShellProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}

export function ProviderShell({ title, subtitle, children, action }: ProviderShellProps) {
  const { status, account, expired } = useAuth();
  const pathname = usePathname();

  if (status === "loading") {
    return (
      <PageShell title={title}>
        <Loading label="Checking your account" />
      </PageShell>
    );
  }

  if (status === "signed-out") {
    return (
      <PageShell title={title}>
        <SignInRequired what="your business" expired={expired} provider />
      </PageShell>
    );
  }

  if (account?.role !== "provider") {
    return (
      <PageShell title={title}>
        <Empty
          icon="🔁"
          title="This part is for providers"
          body="You are signed in as a customer. Your own bookings are on the customer side."
          secondary={{ label: "My bookings", href: "/bookings" }}
        />
      </PageShell>
    );
  }

  const pending = account.provider_status && account.provider_status !== "active";

  return (
    <PageShell title={title} subtitle={subtitle} action={action}>
      {pending && (
        <div className="mb-5 rounded-card border border-warn/30 bg-warn-soft px-4 py-3">
          <p className="text-sm font-semibold text-warn">
            {account.provider_status === "pending"
              ? "Your application is being reviewed"
              : `Your account is ${account.provider_status}`}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-ink-muted">
            {account.provider_status === "pending"
              ? "You can fill in your services and your hours now. Customers will not see you, and you cannot receive bookings, until the office approves you."
              : "Customers cannot see you or book you at the moment. Get in touch if you think this is wrong."}
          </p>
        </div>
      )}

      <nav className="chat-scroll mb-5 -mx-1 flex gap-1 overflow-x-auto px-1">
        {TABS.map((tab) => (
          <Link
            key={tab.href}
            href={tab.href}
            className={cn(
              "flex-shrink-0 rounded-control px-3 py-2 text-sm font-semibold transition-colors",
              pathname === tab.href
                ? "bg-brand-50 text-brand-700"
                : "text-ink-muted hover:bg-surface-hover hover:text-ink"
            )}
          >
            {tab.label}
          </Link>
        ))}
      </nav>

      {children}
    </PageShell>
  );
}
