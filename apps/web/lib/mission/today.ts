/**
 * lib/mission/today.ts
 *
 * Pure prioritization for Mission Control's "Today's Actions".
 * No I/O — the data is fetched by MissionTodayCard and passed in, so the
 * ordering rules can be unit-tested in isolation.
 */

export type MissionActionKind =
  | "approve_draft"
  | "follow_up"
  | "complete_profile"
  | "review_matches";

export interface MissionTodayInput {
  /** Drafts in the apply queue awaiting user approval. */
  pendingDrafts: number;
  /** Applications flagged due for a follow-up nudge. */
  followUpsDue: number;
  /**
   * Profile completeness in the 0..1 range, or `null` when the profile could
   * not be loaded. `null` suppresses the "complete profile" nudge so we never
   * show a false prompt on a failed fetch.
   */
  completenessScore: number | null;
  /** Count of scored opportunities not yet triaged. */
  newMatches: number;
}

export interface MissionAction {
  kind: MissionActionKind;
  /** Lower runs first. */
  priority: number;
  /**
   * Badge count. `complete_profile` is a single binary nudge, so its count is
   * 0 (no badge rendered).
   */
  count: number;
  /** Destination that actually performs the action. */
  href: string;
}

/** At or above this completeness we stop nudging the user to complete the profile. */
export const PROFILE_READY_THRESHOLD = 0.8;

/**
 * Build the ordered Today's Actions list. Deterministic: drafts awaiting
 * approval first, then follow-ups due, then the profile nudge, then new matches.
 */
export function buildMissionToday(input: MissionTodayInput): MissionAction[] {
  const actions: MissionAction[] = [];

  if (input.pendingDrafts > 0) {
    actions.push({ kind: "approve_draft", priority: 1, count: input.pendingDrafts, href: "/queue" });
  }
  if (input.followUpsDue > 0) {
    actions.push({ kind: "follow_up", priority: 2, count: input.followUpsDue, href: "/flow" });
  }
  // Only nudge when a score actually loaded and it is below the bar.
  if (input.completenessScore != null && input.completenessScore < PROFILE_READY_THRESHOLD) {
    actions.push({ kind: "complete_profile", priority: 3, count: 0, href: "/profile" });
  }
  if (input.newMatches > 0) {
    actions.push({ kind: "review_matches", priority: 4, count: input.newMatches, href: "/jobs" });
  }

  return actions.sort((a, b) => a.priority - b.priority);
}
