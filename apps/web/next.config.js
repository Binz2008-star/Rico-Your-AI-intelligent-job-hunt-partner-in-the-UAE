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
};

module.exports = nextConfig;
