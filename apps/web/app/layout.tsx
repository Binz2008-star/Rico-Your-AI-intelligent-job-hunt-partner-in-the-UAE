import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans, Sora, Space_Mono } from "next/font/google";
import "./globals.css";

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
        "http://localhost:3000"
    ),
    title: "Rico AI — Autonomous Career Trajectory Intelligence",
    description: "Cinematic career intelligence system. Memory-weighted trajectory mapping, command-centered orchestration, and opportunity momentum analysis for autonomous career evolution.",
    alternates: { canonical: "/" },
    openGraph: {
        title: "Rico AI — Autonomous Career Trajectory Intelligence",
        description: "The future of career intelligence. Memory-weighted trajectory mapping, command-centered orchestration, and opportunity momentum analysis.",
        type: "website",
        siteName: "Rico AI",
    },
    twitter: {
        card: "summary",
        title: "Rico AI — Autonomous Career Trajectory Intelligence",
        description: "The future of career intelligence. Memory-weighted trajectory mapping, command-centered orchestration, and opportunity momentum analysis.",
    },
};

// viewport-fit=cover is required for env(safe-area-inset-*) to resolve on notched /
// installed-PWA devices; the floating navs and command input rely on it.
export const viewport: Viewport = {
    width: "device-width",
    initialScale: 1,
    viewportFit: "cover",
    themeColor: "#000000",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" className="dark">
            <body className={`${ibmPlexSans.variable} ${sora.variable} ${spaceMono.variable} antialiased bg-background text-text-primary font-body overflow-x-hidden`}>
                {children}
            </body>
        </html>
    );
}
