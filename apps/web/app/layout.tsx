import type { Metadata } from "next";
import "./globals.css";

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

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" className="dark">
            <head>
                <link rel="preconnect" href="https://fonts.googleapis.com" />
                <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
                <link
                    href="https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700&family=Geist:wght@300;400;500;600&family=Space+Mono:wght@400;500;600&display=swap"
                    rel="stylesheet"
                />
                <link
                    href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap"
                    rel="stylesheet"
                />
            </head>
            <body className="antialiased bg-background text-on-surface font-body overflow-x-hidden">
                {children}
            </body>
        </html>
    );
}
