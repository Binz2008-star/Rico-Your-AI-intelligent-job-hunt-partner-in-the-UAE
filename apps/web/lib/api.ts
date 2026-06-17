import {
  AgentChatRequestSchema,
  AgentUIResponseSchema,
  ConfirmCVProfileResponseSchema,
  MeResponseSchema,
  ProfileUpdateResponseSchema,
  RicoChatHistoryResponseSchema,
  RicoChatResponseSchema,
  RicoProfileResponseSchema,
  SavedSearchesResponseSchema,
  UploadCVResponseSchema,
} from "@/lib/schemas";
import type { AgentChatRequest, AgentUIResponse } from "@/lib/schemas";
import type {
  Application,
  ApplicationActionRequest,
  ApplicationActionResponse,
  ApplicationStatus,
  ApplicationsResponse,
  HealthResponse as ClientHealthResponse,
  Job,
  JobActionRequest,
  JobActionResponse,
  JobListResponse,
  MatchingGuardrailWarning,
  SettingsResponse,
  SettingsUpdateRequest,
  TelegramStatusResponse,
} from "@/types";
import type { ZodType } from "zod";

// Absolute backend URL — used only for server-side (SSR) fetches such as fetchHealth().
// No localhost fallback: if unset, SSR fetches will fail loudly rather than silently
// routing to a local process that does not exist in production.
const RICO_API =
  process.env.BACKEND_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_RICO_API;

// All client-side fetches route through /proxy so the session cookie is set and
// sent as a first-party (same-origin) cookie, bypassing Chrome's cross-site
// cookie blocking. Next.js rewrites /proxy/* → RICO_API/* server-side.
const PROXY = "/proxy";
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";

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

function validateShape<T>(
  schema: ZodType<T>,
  data: unknown,
  context: string,
): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    console.error(`Invalid ${context} response`, result.error.flatten());
    throw new Error(`Invalid ${context} response`);
  }
  return result.data;
}

function buildProxyUrl(path: string, params?: Record<string, unknown>): string {
  const url = `${PROXY}${path}`;
  if (!params) return url;

  const qs = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value != null) qs.append(key, String(value));
  });

  const query = qs.toString();
  return query ? `${url}?${query}` : url;
}

export async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  params?: Record<string, unknown>,
): Promise<T> {
  const headers = new Headers(init.headers);
  const isForm = init.body instanceof FormData;
  const hasBody = init.body !== undefined && init.body !== null;

  if (!isForm && hasBody && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(buildProxyUrl(path, params), {
    ...init,
    headers,
    credentials: init.credentials ?? "include",
  });

  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as {
      detail?: unknown;
      message?: string;
    };
    const fallback = `${res.status} ${path}`;
    const message =
      extractDetail(body.detail, body.message ?? fallback) ?? fallback;
    throw new ApiError(message, res.status, body);
  }

  if (res.status === 204) return {} as T;
  return (await res.json()) as T;
}

// ── Health ────────────────────────────────────────────────────────────────────

export interface RicoStatus {
  ready_for_api: boolean;
  ready_for_db: boolean;
  ready_for_telegram: boolean;
  ready_for_openai: boolean;
  ready_for_deepseek: boolean;
  ready_for_jotform: boolean;
  ready_for_hf: boolean;
  ai_provider: string;
}

export interface HealthResponse {
  status: string;
  db: string;
  version: string;
  ready_for_openai?: boolean;
  ready_for_deepseek?: boolean;
  ready_for_hf?: boolean;
  ready_for_jotform?: boolean;
  ai_provider?: string;
  rico: RicoStatus;
}

// Server-side only — uses absolute URL (relative URLs don't resolve in Node.js).
export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${RICO_API}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json() as Promise<HealthResponse>;
}

// Client-side health check via the same-origin proxy.
export async function getHealth(): Promise<ClientHealthResponse> {
  return requestJson<ClientHealthResponse>("/health", { method: "GET" });
}

// ── Version (debug only, non-user-facing) ──────────────────────────────────────

export interface VersionResponse {
  app: string;
  version: string;
  commit: string;
  environment: string;
  deployed_at: string;
}

export async function getVersion(): Promise<VersionResponse> {
  return requestJson<VersionResponse>("/api/v1/version", { method: "GET" });
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface MeResponse {
  email: string | null;
  role: string;
  authenticated: boolean;
  guest?: boolean;
  name?: string | null;
}

export async function fetchMe(signal?: AbortSignal): Promise<MeResponse> {
  const res = await fetch(`${PROXY}/api/v1/me`, {
    credentials: "include",
    signal,
  });
  if (!res.ok) {
    // For 401, return guest response instead of throwing to avoid console noise
    if (res.status === 401) {
      return { email: null, role: "guest", authenticated: false, guest: true };
    }
    throw new Error(`/me failed: ${res.status}`);
  }
  return validateShape(MeResponseSchema, await res.json(), "auth /me");
}

export interface LoginResponse {
  message: string;
  email: string;
}

export async function login(
  email: string,
  password: string,
  publicUserIdToMerge?: string | null,
): Promise<LoginResponse> {
  const body: Record<string, unknown> = { email, password };
  if (publicUserIdToMerge) {
    body.public_user_id_to_merge = publicUserIdToMerge;
  }
  const res = await fetch(`${PROXY}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(err.detail ?? "Login failed", res.status, err);
  }
  return res.json() as Promise<LoginResponse>;
}

export async function logout(): Promise<void> {
  await fetch(`${PROXY}/api/v1/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

// ── Profile ───────────────────────────────────────────────────────────────────

export interface ProfileResponse {
  profile_exists: boolean;
  /** Null for new users who have not completed profile setup. */
  email?: string | null;
  /** Null for new users who have not completed profile setup. */
  user_id?: string | null;
  name?: string | null;
  phone?: string | null;
  telegram_username?: string | null;
  target_roles?: string[] | null;
  preferred_cities?: string[] | null;
  salary_expectation_aed?: number | null;
  minimum_salary_aed?: number | null;
  skills?: string[] | null;
  industries?: string[] | null;
  visa_status?: string | null;
  notice_period?: string | null;
  years_experience?: number | null;
  current_role?: string | null;
  current_company?: string | null;
  linkedin_url?: string | null;
  completeness_score?: number | null;
  settings?: Record<string, unknown>;
  warnings?: MatchingGuardrailWarning[];
}

export async function fetchProfile(): Promise<ProfileResponse> {
  const res = await fetch(`${PROXY}/api/v1/rico/profile`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Profile fetch failed: ${res.status}`);
  // Guard against non-JSON responses (e.g. Vercel timeout HTML on cold start)
  const body = await res.json().catch(() => null);
  if (body === null) throw new Error("Profile response was not valid JSON");
  return validateShape(
    RicoProfileResponseSchema,
    body,
    "Rico profile",
  );
}

// ── User files / documents ────────────────────────────────────────────────────

export interface UserDocument {
  id: string;
  user_id: string;
  filename: string;
  original_filename: string;
  doc_type: "cv" | "cover_letter" | "other";
  file_size: number;
  label?: string | null;
  is_primary: boolean;
  is_legacy?: boolean;
  skills_count?: number | null;
  years_experience?: number | null;
  current_role?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface UserFilesResponse {
  files: UserDocument[];
  total: number;
}

export async function listUserFiles(): Promise<UserFilesResponse> {
  return requestJson<UserFilesResponse>("/api/v1/user/files", { method: "GET" });
}

export async function deleteUserFile(fileId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/v1/user/files/${fileId}`, { method: "DELETE" });
}

export async function updateUserFile(
  fileId: string,
  updates: { label?: string; doc_type?: string },
): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/v1/user/files/${fileId}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export async function setPrimaryFile(fileId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/v1/user/files/${fileId}/set-primary`, { method: "POST" });
}

export async function uploadUserFile(
  file: File,
  docType: "cover_letter" | "other" = "cover_letter",
): Promise<{ ok: boolean; id: string; filename: string; doc_type: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("doc_type", docType);
  const res = await fetch(`${PROXY}/api/v1/user/files?doc_type=${docType}`, {
    method: "POST",
    body: form,
    credentials: "include",
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(err.detail ?? "Upload failed", res.status, err);
  }
  return res.json() as Promise<{ ok: boolean; id: string; filename: string; doc_type: string }>;
}

// ── Saved searches ────────────────────────────────────────────────────────────

export interface SavedSearch {
  id: string;
  query: string;
  filters: Record<string, unknown>;
  created_at: string;
}

export interface SavedSearchesResponse {
  searches: SavedSearch[];
  total: number;
}

export async function fetchSavedSearches(): Promise<SavedSearchesResponse> {
  const res = await fetch(`${PROXY}/api/v1/rico/settings/saved-searches`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Saved searches fetch failed: ${res.status}`);
  return validateShape(
    SavedSearchesResponseSchema,
    await res.json(),
    "saved searches",
  );
}

export async function createSavedSearch(
  query: string,
  filters?: Record<string, unknown>,
): Promise<{ status: string; query: string }> {
  const res = await fetch(`${PROXY}/api/v1/rico/settings/saved-searches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ query, filters: filters ?? {} }),
  });
  if (!res.ok) throw new Error(`Save search failed: ${res.status}`);
  return res.json() as Promise<{ status: string; query: string }>;
}

export async function deleteSavedSearch(id: string): Promise<void> {
  const res = await fetch(
    `${PROXY}/api/v1/rico/settings/saved-searches/${id}`,
    {
      method: "DELETE",
      credentials: "include",
    },
  );
  if (!res.ok) throw new Error(`Delete search failed: ${res.status}`);
}

// ── Jobs ──────────────────────────────────────────────────────────────────────

const MOCK_JOBS: Job[] = [
  {
    job_id: "mock_001",
    title: "Senior Manager - [Your Field]",
    company: "Example Corp",
    location: "Dubai, UAE",
    salary_range: "AED 25-35k/mo",
    score: 94,
    reason: "Profile keyword match + seniority level + location",
    tags: ["Senior", "Management", "UAE"],
    posted_at: new Date().toISOString(),
    apply_url: "#",
  },
  {
    job_id: "mock_002",
    title: "Department Lead - Operations",
    company: "Regional Holdings",
    location: "Abu Dhabi, UAE",
    salary_range: "AED 20-28k/mo",
    score: 87,
    reason: "Role title + experience range + salary band alignment",
    tags: ["Operations", "Leadership", "Full-time"],
    posted_at: new Date().toISOString(),
    apply_url: "#",
  },
  {
    job_id: "mock_003",
    title: "Specialist - Compliance & Governance",
    company: "Acme Group",
    location: "Dubai, UAE",
    salary_range: "AED 18-24k/mo",
    score: 79,
    reason: "Compliance keywords + UAE market match",
    tags: ["Compliance", "Governance", "Mid-level"],
    posted_at: new Date().toISOString(),
    apply_url: "#",
  },
];

function normalizeStringArray(value: unknown, fallback: string[]): string[] {
  const items = Array.isArray(value)
    ? value
        .filter((item): item is string => typeof item === "string")
        .map((item) => item.trim())
        .filter(Boolean)
    : [];

  return items.length > 0 ? items : fallback;
}

function normalizeMatchExplanation(raw: unknown): Job["match_explanation"] {
  if (!raw || typeof raw !== "object") return undefined;

  const item = raw as Record<string, unknown>;
  const verdict = item.verdict;
  const confidence = item.confidence;

  return {
    verdict:
      verdict === "strong_fit" ||
      verdict === "worth_checking" ||
      verdict === "weak_fit"
        ? verdict
        : "worth_checking",
    summary: String(item.summary ?? ""),
    why_this_fits: normalizeStringArray(item.why_this_fits, [
      "Review the role title and score for the main available fit signals.",
    ]),
    worth_checking: normalizeStringArray(item.worth_checking, [
      "Confirm the full role details before applying.",
    ]),
    recommended_next_step: String(
      item.recommended_next_step ?? "Review the role details before deciding.",
    ),
    confidence:
      confidence === "high" || confidence === "medium" || confidence === "low"
        ? confidence
        : "medium",
  };
}

function normalizeJob(raw: unknown): Job {
  const item = raw as Record<string, unknown>;
  const matchExplanation = normalizeMatchExplanation(item.match_explanation);
  return {
    job_id: String(item.job_id ?? item.id ?? item._id ?? ""),
    title: String(item.title ?? "Untitled role"),
    company: String(item.company ?? "Unknown company"),
    location: String(item.location ?? "Remote / unspecified"),
    salary_range: String(item.salary_range ?? item.salary ?? ""),
    score: typeof item.score === "number" ? item.score : 0,
    reason: String(item.reason ?? item.match_reason ?? ""),
    tags: Array.isArray(item.tags) ? (item.tags as string[]) : [],
    posted_at: String(item.posted_at ?? item.date_found ?? ""),
    apply_url: String(item.apply_url ?? item.link ?? ""),
    source_url: String(item.source_url ?? item.url ?? ""),
    verification_status: String(item.verification_status ?? ""),
    match_explanation: matchExplanation,
  };
}

export async function getJobs(
  page = 1,
  limit = 20,
  minScore = 0,
  source?: string,
  signal?: AbortSignal,
): Promise<JobListResponse> {
  if (USE_MOCK) {
    return {
      jobs: MOCK_JOBS,
      total: MOCK_JOBS.length,
      page: 1,
      limit: 20,
      pages: 1,
    };
  }

  const data = await requestJson<JobListResponse>(
    "/api/v1/jobs",
    { method: "GET", signal },
    { page, limit, min_score: minScore, source },
  );
  const rawJobs = Array.isArray(data?.jobs) ? (data.jobs as unknown[]) : [];
  const jobs = rawJobs.map(normalizeJob);

  return {
    jobs,
    total: typeof data.total === "number" ? data.total : jobs.length,
    page: typeof data.page === "number" ? data.page : page,
    limit: typeof data.limit === "number" ? data.limit : limit,
    pages: typeof data.pages === "number" ? data.pages : 1,
  };
}

export async function getJobById(jobId: string): Promise<Job> {
  if (USE_MOCK) {
    const job = MOCK_JOBS.find((item) => item.job_id === jobId);
    if (!job) throw new Error("Job not found");
    return job;
  }

  const data = await requestJson<Job>(`/api/v1/jobs/${jobId}`, {
    method: "GET",
  });
  return normalizeJob(data);
}

export async function applyJob(
  jobId: string,
  payload: JobActionRequest,
): Promise<JobActionResponse> {
  if (USE_MOCK) {
    return {
      status: "applied",
      message: "Application submitted",
      job_id: jobId,
    };
  }

  return requestJson<JobActionResponse>(`/api/v1/jobs/${jobId}/apply`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function saveJob(
  jobId: string,
  payload: JobActionRequest,
): Promise<JobActionResponse> {
  if (USE_MOCK) {
    return { status: "saved", message: "Job saved", job_id: jobId };
  }

  return requestJson<JobActionResponse>(`/api/v1/jobs/${jobId}/save`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function skipJob(
  jobId: string,
  payload: JobActionRequest,
): Promise<JobActionResponse> {
  if (USE_MOCK) {
    return { status: "skipped", message: "Job skipped", job_id: jobId };
  }

  return requestJson<JobActionResponse>(`/api/v1/jobs/${jobId}/skip`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function blockJob(
  jobId: string,
  payload: JobActionRequest,
): Promise<JobActionResponse> {
  if (USE_MOCK) {
    return { status: "blocked", message: "Company blocked", job_id: jobId };
  }

  return requestJson<JobActionResponse>(`/api/v1/jobs/${jobId}/block`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ── Applications ──────────────────────────────────────────────────────────────

const APPLICATION_STATUS_ALIASES: Record<string, ApplicationStatus> = {
  interview_scheduled: "interview",
  offer_extended: "offer",
};

const MOCK_APPLICATIONS: Application[] = [
  {
    application_id: "app_001",
    job_id: "job_001",
    title: "Senior Manager - Operations",
    company: "Acme Corporation",
    location: "Dubai, UAE",
    status: "applied",
    applied_at: "2026-04-20T09:00:00Z",
    apply_url: "#",
  },
  {
    application_id: "app_002",
    job_id: "job_002",
    title: "Team Lead - Projects",
    company: "Global Industries",
    location: "Abu Dhabi, UAE",
    status: "interview",
    applied_at: "2026-04-15T08:00:00Z",
    apply_url: "#",
  },
  {
    application_id: "app_003",
    job_id: "job_003",
    title: "Specialist - Compliance",
    company: "Regional Group",
    location: "Dubai, UAE",
    status: "applied",
    applied_at: "2026-04-18T11:00:00Z",
    apply_url: "#",
  },
  {
    application_id: "app_004",
    job_id: "job_004",
    title: "Manager - Quality Assurance",
    company: "Horizon Enterprises",
    location: "Abu Dhabi, UAE",
    status: "rejected",
    applied_at: "2026-04-10T10:00:00Z",
    apply_url: "#",
  },
];

function normalizeApplicationStatus(raw: string): ApplicationStatus {
  return APPLICATION_STATUS_ALIASES[raw] ?? (raw as ApplicationStatus);
}

function normalizeApplication(raw: unknown): Application {
  const item = raw as Record<string, unknown>;
  const applicationId = String(
    item.application_id ?? item.job_id ?? item.id ?? "",
  );
  const jobId = String(item.job_id ?? item.id ?? applicationId);

  return {
    application_id: applicationId,
    job_id: jobId,
    title: String(item.title ?? "Untitled role"),
    company: String(item.company ?? "Unknown company"),
    location: String(item.location ?? "Remote / unspecified"),
    status: normalizeApplicationStatus(String(item.status ?? "applied")),
    applied_at: String(item.applied_at ?? item.date_applied ?? ""),
    updated_at: String(item.updated_at ?? item.date_updated ?? ""),
    notes: String(item.notes ?? ""),
    apply_url: String(item.apply_url ?? item.link ?? ""),
  };
}

export async function getApplications(
  status?: string,
  page = 1,
  limit = 50,
  signal?: AbortSignal,
): Promise<ApplicationsResponse> {
  if (USE_MOCK) {
    return {
      applications: MOCK_APPLICATIONS,
      total: MOCK_APPLICATIONS.length,
      page: 1,
      limit: 50,
      pages: 1,
    };
  }

  const data = await requestJson<ApplicationsResponse>(
    "/api/v1/applications",
    { method: "GET", signal },
    { status, page, limit },
  );
  const rawApplications = Array.isArray(data?.applications)
    ? (data.applications as unknown[])
    : [];
  const applications = rawApplications.map(normalizeApplication);

  return {
    applications,
    total: typeof data.total === "number" ? data.total : applications.length,
    page: typeof data.page === "number" ? data.page : page,
    limit: typeof data.limit === "number" ? data.limit : limit,
    pages: typeof data.pages === "number" ? data.pages : 1,
  };
}

export async function updateApplicationStatus(
  jobId: string,
  payload: ApplicationActionRequest,
): Promise<ApplicationActionResponse> {
  if (USE_MOCK) {
    return {
      status: payload.status,
      job_id: jobId,
      message: "Status updated",
    };
  }

  return requestJson<ApplicationActionResponse>(
    `/api/v1/applications/${jobId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
}

export async function getApplicationStats(
  signal?: AbortSignal,
): Promise<Record<string, number>> {
  if (USE_MOCK) {
    return {
      applied: 2,
      interview: 1,
      offer: 0,
      rejected: 1,
      saved: 0,
    };
  }

  const data = await requestJson<Record<string, unknown>>(
    "/api/v1/applications/stats",
    {
      method: "GET",
      signal,
    },
  );
  const normalized: Record<string, number> = {};

  for (const [key, value] of Object.entries(data)) {
    // Skip the nested by_status object and the pre-summed total to avoid
    // type coercion bugs (number + object = "[object Object]") and double-counting.
    if (key === "by_status" || key === "total" || typeof value !== "number") continue;
    const normalizedKey = APPLICATION_STATUS_ALIASES[key] ?? key;
    normalized[normalizedKey] = (normalized[normalizedKey] ?? 0) + value;
  }

  return normalized;
}

// ── Settings ──────────────────────────────────────────────────────────────────

const MOCK_SETTINGS: SettingsResponse = {
  include_keywords: ["Environmental", "HSE", "ESG", "Sustainability"],
  exclude_keywords: ["Sales", "Marketing", "Retail"],
  min_score: 65,
  max_daily_applies: 5,
  telegram_chat_id: "",
  score_threshold_apply: 80,
  score_threshold_watch: 60,
  warnings: [],
};

export async function getSettings(
  signal?: AbortSignal,
): Promise<SettingsResponse> {
  if (USE_MOCK) return MOCK_SETTINGS;
  return requestJson<SettingsResponse>("/api/v1/settings", {
    method: "GET",
    signal,
  });
}

export async function updateSettings(
  payload: SettingsUpdateRequest,
): Promise<SettingsResponse> {
  if (USE_MOCK) {
    return { ...MOCK_SETTINGS, ...payload };
  }

  return requestJson<SettingsResponse>("/api/v1/settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

// ── Telegram notifications ──────────────────────────────────────────────────
// Backend endpoints already exist in src/api/routers/settings.py.

const MOCK_TELEGRAM_STATUS: TelegramStatusResponse = {
  opted_in: false,
  telegram_username: null,
};

export async function getTelegramStatus(
  signal?: AbortSignal,
): Promise<TelegramStatusResponse> {
  if (USE_MOCK) return MOCK_TELEGRAM_STATUS;
  return requestJson<TelegramStatusResponse>("/api/v1/settings/telegram/status", {
    method: "GET",
    signal,
  });
}

export async function telegramOptIn(
  telegram_chat_id?: string,
): Promise<TelegramStatusResponse> {
  if (USE_MOCK) return { ...MOCK_TELEGRAM_STATUS, opted_in: true };
  return requestJson<TelegramStatusResponse>("/api/v1/settings/telegram/opt-in", {
    method: "POST",
    body: JSON.stringify(telegram_chat_id ? { telegram_chat_id } : {}),
  });
}

export async function telegramOptOut(): Promise<TelegramStatusResponse> {
  if (USE_MOCK) return { ...MOCK_TELEGRAM_STATUS, opted_in: false };
  return requestJson<TelegramStatusResponse>("/api/v1/settings/telegram/opt-out", {
    method: "POST",
  });
}

// ── Password reset ────────────────────────────────────────────────────────────

export async function forgotPassword(
  email: string,
): Promise<{ message: string }> {
  const res = await fetch(`${PROXY}/api/v1/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json() as Promise<{ message: string }>;
}

export async function resetPassword(
  token: string,
  new_password: string,
): Promise<{ message: string }> {
  const res = await fetch(`${PROXY}/api/v1/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password }),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `Reset failed: ${res.status}`);
  }
  return res.json() as Promise<{ message: string }>;
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export interface JobMatch {
  title: string;
  company: string;
  location?: string;
  /** Score in [0.0, 1.0] — absent/null means no scorer ran; must not be shown as a real score. */
  score?: number | null;
  /** Salary string only present when the provider supplied it — never inferred. */
  salary?: string;
  why?: string;
  actions?: string[];
  confidence?: "high" | "medium" | "low";
  match_reasons?: string[];
  match_concerns?: string[];
  missing_facts?: string[];
  recommended_action?: string;
  apply_url?: string;
  source_url?: string;
  alt_link?: string;
  verification_status?:
    | "live"
    | "live_verified"
    | "lead_needs_verification"
    | "needs_source_verification"
    | "login_required"
    | "rate_limited"
    | "aggregator_untrusted"
    | "google_intermediary";
}

export interface RicoOption {
  action: string;
  label: string;
  message?: string;
  role?: string;
}

export interface NextAction {
  action: string;
  label: string;
  message?: string;
  role?: string;
}

export interface ChatApiResponse {
  response?: string;
  reply?: string;
  message?: string;
  content?: string;
  answer?: string;
  text?: string;
  data?: {
    response?: string;
    reply?: string;
    message?: string;
    content?: string;
    text?: string;
  };
  type?: string;
  matches?: JobMatch[];
  options?: RicoOption[];
  next_action?: string;
  response_source?: string;
  role?: string;
  reasons?: string[];
  next_actions?: NextAction[];
  operation_id?: string;
  operation_status?: string;
  operation_type?: string;
  result_count?: number | null;
  rate_limited?: boolean;
  rate_limit_notice?: string;
  messages_remaining?: number;
  messages_limit?: number;
}

export interface ParsedCV {
  text: string;
  emails: string[];
  phones: string[];
  skills: string[];
  certifications: string[];
  languages: string[];
  years_experience_hint?: number | null;
  years_experience?: number | null;
  extraction_quality?: string;
  extracted_chars?: number;
}

export interface ProfilePreview {
  name: string | null;
  email: string | null;
  phone: string | null;
  current_role: string | null;
  experience_years: number | null;
  target_roles: string[];
  skills_detected: string[];
  existing_skills: string[];
  skills: string[];
  certifications: string[];
  languages: string[];
}

export interface UploadCVResponse {
  ok: boolean;
  status: string;
  document_type?: string;
  extraction_quality?: string;
  extracted_chars?: number;
  filename?: string;
  preview?: ProfilePreview;
  parsed?: ParsedCV;
  message?: string;
  user_id?: string;
}

export interface ConfirmCVProfileRequest {
  preview: ProfilePreview;
  filename: string;
  doc_type?: string;
}

export interface ConfirmCVProfileResponse {
  ok: boolean;
  status: string;
  message: string;
  profile: Record<string, unknown>;
}

export async function confirmCVProfile(
  payload: ConfirmCVProfileRequest,
  userId?: string,
): Promise<ConfirmCVProfileResponse> {
  const data = await requestJson<unknown>(
    "/api/v1/rico/confirm-cv-profile",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    userId ? { user_id: userId } : undefined,
  );
  return validateShape(
    ConfirmCVProfileResponseSchema,
    data,
    "confirm CV profile",
  );
}

function extractDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string; message?: string };
    return first.msg ?? first.message ?? fallback;
  }
  return fallback;
}

export async function uploadCV(
  file: File,
  userId?: string,
): Promise<UploadCVResponse> {
  const form = new FormData();
  form.append("file", file);
  const data = await requestJson<unknown>(
    "/api/v1/rico/upload-cv",
    {
      method: "POST",
      credentials: "include",
      body: form,
    },
    userId ? { user_id: userId } : undefined,
  );
  return validateShape(UploadCVResponseSchema, data, "CV upload");
}

// ── Onboarding ────────────────────────────────────────────────────────────────

export interface OnboardingPayload {
  target_roles?: string[];
  preferred_cities?: string[];
  salary_expectation_aed?: number;
  years_experience?: number;
  current_role?: string;
  skills?: string[];
}

export async function submitOnboarding(
  payload: OnboardingPayload,
): Promise<{ status: string; updated_fields: string[] }> {
  const res = await fetch(`${PROXY}/api/v1/onboarding/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(
      extractDetail(body.detail, `Onboarding submit failed: ${res.status}`),
    );
  }
  return res.json() as Promise<{ status: string; updated_fields: string[] }>;
}

// ── Applications Tracking ───────────────────────────────────────────────────────

export interface ApplicationCreatePayload {
  job_id: string;
  title: string;
  company: string;
  location?: string;
  url?: string;
  status?: string;
  source?: string;
}

export interface ApplicationUpdatePayload {
  status: string;
  notes?: string;
}

export async function createApplication(
  payload: ApplicationCreatePayload,
): Promise<{ status: string; job_id: string; message: string }> {
  const res = await fetch(`${PROXY}/api/v1/applications`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(
      extractDetail(body.detail, `Create application failed: ${res.status}`),
    );
  }
  return res.json() as Promise<{
    status: string;
    job_id: string;
    message: string;
  }>;
}

export interface ManualApplicationCreatePayload {
  title: string;
  company: string;
  location?: string;
  url?: string;
  status?: string;
}

export async function createManualApplication(
  payload: ManualApplicationCreatePayload,
): Promise<{ status: string; job_id: string; message: string }> {
  const res = await fetch(`${PROXY}/api/v1/applications/manual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(
      extractDetail(
        body.detail,
        `Create manual application failed: ${res.status}`,
      ),
    );
  }
  return res.json() as Promise<{
    status: string;
    job_id: string;
    message: string;
  }>;
}

export async function updateApplication(
  jobId: string,
  payload: ApplicationUpdatePayload,
): Promise<{ status: string; job_id: string; message: string }> {
  const res = await fetch(`${PROXY}/api/v1/applications/${jobId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(
      extractDetail(body.detail, `Update application failed: ${res.status}`),
    );
  }
  return res.json() as Promise<{
    status: string;
    job_id: string;
    message: string;
  }>;
}

// ── Profile Updates ───────────────────────────────────────────────────────────

export interface ProfileUpdatePayload {
  name?: string;
  phone?: string;
  telegram_username?: string;
  target_roles?: string[];
  preferred_cities?: string[];
  salary_expectation_aed?: number;
  minimum_salary_aed?: number;
  years_experience?: number;
  current_role?: string;
  current_company?: string;
  linkedin_url?: string;
  visa_status?: string;
  notice_period?: string;
  skills?: string[];
}

export async function updateProfile(
  payload: ProfileUpdatePayload,
): Promise<{ status: string; updated_fields: string[] }> {
  const data = await requestJson<unknown>("/api/v1/rico/profile", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return validateShape(ProfileUpdateResponseSchema, data, "profile update");
}

// ── Auth Register ───────────────────────────────────────────────────────────────

export async function register(
  email: string,
  password: string,
  publicUserIdToMerge?: string | null,
  name?: string | null,
): Promise<{
  email: string;
  role: string;
  email_verification_required?: boolean;
}> {
  const body: Record<string, unknown> = { email, password };
  if (publicUserIdToMerge) {
    body.public_user_id_to_merge = publicUserIdToMerge;
  }
  if (name && name.trim()) {
    body.name = name.trim();
  }
  const res = await fetch(`${PROXY}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(
      err.detail ?? `Registration failed: ${res.status}`,
      res.status,
      err,
    );
  }
  return res.json() as Promise<{
    email: string;
    role: string;
    email_verification_required?: boolean;
  }>;
}

export async function verifyEmail(
  token: string,
): Promise<{ message: string; email: string }> {
  const res = await fetch(
    buildProxyUrl("/api/v1/auth/verify-email", { token }),
    { method: "GET", credentials: "include" },
  );
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(err.detail ?? "Verification failed", res.status, err);
  }
  return res.json() as Promise<{ message: string; email: string }>;
}

export async function resendVerification(
  email: string,
): Promise<{ message: string }> {
  const res = await fetch(`${PROXY}/api/v1/auth/resend-verification`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(err.detail ?? "Resend failed", res.status, err);
  }
  return res.json() as Promise<{ message: string }>;
}

// Public chat — no auth required. Uses session_id stored in localStorage.
export async function sendChatPublic(
  message: string,
  sessionId: string,
  signal?: AbortSignal,
  operationId?: string,
  language?: "en" | "ar",
): Promise<ChatApiResponse> {
  const body: Record<string, unknown> = {
    message,
    session_id: sessionId,
    operation_id: operationId,
  };
  if (language) body.language = language;

  const data = await requestJson<unknown>("/api/v1/rico/chat/public", {
    method: "POST",
    signal,
    body: JSON.stringify(body),
  });
  return validateShape(RicoChatResponseSchema, data, "public Rico chat");
}

// No user_id field — identity comes exclusively from the session cookie.
export async function sendChat(
  message: string,
  signal?: AbortSignal,
  operationId?: string,
  language?: "en" | "ar",
): Promise<ChatApiResponse> {
  const body: Record<string, unknown> = { message, operation_id: operationId };
  if (language) body.language = language;

  const data = await requestJson<unknown>("/api/v1/rico/chat", {
    method: "POST",
    credentials: "include",
    signal,
    body: JSON.stringify(body),
  });
  return validateShape(RicoChatResponseSchema, data, "authenticated Rico chat");
}

export interface ChatStreamEvent {
  type: "token" | "done" | "error";
  text?: string;
  response?: ChatApiResponse;
  error?: string;
}

export async function* sendChatStream(
  message: string,
  signal?: AbortSignal,
  language?: "en" | "ar",
): AsyncGenerator<ChatStreamEvent> {
  const body: Record<string, unknown> = { message };
  if (language) body.language = language;
  const res = await fetch(`${PROXY}/api/v1/rico/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    signal,
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    // Fall back gracefully — caller should use sendChat instead
    yield { type: "error", error: `${res.status}` };
    return;
  }
  yield* _readSSE(res.body);
}

export async function* sendChatStreamPublic(
  message: string,
  sessionId: string,
  signal?: AbortSignal,
  language?: "en" | "ar",
): AsyncGenerator<ChatStreamEvent> {
  const body: Record<string, unknown> = { message, session_id: sessionId };
  if (language) body.language = language;
  const res = await fetch(`${PROXY}/api/v1/rico/chat/stream/public`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    signal,
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    yield { type: "error", error: `${res.status}` };
    return;
  }
  yield* _readSSE(res.body);
}

async function* _readSSE(body: ReadableStream<Uint8Array>): AsyncGenerator<ChatStreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (!raw || raw === "[DONE]") continue;
        try {
          yield JSON.parse(raw) as ChatStreamEvent;
        } catch {
          // malformed SSE line, skip
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export interface ChatHistoryMessage {
  role: string;
  content: string;
  timestamp?: string | null;
}

export interface ChatHistoryResponse {
  messages: ChatHistoryMessage[];
  total: number;
  has_more: boolean;
}

export async function fetchChatHistory(
  limit = 20,
  before?: string,
): Promise<ChatHistoryResponse> {
  const data = await requestJson<unknown>(
    "/api/v1/rico/chat/history",
    { method: "GET" },
    { limit, before },
  );
  return validateShape(
    RicoChatHistoryResponseSchema,
    data,
    "Rico chat history",
  );
}

export async function clearChatHistory(): Promise<void> {
  await requestJson<unknown>("/api/v1/rico/chat/history", {
    method: "DELETE",
    credentials: "include",
  });
}

export async function sendAgentChat(
  data: AgentChatRequest,
): Promise<AgentUIResponse> {
  const payload = AgentChatRequestSchema.parse(data);
  const result = await requestJson<unknown>("/api/v1/agent/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  return validateShape(AgentUIResponseSchema, result, "agent chat");
}

// ── Link Verification ─────────────────────────────────────────────────────────

export interface LinkVerificationResult {
  status:
    | "live"
    | "expired"
    | "blocked"
    | "redirect"
    | "source_only"
    | "needs_review";
  http_status: number | null;
  error_message: string | null;
  verified_at: string;
  redirect_url?: string;
}

export async function verifyLink(url: string): Promise<LinkVerificationResult> {
  const data = await requestJson<LinkVerificationResult>(
    "/api/v1/links/verify",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ url }),
    },
  );
  return data;
}

export async function verifyLinkBatch(
  urls: string[],
): Promise<Record<string, LinkVerificationResult>> {
  const data = await requestJson<Record<string, LinkVerificationResult>>(
    "/api/v1/links/verify/batch",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ urls }),
    },
  );
  return data;
}

// ── Subscription ──────────────────────────────────────────────────────────────

export interface SubscriptionEntitlements {
  monthly_ai_message_limit: number | null;
  saved_jobs_limit: number | null;
  profile_optimization_limit: number | null;
  cv_storage_limit: number | null;
  other_document_limit: number | null;
  premium_recommendations_enabled: boolean;
  application_automation_enabled: boolean;
}

export interface SubscriptionPlan {
  id: string;
  plan: "pro" | "premium";
  name: string;
  price_monthly: number;
  currency: string;
  features: string[];
  entitlements: SubscriptionEntitlements;
  is_popular: boolean;
  description?: string | null;
}

export interface PlansResponse {
  plans: SubscriptionPlan[];
}

export interface UserSubscription {
  user_id: string;
  plan: "free" | "pro" | "premium";
  subscription_status: "active" | "inactive" | "past_due" | "canceled";
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at: string | null;
  canceled_at: string | null;
  entitlements: SubscriptionEntitlements;
  updated_at: string;
}

export interface SubscriptionMeResponse {
  subscription: UserSubscription;
  plan: SubscriptionPlan | null;
  is_active: boolean;
}

export interface CheckoutResponse {
  checkout_url: string;
  provider: "stripe" | "mock" | "manual";
  plan: "free" | "pro" | "premium";
  status: "ready" | "mock" | "manual";
}

export async function getSubscriptionPlans(): Promise<PlansResponse> {
  return requestJson<PlansResponse>("/api/v1/subscription/plans", {
    method: "GET",
  });
}

export async function getMySubscription(): Promise<SubscriptionMeResponse> {
  return requestJson<SubscriptionMeResponse>("/api/v1/subscription/me", {
    method: "GET",
  });
}

export async function createCheckoutSession(
  plan: "pro" | "premium",
): Promise<CheckoutResponse> {
  return requestJson<CheckoutResponse>("/api/v1/subscription/checkout", {
    method: "POST",
    body: JSON.stringify({ plan }),
  });
}

export async function createCustomerPortalSession(): Promise<CheckoutResponse> {
  return requestJson<CheckoutResponse>("/api/v1/subscription/portal", {
    method: "POST",
  });
}

// ── Apply Queue (job agent) ───────────────────────────────────────────────────

export interface ApplicationDraft {
  id: string;
  job_key: string;
  job_title: string;
  company: string;
  apply_url?: string | null;
  tailored_cv: string;
  cover_letter: string;
  status: "pending" | "approved" | "rejected";
  follow_up_at?: string | null;
  created_at: string;
}

export interface PrepareApplicationRequest {
  job_key: string;
  title: string;
  company: string;
  description?: string;
  apply_url?: string;
  location?: string;
  why?: string;
}

export async function prepareApplication(
  req: PrepareApplicationRequest,
  signal?: AbortSignal,
): Promise<ApplicationDraft> {
  return requestJson<ApplicationDraft>("/api/v1/apply/prepare", {
    method: "POST",
    body: JSON.stringify(req),
    signal,
  });
}

const MOCK_QUEUE: ApplicationDraft[] = [
  {
    id: "mock-draft-1",
    job_key: "mock-job-1",
    job_title: "Senior Sustainability Manager",
    company: "Masdar City",
    apply_url: "https://example.com/apply",
    tailored_cv: "ROBEN EDWAN\nSenior ESG & Sustainability Professional\n\nSUMMARY\nSeasoned sustainability leader with 8+ years driving environmental strategy across UAE energy and infrastructure projects. Expert in carbon accounting, ESG reporting, and ISO 14001 implementation — directly aligned with Masdar City's net-zero mandate.\n\nEXPERIENCE\n\nHead of Sustainability | ADNOC Group | 2019–2024\n• Led GHG inventory for 12 operating assets, achieving 18% Scope 1 reduction ahead of 2030 target\n• Secured ISO 14001:2015 certification across 4 facilities within 14 months\n• Authored annual ESG disclosure aligned with GRI Standards and TCFD framework\n\nEnvironmental Consultant | AECOM | 2016–2019\n• Delivered Environmental Impact Assessments for AED 2.3B infrastructure projects in Abu Dhabi\n• Developed waste management plans compliant with UAE Federal Law No. 12\n\nEDUCATION\nMSc Environmental Management | University of Sharjah | 2016\nBSc Environmental Science | Lebanese American University | 2014\n\nSKILLS\nCarbon accounting · GRI Standards · TCFD · ISO 14001 · ESG reporting · UAE regulatory compliance · Stakeholder engagement · Life cycle assessment",
    cover_letter: "Dear Hiring Manager,\n\nI am writing to express my strong interest in the Senior Sustainability Manager role at Masdar City. As the world's most ambitious sustainable urban development, Masdar represents exactly the environment where my 8 years of UAE-focused sustainability leadership can have real impact.\n\nAt ADNOC Group, I led the GHG inventory programme across 12 operating assets and delivered an 18% Scope 1 emissions reduction ahead of schedule. I also secured ISO 14001:2015 certification for four facilities in under 14 months — a track record of execution that translates directly to Masdar's net-zero commitments. My AECOM experience delivering Environmental Impact Assessments for AED 2.3B projects gives me a deep understanding of UAE regulatory frameworks and stakeholder landscapes.\n\nI would welcome the opportunity to discuss how my background aligns with Masdar City's sustainability vision.\n\nSincerely,\nRoben Edwan",
    status: "pending",
    created_at: new Date().toISOString(),
  },
  {
    id: "mock-draft-2",
    job_key: "mock-job-2",
    job_title: "ESG Analyst",
    company: "First Abu Dhabi Bank",
    apply_url: null,
    tailored_cv: "ROBEN EDWAN\nESG & Sustainability Analyst\n\nSUMMARY\nEnvironmental professional with proven experience translating sustainability data into investor-grade ESG disclosures. Skilled in SASB, GRI, and TCFD frameworks with deep understanding of UAE financial sector regulatory requirements.\n\nEXPERIENCE\n\nHead of Sustainability | ADNOC Group | 2019–2024\n• Authored annual ESG report distributed to 3,000+ institutional investors — zero material restatements over 5 years\n• Built internal ESG data management system integrating 45 operational KPIs\n• Engaged rating agencies (MSCI, Sustainalytics) to improve ESG scores by 12 points\n\nEnvironmental Consultant | AECOM | 2016–2019\n• Supported ESG due diligence for PE-backed infrastructure investments in UAE\n• Developed climate risk assessment models for AED 1.8B asset portfolio\n\nEDUCATION\nMSc Environmental Management | University of Sharjah | 2016\n\nSKILLS\nESG data analytics · GRI · SASB · TCFD · Bloomberg ESG · Investor relations · Climate risk · UAE banking regulation",
    cover_letter: "Dear Hiring Manager,\n\nFirst Abu Dhabi Bank's commitment to responsible finance and its position as the UAE's largest bank make this ESG Analyst role an exceptional opportunity to apply my sustainability expertise within a high-impact financial institution.\n\nOver five years at ADNOC Group, I built and maintained the ESG reporting infrastructure for one of the region's largest energy companies — engaging MSCI and Sustainalytics and improving composite ESG scores by 12 points. My experience translating complex operational data into investor-grade disclosures aligns directly with FAB's growing ESG reporting obligations under UAE Central Bank sustainable finance guidelines.\n\nI am confident I can contribute to FAB's ESG strategy from day one and look forward to discussing this further.\n\nSincerely,\nRoben Edwan",
    status: "pending",
    created_at: new Date(Date.now() - 3600000).toISOString(),
  },
];

export async function getApplicationQueue(
  signal?: AbortSignal,
): Promise<ApplicationDraft[]> {
  if (USE_MOCK) return MOCK_QUEUE;
  return requestJson<ApplicationDraft[]>("/api/v1/apply/queue", {
    method: "GET",
    signal,
  });
}

export async function approveApplication(
  draftId: string,
  signal?: AbortSignal,
): Promise<{ ok: boolean; status: string }> {
  return requestJson<{ ok: boolean; status: string }>(
    `/api/v1/apply/approve/${draftId}`,
    { method: "POST", signal },
  );
}

export async function rejectApplication(
  draftId: string,
  signal?: AbortSignal,
): Promise<{ ok: boolean; status: string }> {
  return requestJson<{ ok: boolean; status: string }>(
    `/api/v1/apply/reject/${draftId}`,
    { method: "DELETE", signal },
  );
}

export async function getFollowUpReminders(
  signal?: AbortSignal,
): Promise<ApplicationDraft[]> {
  if (USE_MOCK) return [];
  return requestJson<ApplicationDraft[]>("/api/v1/apply/follow-ups", {
    method: "GET",
    signal,
  });
}

export async function recordSubscriptionIntent(
  plan: string,
  billingMode: "manual" | "stripe" = "manual",
  sourcePage: string = "/subscription",
): Promise<void> {
  try {
    await requestJson("/api/v1/subscription/intent", {
      method: "POST",
      body: JSON.stringify({ plan, billing_mode: billingMode, source_page: sourcePage }),
    });
  } catch {
    // Fire-and-forget — never surface errors to the user
  }
}
