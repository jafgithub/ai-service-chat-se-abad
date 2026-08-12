"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { PageShell } from "@/components/layout/PageShell";
import { AuthPanel } from "@/components/auth/AuthPanel";

/** Creating a customer account on its own, rather than in the middle of a
 *  booking. Same panel, opened on the other tab. */
export default function RegisterPage() {
  const router = useRouter();

  return (
    <PageShell
      title="Create an account"
      subtitle="So you can see what is booked and what you have asked for."
      width="narrow"
    >
      <div className="rounded-card border border-line bg-surface p-5 shadow-card">
        <AuthPanel
          initialMode="register"
          onDone={() => router.push("/chat")}
        />
      </div>

      <p className="mt-4 text-center text-sm text-ink-muted">
        Registering a business instead?{" "}
        <Link href="/provider/register" className="font-semibold text-brand-600 hover:underline">
          Apply as a provider
        </Link>
      </p>
    </PageShell>
  );
}
