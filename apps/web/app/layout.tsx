import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Rico AI",
  description: "Persistent autonomous career assistant",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
