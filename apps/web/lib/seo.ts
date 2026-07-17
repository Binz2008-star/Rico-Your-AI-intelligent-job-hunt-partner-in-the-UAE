import type { Metadata } from "next";

/**
 * Route-level noindex for authenticated / internal app surfaces (#1064).
 *
 * `robots.ts` declares crawl intent, but a robots *disallow* is not a reliable
 * noindex signal — a URL can still be indexed (without a snippet) if linked
 * externally. This route-level directive tells any crawler that does fetch the
 * page not to index it. Apply it via a minimal pass-through `layout.tsx` on
 * internal routes whose `page.tsx` is a client component (client pages cannot
 * export `metadata` themselves).
 */
export const noindexMetadata: Metadata = {
    robots: {
        index: false,
        follow: false,
        googleBot: { index: false, follow: false },
    },
};
