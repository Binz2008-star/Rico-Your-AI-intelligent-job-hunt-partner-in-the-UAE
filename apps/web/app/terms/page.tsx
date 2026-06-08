import type { Metadata } from "next";
import { TermsContent } from "./TermsContent";

export const metadata: Metadata = {
  title: "Terms of Service | Rico Hunt",
  description: "Terms of Service for Rico Hunt — the UAE-focused AI career platform.",
};

export default function TermsPage() {
  return <TermsContent />;
}
