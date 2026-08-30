/**
 * apps/web/lib/chat-timeout-policy.ts
 *
 * Adaptive frontend timeout policy for the /command chat surface.
 *
 * Non-search messages (profile questions, lifecycle lists, general chat)
 * keep the default 45s hard timeout. Retryable job-search messages get an
 * extended 90s budget because the backend runs intent classification +
 * provider cascade + response generation sequentially and can exceed 45s
 * on a real search.
 *
 * The recovery resend does NOT get a fresh unbounded 90s budget — the
 * overall elapsed-time policy caps the total user wait so the phases
 * cannot stack into 90 + 60 + 90.
 *
 * This module is the single source of truth for timeout values. page.tsx
 * imports from here; tests import from here. No duplication.
 */

import { isRetryableJobSearchIntent } from "@/app/command/operationState";

/** Hard timeout for non-search chat messages (profile, lifecycle, general). */
export const DEFAULT_CHAT_TIMEOUT_MS = 45_000;

/** Hard timeout for retryable job-search messages. */
export const JOB_SEARCH_TIMEOUT_MS = 90_000;

/** Polling budget for the operation-status recovery path (unchanged). */
export const OPERATION_POLL_BUDGET_MS = 60_000;

/**
 * Maximum total wall-clock time a single user turn may consume across all
 * phases (primary request + polling + recovery resend). Prevents the
 * individual phase budgets from stacking into an unbounded wait.
 *
 * 90s primary + 60s poll = 150s theoretical max. The overall cap is set
 * to 150s so the poll budget is respected but a fresh 90s recovery resend
 * cannot extend the total beyond 150s.
 */
export const MAX_TOTAL_TURN_MS = 150_000;

/**
 * Returns the hard timeout in milliseconds for a given user message.
 *
 * Job-search intents (as classified by isRetryableJobSearchIntent) get the
 * extended budget; all other messages get the default.
 */
export function getChatTimeoutMs(text: string): number {
  return isRetryableJobSearchIntent(text)
    ? JOB_SEARCH_TIMEOUT_MS
    : DEFAULT_CHAT_TIMEOUT_MS;
}

/**
 * Returns the remaining budget for a recovery resend, given the elapsed
 * time since the turn started. The recovery resend must NOT get a fresh
 * unbounded 90s budget — it gets at most the remaining time within the
 * overall turn cap.
 *
 * @param elapsedMs - milliseconds since the turn started
 * @returns milliseconds available for the recovery resend, minimum 0
 */
export function getRecoveryTimeoutMs(elapsedMs: number): number {
  const remaining = MAX_TOTAL_TURN_MS - elapsedMs;
  return Math.max(0, Math.min(remaining, JOB_SEARCH_TIMEOUT_MS));
}

/**
 * Recovery decision returned by `getRecoveryDecision`.
 * - shouldSend=false means the turn cap is exhausted; the caller must NOT
 *   issue a network request and must render the timeout fallback instead.
 * - timeoutMs is the bounded timeout for the recovery send (0 when shouldSend
 *   is false).
 */
export interface RecoveryDecision {
  shouldSend: boolean;
  timeoutMs: number;
}

/**
 * Production helper that decides whether a recovery resend should be issued
 * and with what timeout. When the overall turn cap is exhausted, returns
 * { shouldSend: false, timeoutMs: 0 } so the caller can render the timeout
 * fallback without beginning a network call that setTimeout(…, 0) would
 * abort before the response arrives.
 *
 * @param elapsedMs - milliseconds since the turn started
 */
export function getRecoveryDecision(elapsedMs: number): RecoveryDecision {
  const timeoutMs = getRecoveryTimeoutMs(elapsedMs);
  return {
    shouldSend: timeoutMs > 0,
    timeoutMs,
  };
}
