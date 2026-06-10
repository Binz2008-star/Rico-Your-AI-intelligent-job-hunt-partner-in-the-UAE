import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
    return {
        rules: {
            userAgent: "*",
            allow: "/",
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
            ],
        },
        sitemap: "https://ricohunt.com/sitemap.xml",
    };
}
