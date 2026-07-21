import type { Metadata } from "next";
import { BlogIndexContent } from "./BlogIndexContent";

export const metadata: Metadata = {
  title: "Career Guides",
  description:
    "Practical, UAE-specific guides on CV writing, job searching, and interview preparation — in English and Arabic — from Rico Hunt.",
  alternates: { canonical: "/blog" },
  openGraph: {
    title: "Career Guides | Rico Hunt",
    description:
      "Practical, UAE-specific guides on CV writing, job searching, and interview preparation — in English and Arabic.",
    url: "https://ricohunt.com/blog",
    type: "website",
  },
};

export default function BlogIndexPage() {
  return <BlogIndexContent />;
}
