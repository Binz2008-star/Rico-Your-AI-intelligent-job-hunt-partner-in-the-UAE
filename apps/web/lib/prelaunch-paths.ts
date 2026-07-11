const PUBLIC_EXACT_PATHS = new Set([
  "/",
  "/login",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/privacy",
  "/terms",
  "/refund-policy",
  "/faq",
  "/contact",
  "/about",
  "/robots.txt",
  "/sitemap.xml",
  "/manifest.webmanifest",
  "/favicon.ico",
  "/icon.svg",
  "/apple-touch-icon.png",
  "/opengraph-image",
]);

const PUBLIC_PREFIXES = [
  "/_next/",
  "/icons/",
  "/api/waitlist/",
  "/proxy/api/v1/waitlist/",
  "/proxy/api/v1/prelaunch/",
  "/proxy/api/v1/auth/login",
  "/proxy/api/v1/auth/logout",
  "/proxy/api/v1/auth/me",
  "/proxy/api/v1/auth/forgot-password",
  "/proxy/api/v1/auth/reset-password",
  "/proxy/api/v1/auth/verify-email",
  "/proxy/api/v1/auth/resend-verification",
];

export function isPublicDuringWaitlist(pathname: string): boolean {
  if (PUBLIC_EXACT_PATHS.has(pathname)) return true;
  return PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

export function isProxyRequest(pathname: string): boolean {
  return pathname === "/proxy" || pathname.startsWith("/proxy/");
}
