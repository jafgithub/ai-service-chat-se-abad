import { test, describe, before } from "node:test";
import assert from "node:assert/strict";

/**
 * The flows, end to end, against a real backend.
 *
 * These exercise the same endpoints and the same request shapes the interface
 * uses, in the same order a person moves through it: describe, find a service,
 * find a provider, take a time, book, look at it, cancel. That is deliberately
 * the boundary being tested. The value is in catching a field the interface
 * reads and the server does not send, and that class of bug lives exactly here
 * rather than in a component.
 *
 * Run against dev:
 *
 *     API_URL=https://dev.agent.fordev.fun/plumber-api npm run test:flows
 *
 * Without API_URL they skip rather than fail, so `npm test` stays offline.
 *
 * They create real rows: two accounts with a timestamped email, one service
 * request, one booking, which is then cancelled. Nothing is deleted afterwards,
 * because the API offers no way to and inventing one for tests would be worse.
 * Point them at dev, never at anything a customer can see.
 */

const API = process.env.API_URL?.replace(/\/$/, "");
const stamp = Date.now();

const CUSTOMER = {
  name: "Flow Test Customer",
  email: `flow-customer-${stamp}@example.com`,
  password: "a-good-enough-password",
  phone: "07700 900000",
  address: "1 Test Street, Testville",
};

const PROVIDER = {
  business_name: `Flow Test Plumbing ${stamp}`,
  contact_name: "Flow Tester",
  email: `flow-provider-${stamp}@example.com`,
  password: "a-good-enough-password",
  phone: "07700 900001",
  city: "Testville",
  description: "Created by the Phase E flow tests.",
};

interface Call {
  status: number;
  body: any;
}

async function call(
  method: string,
  path: string,
  options: { token?: string; body?: unknown } = {}
): Promise<Call> {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  const text = await res.text();
  let body: any = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }
  return { status: res.status, body };
}

// Filled in by the first describe and used by the ones after it.
let customerToken = "";
let providerToken = "";
let serviceId = 0;
let providerId = 0;
let offerPrice = 0;
let offerDuration = 0;
let slotStart = "";
let requestId = 0;
let appointmentId = 0;

describe("signing up and signing in", { skip: !API && "set API_URL to run these" }, () => {
  test("a customer can create an account and is signed in straight away", async () => {
    const res = await call("POST", "/api/v1/auth/register/customer", { body: CUSTOMER });
    assert.equal(res.status, 201, JSON.stringify(res.body));
    assert.ok(res.body.token, "no token returned");
    assert.equal(res.body.role, "customer");
    assert.ok(res.body.customer_id, "no customer id, so nothing could be booked");
    customerToken = res.body.token;
  });

  test("the same email cannot register twice", async () => {
    const res = await call("POST", "/api/v1/auth/register/customer", { body: CUSTOMER });
    assert.equal(res.status, 409);
  });

  test("the token identifies the account", async () => {
    const res = await call("GET", "/api/v1/auth/me", { token: customerToken });
    assert.equal(res.status, 200);
    assert.equal(res.body.email, CUSTOMER.email.toLowerCase());
    assert.equal(res.body.role, "customer");
    assert.equal(res.body.name, CUSTOMER.name);
  });

  test("signing in returns a working token", async () => {
    const res = await call("POST", "/api/v1/auth/login", {
      body: { email: CUSTOMER.email, password: CUSTOMER.password },
    });
    assert.equal(res.status, 200);
    assert.ok(res.body.token);
    customerToken = res.body.token;
  });

  test("a wrong password is refused, and says nothing about the account", async () => {
    const res = await call("POST", "/api/v1/auth/login", {
      body: { email: CUSTOMER.email, password: "not the password" },
    });
    // 429 is also correct here: an earlier run may have used up the window.
    assert.ok([401, 429].includes(res.status), `got ${res.status}`);
  });

  test("a provider applies, and starts pending rather than bookable", async () => {
    const res = await call("POST", "/api/v1/auth/register/provider", { body: PROVIDER });
    assert.equal(res.status, 201, JSON.stringify(res.body));
    assert.equal(res.body.role, "provider");
    assert.equal(res.body.provider_status, "pending",
      "a new provider must not be live before the office approves them");
    providerToken = res.body.token;
    providerId = res.body.provider_id;
  });
});

describe("what needs doing", { skip: !API && "set API_URL to run these" }, () => {
  test("the catalogue carries the guide figures the cards show", async () => {
    const res = await call("GET", "/api/v1/services");
    assert.equal(res.status, 200);
    assert.ok(Array.isArray(res.body) && res.body.length > 0, "no services at all");

    const withDuration = res.body.find((s: any) => s.duration_minutes);
    assert.ok(withDuration, "no service carries a duration, so no card can show one");
    for (const field of ["id", "name", "category", "price_per_unit", "duration_minutes"]) {
      assert.ok(field in withDuration, `services are missing ${field}`);
    }
  });

  test("the assistant answers a problem with services", async () => {
    const res = await call("POST", "/api/v1/chat", {
      body: { message: "there is water leaking under my kitchen sink", session_id: `flow-${stamp}` },
    });
    assert.equal(res.status, 200);
    assert.ok(res.body.reply, "no reply text");
    assert.ok(Array.isArray(res.body.services), "the interface reads `services`");
    assert.ok(res.body.services.length > 0, "nothing matched a plain description of a leak");

    // The wording must not have slipped back into a shop.
    assert.ok(!/cart|checkout/i.test(res.body.reply),
      `the assistant is still talking like a shop: ${res.body.reply}`);
  });

  test("a customer's problem is recorded, in their own words", async () => {
    const res = await call("POST", "/api/v1/requests", {
      token: customerToken,
      body: {
        description: "Water leaking from the pipe under my kitchen sink.",
        urgency: "urgent",
      },
    });
    assert.equal(res.status, 201, JSON.stringify(res.body));
    assert.equal(res.body.description, "Water leaking from the pipe under my kitchen sink.");
    assert.equal(res.body.status, "open", "no service matched, so it is not resolved");
    requestId = res.body.id;
  });

  test("signing out is required to record one", async () => {
    const res = await call("POST", "/api/v1/requests", {
      body: { description: "Anonymous problem" },
    });
    assert.equal(res.status, 401);
  });
});

describe("finding somebody", { skip: !API && "set API_URL to run these" }, () => {
  before(async () => {
    // Whichever service actually has providers behind it. Picking the first
    // service in the catalogue would test an empty list as often as not.
    const services = (await call("GET", "/api/v1/services")).body as any[];
    for (const service of services.slice(0, 40)) {
      const found = await call("GET", `/api/v1/providers/for-service/${service.id}`);
      if (found.status === 200 && found.body.providers.length > 0) {
        serviceId = service.id;
        return;
      }
    }
  });

  test("providers are returned with their own price and duration", async () => {
    assert.ok(serviceId, "no service on the platform has an approved provider");
    const res = await call("GET", `/api/v1/providers/for-service/${serviceId}`);
    assert.equal(res.status, 200);
    assert.ok(res.body.ranked_by, "the interface says why the order is what it is");

    const offer = res.body.providers[0];
    for (const field of [
      "provider_id", "business_name", "price", "duration_minutes",
      "provider_service_id", "next_available", "next_available_label",
    ]) {
      assert.ok(field in offer, `provider offers are missing ${field}`);
    }
    providerId = offer.provider_id;
    offerPrice = offer.price;
    offerDuration = offer.duration_minutes;
  });

  test("the pending provider we just created is not among them", async () => {
    const res = await call("GET", `/api/v1/providers/for-service/${serviceId}`);
    const names = res.body.providers.map((p: any) => p.business_name);
    assert.ok(!names.includes(PROVIDER.business_name),
      "a provider nobody has approved is being offered to customers");
  });

  test("a public profile can be read without an account", async () => {
    const res = await call("GET", `/api/v1/providers/${providerId}`);
    assert.equal(res.status, 200);
    assert.ok(res.body.business_name);
    assert.ok(Array.isArray(res.body.services));
  });

  test("real times come back, and they are naive", async () => {
    const res = await call("GET",
      `/api/v1/providers/${providerId}/availability?service_id=${serviceId}`);
    assert.equal(res.status, 200);
    assert.ok(res.body.slots.length > 0, "no free times at all");

    const slot = res.body.slots[0];
    assert.match(slot.starts_at, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/);
    assert.ok(!/Z|[+-]\d{2}:\d{2}$/.test(slot.starts_at),
      "the interface formats these as wall clock, so an offset would be misread");
    slotStart = slot.starts_at;
  });

  test("asking a provider for something they do not offer is a 404", async () => {
    const res = await call("GET",
      `/api/v1/providers/${providerId}/availability?service_id=999999999`);
    assert.equal(res.status, 404);
  });
});

describe("booking it", { skip: !API && "set API_URL to run these" }, () => {
  test("a booking needs an account", async () => {
    const res = await call("POST", "/api/v1/booking/book", {
      body: { provider_id: providerId, service_id: serviceId, starts_at: slotStart },
    });
    assert.equal(res.status, 401);
  });

  test("one call books it, and answers with everything the confirmation shows", async () => {
    const res = await call("POST", "/api/v1/booking/book", {
      token: customerToken,
      body: {
        provider_id: providerId,
        service_id: serviceId,
        starts_at: slotStart,
        address: "1 Test Street, Testville",
        notes: "Created by the Phase E flow tests.",
        service_request_id: requestId,
      },
    });
    assert.equal(res.status, 200, JSON.stringify(res.body));

    // Every one of these is drawn on the confirmation screen. A rename here is
    // a blank line there, with nothing to say it is missing.
    for (const field of [
      "job_id", "appointment_id", "reference",
      "provider_id", "provider_name",
      "service_id", "service_name",
      "starts_at", "ends_at", "duration_minutes", "label",
      "price", "currency", "payment_status",
      "customer_id", "customer_name", "status",
    ]) {
      assert.ok(field in res.body, `the booking response is missing ${field}`);
    }

    assert.match(res.body.reference, /^BK-\d+$/);
    assert.equal(res.body.price, offerPrice, "the price charged is not the price shown");
    assert.equal(res.body.duration_minutes, offerDuration);
    assert.equal(res.body.payment_status, "unpaid",
      "nothing has been paid, and the screen must not say otherwise");
    assert.equal(res.body.service_request_id, requestId);

    appointmentId = res.body.appointment_id;
  });

  test("the same time cannot be booked twice", async () => {
    const res = await call("POST", "/api/v1/booking/book", {
      token: customerToken,
      body: { provider_id: providerId, service_id: serviceId, starts_at: slotStart },
    });
    assert.equal(res.status, 409, "a taken slot was handed out again");
  });

  test("the request now says it became a booking", async () => {
    const res = await call("GET", `/api/v1/requests/${requestId}`, { token: customerToken });
    assert.equal(res.status, 200);
    assert.equal(res.body.status, "booked");
    assert.ok(res.body.job_id);
  });
});

describe("looking after it", { skip: !API && "set API_URL to run these" }, () => {
  test("it appears under upcoming, with what the list draws", async () => {
    const res = await call("GET", "/api/v1/booking/mine?when=upcoming", { token: customerToken });
    assert.equal(res.status, 200);
    const mine = res.body.find((b: any) => b.appointment_id === appointmentId);
    assert.ok(mine, "the booking just made is not in the customer's own list");
    for (const field of ["reference", "status", "starts_at", "ends_at", "provider_name",
                         "service", "price", "currency", "payment_status"]) {
      assert.ok(field in mine, `my bookings is missing ${field}`);
    }
  });

  test("somebody else's bookings are not visible", async () => {
    const other = await call("POST", "/api/v1/auth/register/customer", {
      body: { ...CUSTOMER, email: `flow-other-${stamp}@example.com` },
    });
    const res = await call("GET", "/api/v1/booking/mine", { token: other.body.token });
    assert.equal(res.status, 200);
    assert.equal(res.body.length, 0, "a new account can see somebody else's bookings");

    // And cannot reach into one by its id.
    const reach = await call("POST", `/api/v1/booking/${appointmentId}/cancel`,
      { token: other.body.token });
    assert.equal(reach.status, 404, "one customer could cancel another's appointment");
  });

  test("the customer can cancel their own", async () => {
    const res = await call("POST", `/api/v1/booking/${appointmentId}/cancel`,
      { token: customerToken });
    assert.equal(res.status, 200);
    assert.equal(res.body.status, "cancelled");
  });

  test("cancelling twice is not an error", async () => {
    const res = await call("POST", `/api/v1/booking/${appointmentId}/cancel`,
      { token: customerToken });
    assert.equal(res.status, 200);
    assert.equal(res.body.status, "cancelled");
  });

  test("it moves to the cancelled tab", async () => {
    const res = await call("GET", "/api/v1/booking/mine?when=cancelled", { token: customerToken });
    assert.ok(res.body.some((b: any) => b.appointment_id === appointmentId));
  });
});

describe("a provider running their business", { skip: !API && "set API_URL to run these" }, () => {
  test("a pending provider can still read and edit their own details", async () => {
    const read = await call("GET", "/api/v1/providers/me/profile", { token: providerToken });
    assert.equal(read.status, 200);
    assert.equal(read.body.status, "pending");

    const write = await call("PATCH", "/api/v1/providers/me/profile", {
      token: providerToken,
      body: { description: "Edited by the flow tests." },
    });
    assert.equal(write.status, 200);
  });

  test("a provider cannot approve themselves", async () => {
    await call("PATCH", "/api/v1/providers/me/profile", {
      token: providerToken,
      body: { status: "active" },
    });
    const after = await call("GET", "/api/v1/providers/me/profile", { token: providerToken });
    assert.equal(after.body.status, "pending", "approval is decorative if this passes");
  });

  test("they can list a service on their own terms", async () => {
    const saved = await call("PUT", "/api/v1/providers/me/services", {
      token: providerToken,
      body: { service_id: serviceId, price: 123.45, duration_minutes: 45, active: true },
    });
    assert.equal(saved.status, 200);

    const mine = await call("GET", "/api/v1/providers/me/services", { token: providerToken });
    const row = mine.body.find((r: any) => r.service_id === serviceId);
    assert.ok(row, "the service just added is not listed");
    assert.equal(row.price, 123.45);
    assert.equal(row.duration_minutes, 45);
    assert.ok("guide_price" in row, "the dashboard shows the guide beside their own");
  });

  test("withdrawing deactivates rather than deletes", async () => {
    const mine = await call("GET", "/api/v1/providers/me/services", { token: providerToken });
    const row = mine.body.find((r: any) => r.service_id === serviceId);

    const gone = await call("DELETE",
      `/api/v1/providers/me/services/${row.provider_service_id}`, { token: providerToken });
    assert.equal(gone.status, 200);

    const after = await call("GET", "/api/v1/providers/me/services", { token: providerToken });
    const stillThere = after.body.find((r: any) => r.service_id === serviceId);
    assert.ok(stillThere, "the row was deleted, so past bookings lost their terms");
    assert.equal(stillThere.active, false);
  });

  test("they can set and clear a working day", async () => {
    const saved = await call("PUT", "/api/v1/providers/me/availability", {
      token: providerToken,
      body: { weekday: 0, opens_at: "09:00:00", closes_at: "17:00:00" },
    });
    assert.equal(saved.status, 200);

    const week = await call("GET", "/api/v1/providers/me/availability", { token: providerToken });
    assert.ok(week.body.some((d: any) => d.weekday === 0));

    const closed = await call("DELETE", "/api/v1/providers/me/availability/0",
      { token: providerToken });
    assert.equal(closed.status, 200);

    const after = await call("GET", "/api/v1/providers/me/availability", { token: providerToken });
    assert.ok(!after.body.some((d: any) => d.weekday === 0), "no row for a day means closed");
  });

  test("closing before opening is refused", async () => {
    const res = await call("PUT", "/api/v1/providers/me/availability", {
      token: providerToken,
      body: { weekday: 1, opens_at: "17:00:00", closes_at: "09:00:00" },
    });
    assert.equal(res.status, 400);
  });

  test("their diary is their own", async () => {
    const res = await call("GET", "/api/v1/providers/me/appointments?upcoming_only=true",
      { token: providerToken });
    assert.equal(res.status, 200);
    assert.ok(Array.isArray(res.body));
  });

  test("a customer cannot reach the provider endpoints", async () => {
    const res = await call("GET", "/api/v1/providers/me/profile", { token: customerToken });
    assert.equal(res.status, 403, "signing in as the wrong sort of person must be a 403");
  });

  test("signing out ends the session", async () => {
    const out = await call("POST", "/api/v1/auth/logout", { token: providerToken });
    assert.equal(out.status, 200);

    const after = await call("GET", "/api/v1/providers/me/profile", { token: providerToken });
    assert.equal(after.status, 401, "a revoked token still works");
  });
});
