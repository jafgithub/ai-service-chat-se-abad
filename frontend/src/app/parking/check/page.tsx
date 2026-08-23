"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api";
import type { ParkingPassHolder } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * The gate. What somebody sees when they scan a resident's parking QR.
 *
 * Behind the office token, and that is the point rather than an inconvenience:
 * a code on a windscreen can be photographed by anyone walking past, so the
 * code itself gives nothing away and reading what it points at is a privileged
 * act. The token is remembered on the device, so a guard enters it once on
 * their phone and scans freely after that.
 *
 * The answer has to be readable at arm's length in the rain, so the verdict is
 * a colour and one word before it is anything else.
 */

const TOKEN_KEY = "ai_order_admin_token";

const verdict = {
  valid: { word: "Let them in", tone: "bg-positive-soft text-positive border-positive" },
  used: { word: "Already used", tone: "bg-surface-sunken text-ink-muted border-line" },
  expired: { word: "Expired", tone: "bg-warn-soft text-warn border-warn" },
  cancelled: { word: "Cancelled", tone: "bg-danger-soft text-danger border-danger" },
} as const;

const when = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";

function Gate() {
  const params = useSearchParams();
  const token = params.get("t") ?? "";

  const [office, setOffice] = useState("");
  const [entry, setEntry] = useState("");
  const [pass, setPass] = useState<ParkingPassHolder | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const check = useCallback(async (officeToken: string) => {
    if (!token) { setError("That link has no code in it."); return; }
    setBusy(true);
    setError("");
    try {
      const found = await apiClient.get<ParkingPassHolder>(
        `/api/v1/parking/check/${token}`, undefined, { "X-Admin-Token": officeToken });
      setPass(found);
      localStorage.setItem(TOKEN_KEY, officeToken);
      setOffice(officeToken);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        localStorage.removeItem(TOKEN_KEY);
        setOffice("");
        setError("That office code was not accepted.");
      } else {
        setError(err instanceof ApiError ? err.detail : "Could not check that pass.");
      }
      setPass(null);
    } finally {
      setBusy(false);
    }
  }, [token]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      const saved = localStorage.getItem(TOKEN_KEY);
      if (saved) await check(saved);
    })();
    return () => { cancelled = true; };
  }, [check]);

  const letOut = async () => {
    setBusy(true);
    try {
      const updated = await apiClient.post<ParkingPassHolder>(
        `/api/v1/parking/check/${token}/exit`, {}, undefined,
        { "X-Admin-Token": office });
      setPass(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not record the exit.");
    } finally {
      setBusy(false);
    }
  };

  if (!pass) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center px-6">
        <h1 className="text-xl font-semibold text-ink">Parking check</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Enter the office code once. This phone will remember it.
        </p>
        <input
          type="password"
          value={entry}
          onChange={(e) => setEntry(e.target.value)}
          placeholder="Office code"
          className="mt-4 h-12 w-full rounded-control border border-line bg-surface px-4 text-ink"
        />
        <button
          type="button"
          onClick={() => check(entry.trim())}
          disabled={busy || !entry.trim()}
          className="mt-3 h-12 rounded-control bg-brand-500 font-semibold text-white disabled:opacity-40"
        >
          {busy ? "Checking..." : "Check the pass"}
        </button>
        {error && <p className="mt-3 text-sm text-danger">{error}</p>}
      </main>
    );
  }

  const v = verdict[pass.state as keyof typeof verdict] ?? verdict.expired;

  return (
    <main className="mx-auto max-w-sm px-5 py-8">
      {/* The verdict first, and big. Whoever is reading this is standing at a
          barrier with a car waiting behind them. */}
      <div className={cn("rounded-card border-2 px-5 py-6 text-center", v.tone)}>
        <p className="text-3xl font-bold">{v.word}</p>
        <p className="mt-1 text-2xl font-semibold">{pass.vehicle_registration}</p>
      </div>

      <dl className="mt-6 space-y-3 text-sm">
        {[
          ["Vehicle", pass.vehicle_description || pass.vehicle_registration],
          ["Resident", pass.holder_name || pass.holder_email || "Not recorded"],
          ["Community", pass.community],
          ["Visiting", pass.visiting || "Not given"],
          ["Valid until", when(pass.expires_at)],
          ...(pass.exited_at ? [["Left at", when(pass.exited_at)] as const] : []),
        ].map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4 border-b border-line pb-2">
            <dt className="text-ink-muted">{label}</dt>
            <dd className="text-right font-medium text-ink">{value}</dd>
          </div>
        ))}
      </dl>

      {pass.state === "valid" && (
        <button
          type="button"
          onClick={letOut}
          disabled={busy}
          className="mt-6 h-12 w-full rounded-control bg-ink font-semibold text-surface disabled:opacity-40"
        >
          {busy ? "Recording..." : "Vehicle is leaving, end the pass"}
        </button>
      )}

      {pass.state === "used" && (
        <p className="mt-6 text-center text-sm text-ink-muted">
          This pass has been used. If the vehicle is coming back, the resident
          needs to ask for a new one.
        </p>
      )}

      {error && <p className="mt-4 text-center text-sm text-danger">{error}</p>}
    </main>
  );
}

export default function ParkingCheckPage() {
  // The token arrives in the query string, and reading it needs a boundary in
  // a statically exported page.
  return (
    <Suspense fallback={<main className="p-8 text-ink-muted">Loading...</main>}>
      <Gate />
    </Suspense>
  );
}
