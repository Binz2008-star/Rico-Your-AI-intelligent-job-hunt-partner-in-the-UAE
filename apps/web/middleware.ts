import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { isWaitlistMode } from "./lib/launch-mode";
import { isProxyRequest, isPublicDuringWaitlist } from "./lib/prelaunch-paths";

function backendBaseUrl(): string {
  return (
    process.env.BACKEND_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_RICO_API ||
    ""
  ).replace(/\/$/, "");
}

function redirectToWaitlist(request: NextRequest) {
  const destination = request.nextUrl.clone();
  destination.pathname = "/";
  destination.search = "";
  return NextResponse.redirect(destination);
}

export async function middleware(request: NextRequest) {
  if (!isWaitlistMode()) return NextResponse.next();

  const { pathname } = request.nextUrl;
  if (isPublicDuringWaitlist(pathname)) return NextResponse.next();

  // The FastAPI launch gate is the authority for proxy/API requests, including
  // direct Render access. Do not duplicate its endpoint policy here.
  if (isProxyRequest(pathname)) return NextResponse.next();

  const token = request.cookies.get("access_token")?.value;
  if (!token) return redirectToWaitlist(request);

  const backend = backendBaseUrl();
  if (!backend) return redirectToWaitlist(request);

  try {
    const response = await fetch(`${backend}/api/v1/prelaunch/access`, {
      method: "GET",
      headers: {
        cookie: `access_token=${encodeURIComponent(token)}`,
        accept: "application/json",
      },
      cache: "no-store",
    });

    if (!response.ok) return redirectToWaitlist(request);
    const decision = (await response.json()) as { allowed?: boolean };
    return decision.allowed === true
      ? NextResponse.next()
      : redirectToWaitlist(request);
  } catch {
    // Fail closed in waitlist mode. Public landing/support/auth-recovery paths
    // above remain reachable during a backend incident.
    return redirectToWaitlist(request);
  }
}

export const config = {
  matcher: ["/((?!_next/static|_next/image).*)"],
};
