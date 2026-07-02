/**
 * apps/web/lib/applicationStatus.ts
 *
 * Single source of truth for the application status taxonomy (BUG-6).
 *
 * Previously /flow's list view, /flow's Kanban board, the chat pipeline
 * summary (command/page.tsx), and StatusBadge's default labels each defined
 * their own copy of the status list / status->stage grouping, and could
 * silently drift out of sync (e.g. the chat summary only knew about 5 of
 * the 10 backend statuses). Every consumer that needs to know "what
 * statuses exist" or "which board column/stage does this status belong to"
 * must import from here instead of redefining its own list.
 */
import type { ApplicationStatus } from "@/types";

// Canonical ordered list of every status the backend can return
// (mirrors VALID_STATUSES in src/applications.py).
export const APPLICATION_STATUSES: ApplicationStatus[] = [
  "saved",
  "opened",
  "opened_external",
  "prepared",
  "applied",
  "follow_up_due",
  "interview",
  "offer",
  "rejected",
  "decision_made",
];

export type StageKey = "lead" | "applied" | "interview" | "outcome";

export interface StageDef {
  key: StageKey;
  statuses: ApplicationStatus[];
}

// Canonical grouping of statuses into pipeline stages / Kanban columns.
// Every status in APPLICATION_STATUSES must appear in exactly one stage.
export const STAGE_DEFS: StageDef[] = [
  { key: "lead", statuses: ["saved", "opened", "opened_external", "prepared"] },
  { key: "applied", statuses: ["applied", "follow_up_due"] },
  { key: "interview", statuses: ["interview"] },
  { key: "outcome", statuses: ["offer", "rejected", "decision_made"] },
];

const STATUS_TO_STAGE: Record<ApplicationStatus, StageKey> = STAGE_DEFS.reduce(
  (acc, stage) => {
    for (const status of stage.statuses) acc[status] = stage.key;
    return acc;
  },
  {} as Record<ApplicationStatus, StageKey>,
);

export function getStageForStatus(status: ApplicationStatus): StageKey | undefined {
  return STATUS_TO_STAGE[status];
}

// Canonical English fallback label per status — used as the default when a
// caller doesn't supply a localized label. Keep wording in sync with the
// flowStatus*/cmdStatus* translation keys in lib/translations.ts.
export const STATUS_DEFAULT_LABEL: Record<ApplicationStatus, string> = {
  saved: "Saved",
  opened: "Link opened",
  opened_external: "Opened externally",
  prepared: "Prepared",
  applied: "Applied",
  follow_up_due: "Follow-up due",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  decision_made: "Decision",
};
