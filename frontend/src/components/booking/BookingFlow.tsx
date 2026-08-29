"use client";

import { useCallback, useRef, useState } from "react";

import { ApiError, bookingApi, paymentsApi, providersApi, requestsApi } from "@/lib/api";
import type { Booked, PaymentMethod, ProviderOffer, ServiceResult, Slot } from "@/lib/api";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/components/auth/AuthProvider";
import { AuthPanel } from "@/components/auth/AuthPanel";
import { Sheet } from "@/components/ui/Sheet";
import { Button } from "@/components/ui/Button";
import { Empty, Failed, Loading } from "@/components/ui/States";
import { ProviderCard } from "./ProviderCard";
import { ProviderProfilePanel } from "./ProviderProfilePanel";
import { SlotPicker } from "./SlotPicker";
import { BookingReview, tipValue } from "./BookingReview";
import type { TipChoice } from "./BookingReview";
import { BookingConfirmation } from "./BookingConfirmation";
import { formatWhen } from "@/lib/datetime";

/** The deployment prefix, so a payment provider sends the browser back to this
 *  application rather than to the shop that shares the host. */
const BASE = "/plumber";

/**
 * Service chosen, everything else to go.
 *
 * One sheet holds the whole of it: who can do it, their profile, when they are
 * free, what it will be, and the confirmation. It is one component because the
 * steps share one set of decisions, and a customer who loses the provider they
 * picked while choosing a time has lost the work of the last two screens.
 *
 * The step order is provider first, then time, and that is not arbitrary. Price
 * and duration are the provider's, so the length of a slot is not even knowable
 * until one is chosen. Asking for a time first would mean re-asking for it.
 *
 * Signing in happens here too, at the point it is genuinely needed, rather than
 * as a gate in front of the whole flow. Somebody should be able to see who can
 * fix their sink and what it costs before they are asked for an email address.
 */

type Step = "providers" | "profile" | "slots" | "review" | "done";

interface BookingFlowProps {
  service: ServiceResult;
  /** The recorded problem this booking answers, when one was recorded already. */
  serviceRequestId?: number | null;
  /**
   * What the customer said was wrong, in their own words.
   *
   * Carried so the problem can still be recorded for somebody who was not
   * signed in when they described it: `POST /requests` needs a customer, and
   * asking them to type it again after signing in would be asking them to
   * repeat themselves to a machine that was listening.
   */
  problem?: string;
  onClose: () => void;
  /** So the conversation can say what happened. */
  onBooked?: (booking: Booked) => void;
}

export function BookingFlow({
  service, serviceRequestId, problem, onClose, onBooked,
}: BookingFlowProps) {
  const { account, status } = useAuth();

  const [step, setStep] = useState<Step>("providers");
  const {
    data: discovery,
    error: discoveryError,
    loading: findingProviders,
    reload: findAgain,
  } = useResource((signal) => providersApi.forService(service.id, signal), [service.id]);

  const [offer, setOffer] = useState<ProviderOffer | null>(null);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [address, setAddress] = useState("");
  const [notes, setNotes] = useState("");
  const [method, setMethod] = useState<PaymentMethod>("cod");
  const [tip, setTip] = useState<TipChoice>({ kind: "none" });

  const [requestId, setRequestId] = useState<number | null>(serviceRequestId ?? null);
  const [booking, setBooking] = useState<Booked | null>(null);
  const [failure, setFailure] = useState("");
  const [placing, setPlacing] = useState(false);
  // A ref as well as the state: React batches, so a double tap can arrive
  // before `placing` has flipped, and this one creates an appointment.
  const placingRef = useRef(false);

  /** The problem, recorded, if it has not been already.
   *
   *  Never fatal: a booking that goes through without its request attached is
   *  worse bookkeeping, but refusing the booking over it would be worse for the
   *  person with the leak. */
  const ensureRequest = useCallback(async (): Promise<number | null> => {
    if (requestId) return requestId;
    if (!problem?.trim()) return null;
    try {
      const created = await requestsApi.create({
        description: problem.trim(),
        service_id: service.id,
        address: address.trim() || undefined,
      });
      setRequestId(created.id);
      return created.id;
    } catch {
      return null;
    }
  }, [requestId, problem, service.id, address]);

  const confirm = useCallback(async () => {
    if (!offer || !slot || placingRef.current) return;
    placingRef.current = true;
    setPlacing(true);
    setFailure("");

    try {
      const attached = await ensureRequest();
      const result = await bookingApi.book({
        provider_id: offer.provider_id,
        service_id: service.id,
        starts_at: slot.starts_at,
        address: address.trim() || undefined,
        notes: notes.trim() || undefined,
        service_request_id: attached ?? undefined,
        payment_method: method,
        /* Only ever one of the two. A percentage is a request for the server to
           work the money out; an amount is only sent when they typed one, and
           is clamped on that side regardless of what arrives. */
        tip_percent: tip.kind === "percent" ? tip.percent : undefined,
        tip_amount:
          tip.kind === "custom" && offer
            ? tipValue(tip, offer.price) || undefined
            : undefined,
      });
      onBooked?.(result);

      /* Paying online means leaving this site, so the appointment is made
         first and the payment page comes after. Deliberately that way round:
         the slot is genuinely taken either way, and somebody who abandons a
         card page still has a plumber coming rather than nothing. */
      if (result.payment_due) {
        const back = `${window.location.origin}${BASE}/bookings`;
        try {
          const { url } = await paymentsApi.checkout(
            result.job_id,
            method,
            `${back}?paid=${result.job_id}`,
            `${back}?payment_cancelled=${result.job_id}`,
          );
          // Everything in React is about to be discarded by a full navigation,
          // and that is fine: the booking is already on the server and shows up
          // under My bookings whether or not they come back.
          window.location.assign(url);
          return;
        } catch (err) {
          // The booking stands. Say so, and let them pay from My bookings.
          setBooking({ ...result, payment_status: "unpaid" });
          setStep("done");
          setFailure(
            err instanceof ApiError
              ? `Booked, but we could not open the payment page: ${err.detail}`
              : "Booked, but we could not reach the payment page."
          );
          return;
        }
      }

      setBooking(result);
      setStep("done");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          // Somebody else took it, or the provider stopped offering it while
          // this was open. Send them back to the times, which will refetch.
          setFailure(`${err.detail} Please choose another time.`);
          setSlot(null);
          setStep("slots");
        } else if (err.status === 401) {
          setFailure("Your session ended. Please sign in again to confirm.");
        } else {
          setFailure(err.detail);
        }
      } else {
        setFailure("We could not reach the server. Nothing has been booked.");
      }
    } finally {
      placingRef.current = false;
      setPlacing(false);
    }
  }, [offer, slot, service.id, address, notes, method, tip, ensureRequest, onBooked]);

  // ── each step ──────────────────────────────────────────────────────────────

  if (step === "done" && booking) {
    return (
      <Sheet title="Booked" onClose={onClose}>
        {failure && (
          <p role="alert" className="mb-3 rounded-control border border-warn/30 bg-warn-soft px-3 py-2 text-sm text-warn">
            {failure}
          </p>
        )}
        <BookingConfirmation booking={booking} onDone={onClose} />
      </Sheet>
    );
  }

  if (step === "review" && offer && slot) {
    const signedIn = status === "signed-in";
    return (
      <Sheet
        title="Check and confirm"
        subtitle={`${offer.business_name}, ${formatWhen(slot.starts_at)}`}
        onBack={() => setStep("slots")}
        onClose={onClose}
        footer={
          signedIn ? (
            <Button onClick={confirm} disabled={placing} size="lg" className="w-full">
              {placing
                ? (method === "cod" ? "Booking…" : "Taking you to pay…")
                : (method === "cod" ? "Book appointment" : "Book and pay")}
            </Button>
          ) : undefined
        }
      >
        {signedIn ? (
          <BookingReview
            service={service}
            offer={offer}
            slot={slot}
            account={account}
            address={address}
            onAddressChange={setAddress}
            notes={notes}
            onNotesChange={setNotes}
            method={method}
            onMethodChange={setMethod}
            tip={tip}
            onTipChange={setTip}
            failure={failure}
          />
        ) : status === "loading" ? (
          <Loading label="Checking your account" rows={1} />
        ) : (
          /* Signing in here rather than sending them to a page. The provider
             and the time they picked are held in this component's state, and a
             navigation would throw both away. */
          <AuthPanel
            intro={`Almost there. Sign in and we will hold ${formatWhen(slot.starts_at)} with ${offer.business_name}.`}
            onDone={() => setFailure("")}
          />
        )}
      </Sheet>
    );
  }

  if (step === "slots" && offer) {
    return (
      <Sheet
        title="Pick a time"
        subtitle={offer.business_name}
        onBack={() => setStep("providers")}
        onClose={onClose}
        footer={
          slot ? (
            <Button onClick={() => setStep("review")} size="lg" className="w-full">
              Continue with {formatWhen(slot.starts_at)}
            </Button>
          ) : undefined
        }
      >
        {failure && (
          <p role="alert" className="mb-3 rounded-control border border-warn/30 bg-warn-soft px-3 py-2 text-sm text-warn">
            {failure}
          </p>
        )}
        <SlotPicker
          providerId={offer.provider_id}
          serviceId={service.id}
          durationMinutes={offer.duration_minutes}
          selected={slot}
          onSelect={setSlot}
        />
      </Sheet>
    );
  }

  if (step === "profile" && offer) {
    return (
      <Sheet
        title={offer.business_name}
        subtitle="Provider profile"
        onBack={() => setStep("providers")}
        onClose={onClose}
      >
        <ProviderProfilePanel
          providerId={offer.provider_id}
          serviceId={service.id}
          onBook={() => setStep("slots")}
        />
      </Sheet>
    );
  }

  // ── who can do it ──────────────────────────────────────────────────────────

  return (
    <Sheet
      title={service.name}
      subtitle={
        discovery
          ? `${discovery.providers.length} provider${discovery.providers.length === 1 ? "" : "s"}`
          : "Finding providers"
      }
      onClose={onClose}
      width="lg"
    >
      {discoveryError ? (
        <Failed detail={discoveryError} onRetry={findAgain} />
      ) : findingProviders || !discovery ? (
        <Loading label="Finding providers" />
      ) : discovery.providers.length === 0 ? (
        /* A real answer, and the one worth recording. Nobody on the platform
           does this yet, which the office sees in the unserved list. */
        <Empty
          icon="🔍"
          title="Nobody covers that yet"
          body="No approved provider offers this service at the moment. Your request has been recorded, and we will let you know when somebody can take it on."
        />
      ) : (
        <>
          <p className="mb-3 text-xs text-ink-muted">
            {rankingNote(discovery.ranked_by)}
          </p>
          <div className="space-y-3">
            {discovery.providers.map((row, i) => (
              <ProviderCard
                key={row.provider_id}
                offer={row}
                best={i === 0 && discovery.providers.length > 1}
                onChoose={(chosen) => {
                  setOffer(chosen);
                  setSlot(null);
                  setFailure("");
                  setStep("slots");
                }}
                onViewProfile={(chosen) => {
                  setOffer(chosen);
                  setStep("profile");
                }}
              />
            ))}
          </div>
        </>
      )}
    </Sheet>
  );
}

/** Says why the list is in the order it is. The backend decides the ordering
 *  and reports which one it used; nothing here re-sorts. */
function rankingNote(rankedBy: string): string {
  switch (rankedBy) {
    case "price":
      return "Cheapest first.";
    case "distance":
      return "Nearest first.";
    case "rating":
      return "Best rated first.";
    default:
      return "Soonest available first, then lowest price.";
  }
}
