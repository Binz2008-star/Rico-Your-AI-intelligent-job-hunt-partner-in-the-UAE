"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";

/**
 * Guard hook for authenticated-only account pages.
 *
 * Wraps the existing session-cookie `useAuth()` (which validates identity via
 * `GET /api/v1/me`). Once the session check has *resolved* (`ready`), a guest is
 * redirected to `/login?next=<encoded current path>`.
 *
 * Consumers render a neutral loading state (e.g. <AuthGate/>) until `authorized`
 * is true, so the private AppShell never renders for a guest and — because
 * `authorized` gates data loading — no private API request fires before an
 * authenticated identity is confirmed.
 *
 * This changes NO backend behavior (cookies / JWT / /me / logout are untouched)
 * and does not affect public routes (e.g. /command) or /onboarding, which do not
 * use this hook.
 */
export function useRequireAuth() {
  const { user, ready, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const authorized = ready && !!user;

  useEffect(() => {
    if (ready && !user) {
      const path = pathname || "/";
      router.replace(`/login?next=${encodeURIComponent(path)}`);
    }
  }, [ready, user, pathname, router]);

  return { user, ready, authorized, logout };
}
