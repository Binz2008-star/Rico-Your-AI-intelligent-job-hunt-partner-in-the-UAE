import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Rico AI",
  description: "Your autonomous AI job hunter.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased bg-zinc-950 text-zinc-100">{children}</body>
    </html>
  );
}
