export interface ChatRequest {
  message: string;
  session_id?: string;
  category_filter?: string;
  latitude?: number;
  longitude?: number;
}

export interface ProductResult {
  id: number;
  name: string;
  category: string;
  description: string | null;
  unit: string;
  price_per_unit: number;
  stock: number;
  image_url: string | null;
  similarity: number;
}

// ── Server-side cart ─────────────────────────────────────────────
export interface CartLine {
  item_id: number;
  name: string;
  unit: string;
  unit_price: number;
  quantity: number;
  subtotal: number;
  image_url: string | null;
  /** From our own items table. No provider call is made to fill these. */
  description?: string | null;
  category?: string | null;
  /** Present only for products sourced from outside our catalog. */
  seller?: string | null;
  product_url?: string | null;
}

export interface CartOut {
  session_id: string;
  items: CartLine[];
  subtotal?: number; // goods only, before tax
  tax?: number;
  total: number;     // subtotal + tax — what the customer pays
  count: number;
}

// Structured action the assistant performed (so the UI can react).
export interface ChatAction {
  type: "added" | "removed" | "quantity" | "checkout";
  items?: { item_id: number; name: string; quantity?: number }[];
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  speech?: string;   // short text to speak aloud (long lists aren't read out)
  services: ProductResult[];
  /** Everything that matched. `products` carries only the best 100 of them. */
  total_services?: number;
  cart: CartOut;
  action: ChatAction | null;
  /** How the message was understood: "search", "add_to_cart", "view_cart"... */
  intent?: string | null;
}

export interface VoiceResponse {
  session_id: string;
  transcript: string;
  reply: string;   // shown on screen, may be a long product list
  speech: string;  // what to read out, e.g. "Here is the list." for a long one
  audio: string;   // base64 audio data URL ('' when the browser should speak instead)
  services: ProductResult[];
  /** Everything that matched. `products` carries only the best 100 of them. */
  total_services?: number;
  cart: CartOut;
  action: ChatAction | null;
  intent?: string | null;
}

export interface CustomerIn {
  name: string;
  email: string;
  phone?: string;
  latitude?: number;
  longitude?: number;
  address?: string;
}

export interface OrderItemIn {
  product_id: number;
  quantity: number;
}

export type PaymentMethod = "cod" | "stripe" | "paypal";

export interface PlaceOrderRequest {
  customer: CustomerIn;
  session_id?: string;
  items?: OrderItemIn[];
  notes?: string;
  delivery_date?: string;  // "YYYY-MM-DD"
  delivery_time?: string;  // e.g. "5:00 PM EST"
  delivery_notes?: string; // free text from the customer, optional
  /** Makes a retried or double-submitted order return the original. */
  idempotency_key?: string;
  /** Cash confirms the order at once; the others redirect to the provider. */
  payment_method?: PaymentMethod;
}

export interface OrderItemOut {
  product_id: number;
  product_name: string;
  quantity: number;
  unit: string;
  unit_price: number;
  subtotal: number;
}

export interface PlaceOrderResponse {
  order_id: number;
  customer_id: number;
  total_amount: number; // subtotal + tax
  subtotal?: number;
  tax?: number;
  status: string;
  items: OrderItemOut[];
  delivery_date?: string | null;
  delivery_time?: string | null;
  delivery_notes?: string | null;
  payment_method?: string | null;
}

export interface Product {
  id: number;
  name: string;
  category: string;
  description: string | null;
  unit: string;
  price_per_unit: number;
  stock: number;
  image_url: string | null;
  is_active: boolean;
}

/** A product found outside our own catalog. */
export interface ExternalProduct {
  source_id: string;
  name: string;
  price: number;
  currency?: string;
  image_url?: string | null;
  /** The retailer's own page. Where "Show More" sends the shopper. */
  product_url?: string | null;
  seller?: string | null;
  description?: string;
  rating?: number | null;
  reviews?: number | null;
  /** Came from our own store of past results, so no search was spent. */
  stored?: boolean;
  /** The provider is returning invented sample data, not real listings. */
  sample?: boolean;
  /** The store the shopper chose in the popup, recorded against the product. */
  vendor_url?: string | null;
}

export interface StoreOffer {
  name: string;
  /** The retailer's own product page, not Google's comparison page. */
  url: string;
  price?: number | null;
  price_text?: string;
}

/** A vendor product as we render it, because their page cannot be embedded. */
export interface ProductDetail {
  source_id: string;
  title: string;
  brand?: string | null;
  rating?: number | null;
  reviews?: number | null;
  description: string;
  images: string[];
  stores: StoreOffer[];
  review_snippets: string[];
  best_url?: string | null;
  best_store?: string | null;
  best_price?: number | null;
  /** False when the retailer detail could not be fetched. */
  resolved: boolean;
}

export interface AdoptResponse {
  product: ProductResult;
  created: boolean;
  cart: CartOut;
  /** It is orderable at once; search picks it up after the next index rebuild. */
  searchable_in_seconds: number;
}


/** One of the stores the shopper can browse from inside the app. */
export interface BrowseStore {
  key: string;
  name: string;
  home: string;
  /** Their search, already carrying the shopper's words. */
  search_url: string;
  /**
   * Whether their pages can actually be drawn inside ours. Measured, not
   * guessed: several of these refuse automated visitors, and one serves an
   * international page because the server is not in the United States. False
   * does not hide the store; it means we go straight to a card with a link out
   * rather than spinning first.
   */
  renders: boolean;
  /**
   * Whether that store's own search produces products in our frame. Several
   * draw perfectly and still search empty, because their results are fetched
   * by scripts we strip. Those open at the catalogue, and the panel says so.
   */
  searches: boolean;
}
