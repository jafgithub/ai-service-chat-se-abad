"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, getAuthToken } from "@/lib/api";
import { parkingApi, docsApi, type ParkingPass, type CommunityOption } from "@/lib/api";
import { storedCommunity } from "@/lib/community";
import { cn } from "@/lib/utils";

/**
 * A resident's parking passes.
 *
 * Signed in only, and that is the feature rather than a hurdle: a pass is
 * personal, and the office has to be able to say whose vehicle is on the
 * property. Somebody signed out is sent to sign in rather than shown a form
 * that will fail when they submit it.
 *
 * The code is drawn on the page and sent by email at the same time, because a
 * resident who closes this tab on the way out of the door still has to open a
 * barrier twenty minutes later.
 */

const state = {
  valid: { label: "Valid", tone: "bg-positive-soft text-positive" },
  used: { label: "Vehicle has left", tone: "bg-surface-sunken text-ink-muted" },
  expired: { label: "Expired", tone: "bg-warn-soft text-warn" },
  cancelled: { label: "Cancelled by the office", tone: "bg-danger-soft text-danger" },
} as const;

const when = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

export default function ParkingPage() {
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [passes, setPasses] = useState<ParkingPass[]>([]);
  const [communities, setCommunities] = useState<CommunityOption[]>([]);
  const [community, setCommunity] = useState("");
  const [registration, setRegistration] = useState("");
  const [description, setDescription] = useState("");
  const [visiting, setVisiting] = useState("");
  const [days, setDays] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [issued, setIssued] = useState<ParkingPass | null>(null);

  const load = useCallback(async () => {
    try {
      const [mine, list] = await Promise.all([parkingApi.mine(), docsApi.communities()]);
      setPasses(mine);
      setCommunities(list.communities);
      setCommunity((c) => c || storedCommunity() || list.home || list.communities[0]?.key || "");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setSignedIn(false);
      else setError(err instanceof ApiError ? err.detail : "Could not load your passes.");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      const token = getAuthToken();
      setSignedIn(Boolean(token));
      if (token) await load();
    })();
    return () => { cancelled = true; };
  }, [load]);

  const ask = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const pass = await parkingApi.request({
        community,
        vehicle_registration: registration,
        vehicle_description: description,
        visiting,
        days,
      });
      setIssued(pass);
      setRegistration("");
      setDescription("");
      setVisiting("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not issue the pass.");
    } finally {
      setBusy(false);
    }
  };

  const leave = async (pass: ParkingPass) => {
    if (!window.confirm(
      `End the pass for ${pass.vehicle_registration}?\n\n` +
      "It stops working straight away, so only do this once the vehicle has left."
    )) return;
    try {
      await parkingApi.leave(pass.id);
      if (issued?.id === pass.id) setIssued(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not end the pass.");
    }
  };

  if (signedIn === false) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-6">
        <h1 className="text-2xl font-semibold text-ink">Parking passes</h1>
        <p className="mt-2 text-ink-muted">
          A pass belongs to a person, so you need to be signed in to have one.
        </p>
        <Link
          href="/login?next=/parking"
          className="mt-5 flex h-12 items-center justify-center rounded-control bg-brand-500 font-semibold text-white"
        >
          Sign in
        </Link>
        <Link href="/register" className="mt-3 text-center text-sm text-ink-muted underline">
          I do not have an account yet
        </Link>
      </main>
    );
  }

  const live = passes.filter((p) => p.state === "valid");
  const past = passes.filter((p) => p.state !== "valid");

  return (
    <main className="mx-auto max-w-2xl px-5 py-10">
      <h1 className="text-2xl font-semibold text-ink">Parking passes</h1>
      <p className="mt-1 text-ink-muted">
        Show the code when you arrive and again when you leave. A copy is emailed
        to you as well.
      </p>

      {issued && (
        <section className="mt-6 rounded-card border border-line bg-surface p-6 text-center">
          <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">
            Your pass
          </p>
          <p className="mt-1 text-xl font-semibold text-ink">{issued.vehicle_registration}</p>
          <div
            className="mx-auto mt-4 w-[220px] [&>svg]:h-auto [&>svg]:w-full"
            // The code comes from our own API, drawn from a token we issued.
            dangerouslySetInnerHTML={{ __html: issued.qr_svg }}
          />
          <p className="mt-3 text-sm text-ink-muted">
            Valid until {when(issued.expires_at)}
          </p>
        </section>
      )}

      <form onSubmit={ask} className="mt-6 grid gap-3 rounded-card border border-line bg-surface p-5 sm:grid-cols-2">
        <label className="text-sm sm:col-span-2">
          <span className="mb-1 block font-medium text-ink">Community</span>
          <select
            value={community}
            onChange={(e) => setCommunity(e.target.value)}
            className="h-11 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
          >
            {communities.map((c) => (
              <option key={c.key} value={c.key}>{c.label}</option>
            ))}
          </select>
        </label>

        <label className="text-sm">
          <span className="mb-1 block font-medium text-ink">Vehicle registration</span>
          <input
            value={registration}
            onChange={(e) => setRegistration(e.target.value)}
            placeholder="ABC 1234"
            className="h-11 w-full rounded-control border border-line bg-surface px-3 text-sm uppercase text-ink"
          />
        </label>

        <label className="text-sm">
          <span className="mb-1 block font-medium text-ink">Make and colour</span>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Blue Toyota Corolla"
            className="h-11 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
          />
        </label>

        <label className="text-sm">
          <span className="mb-1 block font-medium text-ink">Visiting</span>
          <input
            value={visiting}
            onChange={(e) => setVisiting(e.target.value)}
            placeholder="Unit 214"
            className="h-11 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
          />
        </label>

        <label className="text-sm">
          <span className="mb-1 block font-medium text-ink">For how long</span>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="h-11 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
          >
            {[1, 2, 3, 5].map((d) => (
              <option key={d} value={d}>{d} day{d === 1 ? "" : "s"}</option>
            ))}
          </select>
        </label>

        <div className="sm:col-span-2">
          <button
            type="submit"
            disabled={busy || !registration.trim() || !community}
            className="h-11 rounded-control bg-brand-500 px-5 text-sm font-semibold text-white disabled:opacity-40"
          >
            {busy ? "Issuing..." : "Get a pass"}
          </button>
        </div>

        {error && (
          <p className="rounded-control bg-danger-soft px-4 py-3 text-sm text-danger sm:col-span-2">
            {error}
          </p>
        )}
      </form>

      {live.length > 0 && (
        <section className="mt-8">
          <h2 className="text-base font-semibold text-ink">In use</h2>
          <ul className="mt-3 space-y-3">
            {live.map((pass) => (
              <li key={pass.id} className="rounded-card border border-line bg-surface p-4">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-semibold text-ink">{pass.vehicle_registration}</span>
                  <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold",
                                      state.valid.tone)}>
                    {state.valid.label}
                  </span>
                  <span className="text-xs text-ink-faint">until {when(pass.expires_at)}</span>
                  <button
                    type="button"
                    onClick={() => leave(pass)}
                    className="ml-auto text-sm font-medium text-ink-muted hover:text-ink"
                  >
                    I have left
                  </button>
                </div>
                <div
                  className="mx-auto mt-4 w-[180px] [&>svg]:h-auto [&>svg]:w-full"
                  dangerouslySetInnerHTML={{ __html: pass.qr_svg }}
                />
              </li>
            ))}
          </ul>
        </section>
      )}

      {past.length > 0 && (
        <section className="mt-8">
          <h2 className="text-base font-semibold text-ink">Finished</h2>
          <ul className="mt-3 space-y-2">
            {past.map((pass) => {
              const s = state[pass.state as keyof typeof state] ?? state.expired;
              return (
                <li key={pass.id}
                    className="flex flex-wrap items-center gap-3 rounded-control border border-line px-4 py-3">
                  <span className="font-medium text-ink">{pass.vehicle_registration}</span>
                  <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", s.tone)}>
                    {s.label}
                  </span>
                  <span className="text-xs text-ink-faint">{when(pass.issued_at)}</span>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </main>
  );
}
