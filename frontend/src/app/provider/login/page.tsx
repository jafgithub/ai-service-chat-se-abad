"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { PageShell } from "@/components/layout/PageShell";
import { AuthPanel } from "@/components/auth/AuthPanel";
import { useAuth } from "@/components/auth/AuthProvider";

/**
 * Provider sign in.
 *
 * The same endpoint and the same token as the customer side: one account knows
 * which side it belongs to, so there is no second authentication system here.
 * What differs is only where somebody lands afterwards.
 */
export default function ProviderLoginPage() {
  const router = useRouter();
  const { status, account, expired } = useAuth();

  useEffect(() => {
    if (status !== "signed-in") return;
    router.replace(account?.role === "provider" ? "/provider/dashboard" : "/bookings");
  }, [status, account, router]);

  return (
    <PageShell
      title="Provider sign in"
      subtitle="Manage your services, your hours and your diary."
      width="narrow"
    >
      {expired && (
        <p className="mb-4 rounded-control border border-warn/30 bg-warn-soft px-3 py-2 text-sm text-warn">
          Your session ended, so we signed you out. Nothing has been lost.
        </p>
      )}

      <div className="rounded-card border border-line bg-surface p-5 shadow-card">
        <AuthPanel
          audience="provider"
          onDone={(me) => router.push(me?.role === "provider" ? "/provider/dashboard" : "/bookings")}
        />
      </div>

      <p className="mt-4 text-center text-sm text-ink-muted">
        Looking to book somebody instead?{" "}
        <Link href="/login" className="font-semibold text-brand-600 hover:underline">
          Customer sign in
        </Link>
      </p>
    </PageShell>
  );
}
