import type { Metadata } from "next";
import { assertInternalPreviewAccess } from "@/lib/internalPreview";
import ShellSpecimen from "./_specimen";

/**
 * Command v5 PR 2 — WorkspaceShell skin specimen (internal preview only;
 * production 404s via assertInternalPreviewAccess). Renders the REAL
 * WorkspaceShell (document variant, light island) around sample content so
 * the v5 shell treatment can be reviewed and screenshotted without an
 * authenticated session. Mission data stays fail-hidden here exactly as in
 * production when the API is unavailable.
 */
export const metadata: Metadata = {
    title: "Command v5 Shell — Rico Internal",
    description: "Internal design specimen. Not linked from production navigation.",
    robots: { index: false, follow: false },
};

export default function CommandV5ShellPage() {
    assertInternalPreviewAccess();
    return <ShellSpecimen />;
}
