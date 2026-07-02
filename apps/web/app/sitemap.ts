import type { MetadataRoute } from "next";

const SITE_URL = "https://ricohunt.com";

// Public indexable pages only.
// Auth-gated and dashboard routes are excluded (blocked in robots.ts too).
export default function sitemap(): MetadataRoute.Sitemap {
    return [
        // ── Tier 1: Core acquisition pages (highest priority) ──────────────
        {
            url: `${SITE_URL}/`,
            lastModified: new Date(),
            changeFrequency: "weekly",
            priority: 1.0,
        },
        {
            url: `${SITE_URL}/jobs`,
            lastModified: new Date(),
            changeFrequency: "daily",
            priority: 0.95,
        },
        {
            url: `${SITE_URL}/signup`,
            lastModified: new Date(),
            changeFrequency: "monthly",
            priority: 0.9,
        },
        // ── Tier 2: Feature landing pages (SEO value) ──────────────────────
        {
            url: `${SITE_URL}/about`,
            lastModified: new Date(),
            changeFrequency: "monthly",
            priority: 0.8,
        },
        {
            url: `${SITE_URL}/faq`,
            lastModified: new Date(),
            changeFrequency: "monthly",
            priority: 0.75,
        },
        {
            url: `${SITE_URL}/contact`,
            lastModified: new Date(),
            changeFrequency: "yearly",
            priority: 0.6,
        },
        // ── Tier 3: Legal / compliance pages ──────────────────────────────
        {
            url: `${SITE_URL}/privacy`,
            lastModified: new Date(),
            changeFrequency: "yearly",
            priority: 0.3,
        },
        {
            url: `${SITE_URL}/terms`,
            lastModified: new Date(),
            changeFrequency: "yearly",
            priority: 0.3,
        },
        {
            url: `${SITE_URL}/refund-policy`,
            lastModified: new Date(),
            changeFrequency: "yearly",
            priority: 0.2,
        },
    ];
}
