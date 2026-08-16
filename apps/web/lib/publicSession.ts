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

/**
 * Return the guest identity label ONLY when a guest session already exists on
 * this browser (a `rico_sid` was minted earlier). Returns null otherwise.
 *
 * This is the identity to hand to the authenticated login/register flows so the
 * backend can MERGE the guest's data into the new account. The merge itself is
 * server-authoritative: it only succeeds when the HttpOnly `rico_guest_proof`
 * capability cookie proves this browser owns that guest session. We deliberately
 * do NOT mint a session here — logging in must not invent a guest identity that
 * would then claim (and fail, or worse) a merge that never existed.
 */
export function getExistingPublicUserId(): string | null {
    if (typeof window === "undefined") return null;
    const sid = window.localStorage.getItem(STORAGE_KEY);
    if (!sid) return null;
    return `public:${sid}`;
}
