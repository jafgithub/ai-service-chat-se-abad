"use client";

import { useMemo, useState } from "react";

import { ApiError, providerMeApi, servicesApi } from "@/lib/api";
import type { MyServiceRow, Service } from "@/lib/api";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/components/auth/AuthProvider";
import { ProviderShell } from "@/components/provider/ProviderShell";
import { Empty, Failed, Loading } from "@/components/ui/States";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";
import { formatDuration } from "@/lib/datetime";
import { formatMoney } from "@/lib/service";
import { cn } from "@/lib/utils";

/**
 * What this business does, and on what terms.
 *
 * The terms are the whole reason this page exists. The service carries a guide
 * price and a guide duration, and every provider is expected to differ from
 * them; those figures are shown next to each row precisely so the difference is
 * visible rather than mysterious.
 *
 * Withdrawing is a deactivation, not a deletion, and the button says "stop
 * offering" rather than "delete" for that reason: appointments already booked
 * keep the terms they were made under.
 */
export default function ProviderServicesPage() {
  const { status, account } = useAuth();
  const [editing, setEditing] = useState<MyServiceRow | null>(null);
  const [adding, setAdding] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [actionFailure, setActionFailure] = useState("");

  const { data: rows, error, loading, reload } = useResource(
    (signal) => providerMeApi.services(signal),
    [],
    { enabled: status === "signed-in" && account?.role === "provider" }
  );

  const withdraw = async (row: MyServiceRow) => {
    setBusyId(row.provider_service_id);
    setActionFailure("");
    try {
      await providerMeApi.withdrawService(row.provider_service_id);
      reload();
    } catch (err) {
      setActionFailure(err instanceof ApiError ? err.detail : "We could not change that just now.");
    } finally {
      setBusyId(null);
    }
  };

  const restore = async (row: MyServiceRow) => {
    setBusyId(row.provider_service_id);
    setActionFailure("");
    try {
      await providerMeApi.saveService({
        service_id: row.service_id,
        price: row.price,
        duration_minutes: row.duration_minutes,
        notes: row.notes,
        active: true,
      });
      reload();
    } catch (err) {
      setActionFailure(err instanceof ApiError ? err.detail : "We could not change that just now.");
    } finally {
      setBusyId(null);
    }
  };

  const active = rows?.filter((r) => r.active) ?? [];
  const withdrawn = rows?.filter((r) => !r.active) ?? [];

  return (
    <ProviderShell
      title="My services"
      subtitle="What you offer, what you charge, and how long you need."
      action={<Button onClick={() => setAdding(true)}>Add a service</Button>}
    >
      {actionFailure && (
        <p role="alert" className="mb-3 rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
          {actionFailure}
        </p>
      )}

      {error ? (
        <Failed detail={error} onRetry={reload} />
      ) : loading || rows === null ? (
        <Loading label="Loading your services" />
      ) : rows.length === 0 ? (
        <Empty
          icon="🧰"
          title="You have not listed anything yet"
          body="Customers find you by the services you offer, so nothing here means nobody can find you."
          action={{ label: "Add a service", onClick: () => setAdding(true) }}
        />
      ) : (
        <div className="space-y-5">
          <ul className="space-y-2.5">
            {active.map((row) => (
              <li key={row.provider_service_id} className="rounded-card border border-line bg-surface p-4 shadow-card">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="text-sm font-semibold text-ink">{row.name}</h2>
                    <p className="mt-0.5 text-xs text-ink-muted">
                      {/* Says whose number it is. "Guide" means we filled it in
                          because they have not, which they may not realise. */}
                      {row.price != null
                        ? `Your price ${formatMoney(row.price)}`
                        : `Guide price ${formatMoney(row.guide_price)}`}
                      {" · "}
                      {row.duration_minutes != null
                        ? `Your slot ${formatDuration(row.duration_minutes)}`
                        : `Guide slot ${formatDuration(row.guide_duration)}`}
                    </p>
                    {row.notes && <p className="mt-1.5 text-xs text-ink-muted">{row.notes}</p>}
                  </div>

                  <div className="flex flex-shrink-0 gap-2">
                    <Button size="sm" variant="secondary" onClick={() => setEditing(row)}>
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={busyId === row.provider_service_id}
                      onClick={() => withdraw(row)}
                    >
                      {busyId === row.provider_service_id ? "…" : "Stop offering"}
                    </Button>
                  </div>
                </div>
              </li>
            ))}
          </ul>

          {withdrawn.length > 0 && (
            <section>
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
                No longer offered
              </h2>
              <ul className="space-y-2">
                {withdrawn.map((row) => (
                  <li
                    key={row.provider_service_id}
                    className="flex items-center justify-between gap-3 rounded-card border border-line bg-surface-sunken px-4 py-2.5"
                  >
                    <span className="min-w-0 truncate text-sm text-ink-muted">{row.name}</span>
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={busyId === row.provider_service_id}
                      onClick={() => restore(row)}
                    >
                      {busyId === row.provider_service_id ? "…" : "Offer again"}
                    </Button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}

      {editing && (
        <TermsSheet
          row={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); reload(); }}
        />
      )}

      {adding && (
        <AddSheet
          existing={rows ?? []}
          onClose={() => setAdding(false)}
          onSaved={() => { setAdding(false); reload(); }}
        />
      )}
    </ProviderShell>
  );
}

/** Editing one service's price and duration. */
function TermsSheet({
  row, onClose, onSaved,
}: {
  row: MyServiceRow;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [price, setPrice] = useState(row.price != null ? String(row.price) : "");
  const [duration, setDuration] = useState(row.duration_minutes != null ? String(row.duration_minutes) : "");
  const [notes, setNotes] = useState(row.notes ?? "");
  const [failure, setFailure] = useState("");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    const mins = duration ? Number(duration) : null;
    if (mins != null && (mins < 15 || mins > 600)) {
      setFailure("A slot has to be between 15 and 600 minutes.");
      return;
    }
    setSaving(true);
    setFailure("");
    try {
      await providerMeApi.saveService({
        service_id: row.service_id,
        price: price ? Number(price) : null,
        duration_minutes: mins,
        notes: notes.trim() || null,
        active: true,
      });
      onSaved();
    } catch (err) {
      setFailure(err instanceof ApiError ? err.detail : "We could not save that just now.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Sheet
      title={row.name}
      subtitle="Your terms for this service"
      onClose={onClose}
      footer={
        <Button onClick={save} disabled={saving} size="lg" className="w-full">
          {saving ? "Saving…" : "Save"}
        </Button>
      }
    >
      <div className="space-y-3.5">
        <Field
          label="Your price"
          type="number"
          min="0"
          step="0.01"
          value={price}
          onChange={setPrice}
          placeholder={String(row.guide_price)}
          hint={`Leave blank to use the guide price of ${formatMoney(row.guide_price)}.`}
        />
        <Field
          label="How long you need, in minutes"
          type="number"
          min="15"
          step="5"
          value={duration}
          onChange={setDuration}
          placeholder={String(row.guide_duration ?? 60)}
          hint="This decides the length of the slots customers can book."
        />
        <Field
          label="Anything to add"
          value={notes}
          onChange={setNotes}
          rows={3}
          hint="Optional. Shown with this service on your profile."
        />

        {failure && (
          <p role="alert" className="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
            {failure}
          </p>
        )}
      </div>
    </Sheet>
  );
}

/** Picking a new service from the catalogue. */
function AddSheet({
  existing, onClose, onSaved,
}: {
  existing: MyServiceRow[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [search, setSearch] = useState("");
  const [saving, setSaving] = useState<number | null>(null);
  const [addFailure, setAddFailure] = useState("");

  const { data: catalogue, error, loading, reload } = useResource(
    (signal) => servicesApi.list(undefined, signal),
    []
  );

  // Already listed, active or not: adding one they have withdrawn is done from
  // the list itself, so offering it here as new would be two ways to the same
  // row that behave differently.
  const alreadyMine = useMemo(
    () => new Set(existing.map((r) => r.service_id)),
    [existing]
  );

  const shown = useMemo(() => {
    if (!catalogue) return [];
    const q = search.trim().toLowerCase();
    return catalogue
      .filter((s) => !alreadyMine.has(s.id))
      .filter((s) => !q || `${s.name} ${s.category}`.toLowerCase().includes(q))
      .slice(0, 60);
  }, [catalogue, search, alreadyMine]);

  const add = async (service: Service) => {
    setSaving(service.id);
    try {
      // Added on the guide figures. Editing them is one tap away, and a form
      // that demands a price before it will list anything is a form somebody
      // abandons.
      await providerMeApi.saveService({ service_id: service.id, active: true });
      onSaved();
    } catch (err) {
      setAddFailure(err instanceof ApiError ? err.detail : "We could not add that just now.");
    } finally {
      setSaving(null);
    }
  };

  return (
    <Sheet title="Add a service" subtitle="Pick what you offer" onClose={onClose} width="lg">
      {error ? (
        <Failed detail={error} onRetry={reload} />
      ) : loading || !catalogue ? (
        <Loading label="Loading services" rows={3} />
      ) : (
        <>
          {addFailure && (
            <p role="alert" className="mb-3 rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
              {addFailure}
            </p>
          )}

          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search services…"
            className="mb-3 h-11 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink placeholder-ink-faint focus:border-brand-300 focus:outline-none"
          />

          {shown.length === 0 ? (
            <p className="py-6 text-center text-sm text-ink-muted">
              {search ? "Nothing matches that." : "You already offer everything on the list."}
            </p>
          ) : (
            <ul className="space-y-1.5">
              {shown.map((service) => (
                <li
                  key={service.id}
                  className={cn(
                    "flex items-center justify-between gap-3 rounded-control border border-line px-3 py-2.5"
                  )}
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink">{service.name}</p>
                    <p className="text-[11px] text-ink-muted">
                      Guide {formatMoney(service.price_per_unit)}
                      {service.duration_minutes ? `, ${service.duration_minutes} min` : ""}
                    </p>
                  </div>
                  <Button size="sm" disabled={saving === service.id} onClick={() => add(service)}>
                    {saving === service.id ? "Adding…" : "Add"}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Sheet>
  );
}
