const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** The API's own origin, for the few places that need a URL rather than a fetch.
 *  An iframe src is one: the browser loads it, not us. */
export const apiBase = API_BASE;

type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";

interface RequestOptions {
  method?: HttpMethod;
  body?: unknown;
  signal?: AbortSignal;
  // Extra headers, for the admin pages which authenticate with X-Admin-Token.
  headers?: Record<string, string>;
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

async function request<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = "GET", body, signal, headers = {} } = options;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...headers },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const err = await res.json();
      detail = err.detail ?? detail;
    } catch {}
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}

async function requestForm<T>(path: string, form: FormData, signal?: AbortSignal): Promise<T> {
  // No Content-Type header — the browser sets the multipart boundary itself.
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: form, signal });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const err = await res.json();
      detail = err.detail ?? detail;
    } catch {}
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const apiClient = {
  get: <T>(path: string, signal?: AbortSignal, headers?: Record<string, string>) =>
    request<T>(path, { method: "GET", signal, headers }),

  post: <T>(path: string, body: unknown, signal?: AbortSignal, headers?: Record<string, string>) =>
    request<T>(path, { method: "POST", body, signal, headers }),

  patch: <T>(path: string, body: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: "PATCH", body, signal }),

  del: <T>(path: string, signal?: AbortSignal) =>
    request<T>(path, { method: "DELETE", signal }),

  postForm: <T>(path: string, form: FormData, signal?: AbortSignal) =>
    requestForm<T>(path, form, signal),
};

export { ApiError };
