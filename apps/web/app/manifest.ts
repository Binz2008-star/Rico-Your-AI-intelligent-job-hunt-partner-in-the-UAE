import { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
    return {
        name: "Rico Hunt \u2014 AI Career Operating System",
        short_name: "Rico Hunt",
        description:
            "Manage your entire UAE job search with AI \u2014 CV analysis, job matching, application tracking, follow-ups, and interview preparation.",
        start_url: "/command",
        scope: "/",
        display: "standalone",
        orientation: "portrait",
        theme_color: "#06060c",
        background_color: "#06060c",
        categories: ["business", "productivity", "utilities"],
        lang: "en",
        dir: "ltr",
        icons: [
            {
                src: "/icons/icon-192.png",
                sizes: "192x192",
                type: "image/png",
                purpose: "any",
            },
            {
                src: "/icons/icon-512.png",
                sizes: "512x512",
                type: "image/png",
                purpose: "any",
            },
            {
                src: "/icons/icon-192.png",
                sizes: "192x192",
                type: "image/png",
                purpose: "maskable",
            },
            {
                src: "/icons/icon-512.png",
                sizes: "512x512",
                type: "image/png",
                purpose: "maskable",
            },
        ],
        screenshots: [
            {
                src: "/screenshots/desktop.png",
                sizes: "1280x800",
                type: "image/png",
                // @ts-expect-error: form_factor is valid PWA manifest field not yet typed by Next.js
                form_factor: "wide",
                label: "Rico Hunt Desktop \u2014 Job command centre",
            },
            {
                src: "/screenshots/mobile.png",
                sizes: "390x844",
                type: "image/png",
                label: "Rico Hunt Mobile \u2014 Track applications on the go",
            },
        ],
        shortcuts: [
            {
                name: "Browse Jobs",
                url: "/jobs",
                description: "Search and browse UAE job listings",
            },
            {
                name: "Command Centre",
                url: "/command",
                description: "Open Rico AI command centre",
            },
        ],
    };
}
