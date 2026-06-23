import { LanguageProvider } from "@/contexts/LanguageContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import PWAInstallPrompt from "@/components/PWAInstallPrompt";
import { Analytics } from "@vercel/analytics/next";
import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";

// No-flash theme script: runs before paint to apply the stored theme class so a
// light-mode user never sees a dark flash (and vice-versa). Mirrors ThemeContext:
// default "dark", "system" honoured only if explicitly chosen. Kept tiny + inline.
const themeInitScript = `(function(){try{var t=localStorage.getItem("rico-theme");var m=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";var r=(t==="light"||t==="dark")?t:(t==="system"?m:"dark");var e=document.documentElement;e.classList.remove("dark","light");e.classList.add(r);e.setAttribute("data-theme",r);}catch(_){}})();`;

// Service worker registration: only in production and only once. Keeps PWA
// install criteria satisfied (navigator.serviceWorker + manifest + HTTPS).
const swRegScript = `(function(){if('serviceWorker' in navigator){window.addEventListener('load',function(){navigator.serviceWorker.register('/sw.js',{scope:'/'}).catch(function(){});})}})();`;

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

export const metadata: Metadata = {
    metadataBase: new URL(
        process.env.NEXT_PUBLIC_APP_URL ||
        process.env.NEXT_PUBLIC_SITE_URL ||
        "https://ricohunt.com"
    ),
    title: "Rico Hunt — Your AI Job-Hunt Partner in the UAE",
    description: "Your AI job-hunt partner in the UAE. Upload your CV and Rico finds matching jobs, tracks your applications, and guides your next move — in English and Arabic.",
    alternates: { canonical: "/" },
    icons: {
        icon: [
            { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
            { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
        ],
        apple: [
            { url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
        ],
    },
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
    themeColor: "#06060c",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" className="dark" suppressHydrationWarning>
            <head>
                <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
                <script dangerouslySetInnerHTML={{ __html: langInitScript }} />
                <script dangerouslySetInnerHTML={{ __html: swRegScript }} />
                <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />
                <link
                    rel="stylesheet"
                    href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap"
                />
            </head>
            <body className={`${spaceGrotesk.variable} ${inter.variable} ${ibmPlexMono.variable} antialiased bg-background text-text-primary font-body overflow-x-hidden`}>
                <ThemeProvider><LanguageProvider>{children}</LanguageProvider></ThemeProvider>
                <PWAInstallPrompt />
                <Analytics />
            </body>
        </html>
    );
}
