// Must match the resolution order in lib/api.ts and lib/api/client.ts.
// NEXT_PUBLIC_RICO_API is the documented production backend var (see CLAUDE.md);
// omitting it here made the /proxy rewrite fall back to localhost in production,
// which silently broke every client-side API call (chat, /me, jobs, …).
const backendUrl =
    process.env.BACKEND_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_RICO_API ||
    "http://localhost:8000";

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

    // Redirect deprecated user-facing routes to /command (ChatGPT-style: chat is the app).
    // Support pages (/profile, /upload, /subscription) and auth/legal remain accessible.
    async redirects() {
        return [
            { source: "/chat", destination: "/command", permanent: false },
            { source: "/dashboard", destination: "/command", permanent: false },
            { source: "/jobs", destination: "/command", permanent: false },
            { source: "/flow", destination: "/command", permanent: false },
            { source: "/applications", destination: "/command", permanent: false },
            { source: "/signals", destination: "/command", permanent: false },
            { source: "/archive", destination: "/command", permanent: false },
            { source: "/saved-searches", destination: "/command", permanent: false },
            { source: "/onboarding", destination: "/command", permanent: false },
            { source: "/orchestrate", destination: "/command", permanent: false },
            { source: "/settings", destination: "/profile", permanent: false },
        ];
    },
};

module.exports = nextConfig;
