/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // NEXT_PUBLIC_RICO_API is read at build time for client bundles and at
  // runtime for server components. Set it in .env.local for dev.
}

module.exports = nextConfig
