import type { MetadataRoute } from "next";
import { POSTS } from "@/lib/blog/posts";

const SITE_URL = "https://ricohunt.com";

// Stable content-review date. Using a fixed date (not `new Date()`) keeps <lastmod>
// from advancing on every sitemap generation, which would otherwise falsely signal
// that unchanged pages were modified on every build. Bump when content changes. (#1064)
const LAST_UPDATED = new Date("2026-07-16T00:00:00.000Z");

// Public indexable pages only.
// Auth-gated and dashboard routes are excluded (blocked in robots.ts too).
export default function sitemap(): MetadataRoute.Sitemap {
    return [
        // ── Tier 1: Core acquisition pages (highest priority) ──────────────
        {
            url: `${SITE_URL}/`,
            lastModified: LAST_UPDATED,
            changeFrequency: "weekly",
            priority: 1.0,
        },
        {
            url: `${SITE_URL}/signup`,
            lastModified: LAST_UPDATED,
            changeFrequency: "monthly",
            priority: 0.9,
        },
        // ── Tier 2: Feature landing pages (SEO value) ──────────────────────
        {
            url: `${SITE_URL}/about`,
            lastModified: LAST_UPDATED,
            changeFrequency: "monthly",
            priority: 0.8,
        },
        {
            url: `${SITE_URL}/faq`,
            lastModified: LAST_UPDATED,
            changeFrequency: "monthly",
            priority: 0.75,
        },
        {
            url: `${SITE_URL}/contact`,
            lastModified: LAST_UPDATED,
            changeFrequency: "yearly",
            priority: 0.6,
        },
        // ── Tier 2b: Career-guide content (organic acquisition) ───────────
        {
            url: `${SITE_URL}/blog`,
            lastModified: LAST_UPDATED,
            changeFrequency: "weekly",
            priority: 0.8,
        },
        ...POSTS.map((post) => ({
            url: `${SITE_URL}/blog/${post.slug}`,
            lastModified: new Date(post.dateModified),
            changeFrequency: "monthly" as const,
            priority: 0.7,
        })),
        // ── Tier 3: Legal / compliance pages ──────────────────────────────
        {
            url: `${SITE_URL}/privacy`,
            lastModified: LAST_UPDATED,
            changeFrequency: "yearly",
            priority: 0.3,
        },
        {
            url: `${SITE_URL}/terms`,
            lastModified: LAST_UPDATED,
            changeFrequency: "yearly",
            priority: 0.3,
        },
        {
            url: `${SITE_URL}/refund-policy`,
            lastModified: LAST_UPDATED,
            changeFrequency: "yearly",
            priority: 0.2,
        },
    ];
}
