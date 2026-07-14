import type { MetadataRoute } from "next";

const SITE_URL = "https://ricohunt.com";

export default function robots(): MetadataRoute.Robots {
    return {
        rules: [
            {
                // Default: allow crawl of all public pages
                userAgent: "*",
                allow: ["/", "/jobs", "/about", "/faq", "/contact", "/signup", "/login", "/privacy", "/terms", "/refund-policy"],
                disallow: [
                    "/command",
                    "/dashboard",
                    "/profile",
                    "/settings",
                    "/applications",
                    "/flow",
                    "/upload",
                    "/subscription",
                    "/queue",
                    "/admin",
                    "/sandbox",
                    "/design-gallery",
                    "/design-preview",
                    "/rico-preview",
                    "/orchestrate",
                    "/signals",
                    "/archive",
                    "/onboarding",
                    "/verify-email",
                    "/reset-password",
                    "/forgot-password",
                    "/api/",
                ],
            },
            {
                // Prevent AI training crawlers from indexing content
                userAgent: ["GPTBot", "Google-Extended", "CCBot", "anthropic-ai", "Claude-Web"],
                disallow: "/",
            },
        ],
        sitemap: `${SITE_URL}/sitemap.xml`,
        host: SITE_URL,
    };
}
