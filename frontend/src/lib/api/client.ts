const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** The API's own origin, for the few places that need a URL rather than a fetch. */
export const apiBase = API_BASE;

type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";

interface RequestOptions {
  method?: HttpMethod;
  body?: unknown;
  signal?: AbortSignal;
  // Extra headers, for the admin pages which authenticate with X-Admin-Token.
  headers?: Record<string, string>;
  /** Send no Authorization header even when signed in. Used by login and
   *  registration, where a stale token must not travel with the request. */
  anonymous?: boolean;
}

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

// ── the bearer token ─────────────────────────────────────────────────────────
// One token for customers and providers alike, exactly as the backend issues
// it. It lives here rather than in a React context so that every call goes out
// with it whether or not the caller is a component, and so there is one place
// that can be cleared when the server says it is no longer good.

const TOKEN_KEY = "sa_auth_token";

let authToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;

/** Read back whatever the last session left behind. Safe during a static
 *  prerender, where there is no localStorage and the answer is simply null. */
export function loadStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  authToken = window.localStorage.getItem(TOKEN_KEY);
  return authToken;
}

export function setAuthToken(token: string | null): void {
  authToken = token;
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export function getAuthToken(): string | null {
  return authToken;
}

/**
 * Called when the server rejects our token.
 *
 * A token can stop being good while a page is open: it expires, or it is
 * revoked from another device. Handling that in every caller would mean every
 * caller remembering to, so it is handled once here and the provider clears the
 * signed-in state. The failing call still throws, because the screen that made
 * it still has to say something went wrong.
 */
export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

async function failure(res: Response): Promise<ApiError> {
  let detail = res.statusText;
  try {
    const err = await res.json();
    detail = err.detail ?? detail;
  } catch {}
  if (res.status === 401 && authToken) {
    // Only when we actually sent a token. A 401 from an anonymous call means
    // "sign in", not "your session ended", and clearing state on it would sign
    // people out for visiting a page while signed out.
    setAuthToken(null);
    unauthorizedHandler?.();
  }
  return new ApiError(res.status, detail);
}

function authHeaders(anonymous?: boolean): Record<string, string> {
  if (anonymous || !authToken) return {};
  return { Authorization: `Bearer ${authToken}` };
}

async function request<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = "GET", body, signal, headers = {}, anonymous } = options;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(anonymous),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });

  if (!res.ok) throw await failure(res);

  // 204 and friends have nothing to parse. None of ours do today, but a caller
  // should not blow up if one starts to.
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

async function requestForm<T>(path: string, form: FormData, signal?: AbortSignal,
                              headers: Record<string, string> = {}): Promise<T> {
  // No Content-Type header — the browser sets the multipart boundary itself.
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { ...authHeaders(), ...headers },
    body: form,
    signal,
  });
  if (!res.ok) throw await failure(res);
  return res.json() as Promise<T>;
}

export const apiClient = {
  get: <T>(path: string, signal?: AbortSignal, headers?: Record<string, string>) =>
    request<T>(path, { method: "GET", signal, headers }),

  post: <T>(path: string, body: unknown, signal?: AbortSignal, headers?: Record<string, string>) =>
    request<T>(path, { method: "POST", body, signal, headers }),

  /** For login and registration: never carries a stale token. */
  postAnonymous: <T>(path: string, body: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: "POST", body, signal, anonymous: true }),

  put: <T>(path: string, body: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: "PUT", body, signal }),

  patch: <T>(path: string, body: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: "PATCH", body, signal }),

  del: <T>(path: string, signal?: AbortSignal, headers?: Record<string, string>) =>
    request<T>(path, { method: "DELETE", signal, headers }),

  postForm: <T>(path: string, form: FormData, signal?: AbortSignal,
                headers?: Record<string, string>) =>
    requestForm<T>(path, form, signal, headers),
};

export { ApiError };
