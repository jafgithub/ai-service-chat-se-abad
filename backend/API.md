# API reference

Base path `/api/v1`. On dev the browser reaches it at
`https://dev.agent.fordev.fun/plumber-api/api/v1`, which nginx forwards to the
service in Oregon.

FastAPI publishes the same thing as OpenAPI at `/openapi.json`, which is the
authority on exact field types. This file exists for the questions OpenAPI does
not answer: which endpoints need a token, which need which role, and what goes
wrong in practice.

## Authenticating

Send `Authorization: Bearer <token>` from `/auth/login` or either registration.
Tokens last 30 days and can be revoked; the server stores only a hash of them.

Admin is separate and unchanged: `X-Admin-Token: <ADMIN_TOKEN>`. An account with
the admin role also works, so both routes in are supported.

Three answers mean three different things and the interface should treat them
differently:

| | |
|---|---|
| **401** | Not signed in, or the token has expired or been revoked. Sign in again. |
| **403** | Signed in as the wrong sort of person. Signing in again will not help. |
| **404** | Either it does not exist or it is not yours. Deliberately the same, so ids cannot be probed. |

## Signing in

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/auth/register/customer` | none | 201. `{name, email, password, phone?, address?}`. An email that has booked before is linked to that customer rather than duplicated. **409** if an account exists. |
| POST | `/auth/register/provider` | none | 201. Business details plus optional `services: [{service_id, price?, duration_minutes?}]`. Starts **pending**. An unknown `service_id` is skipped, not fatal. |
| POST | `/auth/login` | none | `{email, password}`. **401** for wrong password *and* unknown email, identically. **429** with `Retry-After` after 8 failures for an email or 20 for an address in 15 minutes. |
| POST | `/auth/logout` | bearer | Idempotent. |
| GET | `/auth/me` | bearer | Account, role, and the linked customer or provider. |
| GET | `/auth/session` | optional | `{signed_in, role}` without a 401 in the console. |

Registration and login return `{token, role, name, customer_id?, provider_id?, provider_status?}`.

## Finding a provider

Open, so somebody can see who can help before making an account.

| Method | Path | Notes |
|---|---|---|
| GET | `/providers/for-service/{service_id}` | Approved providers who offer it, ranked. Returns `ranked_by` so the interface can say why the order is what it is. |
| GET | `/providers/{id}` | One provider and their services. **404** when pending, same as missing. |
| GET | `/providers/{id}/availability?service_id=&days_ahead=` | Real slots. **404** if they do not offer that service; **503** if the diary itself failed, which is not the same as being fully booked. |

Each provider in the list carries `provider_id, business_name, description,
website, phone, city, price, duration_minutes, provider_service_id,
next_available, next_available_label`.

`price` and `duration_minutes` are **that provider's**, not the service's guide
figures. Two providers offering one service will differ, and that is the point.

Ranking is `PROVIDER_RANKING`: `soonest` (default; then cheapest), `price`, or
`distance`/`rating`, which are named but fall back to `soonest` because neither
has data behind it yet.

## Describing the problem

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/requests` | customer | 201. `{description, service_id?, address?, postcode?, urgency?, session_id?}`. Status is `matched` with a service and `open` without. |
| GET | `/requests` | customer | Only the caller's own. |
| GET | `/requests/{id}` | customer | **404** if it is somebody else's. |
| POST | `/requests/{id}/close` | customer | **409** once it has become a booking; cancel the booking instead. |
| GET | `/requests/admin/unserved` | admin | What people asked for that nobody could do. |

A request is not the conversation. The transcript stays where it is; this stores
the problem, what it matched, and what became of it.

## Booking

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/booking/book` | customer | `{provider_id, service_id, starts_at, address?, notes?, service_request_id?}`. **409** for a taken slot, a pending provider, or a provider who does not offer the service. **404** for an unknown provider or service. |
| GET | `/booking/mine?when=all\|upcoming\|past\|cancelled` | customer | Only the caller's own. |
| POST | `/booking/{appointment_id}/cancel` | customer | Idempotent. **404** if it is not theirs. |

The customer is taken from the token and never from the body, so a booking
cannot be made in somebody else's name.

`POST /booking/book` returns everything a confirmation screen needs, so it
should not need a second request:

```
job_id, appointment_id, reference ("BK-00006"),
provider_id, provider_name, provider_phone, provider_website,
service_id, service_name,
starts_at, ends_at, duration_minutes, label,
price, currency, payment_status,
customer_id, customer_name, customer_email, address, notes,
status, service_request_id
```

`payment_status` is always `"unpaid"` until payments move into this flow. It is
carried now so the screen written against this response does not change shape
later. It is never invented: a booking that has not been paid for must not read
as though it has.

## A provider managing themselves

Every one of these reads the provider from the token. There is no id to change.

| Method | Path | Notes |
|---|---|---|
| GET / PATCH | `/providers/me/profile` | `status` is not editable; a provider approving itself would make approval decorative. |
| GET | `/providers/me/services` | Their terms, and the guide figures for comparison. |
| PUT | `/providers/me/services` | `{service_id, price?, duration_minutes?, notes?, active?}`. Adds or edits. |
| DELETE | `/providers/me/services/{id}` | Deactivates, so past bookings keep the terms they were made under. **404** for another firm's row. |
| GET / PUT | `/providers/me/availability` | `{weekday (0 = Monday), opens_at, closes_at}`. |
| DELETE | `/providers/me/availability/{weekday}` | No row means closed. |
| POST | `/providers/me/time-off` | `{starts_at, ends_at, reason?}`. |
| GET | `/providers/me/appointments?upcoming_only=` | Their own diary only. |

Pending providers may use all of these. What approval gates is being offered to
customers.

## The office

| Method | Path | Notes |
|---|---|---|
| GET | `/providers/?status=` | Everybody, including pending. |
| POST | `/providers/{id}/approve?new_status=active\|suspended\|rejected\|pending` | |
| GET | `/admin/summary`, `/admin/jobs`, `/admin/payments` | As before. |

## Still there from the shop

`/chat`, `/voice`, `/services`, `/media/{id}`, `/payments/*` are unchanged and
still work. `/cart` and `/jobs` exist and are **not** part of the booking flow;
they are the shop's checkout and will be removed or repurposed when payments
move across.

## Times

Every datetime in and out is **naive UTC**, ISO 8601, with no offset. The
interface should format for the reader's timezone and send back UTC.

Worth knowing, because it caused three bugs: MySQL returns `TIME` as a
`timedelta` and `DATETIME` as a `datetime`; SQLite returns both as strings. The
diary converts explicitly rather than trusting the driver, and anything reading
those columns directly should do the same.
