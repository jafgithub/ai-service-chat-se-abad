/**
 * The one piece of state that has to survive leaving the site.
 *
 * Paying means a full navigation to Stripe or PayPal and back, so every bit of
 * React state is gone by the time the shopper returns. The provider sends them
 * to `/chat?paid={order_id}`, which is not enough on its own: the id alone
 * cannot be used to fetch the order without letting anyone read any order by
 * counting upwards.
 *
 * So before redirecting we keep the idempotency key here. It is a UUID the
 * browser generated for that checkout, it is not personal data, and it is what
 * `GET /orders/by-key/{key}` accepts. On return we can show the shopper exactly
 * what they bought, and nobody else can.
 */

const KEY = "pending_order";

export interface PendingOrder {
  orderId: number;
  idempotencyKey: string;
  /** ms epoch, so a key left behind by an abandoned payment can be aged out. */
  startedAt: number;
}

/** Abandoned checkouts should not haunt a session forever. */
const MAX_AGE_MS = 6 * 60 * 60 * 1000; // 6 hours

export function rememberPendingOrder(orderId: number, idempotencyKey: string): void {
  try {
    const value: PendingOrder = { orderId, idempotencyKey, startedAt: Date.now() };
    localStorage.setItem(KEY, JSON.stringify(value));
  } catch {
    // Private mode or a full quota. The return trip falls back to showing the
    // order number on its own, which is degraded but not broken.
  }
}

export function readPendingOrder(): PendingOrder | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as PendingOrder;
    if (
      typeof value?.orderId !== "number" ||
      typeof value?.idempotencyKey !== "string" ||
      !value.idempotencyKey
    ) {
      return null;
    }
    if (Date.now() - (value.startedAt ?? 0) > MAX_AGE_MS) {
      clearPendingOrder();
      return null;
    }
    return value;
  } catch {
    return null;
  }
}

export function clearPendingOrder(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* nothing worth doing */
  }
}
