/**
 * lib/client.ts
 * Axios-compatible fetch wrapper for generated services.
 * Uses /proxy so session cookies are first-party (same-origin).
 */

export class ApiError extends Error {
  statusCode: number;
  data?: unknown;
  constructor(message: string, statusCode: number, data?: unknown) {
    super(message);
    this.statusCode = statusCode;
    this.data = data;
    this.name = "ApiError";
  }
}

const PROXY = "/proxy";

// Remap generated service paths to actual backend paths.
const PATH_MAP: Record<string, string> = {
  "/api/applications": "/api/v1/applications",
  "/api/jobs": "/api/v1/jobs",
  "/api/chat": "/api/v1/rico/chat",
  "/api/profile": "/api/v1/rico/profile",
  "/api/upload-cv": "/api/v1/rico/profile/cv",
  "/api/settings": "/api/v1/settings",
};

function resolve(path: string): string {
  // Exact match first (handles no-subpath routes like /api/settings)
  if (PATH_MAP[path]) return PATH_MAP[path];
  // Prefix match: find the longest registered prefix that matches
  const sorted = Object.keys(PATH_MAP).sort((a, b) => b.length - a.length);
  for (const prefix of sorted) {
    if (path === prefix || path.startsWith(`${prefix}/`)) {
      return PATH_MAP[prefix] + path.slice(prefix.length);
    }
  }
  return path;
}

function buildUrl(path: string, params?: Record<string, unknown>): string {
  const mapped = resolve(path);
  const url = `${PROXY}${mapped}`;
  if (!params) return url;
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v != null) qs.append(k, String(v));
  });
  return `${url}?${qs.toString()}`;
}

async function handleError(path: string, res: Response): Promise<never> {
  const body = (await res.json().catch(() => ({}))) as { detail?: string };
  throw new ApiError(body.detail ?? `${res.status} ${path}`, res.status, body);
}

async function request<T>(
  path: string,
  method: string,
  data?: unknown,
  config?: { params?: Record<string, unknown> }
): Promise<{ data: T }> {
  const isForm = data instanceof FormData;
  const res = await fetch(buildUrl(path, config?.params), {
    method,
    headers: isForm ? undefined : { "Content-Type": "application/json" },
    credentials: "include",
    body: isForm ? data : data ? JSON.stringify(data) : undefined,
  });
  if (!res.ok) return handleError(path, res);
  if (res.status === 204) return { data: {} as T };
  return { data: (await res.json()) as T };
}

const client = {
  get: <T>(path: string, config?: { params?: Record<string, unknown> }) =>
    request<T>(path, "GET", undefined, config),
  post: <T>(path: string, data?: unknown) => request<T>(path, "POST", data),
  patch: <T>(path: string, data?: unknown) => request<T>(path, "PATCH", data),
  put: <T>(path: string, data?: unknown) => request<T>(path, "PUT", data),
  del: <T>(path: string) => request<T>(path, "DELETE"),
};

export default client;
