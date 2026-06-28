import { LanguageProvider } from "@/contexts/LanguageContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { Analytics } from "@vercel/analytics/next";
import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Inter, Space_Grotesk } from "next/font/google";
import Script from "next/script";
import "./globals.css";

// No-flash theme script: runs before paint to apply the stored theme class so a
// light-mode user never sees a dark flash (and vice-versa). Mirrors ThemeContext:
// default "dark", "system" honoured only if explicitly chosen. Kept tiny + inline.
const themeInitScript = `(function(){try{var t=localStorage.getItem("rico-theme");var m=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";var r=(t==="light"||t==="dark")?t:(t==="system"?m:"dark");var e=document.documentElement;e.classList.remove("dark","light");e.classList.add(r);e.setAttribute("data-theme",r);}catch(_){}})();`;

// No-flash language script: mirrors LanguageContext — sets lang/dir on <html> before
// React hydrates so Arabic users never see an LTR flash on page load or refresh.
const langInitScript = `(function(){try{var l=localStorage.getItem("rico-language");if(l==="ar"){var e=document.documentElement;e.lang="ar";e.dir="rtl";}}catch(_){}})();`;

// Nocturne type system: Space Grotesk (display) + Inter (body) + IBM Plex Mono (labels/data)
const spaceGrotesk = Space_Grotesk({
    subsets: ["latin"],
    weight: ["400", "500", "600", "700"],
    variable: "--font-display",
    display: "swap",
});

const inter = Inter({
    subsets: ["latin"],
    weight: ["400", "500", "600"],
    variable: "--font-body",
    display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
    subsets: ["latin"],
    weight: ["400", "500", "600"],
    variable: "--font-mono",
    display: "swap",
});

const SITE_URL = "https://ricohunt.com";
const OG_IMAGE = `${SITE_URL}/opengraph-image`;

export const metadata: Metadata = {
    metadataBase: new URL(
        process.env.NEXT_PUBLIC_APP_URL ||
        process.env.NEXT_PUBLIC_SITE_URL ||
        SITE_URL
    ),
    title: "Rico Hunt — AI Career Operating System for the UAE",
    description:
        "Rico Hunt helps professionals in the UAE manage their entire job search with AI — from CV analysis and job matching to application tracking, follow-ups, and interview preparation.",
    alternates: {
        canonical: "/",
    },
    openGraph: {
        title: "Rico Hunt — AI Career Operating System for the UAE",
        description:
            "Rico Hunt helps professionals in the UAE manage their entire job search with AI — from CV analysis and job matching to application tracking, follow-ups, and interview preparation.",
        url: `${SITE_URL}/`,
        siteName: "Rico Hunt",
        type: "website",
        images: [
            {
                url: OG_IMAGE,
                width: 1200,
                height: 630,
                alt: "Rico Hunt — AI Career Operating System for the UAE",
            },
        ],
    },
    twitter: {
        card: "summary_large_image",
        title: "Rico Hunt — AI Career Operating System for the UAE",
        description:
            "Rico Hunt helps professionals in the UAE manage their entire job search with AI — from CV analysis and job matching to application tracking, follow-ups, and interview preparation.",
        images: [OG_IMAGE],
    },
    icons: {
        icon: [
            { url: "/favicon.ico", sizes: "any" },
            { url: "/icon.svg", type: "image/svg+xml" },
        ],
        apple: "/apple-touch-icon.png",
    },
};

// viewport-fit=cover is required for env(safe-area-inset-*) to resolve on notched /
// installed-PWA devices; the floating navs and command input rely on it.
export const viewport: Viewport = {
    width: "device-width",
    initialScale: 1,
    viewportFit: "cover",
    themeColor: "#06060c",
};

// JSON-LD structured data: Organization + WebSite + SoftwareApplication
const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "Organization",
            "@id": `${SITE_URL}/#organization`,
            name: "Rico Hunt",
            url: SITE_URL,
            logo: {
                "@type": "ImageObject",
                url: `${SITE_URL}/icon.svg`,
            },
            sameAs: [],
            contactPoint: {
                "@type": "ContactPoint",
                contactType: "customer support",
                areaServed: "AE",
                availableLanguage: ["English", "Arabic"],
            },
        },
        {
            "@type": "WebSite",
            "@id": `${SITE_URL}/#website`,
            url: SITE_URL,
            name: "Rico Hunt",
            description:
                "AI Career Operating System for professionals in the UAE — CV analysis, job matching, application tracking, follow-ups, and interview preparation.",
            publisher: { "@id": `${SITE_URL}/#organization` },
            potentialAction: {
                "@type": "SearchAction",
                target: {
                    "@type": "EntryPoint",
                    urlTemplate: `${SITE_URL}/jobs?q={search_term_string}`,
                },
                "query-input": "required name=search_term_string",
            },
            inLanguage: ["en", "ar"],
        },
        {
            "@type": "SoftwareApplication",
            "@id": `${SITE_URL}/#app`,
            name: "Rico Hunt",
            url: SITE_URL,
            applicationCategory: "BusinessApplication",
            operatingSystem: "Web",
            description:
                "Rico Hunt helps professionals in the UAE manage their entire job search with AI — from CV analysis and job matching to application tracking, follow-ups, and interview preparation.",
            offers: {
                "@type": "Offer",
                price: "0",
                priceCurrency: "AED",
            },
            publisher: { "@id": `${SITE_URL}/#organization` },
            availableOnDevice: "Desktop, Mobile",
            inLanguage: ["en", "ar"],
            areaServed: {
                "@type": "Country",
                name: "United Arab Emirates",
            },
        },
    ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" className="dark" suppressHydrationWarning>
            <head>
                <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
                <script dangerouslySetInnerHTML={{ __html: langInitScript }} />
                <link
                    rel="stylesheet"
                    href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap"
                />
            </head>
            <body className={`${spaceGrotesk.variable} ${inter.variable} ${ibmPlexMono.variable} antialiased bg-background text-text-primary font-body overflow-x-hidden`}>
                <Script
                    id="json-ld-root"
                    type="application/ld+json"
                    strategy="beforeInteractive"
                    dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
                />
                <ThemeProvider><LanguageProvider>{children}</LanguageProvider></ThemeProvider>
                <Analytics />
            </body>
        </html>
    );
}
