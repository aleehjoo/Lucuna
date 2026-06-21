// Typed fetch wrapper around the FastAPI backend. The frontend holds no
// secrets and talks ONLY to NEXT_PUBLIC_API_BASE — never an upstream source
// directly (Frontend PRD §13.7).

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

// Carries the HTTP status alongside the backend's `detail` message so
// callers can distinguish e.g. 404 ("not found" -> EmptyState) from other
// failures ("something broke" -> ErrorState + retry) without parsing prose.
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new ApiError(detail?.detail ?? `Request failed: ${res.status}`, res.status);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") ?? "";
  return (ct.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

export const api = {
  get: <T>(path: string) => req<T>(path),
  post: <T>(path: string, body?: unknown) =>
    req<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
  put: <T>(path: string, body?: unknown) =>
    req<T>(path, { method: "PUT", body: JSON.stringify(body ?? {}) }),
  del: <T>(path: string) => req<T>(path, { method: "DELETE" }),
};
