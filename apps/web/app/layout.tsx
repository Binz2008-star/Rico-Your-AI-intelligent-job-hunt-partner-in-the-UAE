import { JsonLd } from "@/components/seo/JsonLd";
import { LanguageProvider } from "@/contexts/LanguageContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { Analytics } from "@vercel/analytics/next";
import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans, Sora, Space_Mono } from "next/font/google";
import "./globals.css";

// Canonical production origin — kept in sync with metadataBase below.
const SITE_URL =
    process.env.NEXT_PUBLIC_APP_URL ||
    process.env.NEXT_PUBLIC_SITE_URL ||
    "https://ricohunt.com";

// Site-wide structured data (schema.org). Reinforces legitimacy and enables
// rich results. Only factual, code-defined claims here — no ratings/review
// counts are fabricated.
const siteStructuredData = [
    {
        "@context": "https://schema.org",
        "@type": "Organization",
        name: "Rico Hunt",
        legalName: "Eco Technology Environment Protection Services L.L.C",
        url: SITE_URL,
        logo: `${SITE_URL}/icons/icon-512.png`,
        email: "info@ricohunt.com",
        areaServed: "AE",
        address: { "@type": "PostalAddress", addressCountry: "AE" },
        sameAs: [
            "https://www.linkedin.com/company/eco-technology-environment-protection-services-l-l-c/",
        ],
    },
    {
        "@context": "https://schema.org",
        "@type": "WebSite",
        name: "Rico Hunt",
        url: SITE_URL,
        inLanguage: ["en", "ar"],
    },
    {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        name: "Rico Hunt",
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web",
        url: SITE_URL,
        description:
            "AI job-hunt partner for the UAE. Upload your CV and Rico finds matching jobs, explains the fit, and tracks your applications — in English and Arabic.",
        offers: [
            { "@type": "Offer", name: "Free", price: "0", priceCurrency: "AED" },
            { "@type": "Offer", name: "Pro", price: "29", priceCurrency: "AED" },
            { "@type": "Offer", name: "Premium", price: "49", priceCurrency: "AED" },
        ],
    },
];

// No-flash theme script: runs before paint to apply the stored theme class so a
// light-mode user never sees a dark flash (and vice-versa). Mirrors ThemeContext:
// default "dark", "system" honoured only if explicitly chosen. Kept tiny + inline.
const themeInitScript = `(function(){try{var t=localStorage.getItem("rico-theme");var m=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";var r=(t==="light"||t==="dark")?t:(t==="system"?m:"dark");var e=document.documentElement;e.classList.remove("dark","light");e.classList.add(r);e.setAttribute("data-theme",r);}catch(_){}})();`;

// No-flash language script: mirrors LanguageContext — sets lang/dir on <html> before
// React hydrates so Arabic users never see an LTR flash on page load or refresh.
const langInitScript = `(function(){try{var l=localStorage.getItem("rico-language");if(l==="ar"){var e=document.documentElement;e.lang="ar";e.dir="rtl";}}catch(_){}})();`;

// DESIGN.md spec: IBM Plex Sans Variable + Sora
const ibmPlexSans = IBM_Plex_Sans({
    subsets: ["latin"],
    weight: ["300", "400", "500", "600", "700"],
    variable: "--font-ibm-plex-sans",
    display: "swap",
});

const sora = Sora({
    subsets: ["latin"],
    variable: "--font-sora",
    display: "swap",
});

const spaceMono = Space_Mono({
    subsets: ["latin"],
    weight: ["400", "700"],
    variable: "--font-space-mono",
    display: "swap",
});

export const metadata: Metadata = {
    metadataBase: new URL(
        process.env.NEXT_PUBLIC_APP_URL ||
        process.env.NEXT_PUBLIC_SITE_URL ||
        "https://ricohunt.com"
    ),
    title: "Rico Hunt — Your AI Job-Hunt Partner in the UAE",
    description: "Your AI job-hunt partner in the UAE. Upload your CV and Rico finds matching jobs, tracks your applications, and guides your next move — in English and Arabic.",
    alternates: { canonical: "/" },
    openGraph: {
        title: "Rico Hunt — Your AI Job-Hunt Partner in the UAE",
        description: "Upload your CV. Rico finds matching UAE jobs, tracks your applications, and guides your next move — in English and Arabic.",
        type: "website",
        siteName: "Rico Hunt",
    },
    twitter: {
        card: "summary_large_image",
        title: "Rico Hunt — Your AI Job-Hunt Partner in the UAE",
        description: "Upload your CV. Rico finds matching UAE jobs, tracks your applications, and guides your next move — in English and Arabic.",
    },
};

// viewport-fit=cover is required for env(safe-area-inset-*) to resolve on notched /
// installed-PWA devices; the floating navs and command input rely on it.
export const viewport: Viewport = {
    width: "device-width",
    initialScale: 1,
    viewportFit: "cover",
    themeColor: "#0a0a1a",
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
            <body className={`${ibmPlexSans.variable} ${sora.variable} ${spaceMono.variable} antialiased bg-background text-text-primary font-body overflow-x-hidden`}>
                <JsonLd data={siteStructuredData} />
                <ThemeProvider><LanguageProvider>{children}</LanguageProvider></ThemeProvider>
                <Analytics />
            </body>
        </html>
    );
}
