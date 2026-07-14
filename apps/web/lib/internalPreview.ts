import { notFound } from "next/navigation";

/**
 * Internal design/preview surfaces must not be publicly reachable in
 * production (finding F-4, AI_WORKSPACE/ATELIER_FULL_SITE_MIGRATION.md §7).
 *
 * Vercel sets VERCEL_ENV to "production" | "preview" | "development"; local
 * dev servers and CI builds leave it unset. Blocking only real production
 * keeps approved review access on Vercel preview deployments and in local
 * development, with robots noindex/disallow as defense in depth — not the
 * only protection.
 */
export const INTERNAL_PREVIEW_ROUTES = [
    "/design-preview",
    "/rico-preview",
    "/design-gallery",
    "/sandbox/command-primitives",
] as const;

export function isInternalPreviewBlocked(
    vercelEnv: string | undefined = process.env.VERCEL_ENV,
): boolean {
    return vercelEnv === "production";
}

/**
 * Server-component gate for internal preview pages: render the app's 404 in
 * production, no-op everywhere else. Uses notFound() — never a redirect — so
 * a redirect loop is impossible. For statically generated pages the gate runs
 * at build time on Vercel (VERCEL_ENV is set during builds), baking the 404
 * into the production deployment.
 */
export function assertInternalPreviewAccess(): void {
    if (isInternalPreviewBlocked()) {
        notFound();
    }
}
