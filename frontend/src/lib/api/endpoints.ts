import { apiClient } from "./client";
import type {
  Account,
  Availability,
  Booked,
  BookIn,
  BookingSummary,
  ChatRequest,
  ChatResponse,
  CustomerRegisterIn,
  Discovery,
  MyServiceRow,
  ProviderAppointment,
  ProviderDetail,
  ProviderProfile,
  ProviderRegisterIn,
  Service,
  ServiceRequest,
  ServiceRequestIn,
  TokenOut,
  VoiceResponse,
  WorkingDay,
} from "./types";

export const chatApi = {
  send: (payload: ChatRequest, signal?: AbortSignal) =>
    apiClient.post<ChatResponse>("/api/v1/chat", payload, signal),
};

export const voiceApi = {
  send: (
    audio: Blob,
    opts: { sessionId: string; categoryFilter?: string; latitude?: number; longitude?: number },
    signal?: AbortSignal
  ) => {
    const form = new FormData();
    // Name the part after what the browser actually produced: Chrome and Firefox
    // record WebM, Safari records MP4. The server transcodes either way, but an
    // honest filename makes a bad recording obvious in the logs.
    const ext = audio.type.includes("mp4") ? "mp4" : "webm";
    form.append("file", audio, `audio.${ext}`);
    form.append("session_id", opts.sessionId);
    if (opts.categoryFilter) form.append("category_filter", opts.categoryFilter);
    if (opts.latitude != null) form.append("latitude", String(opts.latitude));
    if (opts.longitude != null) form.append("longitude", String(opts.longitude));
    return apiClient.postForm<VoiceResponse>("/api/v1/voice", form, signal);
  },
};

// ── signing in ───────────────────────────────────────────────────────────────

export const authApi = {
  registerCustomer: (payload: CustomerRegisterIn, signal?: AbortSignal) =>
    apiClient.postAnonymous<TokenOut>("/api/v1/auth/register/customer", payload, signal),

  registerProvider: (payload: ProviderRegisterIn, signal?: AbortSignal) =>
    apiClient.postAnonymous<TokenOut>("/api/v1/auth/register/provider", payload, signal),

  login: (email: string, password: string, signal?: AbortSignal) =>
    apiClient.postAnonymous<TokenOut>("/api/v1/auth/login", { email, password }, signal),

  logout: (signal?: AbortSignal) =>
    apiClient.post<{ status: string }>("/api/v1/auth/logout", {}, signal),

  me: (signal?: AbortSignal) => apiClient.get<Account>("/api/v1/auth/me", signal),
};

// ── finding somebody who can do it ───────────────────────────────────────────

export const providersApi = {
  /** Open: choosing who to call should not need an account. */
  forService: (serviceId: number, signal?: AbortSignal) =>
    apiClient.get<Discovery>(`/api/v1/providers/for-service/${serviceId}`, signal),

  detail: (providerId: number, signal?: AbortSignal) =>
    apiClient.get<ProviderDetail>(`/api/v1/providers/${providerId}`, signal),

  /** The backend is the source of truth for what is free. Nothing about
   *  availability is worked out in the browser. */
  availability: (providerId: number, serviceId: number, daysAhead?: number, signal?: AbortSignal) =>
    apiClient.get<Availability>(
      `/api/v1/providers/${providerId}/availability?service_id=${serviceId}` +
        (daysAhead ? `&days_ahead=${daysAhead}` : ""),
      signal
    ),
};

// ── the customer's own things ────────────────────────────────────────────────

export const requestsApi = {
  create: (payload: ServiceRequestIn, signal?: AbortSignal) =>
    apiClient.post<ServiceRequest>("/api/v1/requests", payload, signal),

  mine: (signal?: AbortSignal) =>
    apiClient.get<ServiceRequest[]>("/api/v1/requests", signal),

  close: (id: number, outcomeNote = "", signal?: AbortSignal) =>
    apiClient.post<ServiceRequest>(`/api/v1/requests/${id}/close`,
      { outcome_note: outcomeNote }, signal),
};

export const bookingApi = {
  book: (payload: BookIn, signal?: AbortSignal) =>
    apiClient.post<Booked>("/api/v1/booking/book", payload, signal),

  mine: (when: "all" | "upcoming" | "past" | "cancelled" = "all", signal?: AbortSignal) =>
    apiClient.get<BookingSummary[]>(`/api/v1/booking/mine?when=${when}`, signal),

  cancel: (appointmentId: number, signal?: AbortSignal) =>
    apiClient.post<{ status: string; reference: string }>(
      `/api/v1/booking/${appointmentId}/cancel`, {}, signal),
};

// ── a provider running their own business ────────────────────────────────────
// Every one of these reads the provider from the token, so none of them takes
// an id. There is nothing here for one business to point at another's.

export const providerMeApi = {
  profile: (signal?: AbortSignal) =>
    apiClient.get<ProviderProfile>("/api/v1/providers/me/profile", signal),

  saveProfile: (payload: Partial<ProviderProfile>, signal?: AbortSignal) =>
    apiClient.patch<{ status: string; provider_status: string }>(
      "/api/v1/providers/me/profile", payload, signal),

  services: (signal?: AbortSignal) =>
    apiClient.get<MyServiceRow[]>("/api/v1/providers/me/services", signal),

  saveService: (
    payload: { service_id: number; price?: number | null; duration_minutes?: number | null; notes?: string | null; active?: boolean },
    signal?: AbortSignal
  ) =>
    apiClient.put<{ provider_service_id: number; status: string }>(
      "/api/v1/providers/me/services", payload, signal),

  withdrawService: (providerServiceId: number, signal?: AbortSignal) =>
    apiClient.del<{ status: string }>(
      `/api/v1/providers/me/services/${providerServiceId}`, signal),

  hours: (signal?: AbortSignal) =>
    apiClient.get<WorkingDay[]>("/api/v1/providers/me/availability", signal),

  saveHours: (weekday: number, opensAt: string, closesAt: string, signal?: AbortSignal) =>
    apiClient.put<{ status: string }>("/api/v1/providers/me/availability",
      { weekday, opens_at: opensAt, closes_at: closesAt }, signal),

  closeDay: (weekday: number, signal?: AbortSignal) =>
    apiClient.del<{ status: string }>(
      `/api/v1/providers/me/availability/${weekday}`, signal),

  addTimeOff: (startsAt: string, endsAt: string, reason: string, signal?: AbortSignal) =>
    apiClient.post<{ id: number; status: string }>("/api/v1/providers/me/time-off",
      { starts_at: startsAt, ends_at: endsAt, reason: reason || null }, signal),

  appointments: (upcomingOnly: boolean, signal?: AbortSignal) =>
    apiClient.get<ProviderAppointment[]>(
      `/api/v1/providers/me/appointments?upcoming_only=${upcomingOnly}`, signal),
};

// ── the catalogue of services ────────────────────────────────────────────────

export const servicesApi = {
  /** Everything the platform knows how to book. Used by provider registration,
   *  where a business ticks what it does. */
  list: (category?: string, signal?: AbortSignal) => {
    const path = category
      ? `/api/v1/services?category=${encodeURIComponent(category)}`
      : "/api/v1/services";
    return apiClient.get<Service[]>(path, signal);
  },
};

/**
 * Payments.
 *
 * The same two endpoints the shop uses, against the same provider code. A
 * booking creates a job, and `order_id` here is that job's id, which is why
 * nothing had to be written twice.
 *
 * There is no "mark as paid" call and there must never be one. The customer
 * returning to a success page proves only that they returned to a success page;
 * the provider's webhook is the only thing that may change a payment status.
 */
export const paymentsApi = {
  /** Which methods the server can actually take right now. */
  list: (signal?: AbortSignal) =>
    apiClient.get<{ enabled: boolean; providers: string[] }>(
      "/api/v1/payments/providers", signal),

  /** Start a checkout and get the provider's own page to send the browser to. */
  checkout: (
    jobId: number,
    provider: string,
    successUrl: string,
    cancelUrl: string,
    signal?: AbortSignal
  ) =>
    apiClient.post<{ url: string; provider: string; provider_ref: string }>(
      "/api/v1/payments/checkout",
      { order_id: jobId, provider, success_url: successUrl, cancel_url: cancelUrl },
      signal
    ),
};
