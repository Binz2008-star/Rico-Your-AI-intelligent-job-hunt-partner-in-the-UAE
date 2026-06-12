// Must match the resolution order in lib/api.ts and lib/api/client.ts.
// NEXT_PUBLIC_RICO_API is the documented production backend var (see CLAUDE.md).
// No localhost fallback: if unset, rewrites return [] (handled below), which is
// safer than silently proxying to a local process that does not exist in production.
const backendUrl =
    process.env.BACKEND_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_RICO_API;

// CSP enforced. Inline scripts in layout.tsx (theme + lang init) are locked to
// their SHA-256 hashes so 'unsafe-inline' is not needed.
// To update hashes: python3 -c "import hashlib,base64; print('sha256-' + base64.b64encode(hashlib.sha256('<script content>'.encode()).digest()).decode())"
const csp = [
    "default-src 'self'",
    // theme-init hash: sha256-e3jHsOXxdXVtROmxFsrXZluLXMJZalSnzegpELleX6Y=
    // lang-init hash:  sha256-y0eJobwms3FTv51+hvoyq6L38bxbY6yjgcfFsbD/Hmk=
    "script-src 'self' 'sha256-e3jHsOXxdXVtROmxFsrXZluLXMJZalSnzegpELleX6Y=' 'sha256-y0eJobwms3FTv51+hvoyq6L38bxbY6yjgcfFsbD/Hmk=' https://va.vercel-scripts.com",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob: https:",
    "connect-src 'self' https://rico-job-automation-api.onrender.com https://vitals.vercel-insights.com",
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
                    { key: "X-Frame-Options", value: "DENY" },
                    { key: "X-Content-Type-Options", value: "nosniff" },
                    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
                    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
                    // Explicit scoped ACAO overrides any platform-level wildcard; same-origin BFF calls don't need CORS.
                    { key: "Access-Control-Allow-Origin", value: "https://ricohunt.com" },
                    { key: "Vary", value: "Origin" },
                    { key: "Content-Security-Policy", value: csp },
                ],
            },
        ];
    },

    // www → apex 308 (requires www.ricohunt.com to be a Vercel domain alias for this to fire).
    // Deprecated user-facing routes redirect to /command (ChatGPT-style: chat is the app).
    // NOTE: /flow and /applications are NOT redirected — /flow is the live Application Flow page.
    async redirects() {
        return [
            {
                source: "/:path*",
                has: [{ type: "host", value: "www.ricohunt.com" }],
                destination: "https://ricohunt.com/:path*",
                permanent: true,
            },
            { source: "/chat", destination: "/command", permanent: false },
            { source: "/dashboard", destination: "/command", permanent: false },
            { source: "/jobs", destination: "/command", permanent: false },
            { source: "/signals", destination: "/command", permanent: false },
            { source: "/archive", destination: "/command", permanent: false },
            { source: "/saved-searches", destination: "/command", permanent: false },
            { source: "/onboarding", destination: "/command", permanent: false },
            { source: "/orchestrate", destination: "/command", permanent: false },
        ];
    },
};

module.exports = nextConfig;
