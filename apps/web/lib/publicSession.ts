/**
 * publicSession — the ONE place a guest session id is minted (#1070).
 *
 * The public session id (`rico_sid`) names the guest's temporary profile,
 * uploaded-document OCR text, and chat history, so it must be unguessable and
 * CSPRNG-generated on every path. The server additionally binds the session to
 * this browser with a signed HttpOnly proof cookie (`rico_guest_proof`): the
 * id string alone is NOT a bearer credential. If the server rejects a session
 * as unverified (403 `guest_session_unverified` — e.g. the id leaked to, or
 * was minted by, another browser), callers rotate to a fresh id with
 * `rotatePublicSessionId()` and continue as a new guest.
 *
 * There is deliberately NO Math.random/Date.now fallback: every production
 * runtime (browsers, jsdom, Node 20) provides Web Crypto.
 */

const STORAGE_KEY = "rico_sid";

/** Server error code for an unproved claim over an existing guest session. */
export const GUEST_SESSION_UNVERIFIED = "guest_session_unverified";

function mintSessionId(): string {
    if (typeof crypto === "undefined" || (!crypto.randomUUID && !crypto.getRandomValues)) {
        throw new Error("Web Crypto is unavailable — cannot mint a guest session id");
    }
    const rnd = crypto.randomUUID
        ? crypto.randomUUID()
        : Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) =>
              b.toString(16).padStart(2, "0"),
          ).join("");
    // "web-" + uuid (40 chars) stays within the server's ^[A-Za-z0-9_-]{8,64}$ rule.
    return `web-${rnd}`;
}

/** Return the stored guest session id, minting one (CSPRNG) if absent. */
export function ensurePublicSessionId(): string {
    let sid = window.localStorage.getItem(STORAGE_KEY);
    if (!sid) {
        sid = mintSessionId();
        window.localStorage.setItem(STORAGE_KEY, sid);
    }
    return sid;
}

/** Discard the current guest session id and mint a fresh one. */
export function rotatePublicSessionId(): string {
    const sid = mintSessionId();
    window.localStorage.setItem(STORAGE_KEY, sid);
    return sid;
}

/** Canonical guest identity for upload/confirm flows. */
export function getPublicUserId(): string {
    return `public:${ensurePublicSessionId()}`;
}

/** True when an error body carries the guest-session-unverified code. */
export function isGuestSessionUnverified(errorData: unknown): boolean {
    if (!errorData || typeof errorData !== "object") return false;
    const detail = (errorData as { detail?: unknown }).detail;
    if (!detail || typeof detail !== "object") return false;
    return (detail as { code?: unknown }).code === GUEST_SESSION_UNVERIFIED;
}
