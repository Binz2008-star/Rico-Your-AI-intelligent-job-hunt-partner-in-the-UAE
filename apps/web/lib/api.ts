const RICO_API =
  process.env.NEXT_PUBLIC_RICO_API ??
  "https://rico-job-automation-api.onrender.com";

export interface RicoStatus {
  ready_for_api: boolean;
  ready_for_db: boolean;
  ready_for_telegram: boolean;
  ready_for_openai: boolean;
  ready_for_jotform: boolean;
}

export interface HealthResponse {
  status: string;
  db: string;
  version: string;
  rico: RicoStatus;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${RICO_API}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json() as Promise<HealthResponse>;
}

export interface LoginResponse {
  message: string;
  email: string;
}

export async function login(
  email: string,
  password: string
): Promise<LoginResponse> {
  const res = await fetch(`${RICO_API}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? "Login failed");
  }
  return res.json() as Promise<LoginResponse>;
}

export async function logout(): Promise<void> {
  await fetch(`${RICO_API}/api/v1/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

// No user_id field — identity comes exclusively from the session cookie.
export async function sendChat(
  message: string
): Promise<{ reply?: string; message?: string }> {
  const res = await fetch(`${RICO_API}/api/v1/rico/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error(`Chat failed: ${res.status}`);
  return res.json() as Promise<{ reply?: string; message?: string }>;
}
