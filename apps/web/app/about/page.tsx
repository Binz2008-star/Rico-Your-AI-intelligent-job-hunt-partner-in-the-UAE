import type { Metadata } from "next";
import { AboutContent } from "./AboutContent";

export const metadata: Metadata = {
  title: "About | Rico Hunt",
  description: "Rico Hunt is a UAE-focused AI career companion that reads your CV, finds matching jobs, and helps you execute your job search — without applying silently.",
};

export default function AboutPage() {
  return <AboutContent />;
}
