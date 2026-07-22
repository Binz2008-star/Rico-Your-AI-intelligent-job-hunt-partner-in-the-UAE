/**
 * LOW-1 (security audit refresh 2026-07-21): validate a backend-supplied URL
 * against an https + host allowlist before navigating to it, so a compromised
 * or unexpected upstream value cannot become an open redirect.
 *
 * Returns the normalized URL string when it is https AND its host equals — or
 * is a subdomain of — an allowed host; otherwise null. A null return means the
 * caller must NOT navigate.
 *
 * The `"." + host` subdomain check is deliberate: it matches `wa.me` and
 * `api.whatsapp.com` (for allow `whatsapp.com`) while rejecting look-alikes
 * such as `evilwhatsapp.com` or `whatsapp.com.evil.com`.
 */
export function safeExternalUrl(raw: unknown, allowedHosts: string[]): string | null {
    if (typeof raw !== "string" || raw.length === 0) return null;
    let u: URL;
    try {
        u = new URL(raw);
    } catch {
        return null;
    }
    if (u.protocol !== "https:") return null;
    const host = u.hostname.toLowerCase();
    const ok = allowedHosts.some((h) => host === h || host.endsWith("." + h));
    return ok ? u.toString() : null;
}
