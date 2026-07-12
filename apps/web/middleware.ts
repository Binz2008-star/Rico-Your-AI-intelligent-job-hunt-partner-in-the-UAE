import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

/**
 * Teaser gate.
 *
 * While the product is still under development, the public should see ONLY the
 * launch film (teaser) at /explainer — not the unfinished app. This middleware
 * redirects every page route to the teaser, while keeping the doors people need
 * (the film itself, sign-up / sign-in, password reset) open.
 *
 * Teaser mode is ON by default. To open the full site to the public later, set
 *   NEXT_PUBLIC_SITE_LIVE=true
 * in the Vercel project's Environment Variables and redeploy. No code change.
 *
 * Static files (anything with a file extension, e.g. /explainer/option-3.html,
 * images, fonts), Next internals (/_next), and API/proxy routes are excluded by
 * the matcher below, so they always pass through untouched.
 */

const SITE_LIVE = process.env.NEXT_PUBLIC_SITE_LIVE === 'true'

// Page routes that must stay reachable even while the teaser gate is on.
const ALLOW = [
  '/explainer',        // the teaser film itself
  '/signup',           // capture new users
  '/login',
  '/forgot-password',
  '/reset-password',
]

export function middleware(req: NextRequest) {
  // Full site open — do nothing.
  if (SITE_LIVE) return NextResponse.next()

  const { pathname } = req.nextUrl

  const allowed = ALLOW.some(
    (p) => pathname === p || pathname.startsWith(p + '/'),
  )
  if (allowed) return NextResponse.next()

  // Everything else → the teaser film.
  const url = req.nextUrl.clone()
  url.pathname = '/explainer/'
  url.search = ''
  return NextResponse.redirect(url)
}

export const config = {
  // Run on page routes only: skip Next internals, API/proxy, and any file
  // request (paths containing a dot), so static assets and the film's .html
  // files are served directly.
  matcher: ['/((?!_next/|api/|proxy/|.*\\.).*)'],
}
