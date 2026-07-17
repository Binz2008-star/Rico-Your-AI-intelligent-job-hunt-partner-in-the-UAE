import type { MutableRefObject } from "react";

import { ensurePublicSessionId } from "@/lib/publicSession";

/**
 * Resolve (and lazily mint) the public chat session id.
 *
 * Minting is centralized in lib/publicSession (CSPRNG-only, #1070); this
 * wrapper keeps the ref-based API the command page uses. It re-reads storage
 * on every call so a rotation (after a 403 guest_session_unverified) is
 * picked up even while the ref still holds the retired id.
 */
export function ensureSessionId(sessionIdRef: MutableRefObject<string | null>): string {
    if (typeof window === "undefined") return sessionIdRef.current || "ssr-session";
    const sid = ensurePublicSessionId();
    sessionIdRef.current = sid;
    return sid;
}

export function getSessionId(sessionIdRef: MutableRefObject<string | null>): string {
    return ensureSessionId(sessionIdRef);
}
