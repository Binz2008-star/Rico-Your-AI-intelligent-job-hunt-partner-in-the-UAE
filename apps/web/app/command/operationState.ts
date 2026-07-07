import type { TranslationKey } from "@/lib/translations";

/**
 * Pick the optimistic "operation state" chip shown while the chat server is
 * still responding, from the outgoing user message (already lowercased).
 *
 * Lives in its own module (not `page.tsx`) because Next.js App Router route
 * files may only export the page and a fixed set of route fields — an arbitrary
 * named export there fails the build. Keeping it here also makes it unit-testable
 * without importing the client component.
 *
 * Order matters:
 *  1. Explicit job-search phrasing (a search verb or unambiguous job noun) wins
 *     first, so "find jobs from my CV" still reads as a search.
 *  2. Self-referential profile/career questions ("what is my current role?",
 *     "my position", "review my profile") must NOT flash a job-search chip. The
 *     tokens "role"/"position" are both search nouns and profile nouns; the old
 *     flat list matched them under search, so any profile/career question that
 *     mentioned a role flashed "Searching UAE jobs…" first (TC-11).
 *  3. A bare "role(s)"/"position(s)" with no self-reference is still most likely
 *     a job lookup, so it keeps the search hint.
 *
 * This is a client-side hint only — the real intent is decided server-side and
 * replaces this chip when the response arrives.
 */
export function pickOperationState(
  lc: string,
): { state: string; messageKey: TranslationKey } | null {
  if (/\b(subscri|plan|pricing|package|upgrade)\b/.test(lc)) {
    return { state: "checking", messageKey: "cmdWorkingPlans" };
  }
  if (/\b(jobs?|find|search|vacanc|opening|hiring)\b/.test(lc)) {
    return { state: "searching", messageKey: "cmdWorkingJobs" };
  }
  if (
    /\bmy\b[^?.!\n]{0,40}\b(profile|cv|resume|experience|skills|role|roles|position|positions|title|background|seniority)\b/.test(lc)
    || /\b(profile|cv|resume)\b/.test(lc)
  ) {
    return { state: "reading", messageKey: "cmdWorkingProfile" };
  }
  if (/\b(appli|track|application|status|applied|offer)\b/.test(lc)) {
    return { state: "reviewing", messageKey: "cmdWorkingApplications" };
  }
  if (/\b(experience|skills)\b/.test(lc)) {
    return { state: "reading", messageKey: "cmdWorkingProfile" };
  }
  if (/\b(career|next move|recommend|suggest|direction|trajectory|what should)\b/.test(lc)) {
    return { state: "extracting", messageKey: "cmdWorkingRecommendations" };
  }
  if (/\b(roles?|positions?)\b/.test(lc)) {
    return { state: "searching", messageKey: "cmdWorkingJobs" };
  }
  if (/\b(interview|prep|prepare|question)\b/.test(lc)) {
    return { state: "extracting", messageKey: "cmdWorkingInterview" };
  }
  return null;
}
