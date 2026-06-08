import type { Metadata } from "next";
import { ContactContent } from "./ContactContent";

export const metadata: Metadata = {
  title: "Contact | Rico Hunt",
  description: "Get in touch with the Rico Hunt team. We read every message — email, WhatsApp, or through the app.",
};

export default function ContactPage() {
  return <ContactContent />;
}
