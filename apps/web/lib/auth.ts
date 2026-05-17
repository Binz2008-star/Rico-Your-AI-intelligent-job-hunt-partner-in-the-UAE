/**
 * Session-cookie auth helpers.
 * Identity comes from the HTTP-only session cookie set by the backend.
 * No localStorage tokens — this avoids XSS token theft.
 */

export interface StoredUser {
  user_id: string;
  name: string;
  email: string;
}

/** HTTP-only cookies are not readable in the browser. Validate with fetchMe(). */
export function isAuthenticated(): boolean {
  return false;
}

/** Call backend logout to clear the session cookie. */
export async function clearAuth(): Promise<void> {
  await fetch("/proxy/api/v1/auth/logout", {
    method: "POST",
    credentials: "include",
  });
}

/** Placeholder — use fetchMe() from lib/api.ts for live user data. */
export function getStoredUser(): StoredUser | null {
  return null;
}
