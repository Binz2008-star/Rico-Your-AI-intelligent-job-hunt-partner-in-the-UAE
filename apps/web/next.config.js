// Must match the resolution order in lib/api.ts and lib/api/client.ts.
// NEXT_PUBLIC_RICO_API is the documented production backend var (see CLAUDE.md).
// No localhost fallback: if unset, rewrites return [] (handled below), which is
// safer than silently proxying to a local process that does not exist in production.
const backendUrl =
    process.env.BACKEND_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_RICO_API;

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

    // Baseline security headers — no CSP (inline scripts in layout require nonces; deferred to a separate PR).
    async headers() {
        return [
            {
                source: "/(.*)",
                headers: [
                    { key: "X-Frame-Options", value: "DENY" },
                    { key: "X-Content-Type-Options", value: "nosniff" },
                    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
                    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
                ],
            },
        ];
    },

    // Redirect deprecated user-facing routes to /command (ChatGPT-style: chat is the app).
    // Support pages (/profile, /upload, /subscription, /flow) and auth/legal remain accessible.
    // NOTE: /flow and /applications are NOT redirected — /flow is the live Application Flow page.
    async redirects() {
        return [
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
