import type { Metadata } from "next";
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

const projectTitle = "Rico: Your AI-intelligent job hunt partner in the UAE";
const projectDescription =
  "Rico helps UAE job seekers turn their CV into smarter job matches, clearer next steps, and a more focused job hunt.";

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_APP_URL ||
      process.env.NEXT_PUBLIC_SITE_URL ||
      "http://localhost:3000",
  ),
  title: projectTitle,
  description: projectDescription,
  alternates: { canonical: "/" },
  viewport: {
    width: "device-width",
    initialScale: 1,
  },
  themeColor: "#000000",
  manifest: "/manifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Rico",
  },
  icons: {
    icon: [{ url: "/icon.svg" }],
    apple: [{ url: "/apple-touch-icon.svg" }],
  },
  openGraph: {
    title: projectTitle,
    description: projectDescription,
    type: "website",
    siteName: "Rico",
  },
  twitter: {
    card: "summary",
    title: projectTitle,
    description: projectDescription,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${ibmPlexSans.variable} ${sora.variable} ${spaceMono.variable} antialiased bg-background text-text-primary font-body overflow-x-hidden`}
      >
        {children}
      </body>
    </html>
  );
}
