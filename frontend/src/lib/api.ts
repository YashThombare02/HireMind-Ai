const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean;
};

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (opts.auth) {
    const token = sessionStorage.getItem("token");
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}) as Record<string, unknown>);
    const detail =
      typeof data.detail === "string" ? data.detail : `Request failed with status ${res.status}`;
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export const apiGet = <T,>(path: string, auth = false) => request<T>(path, { auth });
export const apiPost = <T,>(path: string, body: unknown, auth = false) =>
  request<T>(path, { method: "POST", body, auth });
export const apiPatch = <T,>(path: string, body: unknown, auth = false) =>
  request<T>(path, { method: "PATCH", body, auth });

// Separate from request() because multipart bodies must NOT have a manual
// Content-Type header set — the browser has to generate it itself so it can
// include the multipart boundary string.
export async function apiUpload<T>(path: string, file: File, fieldName = "file"): Promise<T> {
  const token = sessionStorage.getItem("token");
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const formData = new FormData();
  formData.append(fieldName, file);

  const res = await fetch(`${API_BASE_URL}${path}`, { method: "POST", headers, body: formData });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}) as Record<string, unknown>);
    const detail =
      typeof data.detail === "string" ? data.detail : `Upload failed with status ${res.status}`;
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}
