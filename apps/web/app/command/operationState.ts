import type { TranslationKey } from "@/lib/translations";

const SUBSCRIPTION_RE = /\b(subscri|plan|pricing|package|upgrade)\b/;
// Explicit search phrasing (verb or unambiguous job noun).
const SEARCH_VERB_RE = /\b(jobs?|find|search|vacanc|opening|hiring)\b/;
const ROLE_TOKEN_RE = /\b(roles?|positions?)\b/;
// The user referring to their OWN role/position ("what is my current role?",
// "my position at the company", "show me my target roles") — a profile question,
// not a job hunt. Requires "my" to precede the role token, so "…position … based
// on my CV" does NOT match (there "my" attaches to the CV, which is a search basis).
const SELF_REF_ROLE_RE = /\bmy\b[^?.!\n]{0,20}\b(roles?|positions?)\b/;
const SELF_REF_PROFILE_RE = /\bmy\b[^?.!\n]{0,40}\b(profile|cv|resume|experience|skills|background|title|seniority)\b/;

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
 *  2. Role/position phrases resolve next, before the profile/career branches, so
 *     a role search never gets mislabeled as profile-reading or recommendations.
 *     A role/position is a *profile read* only when the user refers to their OWN
 *     role ("what is my current role?"); otherwise ("sales manager position in
 *     Dubai based on my CV", "cybersecurity career role in Dubai") it is a job
 *     search (TC-11 item 7 — these must retry on cold-start timeout).
 *  3. Remaining self-referential profile questions ("what is my profile?",
 *     "review my cv") read; career/interview/etc. fall through as before.
 *
 * This is a client-side hint only — the real intent is decided server-side and
 * replaces this chip when the response arrives.
 */
export function pickOperationState(
  lc: string,
): { state: string; messageKey: TranslationKey } | null {
  if (SUBSCRIPTION_RE.test(lc)) {
    return { state: "checking", messageKey: "cmdWorkingPlans" };
  }
  if (SEARCH_VERB_RE.test(lc)) {
    return { state: "searching", messageKey: "cmdWorkingJobs" };
  }
  if (ROLE_TOKEN_RE.test(lc)) {
    if (SELF_REF_ROLE_RE.test(lc)) {
      return { state: "reading", messageKey: "cmdWorkingProfile" };
    }
    return { state: "searching", messageKey: "cmdWorkingJobs" };
  }
  if (SELF_REF_PROFILE_RE.test(lc) || /\b(profile|cv|resume)\b/.test(lc)) {
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
  if (/\b(interview|prep|prepare|question)\b/.test(lc)) {
    return { state: "extracting", messageKey: "cmdWorkingInterview" };
  }
  return null;
}

/**
 * Whether a message should be treated as a job-search intent by the
 * timeout/retry path (which shows "Retrying search…" and retries once with a
 * longer timeout). Routed through the same classifier as the pre-send chip so a
 * profile/career question ("what is my current role?") is never retried as a
 * search (TC-11), while a real role/position search — including CV-based and
 * career-role phrasing — still gets the retry. Keeps the Arabic search tokens
 * the English classifier does not cover.
 */
export function isJobSearchIntent(text: string): boolean {
  return (
    pickOperationState(text.toLowerCase())?.state === "searching"
    || /ابحث|وظيف|بحث/.test(text)
  );
}
