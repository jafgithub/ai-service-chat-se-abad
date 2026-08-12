import { apiClient, apiBase } from "./client";
import type {
  AdoptResponse,
  ExternalProduct,
  ProductDetail,
  BrowseStore,
  ChatRequest,
  ChatResponse,
  CartOut,
  VoiceResponse,
  PlaceOrderRequest,
  PlaceOrderResponse,
  Product,
} from "./types";

export const chatApi = {
  send: (payload: ChatRequest, signal?: AbortSignal) =>
    apiClient.post<ChatResponse>("/api/v1/chat", payload, signal),
};

export const cartApi = {
  get: (sessionId: string, signal?: AbortSignal) =>
    apiClient.get<CartOut>(`/api/v1/cart?session_id=${encodeURIComponent(sessionId)}`, signal),

  add: (sessionId: string, itemId: number, quantity = 1, signal?: AbortSignal) =>
    apiClient.post<CartOut>("/api/v1/cart/items", { session_id: sessionId, item_id: itemId, quantity }, signal),

  setQuantity: (sessionId: string, itemId: number, quantity: number, signal?: AbortSignal) =>
    apiClient.patch<CartOut>(`/api/v1/cart/items/${itemId}?session_id=${encodeURIComponent(sessionId)}`, { quantity }, signal),

  remove: (sessionId: string, itemId: number, signal?: AbortSignal) =>
    apiClient.del<CartOut>(`/api/v1/cart/items/${itemId}?session_id=${encodeURIComponent(sessionId)}`, signal),

  clear: (sessionId: string, signal?: AbortSignal) =>
    apiClient.del<CartOut>(`/api/v1/cart?session_id=${encodeURIComponent(sessionId)}`, signal),
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

export const shoppingApi = {
  /** Whether off-catalog search is switched on at all. */
  status: (signal?: AbortSignal) =>
    apiClient.get<{ enabled: boolean; provider: string | null; sample: boolean }>(
      "/api/v1/shopping/status", signal),

  search: (q: string, signal?: AbortSignal) =>
    apiClient.get<ExternalProduct[]>(`/api/v1/shopping/search?q=${encodeURIComponent(q)}`, signal),

  /** One product with every store selling it. Costs a provider search the
   *  first time a product is opened, and nothing after. */
  product: (sourceId: string, signal?: AbortSignal) =>
    apiClient.get<ProductDetail>(
      `/api/v1/shopping/product/${encodeURIComponent(sourceId)}`, signal),

  /** The retailer's own page, rendered on our server so it can be framed.
   *
   *  A URL rather than a fetch: the iframe loads it. Used only by the browser
   *  view at /v1/chat; the ordinary chat never calls it. */
  browseUrl: (vendorUrl: string, frameWidth?: number) =>
    `${apiBase}/api/v1/browse/page?u=${encodeURIComponent(vendorUrl)}` +
    // The width decides which layout the store is asked for. Squeezing a
    // desktop page into a phone keeps the four-across product grid and makes
    // every card unreadable.
    (frameWidth ? `&w=${Math.round(frameWidth)}` : ""),

  /** The stores a shopper can browse from inside the app, with each one's
   *  search already pointed at their words. */
  stores: (q: string, signal?: AbortSignal) =>
    apiClient.get<BrowseStore[]>(
      `/api/v1/browse/stores?q=${encodeURIComponent(q)}`, signal),

  /** Bring an external product into the catalog and put it in the cart. */
  adopt: (
    sessionId: string,
    product: ExternalProduct,
    query: string,
    signal?: AbortSignal
  ) =>
    apiClient.post<AdoptResponse>(
      "/api/v1/shopping/adopt",
      { session_id: sessionId, product, query },
      signal
    ),
};

export const paymentsApi = {
  /** Which methods the server can actually take money with right now. */
  list: (signal?: AbortSignal) =>
    apiClient.get<{ enabled: boolean; providers: string[] }>("/api/v1/payments/providers", signal),

  /** Start a checkout and get the provider's hosted page to redirect to. */
  checkout: (orderId: number, provider: string, signal?: AbortSignal) =>
    apiClient.post<{ url: string; provider: string; provider_ref: string }>(
      "/api/v1/payments/checkout",
      { order_id: orderId, provider },
      signal
    ),
};

export const ordersApi = {
  place: (payload: PlaceOrderRequest, signal?: AbortSignal) =>
    apiClient.post<PlaceOrderResponse>("/api/v1/orders", payload, signal),

  /**
   * Fetch an order the shopper already placed, by the idempotency key their
   * browser generated for it. Used on the way back from a payment provider,
   * where the URL carries the order id but the page has lost everything else.
   */
  byKey: (idempotencyKey: string, signal?: AbortSignal) =>
    apiClient.get<PlaceOrderResponse>(
      `/api/v1/orders/by-key/${encodeURIComponent(idempotencyKey)}`,
      signal
    ),
};

export const productsApi = {
  list: (category?: string, signal?: AbortSignal) => {
    const path = category
      ? `/api/v1/products?category=${encodeURIComponent(category)}`
      : "/api/v1/products";
    return apiClient.get<Product[]>(path, signal);
  },
};

export const partnersApi = {
  submit: (payload: { name: string; email: string; phone?: string; address?: string }) =>
    apiClient.post<{ id: number; message: string }>("/api/v1/partners", payload),
};
