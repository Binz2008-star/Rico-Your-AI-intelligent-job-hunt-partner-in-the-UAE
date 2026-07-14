import type { Metadata } from "next";
import { assertInternalPreviewAccess } from "@/lib/internalPreview";
import CommandPrimitivesSandbox from "./_client";

/**
 * /sandbox/command-primitives — INTERNAL component sandbox.
 *
 * Visual testing surface for RicoMessageBubble and RicoJobMatchCard. NOT
 * production: internal, noindex, sample data only. Not linked from production
 * navigation. Unreachable in production (assertInternalPreviewAccess → 404).
 */

export const metadata: Metadata = {
  title: "Command Primitives Sandbox (Internal)",
  description:
    "Internal component sandbox for Rico chat primitives. Sample data only. Not production navigation.",
  robots: { index: false, follow: false },
};

export default function CommandPrimitivesSandboxPage() {
  assertInternalPreviewAccess();
  return <CommandPrimitivesSandbox />;
}
