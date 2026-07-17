import { LanguageProvider } from "@/contexts/LanguageContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { Analytics } from "@vercel/analytics/next";
import type { Metadata, Viewport } from "next";
import { Amiri, Fraunces, IBM_Plex_Sans_Arabic, Inter, JetBrains_Mono, Space_Grotesk } from "next/font/google";
import Script from "next/script";
import "./globals.css";

const themeInitScript = `(function(){try{var t=localStorage.getItem("rico-theme");var m=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";var r=(t==="light"||t==="dark")?t:(t==="system"?m:"dark");var e=document.documentElement;e.classList.remove("dark","light");e.classList.add(r);e.setAttribute("data-theme",r);}catch(_){}})();`;
const langInitScript = `(function(){try{var l=localStorage.getItem("rico-language");if(l==="ar"){var e=document.documentElement;e.lang="ar";e.dir="rtl";}}catch(_){}})();`;

// Atelier V3 fonts
const spaceGrotesk = Space_Grotesk({
    subsets: ["latin"],
    weight: ["400", "500", "600", "700"],
    variable: "--font-display",
    display: "swap",
});

const inter = Inter({
    subsets: ["latin"],
    weight: ["400", "500", "600"],
    variable: "--font-sans",
    display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
    subsets: ["latin"],
    weight: ["400", "500", "600"],
    variable: "--font-mono",
    display: "swap",
});

const fraunces = Fraunces({
    subsets: ["latin"],
    weight: ["400"],
    variable: "--font-editorial",
    display: "swap",
    style: ["italic"],
});

const ibmPlexSansArabic = IBM_Plex_Sans_Arabic({
    subsets: ["arabic"],
    weight: ["400", "500", "600", "700"],
    variable: "--font-sans-ar",
    display: "swap",
});

const amiri = Amiri({
    subsets: ["arabic"],
    weight: ["400", "700"],
    variable: "--font-display-ar",
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
    title: {
        default: "Rico Hunt \u2014 AI Career Operating System for the UAE",
        template: "%s | Rico Hunt",
    },
    description:
        "Rico Hunt helps professionals in the UAE manage their entire job search with AI \u2014 from CV analysis and job matching to application tracking, follow-ups, and interview preparation.",
    alternates: {
        canonical: "/",
    },
    openGraph: {
        title: "Rico Hunt \u2014 AI Career Operating System for the UAE",
        description:
            "Rico Hunt helps professionals in the UAE manage their entire job search with AI \u2014 from CV analysis and job matching to application tracking, follow-ups, and interview preparation.",
        url: `${SITE_URL}/`,
        siteName: "Rico Hunt",
        type: "website",
        locale: "en_AE",
        images: [
            {
                url: OG_IMAGE,
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
        images: [OG_IMAGE],
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

export const viewport: Viewport = {
    width: "device-width",
    initialScale: 1,
    viewportFit: "cover",
    themeColor: "#0B0D1C",
};

// ─── JSON-LD: Organization (full) ────────────────────────────────────────────
const organizationSchema = {
    "@type": "Organization",
    "@id": `${SITE_URL}/#organization`,
    name: "Rico Hunt",
    url: SITE_URL,
    logo: {
        "@type": "ImageObject",
        "@id": `${SITE_URL}/#logo`,
        url: `${SITE_URL}/icon.svg`,
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
    "@id": `${SITE_URL}/#website`,
    url: SITE_URL,
    name: "Rico Hunt",
    description:
        "AI Career Operating System for professionals in the UAE \u2014 CV analysis, job matching, application tracking, follow-ups, and interview preparation.",
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
};

// ─── JSON-LD: SoftwareApplication (full) ─────────────────────────────────────
const softwareAppSchema = {
    "@type": "SoftwareApplication",
    "@id": `${SITE_URL}/#app`,
    name: "Rico Hunt",
    url: SITE_URL,
    applicationCategory: "BusinessApplication",
    applicationSubCategory: "CareerPlatform",
    operatingSystem: "Web, iOS, Android",
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
    publisher: { "@id": `${SITE_URL}/#organization` },
    inLanguage: ["en", "ar"],
    areaServed: {
        "@type": "Country",
        name: "United Arab Emirates",
    },
};

// ─── JSON-LD: FAQ ─────────────────────────────────────────────────────────────
const faqSchema = {
    "@type": "FAQPage",
    "@id": `${SITE_URL}/#faq`,
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
                text: "Rico offers a free tier with core features. Premium plans unlock advanced AI matching, unlimited applications, and priority interview coaching.",
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
    "@id": `${SITE_URL}/#breadcrumb`,
    itemListElement: [
        {
            "@type": "ListItem",
            position: 1,
            name: "Home",
            item: `${SITE_URL}/`,
        },
    ],
};

const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
        organizationSchema,
        websiteSchema,
        softwareAppSchema,
        faqSchema,
        breadcrumbSchema,
    ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" className="dark" suppressHydrationWarning>
            <head>
                <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
                <script dangerouslySetInnerHTML={{ __html: langInitScript }} />
            </head>
            <body
                className={`${spaceGrotesk.variable} ${inter.variable} ${jetbrainsMono.variable} ${fraunces.variable} ${ibmPlexSansArabic.variable} ${amiri.variable} antialiased bg-background text-text-primary font-body overflow-x-hidden`}
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
                <Analytics />
            </body>
        </html>
    );
}
