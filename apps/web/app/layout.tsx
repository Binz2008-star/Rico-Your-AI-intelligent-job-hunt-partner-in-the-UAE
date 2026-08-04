import { LanguageProvider } from "@/contexts/LanguageContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { Analytics } from "@vercel/analytics/next";
import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Inter, Space_Grotesk } from "next/font/google";
import { headers } from "next/headers";
import Script from "next/script";
import "./globals.css";

// Vercel Analytics is only rendered when running on Vercel.
// On Cloudflare Workers (or other platforms) the script beacon would point
// to va.vercel-scripts.com / vitals.vercel-insights.com with no receiver,
// adding unnecessary external requests and CSP surface.
const isVercel = !!process.env.NEXT_PUBLIC_VERCEL_ENV || !!process.env.VERCEL;

// Resolve the canonical site URL dynamically so that staging deployments
// (e.g. rico-web.loyal-ro.workers.dev) don't emit canonical/OG URLs pointing
// to the production apex. On Vercel, NEXT_PUBLIC_VERCEL_URL is used; otherwise
// the request Host header is read. Falls back to the production URL.
async function resolveSiteUrl(): Promise<string> {
    if (process.env.NEXT_PUBLIC_APP_URL || process.env.NEXT_PUBLIC_SITE_URL) {
        return process.env.NEXT_PUBLIC_APP_URL || process.env.NEXT_PUBLIC_SITE_URL!;
    }
    if (process.env.NEXT_PUBLIC_VERCEL_URL) {
        return `https://${process.env.NEXT_PUBLIC_VERCEL_URL}`;
    }
    try {
        const hdrs = await headers();
        const host = hdrs.get("x-forwarded-host") || hdrs.get("host");
        if (host) {
            const proto = hdrs.get("x-forwarded-proto") || "https";
            return `${proto}://${host}`;
        }
    } catch {
        // headers() called outside request scope — fall through to default
    }
    return DEFAULT_SITE_URL;
}

const themeInitScript = `(function(){try{var t=localStorage.getItem("rico-theme");var m=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";var r=(t==="light"||t==="dark")?t:(t==="system"?m:"dark");var e=document.documentElement;e.classList.remove("dark","light");e.classList.add(r);e.setAttribute("data-theme",r);}catch(_){}})();`;
const langInitScript = `(function(){try{var l=localStorage.getItem("rico-language");if(l==="ar"){var e=document.documentElement;e.lang="ar";e.dir="rtl";}}catch(_){}})();`;

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

const DEFAULT_SITE_URL = "https://ricohunt.com";

export async function generateMetadata(): Promise<Metadata> {
    const siteUrl = await resolveSiteUrl();
    const ogImage = `${siteUrl}/opengraph-image`;
    return {
        metadataBase: new URL(siteUrl),
        title: {
            default: "Rico Hunt \u2014 AI Career Operating System for the UAE",
            template: "%s | Rico Hunt",
        },
        description:
            "Rico Hunt helps professionals in the UAE manage their entire job search with AI \u2014 from CV analysis and job matching to application tracking, follow-ups, and interview preparation.",
        // Home ("/") self-canonical. Public sub-pages declare their own canonical and
        // internal/app routes are noindex (see lib/seo.ts + robots.ts), so this default
        // only governs the home route. (#1064)
        alternates: {
            canonical: "/",
        },
        openGraph: {
            title: "Rico Hunt \u2014 AI Career Operating System for the UAE",
            description:
                "Rico Hunt helps professionals in the UAE manage their entire job search with AI \u2014 from CV analysis and job matching to application tracking, follow-ups, and interview preparation.",
            url: `${siteUrl}/`,
            siteName: "Rico Hunt",
            type: "website",
            locale: "en_AE",
            images: [
                {
                    url: ogImage,
                    width: 1200,
                    height: 630,
                    alt: "Rico Hunt \u2014 AI Career Operating System for the UAE",
                },
            ],
        },
        twitter: {
            card: "summary_large_image",
            title: "Rico Hunt \u2014 AI Career Operating System for the UAE",
            description:
                "Rico Hunt helps professionals in the UAE manage their entire job search with AI \u2014 from CV analysis and job matching to application tracking, follow-ups, and interview preparation.",
            images: [ogImage],
        },
        icons: {
            icon: [
                { url: "/favicon.ico", sizes: "any" },
                { url: "/icon.svg", type: "image/svg+xml" },
            ],
            apple: "/apple-touch-icon.png",
        },
        keywords: [
            "AI job search UAE",
            "career platform UAE",
            "CV analysis AI",
            "job matching Dubai",
            "application tracking",
            "interview preparation AI",
            "AI career operating system",
            "Rico Hunt",
        ],
        robots: {
            index: true,
            follow: true,
            googleBot: {
                index: true,
                follow: true,
                "max-snippet": -1,
                "max-image-preview": "large",
                "max-video-preview": -1,
            },
        },
    };
}

export const viewport: Viewport = {
    width: "device-width",
    initialScale: 1,
    viewportFit: "cover",
    themeColor: "#0B0D1C",
};

// ─── JSON-LD: Organization (full) ────────────────────────────────────────────
function buildJsonLd(siteUrl: string) {
    const organizationSchema = {
        "@type": "Organization",
        "@id": `${siteUrl}/#organization`,
        name: "Rico Hunt",
        url: siteUrl,
        logo: {
            "@type": "ImageObject",
            "@id": `${siteUrl}/#logo`,
            url: `${siteUrl}/icon.svg`,
            width: 512,
            height: 512,
            caption: "Rico Hunt",
        },
        foundingDate: "2026",
        founder: {
            "@type": "Person",
            name: "Roben Edwan",
        },
        description:
            "Rico Hunt is an AI-powered career platform for UAE professionals — covering CV analysis, job matching, application tracking, follow-ups, and interview preparation.",
        areaServed: {
            "@type": "Country",
            name: "United Arab Emirates",
        },
        contactPoint: {
            "@type": "ContactPoint",
            contactType: "customer support",
            areaServed: "AE",
            availableLanguage: ["English", "Arabic"],
        },
        sameAs: [
            "https://linkedin.com/company/ricohunt",
            "https://twitter.com/ricohunt",
        ],
    };

    // ─── JSON-LD: WebSite ─────────────────────────────────────────────────────────
    const websiteSchema = {
        "@type": "WebSite",
        "@id": `${siteUrl}/#website`,
        url: siteUrl,
        name: "Rico Hunt",
        description:
            "AI Career Operating System for professionals in the UAE \u2014 CV analysis, job matching, application tracking, follow-ups, and interview preparation.",
        publisher: { "@id": `${siteUrl}/#organization` },
        // No SearchAction: there is no stable public search landing. `/jobs` redirects
        // to the (noindex) `/command` app surface, so advertising it as a search
        // entry point would be false. (#1064)
        inLanguage: ["en", "ar"],
    };

    // ─── JSON-LD: SoftwareApplication (full) ─────────────────────────────────────
    const softwareAppSchema = {
        "@type": "SoftwareApplication",
        "@id": `${siteUrl}/#app`,
        name: "Rico Hunt",
        url: siteUrl,
        applicationCategory: "BusinessApplication",
        applicationSubCategory: "CareerPlatform",
        operatingSystem: "Web",
        description:
            "Rico Hunt helps professionals in the UAE manage their entire job search with AI \u2014 from CV analysis and job matching to application tracking, follow-ups, and interview preparation.",
        featureList: [
            "AI CV Analysis",
            "Intelligent Job Matching",
            "Application Tracking",
            "Automated Follow-Ups",
            "Interview Preparation",
            "Arabic and English support",
            "UAE-focused job market coverage",
        ],
        offers: {
            "@type": "Offer",
            price: "0",
            priceCurrency: "AED",
            description: "Free tier available",
        },
        publisher: { "@id": `${siteUrl}/#organization` },
        inLanguage: ["en", "ar"],
        areaServed: {
            "@type": "Country",
            name: "United Arab Emirates",
        },
    };

    // ─── JSON-LD: FAQ ─────────────────────────────────────────────────────────────
    const faqSchema = {
        "@type": "FAQPage",
        "@id": `${siteUrl}/#faq`,
        mainEntity: [
            {
                "@type": "Question",
                name: "How does Rico match jobs?",
                acceptedAnswer: {
                    "@type": "Answer",
                    text: "Rico analyses your uploaded CV and career profile to surface UAE job listings that match your skills, experience level, and preferences \u2014 ranked by relevance, not recency.",
                },
            },
            {
                "@type": "Question",
                name: "Does Rico rewrite my CV?",
                acceptedAnswer: {
                    "@type": "Answer",
                    text: "Yes. Rico\u2019s AI analyses your CV against each job description and suggests targeted edits to increase your match rate and pass ATS screening.",
                },
            },
            {
                "@type": "Question",
                name: "Can Rico track my job applications?",
                acceptedAnswer: {
                    "@type": "Answer",
                    text: "Yes. Rico\u2019s application tracker logs every job you apply to, monitors status changes, and sends follow-up reminders so nothing falls through the cracks.",
                },
            },
            {
                "@type": "Question",
                name: "Is Rico free to use?",
                acceptedAnswer: {
                    "@type": "Answer",
                    text: "Rico offers a free tier with core features. The Rico Monthly subscription raises your usage limits — more AI messages, saved jobs, CV analyses, and stored documents.",
                },
            },
            {
                "@type": "Question",
                name: "Does Rico support Arabic?",
                acceptedAnswer: {
                    "@type": "Answer",
                    text: "Yes. Rico is fully bilingual \u2014 English and Arabic \u2014 including CV analysis, job matching results, and the conversational AI interface.",
                },
            },
            {
                "@type": "Question",
                name: "Which countries does Rico cover?",
                acceptedAnswer: {
                    "@type": "Answer",
                    text: "Rico is built for the UAE job market, covering Dubai, Abu Dhabi, Sharjah, and all emirates. GCC expansion is planned for 2026.",
                },
            },
        ],
    };

    // ─── JSON-LD: BreadcrumbList ──────────────────────────────────────────────────
    const breadcrumbSchema = {
        "@type": "BreadcrumbList",
        "@id": `${siteUrl}/#breadcrumb`,
        itemListElement: [
            {
                "@type": "ListItem",
                position: 1,
                name: "Home",
                item: `${siteUrl}/`,
            },
        ],
    };

    return {
        "@context": "https://schema.org",
        "@graph": [
            organizationSchema,
            websiteSchema,
            softwareAppSchema,
            faqSchema,
            breadcrumbSchema,
        ],
    };
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
    const siteUrl = await resolveSiteUrl();
    const jsonLd = buildJsonLd(siteUrl);
    return (
        <html lang="en" className="dark" suppressHydrationWarning>
            <head>
                <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
                <script dangerouslySetInnerHTML={{ __html: langInitScript }} />
            </head>
            <body
                className={`${spaceGrotesk.variable} ${inter.variable} ${ibmPlexMono.variable} antialiased bg-background text-text-primary font-body overflow-x-hidden`}
            >
                <Script
                    id="json-ld-root"
                    type="application/ld+json"
                    strategy="beforeInteractive"
                    dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
                />
                <ThemeProvider>
                    <LanguageProvider>{children}</LanguageProvider>
                </ThemeProvider>
                {isVercel && <Analytics />}
            </body>
        </html>
    );
}
