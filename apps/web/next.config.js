/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Proxy all client-side /proxy/* requests through the Next.js server so that
  // the session cookie is set and sent as a first-party (same-origin) cookie.
  // This avoids Chrome's third-party cookie blocking when the frontend and the
  // backend API are on different origins (e.g. localhost:3001 vs onrender.com).
  async rewrites() {
    const api =
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      process.env.NEXT_PUBLIC_RICO_API ||
      "http://localhost:8000";
    return [
      { source: "/proxy/api/:path*", destination: `${api}/api/:path*` },
      { source: "/proxy/health",     destination: `${api}/health` },
    ];
  },
};

module.exports = nextConfig;
