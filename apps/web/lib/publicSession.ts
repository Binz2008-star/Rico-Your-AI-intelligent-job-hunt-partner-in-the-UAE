/**
 * publicSession — the guest CORRELATION id (#1070, locked design).
 *
 * Authorization for guest sessions lives exclusively in the server-minted,
 * signed, HttpOnly `rico_guest_proof` capability cookie. The value stored in
 * localStorage (`rico_sid`) is correlation-only: it labels requests for
 * logging only. The server-authoritative sid is NEVER disclosed to
 * JavaScript — it exists only inside the HttpOnly cookie — so this value
 * carries ZERO authorization meaning and never has to match it.
 *
 * Minting is CSPRNG-only (no Date.now/Math.random path): even a correlation
 * id must not be guessable enough to invite probing. There is deliberately no
 * automatic rotate-and-retry: capability failures (403
 * guest_capability_invalid, 503 guest_capability_unavailable) surface as
 * errors and stay observable — the server clears an invalid cookie itself and
 * the next request transparently starts a fresh identity.
 */

const STORAGE_KEY = "rico_sid";

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

/** Return the stored correlation id, minting one (CSPRNG) if absent. */
export function ensurePublicSessionId(): string {
    let sid = window.localStorage.getItem(STORAGE_KEY);
    if (!sid) {
        sid = mintSessionId();
        window.localStorage.setItem(STORAGE_KEY, sid);
    }
    return sid;
}

/** Canonical guest identity label for upload/confirm flows (correlation-only). */
export function getPublicUserId(): string {
    return `public:${ensurePublicSessionId()}`;
}
