import type { MutableRefObject } from "react";

/**
 * Resolve (and lazily mint) the public chat session id.
 *
 * This id is the bearer token guarding a public session's uploaded-document OCR
 * text and chat history, so it must be unguessable. We generate it with a CSPRNG
 * — `crypto.randomUUID` when available, else `crypto.getRandomValues` — keeping
 * the `web-` prefix within the server's `^[A-Za-z0-9_-]{8,64}$` constraint
 * (uuid hex + hyphens qualify; `web-` + 36-char uuid = 40 chars). `Math.random`
 * is only a last-resort dev fallback when no Web Crypto is present.
 */
export function ensureSessionId(sessionIdRef: MutableRefObject<string | null>): string {
    if (typeof window === "undefined") return sessionIdRef.current || "ssr-session";
    if (!sessionIdRef.current) {
        let sid = localStorage.getItem("rico_sid");
        if (!sid) {
            const rnd = (typeof crypto !== "undefined" && crypto.randomUUID)
                ? crypto.randomUUID()
                : (typeof crypto !== "undefined" && crypto.getRandomValues)
                    ? Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, "0")).join("")
                    : Date.now().toString(36) + Math.random().toString(36).slice(2, 10); // last-resort dev fallback
            sid = "web-" + rnd;
            localStorage.setItem("rico_sid", sid);
        }
        sessionIdRef.current = sid;
    }
    return sessionIdRef.current;
}

export function getSessionId(sessionIdRef: MutableRefObject<string | null>): string {
    return ensureSessionId(sessionIdRef);
}
