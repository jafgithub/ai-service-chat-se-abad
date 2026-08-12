"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { PageShell } from "@/components/layout/PageShell";
import { AuthPanel } from "@/components/auth/AuthPanel";
import { useAuth } from "@/components/auth/AuthProvider";

/**
 * Signing in as a customer.
 *
 * Most people never see this page: the booking flow signs them in where they
 * stand, which is better, because it keeps the provider and the time they had
 * already chosen. This is for coming back later to look at what is booked.
 */
export default function LoginPage() {
  const router = useRouter();
  const { status, account, expired } = useAuth();

  // Already signed in? Do not show a sign-in form to somebody who is. Providers
  // belong in their own part of the application.
  useEffect(() => {
    if (status !== "signed-in") return;
    router.replace(account?.role === "provider" ? "/provider/dashboard" : "/bookings");
  }, [status, account, router]);

  return (
    <PageShell
      title="Sign in"
      subtitle="To see your bookings and what you have asked for."
      width="narrow"
    >
      {expired && (
        <p className="mb-4 rounded-control border border-warn/30 bg-warn-soft px-3 py-2 text-sm text-warn">
          Your session ended, so we signed you out. Nothing has been lost.
        </p>
      )}

      <div className="rounded-card border border-line bg-surface p-5 shadow-card">
        <AuthPanel onDone={(me) => router.push(me?.role === "provider" ? "/provider/dashboard" : "/bookings")} />
      </div>

      <p className="mt-4 text-center text-sm text-ink-muted">
        Run a business?{" "}
        <Link href="/provider/login" className="font-semibold text-brand-600 hover:underline">
          Sign in as a provider
        </Link>
      </p>
    </PageShell>
  );
}
