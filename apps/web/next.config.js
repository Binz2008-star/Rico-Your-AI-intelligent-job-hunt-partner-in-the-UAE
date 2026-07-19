// Must match the resolution order in lib/api.ts and lib/api/client.ts.
// NEXT_PUBLIC_RICO_API is the documented production backend var (see CLAUDE.md).
// No localhost fallback: if unset, rewrites return [] (handled below), which is
// safer than silently proxying to a local process that does not exist in production.
const backendUrl =
    process.env.BACKEND_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_RICO_API;

// CSP in report-only mode. Our two inline init scripts are whitelisted by their
// SHA-256 hashes (no 'unsafe-inline' needed for them). Next.js injects additional
// inline scripts that vary per build; full enforcement requires nonce-based CSP
// via Next.js middleware — flip to Content-Security-Policy once that is wired up.
// To update hashes: python3 -c "import hashlib,base64; print('sha256-' + base64.b64encode(hashlib.sha256('<script content>'.encode()).digest()).decode())"
const csp = [
    "default-src 'self'",
    // theme-init hash: sha256-e3jHsOXxdXVtROmxFsrXZluLXMJZalSnzegpELleX6Y=
    // lang-init hash:  sha256-y0eJobwms3FTv51+hvoyq6L38bxbY6yjgcfFsbD/Hmk=
    // https://cdn.paddle.com — Paddle.js v2 client SDK (loaded lazily by lib/paddle.ts)
    "script-src 'self' 'unsafe-inline' 'sha256-e3jHsOXxdXVtROmxFsrXZluLXMJZalSnzegpELleX6Y=' 'sha256-y0eJobwms3FTv51+hvoyq6L38bxbY6yjgcfFsbD/Hmk=' https://va.vercel-scripts.com https://cdn.paddle.com",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob: https:",
    // https://rico-job-automation-api.onrender.com — backend proxy (existing)
    // https://sandbox-api.paddle.com — Paddle.js SDK calls during sandbox checkout
    // https://api.paddle.com          — Paddle.js SDK calls during production checkout
    "connect-src 'self' https://rico-job-automation-api.onrender.com https://vitals.vercel-insights.com https://sandbox-api.paddle.com https://api.paddle.com",
    // https://checkout.paddle.com — Paddle overlay checkout iframe (sandbox and production share this host)
    "frame-src 'self' https://checkout.paddle.com",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'self'",
].join("; ");

/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: true,

    // Keep proxy rewrites in Next config so Vercel project envs control the backend target.
    async rewrites() {
        if (!backendUrl) return [];

        return [
            {
                source: "/proxy/:path*",
                destination: `${backendUrl}/:path*`,
            },
        ];
    },

    async headers() {
        return [
            {
                source: "/(.*)",
                headers: [
                    { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
                    { key: "X-Frame-Options", value: "DENY" },
                    { key: "X-Content-Type-Options", value: "nosniff" },
                    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
                    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
                    // Explicit scoped ACAO overrides any platform-level wildcard; same-origin BFF calls don't need CORS.
                    { key: "Access-Control-Allow-Origin", value: "https://ricohunt.com" },
                    { key: "Vary", value: "Origin" },
                    { key: "Content-Security-Policy-Report-Only", value: csp },
                ],
            },
            {
                // #1101: everything under /proxy/* carries account data (identity,
                // profile, CV/files, applications, billing). It must never be
                // storable by the browser, the Vercel CDN, or any intermediary —
                // regardless of upstream or platform defaults. Listed AFTER the
                // catch-all so these keys win where both match. Public static
                // assets and pages are untouched (this block matches /proxy/* only).
                source: "/proxy/:path*",
                headers: [
                    { key: "Cache-Control", value: "private, no-store, max-age=0" },
                    { key: "CDN-Cache-Control", value: "no-store" },
                    { key: "Vercel-CDN-Cache-Control", value: "no-store" },
                    { key: "Pragma", value: "no-cache" },
                    { key: "Vary", value: "Cookie, Authorization, Origin" },
                ],
            },
        ];
    },

    // www → apex 308 (requires www.ricohunt.com to be a Vercel domain alias for this to fire).
    // Deprecated user-facing routes redirect to /command (ChatGPT-style: chat is the app).
    // NOTE: /dashboard, /applications, and /flow are NOT redirected — /dashboard is the
    // live Shell C workspace home (Atelier migration), and /flow redirects to
    // /applications at the page level. See AI_WORKSPACE/ATELIER_FULL_SITE_MIGRATION.md §6.
    async redirects() {
        return [
            {
                source: "/:path*",
                has: [{ type: "host", value: "www.ricohunt.com" }],
                destination: "https://ricohunt.com/:path*",
                permanent: true,
            },
            { source: "/chat", destination: "/command", permanent: false },
            { source: "/jobs", destination: "/command", permanent: false },
            { source: "/signals", destination: "/command", permanent: false },
            { source: "/archive", destination: "/command", permanent: false },
            { source: "/saved-searches", destination: "/command", permanent: false },
            { source: "/orchestrate", destination: "/command", permanent: false },
        ];
    },
};

module.exports = nextConfig;
