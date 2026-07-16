/**
 * CommandEventAdapter — slice C2 of the Command Obsidian program
 * (owner-approved scope, 2026-07-16).
 *
 * PURE mapping from Rico's real production state to the canonical transcript
 * grammar. No React, no I/O, no handlers — unit-testable in isolation.
 *
 * Anti-fabrication contract (owner directive):
 * - No hidden model reasoning / chain-of-thought is ever surfaced.
 * - No PLAN/TOOL events are invented: RUN rows exist only while a real
 *   `operationState` is active; CHECK/FAIL progress rows come only from real
 *   `agentic_ui.progress` items the API actually sent.
 * - The scripted Lovable SCRIPT content is NOT ported.
 * - A deliberate user Stop is distinct from a timeout: `stopped` rows come
 *   only from the real stop flow (partial streamed content is preserved by
 *   the page); timeout/network failures remain `fail` rows with real Retry.
 */

import type { RicoAgenticUi } from "@/lib/schemas";

/** The minimal message shape the adapter reads — a structural subset of the
 *  page's `Message`; nothing here is invented. */
export interface TranscriptMessageLike {
    role: "user" | "rico";
    text?: string;
    type?: string;
    isError?: boolean;
    streaming?: boolean;
    matches?: unknown[];
    applications?: unknown[];
    follow_up_needed?: unknown[];
    profile_gaps?: string[];
    preview?: unknown;
    agentic_ui?: RicoAgenticUi | null;
}

/** Canonical row kinds C2 owns. Card-bearing turns pass through as `card`
 *  with their existing (4c/4d) presentation untouched — card restyles are
 *  C4/C5 scope. */
export type TranscriptRowKind = "you" | "rico" | "fail" | "stopped" | "card";

function hasAgenticSurface(ui: RicoAgenticUi | null | undefined): boolean {
    if (!ui) return false;
    return Boolean(
        (ui.actions && ui.actions.length > 0) ||
        ui.permission_request ||
        (ui.proposed_changes && ui.proposed_changes.length > 0) ||
        (ui.attachment_analysis && ui.attachment_analysis.length > 0),
    );
}

const CARD_TYPES = new Set([
    "job_matches",
    "profile_preview",
    "application_status",
    "profile_gap",
    "role_confirmation",
]);

/** Classify one real message into its canonical row kind. */
export function classifyMessage(m: TranscriptMessageLike): TranscriptRowKind {
    if (m.role === "user") return "you";
    if (m.type === "stopped") return "stopped";
    if (m.isError) return "fail";
    if (
        (m.type && CARD_TYPES.has(m.type)) ||
        (m.matches && m.matches.length > 0) ||
        (m.applications && m.applications.length > 0) ||
        (m.follow_up_needed && m.follow_up_needed.length > 0) ||
        (m.profile_gaps && m.profile_gaps.length > 0) ||
        m.preview != null ||
        hasAgenticSurface(m.agentic_ui)
    ) {
        return "card";
    }
    return "rico";
}

/** Real progress rows for one message — exactly what the API sent, nothing
 *  more. Empty when the API sent none (no fabricated steps). */
export function realProgressRows(
    m: TranscriptMessageLike,
): Array<{ id: string; label: string; status: "pending" | "running" | "complete" | "failed" }> {
    return m.agentic_ui?.progress ?? [];
}

/** Top-bar status derived from real state only. */
export function deriveStatus(input: {
    thinking: boolean;
    streaming: boolean;
}): "ready" | "working" | "replying" {
    if (input.streaming) return "replying";
    if (input.thinking) return "working";
    return "ready";
}

/** Safe RUN label: the existing operation-state taxonomy or the generic
 *  working fallback. Never a fabricated tool name. */
export function runLabel(
    operationMessage: string | null | undefined,
    fallback: string,
): string {
    const label = operationMessage?.trim();
    return label && label.length > 0 ? label : fallback;
}
