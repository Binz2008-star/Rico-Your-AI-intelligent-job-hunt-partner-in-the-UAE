import type { Metadata } from "next";
import { assertInternalPreviewAccess } from "@/lib/internalPreview";
import DesignGalleryClient from "./_client";

export const metadata: Metadata = {
  title: "Design Gallery — Rico Internal",
  description: "Internal design preview. Not linked from production navigation.",
  robots: { index: false, follow: false },
};

export default function DesignGalleryPage() {
  assertInternalPreviewAccess();
  return <DesignGalleryClient />;
}
