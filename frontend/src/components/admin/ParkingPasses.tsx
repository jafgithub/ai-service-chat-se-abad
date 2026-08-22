"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { parkingApi, type ParkingPassHolder } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Every parking pass, and whose it is.
 *
 * The office's half of the feature. A resident gets a code; this is where
 * somebody can answer "whose car is that", which is the whole reason a pass
 * requires a login in the first place.
 */

const state = {
  valid: { label: "Valid", tone: "bg-positive-soft text-positive" },
  used: { label: "Left", tone: "bg-surface-sunken text-ink-muted" },
  expired: { label: "Expired", tone: "bg-warn-soft text-warn" },
  cancelled: { label: "Cancelled", tone: "bg-danger-soft text-danger" },
} as const;

const when = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";

export function ParkingPasses({ token }: { token: string }) {
  const [passes, setPasses] = useState<ParkingPassHolder[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setPasses(await parkingApi.all({ "X-Admin-Token": token }));
      setError("");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not load the passes.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (!cancelled) await load();
    })();
    return () => { cancelled = true; };
  }, [load]);

  const live = passes.filter((p) => p.state === "valid").length;

  return (
    <section className="rounded-card border border-line bg-surface">
      <header className="border-b border-line px-5 py-4">
        <h2 className="text-base font-semibold text-ink">Parking passes</h2>
        <p className="mt-0.5 text-sm text-ink-muted">
          {loading ? "Loading..." : `${live} vehicle${live === 1 ? "" : "s"} on the property now, ${passes.length} pass${passes.length === 1 ? "" : "es"} in total.`}
        </p>
      </header>

      {error && (
        <p className="m-5 rounded-control bg-danger-soft px-4 py-3 text-sm text-danger">{error}</p>
      )}

      {!loading && passes.length === 0 ? (
        <p className="px-5 py-4 text-sm text-ink-muted">No passes have been issued yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                <th className="px-5 py-2 font-medium">Vehicle</th>
                <th className="px-4 py-2 font-medium">Resident</th>
                <th className="px-4 py-2 font-medium">Community</th>
                <th className="px-4 py-2 font-medium">Visiting</th>
                <th className="px-4 py-2 font-medium">Valid until</th>
                <th className="px-4 py-2 font-medium">State</th>
              </tr>
            </thead>
            <tbody>
              {passes.map((pass) => {
                const s = state[pass.state as keyof typeof state] ?? state.expired;
                return (
                  <tr key={pass.id} className="border-b border-line last:border-0">
                    <td className="px-5 py-2.5 font-medium text-ink">
                      {pass.vehicle_registration}
                      {pass.vehicle_description && (
                        <span className="block text-xs text-ink-faint">{pass.vehicle_description}</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      {pass.holder_name || "—"}
                      <span className="block text-xs text-ink-faint">{pass.holder_email}</span>
                    </td>
                    <td className="px-4 py-2.5 text-ink-muted">{pass.community}</td>
                    <td className="px-4 py-2.5 text-ink-muted">{pass.visiting || "—"}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap text-ink-muted">
                      {when(pass.expires_at)}
                      {pass.exited_at && (
                        <span className="block text-xs text-ink-faint">left {when(pass.exited_at)}</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", s.tone)}>
                        {s.label}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
