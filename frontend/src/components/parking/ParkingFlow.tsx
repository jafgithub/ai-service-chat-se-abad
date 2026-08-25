"use client";

import { useState } from "react";

import { ApiError, parkingApi, type ParkingPass } from "@/lib/api";
import { useCommunities } from "@/lib/community";
import { useAuth } from "@/components/auth/AuthProvider";
import { AuthPanel } from "@/components/auth/AuthPanel";
import { Sheet } from "@/components/ui/Sheet";
import { Button } from "@/components/ui/Button";

/**
 * A parking pass, asked for in the conversation and filled in on a form.
 *
 * The client asked for this to start from the chat: "users ask for create
 * parking permit in the chat, it opens up a form, the users fill info, it
 * creates the qr code". So the chat recognises the request and opens this, the
 * same way asking to check out opens the checkout on the shop.
 *
 * It is a form rather than a series of questions on purpose. Five details asked
 * one at a time is a worse way to fill in a form than a form, and a resident
 * standing at a barrier with a visitor waiting is the least patient user this
 * product has.
 *
 * Signing in happens here, at the point it is needed, exactly as it does in the
 * booking flow. A pass belongs to a person: the office has to be able to say
 * whose vehicle is on the property, so an anonymous pass is not a pass.
 */

const DAYS = [1, 2, 3, 5];

interface ParkingFlowProps {
  onClose: () => void;
  /** Told to the conversation, so the transcript records what happened. */
  onIssued?: (pass: ParkingPass) => void;
}

export function ParkingFlow({ onClose, onIssued }: ParkingFlowProps) {
  const { status } = useAuth();
  const { options, current } = useCommunities();

  // "" means "not chosen here yet", which falls back to the community already
  // picked for the documents. Derived rather than copied into state on an
  // effect: the fallback arrives asynchronously, and syncing it would render
  // twice and fight anyone who chose before it landed.
  const [choice, setChoice] = useState("");
  const [registration, setRegistration] = useState("");
  const [description, setDescription] = useState("");
  const [visiting, setVisiting] = useState("");
  const [days, setDays] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [issued, setIssued] = useState<ParkingPass | null>(null);

  // The community they already chose for the documents, rather than asking a
  // resident of one association which association they live in.
  const community = choice || current?.key || "";
  const signedIn = status === "signed-in";

  const submit = async () => {
    if (!registration.trim() || !community) return;
    setBusy(true);
    setError("");
    try {
      const pass = await parkingApi.request({
        community,
        vehicle_registration: registration.trim().toUpperCase(),
        vehicle_description: description.trim() || undefined,
        visiting: visiting.trim() || undefined,
        days,
      });
      setIssued(pass);
      onIssued?.(pass);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not issue the pass.");
    } finally {
      setBusy(false);
    }
  };

  if (issued) {
    return (
      <Sheet title="Your parking pass" onClose={onClose}>
        <div className="text-center">
          <p className="text-sm text-ink-muted">
            {issued.vehicle_registration}, valid until{" "}
            {new Date(issued.expires_at).toLocaleString(undefined, {
              dateStyle: "medium",
              timeStyle: "short",
            })}
          </p>

          {/* Drawn from the response, so this screen makes no second request
              and cannot spin over a pass that already exists. */}
          <div
            className="mx-auto mt-4 w-[210px] [&>svg]:h-auto [&>svg]:w-full"
            dangerouslySetInnerHTML={{ __html: issued.qr_svg }}
          />

          <p className="mt-4 text-sm text-ink">
            The same code is on its way to your email, so you can forward it to
            whoever is driving.
          </p>
          <p className="mt-2 text-xs text-ink-faint">
            Show it at the gate. The pass is finished once the vehicle leaves.
          </p>

          <Button onClick={onClose} size="lg" className="mt-5 w-full">
            Done
          </Button>
        </div>
      </Sheet>
    );
  }

  return (
    <Sheet
      title="Parking pass"
      subtitle={signedIn ? "For a visitor, or for your own second vehicle" : undefined}
      onClose={onClose}
      footer={
        signedIn ? (
          <Button
            onClick={submit}
            disabled={busy || !registration.trim() || !community}
            size="lg"
            className="w-full"
          >
            {busy ? "Issuing..." : "Get the pass"}
          </Button>
        ) : undefined
      }
    >
      {!signedIn ? (
        /* In the sheet rather than on a page of its own: what they have typed
           so far is in this component's state, and a navigation would throw it
           away. */
        <AuthPanel
          intro="A pass belongs to a person, so the office can say whose vehicle is on the property. Sign in and I will issue it."
          onDone={() => setError("")}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm">
            <span className="mb-1 block font-medium text-ink">Vehicle registration</span>
            <input
              value={registration}
              onChange={(e) => setRegistration(e.target.value)}
              placeholder="ABC 1234"
              autoFocus
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
            <span className="mb-1 block font-medium text-ink">Community</span>
            <select
              value={community}
              onChange={(e) => setChoice(e.target.value)}
              className="h-11 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
            >
              <option value="">Choose one</option>
              {options.map((c) => (
                <option key={c.key} value={c.key}>{c.label}</option>
              ))}
            </select>
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

          <label className="text-sm sm:col-span-2">
            <span className="mb-1 block font-medium text-ink">For how long</span>
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="h-11 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
            >
              {DAYS.map((d) => (
                <option key={d} value={d}>{d} day{d === 1 ? "" : "s"}</option>
              ))}
            </select>
          </label>

          {error && (
            <p role="alert" className="rounded-control bg-danger-soft px-4 py-3 text-sm text-danger sm:col-span-2">
              {error}
            </p>
          )}
        </div>
      )}
    </Sheet>
  );
}
