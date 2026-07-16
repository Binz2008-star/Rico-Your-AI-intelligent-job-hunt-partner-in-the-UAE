import type { Metadata } from "next";
import { FAQContent } from "./FAQContent";

export const metadata: Metadata = {
  title: "FAQ",
  description: "Frequently asked questions about Rico Hunt — where jobs come from, how AI matching works, what data we store, and how applications are handled.",
  alternates: { canonical: "/faq" },
};

export default function FAQPage() {
  return <FAQContent />;
}
