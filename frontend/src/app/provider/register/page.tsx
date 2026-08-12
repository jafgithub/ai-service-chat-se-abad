"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { ApiError, authApi, servicesApi } from "@/lib/api";
import type { Service } from "@/lib/api";
import { useAuth } from "@/components/auth/AuthProvider";
import { PageShell } from "@/components/layout/PageShell";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { formatMoney } from "@/lib/service";
import { cn } from "@/lib/utils";

/**
 * A business applying to join.
 *
 * Two things are worth knowing about this form.
 *
 * The services are optional. A business filling in a form at nine at night
 * should not be stopped by not having decided its prices yet, and the backend
 * accepts a registration with none: they can add them from the dashboard, which
 * is the same screen either way.
 *
 * It ends by saying plainly that nobody can book them yet. A provider who
 * thinks they are live and is not will wait for work that cannot arrive, and
 * will blame us for the silence.
 */
export default function ProviderRegisterPage() {
  const { accept, status } = useAuth();

  const [form, setForm] = useState({
    business_name: "",
    contact_name: "",
    email: "",
    password: "",
    phone: "",
    website: "",
    description: "",
    address: "",
    city: "",
    postcode: "",
  });
  const set = (key: keyof typeof form) => (value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const [catalogue, setCatalogue] = useState<Service[] | null>(null);
  const [catalogueFailed, setCatalogueFailed] = useState(false);
  const [chosen, setChosen] = useState<Record<number, { price: string; duration: string }>>({});
  const [search, setSearch] = useState("");

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [failure, setFailure] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let dropped = false;
    servicesApi
      .list()
      .then((rows) => { if (!dropped) setCatalogue(rows); })
      // Not fatal. Without the catalogue the application still goes through,
      // and the services are added afterwards from the dashboard.
      .catch(() => { if (!dropped) setCatalogueFailed(true); })
      ;
    return () => { dropped = true; };
  }, []);

  const shown = useMemo(() => {
    if (!catalogue) return [];
    const q = search.trim().toLowerCase();
    const rows = q
      ? catalogue.filter((s) => `${s.name} ${s.category}`.toLowerCase().includes(q))
      : catalogue;
    return rows.slice(0, 60);
  }, [catalogue, search]);

  const toggle = (service: Service) => {
    setChosen((prev) => {
      const next = { ...prev };
      if (next[service.id]) delete next[service.id];
      else next[service.id] = { price: "", duration: "" };
      return next;
    });
  };

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (form.business_name.trim().length < 2) errs.business_name = "The name of your business is needed";
    if (!form.email.trim()) errs.email = "An email address is needed";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errs.email = "That does not look like an email address";
    if (form.password.length < 8) errs.password = "Please use at least eight characters";

    for (const [id, row] of Object.entries(chosen)) {
      if (row.price && Number(row.price) < 0) errs[`price-${id}`] = "A price cannot be negative";
      const mins = Number(row.duration);
      if (row.duration && (mins < 15 || mins > 600)) {
        // The server enforces the same bounds. Saying so here saves a round
        // trip that would otherwise reject the whole application.
        errs[`duration-${id}`] = "Between 15 and 600 minutes";
      }
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy || !validate()) return;

    setBusy(true);
    setFailure("");
    try {
      const token = await authApi.registerProvider({
        business_name: form.business_name.trim(),
        contact_name: form.contact_name.trim() || undefined,
        email: form.email.trim(),
        password: form.password,
        phone: form.phone.trim() || undefined,
        website: form.website.trim() || undefined,
        description: form.description.trim() || undefined,
        address: form.address.trim() || undefined,
        city: form.city.trim() || undefined,
        postcode: form.postcode.trim() || undefined,
        services: Object.entries(chosen).map(([id, row]) => ({
          service_id: Number(id),
          price: row.price ? Number(row.price) : null,
          duration_minutes: row.duration ? Number(row.duration) : null,
        })),
      });
      await accept(token);
      setDone(true);
    } catch (err) {
      if (err instanceof ApiError) {
        setFailure(
          err.status === 409
            ? "There is already an account with that email. Sign in instead."
            : err.detail
        );
      } else {
        setFailure("We could not reach the server. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <PageShell title="Application received" width="narrow">
        <div className="rounded-card border border-line bg-surface p-6 text-center shadow-card">
          <span className="mb-3 block text-4xl" aria-hidden>📨</span>
          <h2 className="text-lg font-bold text-ink">Thanks. We have your application.</h2>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">
            The office reviews new businesses before they appear to customers.
            <strong className="font-semibold text-ink"> You cannot receive bookings yet.</strong>
          </p>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">
            You are signed in already, so you can fill in the rest of your
            services and set your working hours now. Everything will be ready the
            moment you are approved.
          </p>
          <div className="mt-5 flex flex-col gap-2">
            <Link
              href="/provider/dashboard"
              className="inline-flex h-11 items-center justify-center rounded-control bg-brand-500 px-5 text-sm font-semibold text-white transition-colors hover:bg-brand-600"
            >
              Go to my dashboard
            </Link>
          </div>
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell
      title="Register your business"
      subtitle="Tell us what you do and where. Approval usually takes a day or two."
    >
      {status === "signed-in" && (
        <p className="mb-4 rounded-control border border-warn/30 bg-warn-soft px-3 py-2 text-sm text-warn">
          You are already signed in. Registering here will create a second,
          separate account.
        </p>
      )}

      <form onSubmit={submit} className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section className="space-y-3.5 rounded-card border border-line bg-surface p-5 shadow-card">
          <h2 className="text-sm font-semibold text-ink">Your business</h2>

          <Field label="Business name" value={form.business_name} onChange={set("business_name")}
                 error={errors.business_name} required placeholder="Riverside Plumbing & Heating" />
          <Field label="Your name" value={form.contact_name} onChange={set("contact_name")}
                 autoComplete="name" hint="Who we should speak to." />
          <Field label="Email" type="email" value={form.email} onChange={set("email")}
                 error={errors.email} required autoComplete="email" />
          <Field label="Password" type="password" value={form.password} onChange={set("password")}
                 error={errors.password} required autoComplete="new-password"
                 hint="At least eight characters." />
          <Field label="Phone" type="tel" value={form.phone} onChange={set("phone")} autoComplete="tel" />
          <Field label="Website" value={form.website} onChange={set("website")}
                 placeholder="https://" hint="Optional. Shown on your profile." />

          <h2 className="pt-2 text-sm font-semibold text-ink">Where you work</h2>
          <Field label="Address" value={form.address} onChange={set("address")} autoComplete="street-address" />
          <div className="grid grid-cols-2 gap-3">
            <Field label="Town or city" value={form.city} onChange={set("city")} />
            <Field label="Postcode" value={form.postcode} onChange={set("postcode")} />
          </div>

          <Field label="About your business" value={form.description} onChange={set("description")}
                 rows={4} hint="What you do, how long you have done it. Customers see this." />
        </section>

        <section className="space-y-3 rounded-card border border-line bg-surface p-5 shadow-card">
          <div>
            <h2 className="text-sm font-semibold text-ink">What you do</h2>
            <p className="mt-1 text-xs leading-relaxed text-ink-muted">
              Tick what you offer and set your own price and how long you need.
              Leave either blank to use the guide figure. You can change all of
              this later.
            </p>
          </div>

          {catalogueFailed ? (
            <p className="rounded-control border border-warn/30 bg-warn-soft px-3 py-2 text-sm text-warn">
              We could not load the list of services just now. Your application
              will still go through, and you can add them from your dashboard.
            </p>
          ) : catalogue === null ? (
            <div className="space-y-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-11 animate-pulse rounded-control bg-surface-hover" />
              ))}
            </div>
          ) : (
            <>
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search services…"
                className="h-11 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink placeholder-ink-faint focus:border-brand-300 focus:outline-none"
              />

              <ul className="chat-scroll max-h-[26rem] space-y-1.5 overflow-y-auto pr-1">
                {shown.map((service) => {
                  const picked = chosen[service.id];
                  return (
                    <li
                      key={service.id}
                      className={cn(
                        "rounded-control border px-3 py-2 transition-colors",
                        picked ? "border-brand-300 bg-brand-50" : "border-line"
                      )}
                    >
                      <label className="flex cursor-pointer items-start gap-2.5">
                        <input
                          type="checkbox"
                          checked={Boolean(picked)}
                          onChange={() => toggle(service)}
                          className="mt-1 h-4 w-4 flex-shrink-0 accent-[color:var(--color-brand-500)]"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block text-sm font-medium text-ink">{service.name}</span>
                          <span className="block text-[11px] text-ink-muted">
                            Guide: {formatMoney(service.price_per_unit)}
                            {service.duration_minutes ? `, ${service.duration_minutes} min` : ""}
                          </span>
                        </span>
                      </label>

                      {picked && (
                        <div className="mt-2 grid grid-cols-2 gap-2 pl-7">
                          <Field
                            label="Your price"
                            type="number"
                            min="0"
                            step="0.01"
                            value={picked.price}
                            onChange={(v) =>
                              setChosen((prev) => ({ ...prev, [service.id]: { ...prev[service.id], price: v } }))
                            }
                            error={errors[`price-${service.id}`]}
                            placeholder={String(service.price_per_unit)}
                          />
                          <Field
                            label="Minutes"
                            type="number"
                            min="15"
                            step="5"
                            value={picked.duration}
                            onChange={(v) =>
                              setChosen((prev) => ({ ...prev, [service.id]: { ...prev[service.id], duration: v } }))
                            }
                            error={errors[`duration-${service.id}`]}
                            placeholder={String(service.duration_minutes ?? 60)}
                          />
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>

              {catalogue.length > shown.length && (
                <p className="text-xs text-ink-faint">
                  Showing {shown.length} of {catalogue.length}. Search to narrow it down.
                </p>
              )}
            </>
          )}
        </section>

        <div className="lg:col-span-2">
          {failure && (
            <p role="alert" className="mb-3 rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
              {failure}
            </p>
          )}

          <div className="flex flex-col items-center gap-3 sm:flex-row">
            <Button type="submit" size="lg" disabled={busy} className="w-full sm:w-auto">
              {busy ? "Sending your application…" : "Apply to join"}
            </Button>
            <p className="text-xs text-ink-muted">
              Already registered?{" "}
              <Link href="/provider/login" className="font-semibold text-brand-600 hover:underline">
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </form>
    </PageShell>
  );
}
