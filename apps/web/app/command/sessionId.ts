import type { MutableRefObject } from "react";

import { ensurePublicSessionId } from "@/lib/publicSession";

/**
 * Resolve (and lazily mint) the public chat CORRELATION id.
 *
 * Minting is centralized in lib/publicSession (CSPRNG-only, #1070); this
 * wrapper keeps the ref-based API the command page uses and re-reads storage
 * on every call. Authorization lives in the server's HttpOnly capability
 * cookie; the server-authoritative sid is never disclosed to JavaScript and
 * this correlation id never has to match it.
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
