"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api";
import { AiRuntime } from "@/components/admin/AiRuntime";
import { ParkingPasses } from "@/components/admin/ParkingPasses";

/**
 * Staff view: orders, payments and takings.
 *
 * The site is a static export, so there is no server here to hold a session on.
 * The admin token is entered once, kept in localStorage and sent as
 * `X-Admin-Token` with every request, which is the same guard the backend
 * already uses for the reindex endpoint. That means anyone with the token has
 * full read access, so it belongs to staff and not to a shared machine.
 */

const TOKEN_KEY = "ai_order_admin_token";

interface Summary {
  window_days: number;
  orders: { total: number; in_window: number; by_status: Record<string, number> };
  revenue: { all_time: number; in_window: number };
  payments: { provider: string; status: string; count: number; amount: number }[];
  customers: number;
  index: { state?: string; rows?: number; built_at?: string };
}

interface OrderRow {
  id: number;
  status: string;
  payment_method: string | null;
  total: number;
  items: number;
  customer_name: string | null;
  customer_email: string | null;
  delivery_date: string | null;
  delivery_time: string | null;
  created_at: string | null;
  payments: { provider: string; status: string; amount: number }[];
}

interface PaymentRow {
  id: number;
  order_id: number;
  provider: string;
  status: string;
  amount: number;
  currency: string;
  provider_ref: string;
  created_at: string | null;
}

const money = (n: number) => `$${n.toFixed(2)}`;

const when = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";

/** Colour carries the same meaning everywhere: green paid, amber waiting, red failed. */
function StatusPill({ value }: { value: string }) {
  const tone =
    value === "confirmed" || value === "paid" || value === "delivered"
      ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20"
      : value === "pending"
        ? "bg-amber-50 text-amber-700 ring-amber-600/20"
        : value === "cancelled" || value === "failed"
          ? "bg-rose-50 text-rose-700 ring-rose-600/20"
          : "bg-gray-100 text-ink-muted ring-gray-500/20";
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ring-1 ring-inset ${tone}`}>
      {value}
    </span>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-surface rounded-control border border-line p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</p>
      <p className="text-2xl font-semibold text-ink mt-1 tabular-nums">{value}</p>
      {sub && <p className="text-xs text-ink-muted mt-0.5">{sub}</p>}
    </div>
  );
}

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [entry, setEntry] = useState("");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [payments, setPayments] = useState<PaymentRow[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (t: string) => {
    setLoading(true);
    setError("");
    try {
      const headers = { "X-Admin-Token": t };
      const [s, o, p] = await Promise.all([
        apiClient.get<Summary>("/api/v1/admin/summary", undefined, headers),
        apiClient.get<OrderRow[]>("/api/v1/admin/orders?limit=50", undefined, headers),
        apiClient.get<PaymentRow[]>("/api/v1/admin/payments?limit=50", undefined, headers),
      ]);
      setSummary(s);
      setOrders(o);
      setPayments(p);
      localStorage.setItem(TOKEN_KEY, t);
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : "Could not reach the server.";
      setError(detail);
      if (err instanceof ApiError && err.status === 401) {
        localStorage.removeItem(TOKEN_KEY);
        setToken("");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  /** Restore a saved token on first load and fetch straight away.
   *
   * localStorage is only readable in the browser, so this has to be an effect.
   * The state updates all happen after an await, because setting state
   * synchronously inside an effect triggers a cascading render. Everything
   * else is event driven: signing in and Refresh call `load` directly, so
   * this is the only effect that fetches. */
  useEffect(() => {
    const saved = localStorage.getItem(TOKEN_KEY);
    if (!saved) return;
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      setToken(saved);
      await load(saved);
    })();
    return () => { cancelled = true; };
  }, [load]);

  const signIn = async (value: string) => {
    const t = value.trim();
    if (!t) return;
    setToken(t);
    await load(t);
  };

  if (!token) {
    return (
      <main className="min-h-dvh flex items-center justify-center bg-surface-sunken p-6">
        <form
          onSubmit={(e) => { e.preventDefault(); void signIn(entry); }}
          className="w-full max-w-sm bg-surface rounded-card border border-line p-6"
        >
          <h1 className="text-lg font-semibold text-ink">Admin</h1>
          <p className="text-sm text-ink-muted mt-1 mb-4">Enter the admin token to continue.</p>
          <input
            type="password"
            value={entry}
            onChange={(e) => setEntry(e.target.value)}
            placeholder="Admin token"
            autoFocus
            className="w-full border border-line rounded-control px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
          />
          {error && <p className="text-rose-600 text-sm mt-2">{error}</p>}
          <button
            type="submit"
            className="w-full mt-4 py-2.5 bg-gray-900 hover:bg-gray-800 text-white rounded-control text-sm font-semibold transition-colors"
          >
            Sign in
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className="min-h-dvh bg-surface-sunken p-6">
      <div className="max-w-6xl mx-auto">
        <header className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold text-ink">Orders, payments and documents</h1>
            {summary && (
              <p className="text-sm text-ink-muted">
                Last {summary.window_days} days
                {summary.index?.rows ? ` · ${summary.index.rows.toLocaleString()} products indexed` : ""}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => load(token)}
              disabled={loading}
              className="px-3 py-2 text-sm font-medium border border-line rounded-control bg-surface hover:bg-surface-sunken disabled:opacity-60"
            >
              {loading ? "Refreshing…" : "Refresh"}
            </button>
            <button
              onClick={() => { localStorage.removeItem(TOKEN_KEY); setToken(""); setEntry(""); }}
              className="px-3 py-2 text-sm font-medium border border-line rounded-control bg-surface hover:bg-surface-sunken"
            >
              Sign out
            </button>
          </div>
        </header>

        {error && (
          <div className="mb-4 p-3 rounded-control bg-rose-50 text-rose-700 text-sm border border-rose-200">
            {error}
          </div>
        )}

        {summary && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <Stat
              label="Taken"
              value={money(summary.revenue.in_window)}
              sub={`${money(summary.revenue.all_time)} all time`}
            />
            <Stat
              label="Orders"
              value={String(summary.orders.in_window)}
              sub={`${summary.orders.total} all time`}
            />
            <Stat
              label="Awaiting payment"
              value={String(summary.orders.by_status?.pending ?? 0)}
              sub="not yet charged"
            />
            <Stat label="Customers" value={String(summary.customers)} sub="excludes partner enquiries" />
          </div>
        )}

        <div className="mb-6">
          <AiRuntime token={token} />
        </div>

        <div className="mb-6">
        </div>

        <div className="mb-6">
          <ParkingPasses token={token} />
        </div>

        <section className="bg-surface rounded-control border border-line overflow-hidden mb-6">
          <h2 className="px-4 py-3 text-sm font-semibold text-ink border-b border-line">
            Recent orders
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface-sunken text-ink-muted">
                <tr>
                  {["Order", "Customer", "Total", "Status", "Payment", "Delivery", "Placed"].map((h) => (
                    <th key={h} className="text-left font-medium px-4 py-2 whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id} className="border-t border-line">
                    <td className="px-4 py-2 font-medium tabular-nums">#{o.id}</td>
                    <td className="px-4 py-2">
                      <div className="text-ink">{o.customer_name ?? "—"}</div>
                      <div className="text-ink-muted text-xs">{o.customer_email}</div>
                    </td>
                    <td className="px-4 py-2 tabular-nums whitespace-nowrap">{money(o.total)}</td>
                    <td className="px-4 py-2"><StatusPill value={o.status} /></td>
                    <td className="px-4 py-2 text-xs whitespace-nowrap">
                      {/* A cash order reads "confirmed" like any other, so the
                          money still owed has to be said out loud here. */}
                      {o.payment_method === "cod" ? (
                        <span className="rounded-full bg-warn-soft px-2 py-0.5 font-semibold text-warn">
                          Cash to collect
                        </span>
                      ) : o.payments.length === 0 ? (
                        <span className="text-ink-muted">—</span>
                      ) : (
                        o.payments.map((p, i) => (
                          <div key={i} className="text-ink-muted">{p.provider} · {p.status}</div>
                        ))
                      )}
                    </td>
                    <td className="px-4 py-2 text-xs text-ink-muted whitespace-nowrap">
                      {o.delivery_date ?? "—"}{o.delivery_time ? ` · ${o.delivery_time}` : ""}
                    </td>
                    <td className="px-4 py-2 text-xs text-ink-muted whitespace-nowrap">{when(o.created_at)}</td>
                  </tr>
                ))}
                {orders.length === 0 && !loading && (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-ink-muted">No orders yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="bg-surface rounded-control border border-line overflow-hidden">
          <h2 className="px-4 py-3 text-sm font-semibold text-ink border-b border-line">
            Payment attempts
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface-sunken text-ink-muted">
                <tr>
                  {["Payment", "Order", "Provider", "Amount", "Status", "Reference", "When"].map((h) => (
                    <th key={h} className="text-left font-medium px-4 py-2 whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {payments.map((p) => (
                  <tr key={p.id} className="border-t border-line">
                    <td className="px-4 py-2 tabular-nums">#{p.id}</td>
                    <td className="px-4 py-2 tabular-nums">#{p.order_id}</td>
                    <td className="px-4 py-2 capitalize">{p.provider}</td>
                    <td className="px-4 py-2 tabular-nums whitespace-nowrap">{money(p.amount)} {p.currency}</td>
                    <td className="px-4 py-2"><StatusPill value={p.status} /></td>
                    <td className="px-4 py-2 font-mono text-xs text-ink-muted">{p.provider_ref}…</td>
                    <td className="px-4 py-2 text-xs text-ink-muted whitespace-nowrap">{when(p.created_at)}</td>
                  </tr>
                ))}
                {payments.length === 0 && !loading && (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-ink-muted">No payments yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  );
}
