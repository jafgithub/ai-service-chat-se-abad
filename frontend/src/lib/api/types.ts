import type { RequestTrace } from "@/components/chat/RequestJourney";

// The shapes the backend actually returns. Every one of these was read off
// `backend/API.md` and the endpoint that serves it, not guessed: a field name
// invented here becomes a blank space on screen with nothing to say it is wrong.

export interface ChatRequest {
  message: string;
  session_id?: string;
  category_filter?: string;
  latitude?: number;
  longitude?: number;
  /** Which association the resident belongs to, so a rules answer comes from
   *  their own documents rather than the home community's. */
  community?: string;
  /** Only when they answered "community or a service?" with a button. */
  route?: "documents" | "services";
}

/** One service the assistant matched. Not the booking target: price and
 *  duration below are the service's guide figures, and the provider's own
 *  replace them the moment one is chosen. */
export interface ServiceResult {
  id: number;
  name: string;
  category: string;
  description: string | null;
  unit: string;
  price_per_unit: number;
  stock: number;
  image_url: string | null;
  /** Roughly how long a visit takes. Null when the service does not say. */
  duration_minutes?: number | null;
  /** Attended out of hours. */
  emergency?: boolean;
  similarity: number;
}

/** What the assistant did, so the interface can follow. `added` means the
 *  customer chose a service ("book item 2"), which is the cue to go and find
 *  providers for it. */
export interface ChatAction {
  /** `parking` opens the pass form; `documents` means the files are in
   *  `documents` on the response and there is nothing else to do. */
  type: "added" | "removed" | "quantity" | "checkout" | "parking" | "documents"
      | "clarify" | "pick_community" | "documents_miss";
  items?: { item_id: number; name: string; quantity?: number }[];
  /** `clarify` and `pick_community`: the question to ask again once they have
   *  said which way they meant it, or where they live. */
  question?: string;
  /** `pick_community` only: the communities worth offering, which is the ones
   *  that actually hold documents. */
  options?: { key: string; label: string }[];
  /** `documents_miss` only: whose documents were searched and came up empty. */
  community?: string;
}

/** A document the assistant found by name, ready to download.
 *
 *  Not a `ServiceResult`: nothing here is bookable, priced or scored against
 *  the catalogue, and drawing one as a service card would be offering to send
 *  somebody a tradesperson called "Site map". */
export interface DocumentResult {
  id: string;
  title: string;
  community: string;
  /** False for a scan: the file downloads, the assistant cannot quote it. */
  answerable: boolean;
  /** The section the answer leant on, when this document was cited rather than
   *  asked for by name. "Rules and Regulations" is 55 sections long, so without
   *  this a resident opens the PDF and starts reading page one. */
  section?: string;
  download_url: string;
  /** The same file served inline, for reading in a tab rather than saving. */
  view_url?: string;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  speech?: string;
  services: ServiceResult[];
  total_services?: number;
  documents: DocumentResult[];
  /** Everything the resident's association holds, sent with any reply that is
   *  about that association. The panel is drawn from this rather than fetched
   *  separately, so it can never disagree with the answer beside it. */
  shelf: DocumentResult[];
  action: ChatAction | null;
  intent?: string | null;
  /** The journey: stages, timings, and which engine wrote the reply. */
  trace?: RequestTrace;
}

export interface VoiceResponse {
  session_id: string;
  transcript: string;
  reply: string;
  speech: string;
  /** base64 audio data URL; empty when the browser should speak instead. */
  audio: string;
  services: ServiceResult[];
  total_services?: number;
  documents?: DocumentResult[];
  shelf?: DocumentResult[];
  action: ChatAction | null;
  intent?: string | null;
  /** The journey: stages, timings, and which engine wrote the reply. */
  trace?: RequestTrace;
}

// ── who is signed in ─────────────────────────────────────────────────────────

export type Role = "customer" | "provider" | "admin";

/** Returned by both registrations and by login. Carries enough for the
 *  interface to know where to send somebody without a second call. */
export interface TokenOut {
  token: string;
  role: Role;
  name: string;
  customer_id?: number | null;
  provider_id?: number | null;
  provider_status?: string | null;
}

export interface Account {
  account_id: number;
  email: string;
  role: Role;
  name: string;
  customer_id?: number | null;
  provider_id?: number | null;
  /** pending | active | suspended | rejected. Only providers have one. */
  provider_status?: string | null;
}

export interface CustomerRegisterIn {
  name: string;
  email: string;
  password: string;
  phone?: string;
  address?: string;
}

export interface ProviderRegisterIn {
  business_name: string;
  contact_name?: string;
  email: string;
  password: string;
  phone?: string;
  website?: string;
  description?: string;
  address?: string;
  city?: string;
  postcode?: string;
  services?: { service_id: number; price?: number | null; duration_minutes?: number | null }[];
}

// ── finding somebody ─────────────────────────────────────────────────────────

/** One provider's offer of one service. `price` and `duration_minutes` are
 *  theirs, which is the whole reason the booking target is a provider and a
 *  service together rather than a service on its own. */
export interface ProviderOffer {
  provider_id: number;
  business_name: string;
  description?: string | null;
  website?: string | null;
  phone?: string | null;
  city?: string | null;
  price: number;
  duration_minutes: number;
  provider_service_id: number;
  next_available?: string | null;
  next_available_label?: string | null;
}

export interface Discovery {
  service_id: number;
  service_name: string;
  /** How the list is ordered. Shown to the customer so the order is explained
   *  rather than mysterious. The backend decides it; nothing re-sorts here. */
  ranked_by: string;
  providers: ProviderOffer[];
}

export interface ProviderServiceRow {
  provider_service_id: number;
  service_id: number;
  name: string;
  price: number;
  duration_minutes: number;
  notes?: string | null;
}

export interface ProviderDetail {
  id: number;
  business_name: string;
  contact_name?: string | null;
  description?: string | null;
  website?: string | null;
  phone?: string | null;
  email?: string | null;
  city?: string | null;
  postcode?: string | null;
  status: string;
  services: ProviderServiceRow[];
}

export interface Slot {
  /** Naive UTC, no offset. Formatted for the reader by lib/datetime. */
  starts_at: string;
  ends_at: string;
  label: string;
}

export interface Availability {
  provider_id: number;
  service_id: number;
  duration_minutes: number;
  slots: Slot[];
}

// ── the problem, and the booking ─────────────────────────────────────────────

export type Urgency = "whenever" | "this_week" | "urgent";

export interface ServiceRequestIn {
  description: string;
  service_id?: number | null;
  address?: string;
  postcode?: string;
  urgency?: Urgency;
  session_id?: string;
}

export interface ServiceRequest {
  id: number;
  description: string;
  status: string;
  urgency: string;
  address?: string | null;
  postcode?: string | null;
  service_id?: number | null;
  service_name?: string | null;
  provider_id?: number | null;
  provider_name?: string | null;
  job_id?: number | null;
  created_at: string;
}

/** Cash is settled with the provider on the day. The other two send the
 *  customer to that provider's own page, and the booking is held meanwhile. */
export type PaymentMethod = "cod" | "stripe" | "paypal";

export interface BookIn {
  provider_id: number;
  service_id: number;
  starts_at: string;
  address?: string;
  notes?: string;
  service_request_id?: number | null;
  payment_method?: PaymentMethod;
  /** One of the offered percentages. The server works the money out from it. */
  tip_percent?: number | null;
  /** Only when they typed their own. Ignored if a percentage is sent too. */
  tip_amount?: number | null;
}

/** Everything the confirmation screen needs, so it makes no second call.
 *  `payment_status` is "unpaid" until Phase G and is never inferred. */
export interface Booked {
  job_id: number;
  appointment_id: number;
  reference: string;

  provider_id: number;
  provider_name: string;
  provider_phone?: string | null;
  provider_website?: string | null;

  service_id: number;
  service_name: string;

  starts_at: string;
  ends_at: string;
  duration_minutes: number;
  label: string;

  /** The provider's price for the work, before any tip. */
  price: number;
  /** What was added for the provider, and what the customer actually pays. */
  tip: number;
  total: number;
  currency: string;
  payment_method: string;
  /** "cod", "unpaid" or "paid". Only the payment provider's webhook may make
   *  it "paid": coming back to a success page proves nothing. */
  payment_status: string;
  /** True when the customer still has to be sent to a payment page. */
  payment_due: boolean;

  customer_id: number;
  customer_name: string;
  customer_email?: string | null;
  address?: string | null;
  notes?: string | null;

  status: string;
  service_request_id?: number | null;
}

export interface BookingSummary {
  reference: string;
  appointment_id: number;
  job_id: number;
  status: string;
  starts_at: string;
  ends_at: string;
  label: string;
  provider_name?: string | null;
  provider_phone?: string | null;
  provider_website?: string | null;
  service?: string | null;
  /** The work, before any tip. `total` is what is owed or was paid. */
  price: number;
  tip: number;
  total: number;
  currency: string;
  address?: string | null;
  notes?: string | null;
  payment_method?: string;
  payment_status: string;
}

// ── a provider running their own business ────────────────────────────────────

export interface ProviderProfile {
  id: number;
  business_name: string;
  contact_name?: string | null;
  email?: string | null;
  phone?: string | null;
  website?: string | null;
  description?: string | null;
  address?: string | null;
  city?: string | null;
  postcode?: string | null;
  travel_radius_miles?: number | null;
  requires_approval?: boolean | null;
  status: string;
}

/** What a provider offers. `price` and `duration_minutes` are null when they
 *  have not set their own, in which case the guide figures apply and are shown
 *  beside them so the difference is visible. */
export interface MyServiceRow {
  provider_service_id: number;
  service_id: number;
  name: string;
  price: number | null;
  duration_minutes: number | null;
  guide_price: number;
  guide_duration: number | null;
  notes?: string | null;
  active: boolean;
}

export interface WorkingDay {
  id: number;
  /** 0 is Monday. */
  weekday: number;
  opens_at: string;
  closes_at: string;
}

export interface ProviderAppointment {
  appointment_id: number;
  job_id: number;
  status: string;
  starts_at: string;
  ends_at: string;
  label: string;
  customer_name?: string | null;
  customer_phone?: string | null;
  address?: string | null;
  notes?: string | null;
  /** The work, what the customer added on top, and what that comes to. On a
   *  cash job the total is what there is to collect at the door. */
  price: number;
  tip: number;
  total: number;
  currency: string;
  payment_method?: string;
  payment_status: string;
}

// ── still the shop's, kept for the admin pages and for Phase G ───────────────

/** One entry in the catalogue of things that can be booked, with the guide
 *  figures a provider sets their own terms against. */
export interface Service {
  id: number;
  name: string;
  category: string;
  description: string | null;
  unit: string;
  price_per_unit: number;
  stock: number;
  image_url: string | null;
  duration_minutes?: number | null;
  emergency?: boolean;
  is_active: boolean;
}
