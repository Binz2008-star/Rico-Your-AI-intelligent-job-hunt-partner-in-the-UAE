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

// --- Timeout/retry guard -----------------------------------------------------
// Deliberately independent of pickOperationState (the optimistic chip). The
// retry is cheap cold-start insurance, so this errs toward retrying real
// job/role/position searches, while excluding the two things that must NOT be
// retried as a search: pure self-referential profile questions (TC-11 item 7)
// and applied/saved/opened lifecycle list requests. Not delegating to the chip
// avoids inheriting its branch ordering (subscription-first, jobs?-plural,
// self-reference) — the root cause of the Codex P2 regressions.
const JOB_SEARCH_SIGNAL_RE = /\b(jobs?|find|search|vacanc|opening|hiring|recruit|roles?|positions?)\b/;
// Applied/saved/opened lifecycle *lists* — a pipeline view, not a job search.
// Matches ownership/list phrasing ("my applied", "saved jobs", "jobs I opened")
// rather than a bare keyword, so a title adjective like "Applied Scientist" /
// "Applied AI" in a real search is not suppressed (Codex "A").
const LIFECYCLE_LIST_RE =
  /\b(?:my|the)\s+(?:applied|saved|opened|archived|bookmarked|shortlisted)\b|\b(?:applied|saved|opened|archived|bookmarked|shortlisted)\s+jobs?\b|\bjobs?\s+i\s+(?:applied|opened|saved|bookmarked)\b/;
// The user's OWN role/position/profile as the subject of the message.
const PROFILE_SELF_RE = /\bmy\b[^?.!\n]{0,20}\b(roles?|positions?|profile|title|cv|resume|experience|skills|background|seniority)\b/;
// Signals that a "my role/position" phrase is a search basis, not a self-question
// ("roles similar to my current role in Dubai", "…based on my CV").
const SEARCH_CONTEXT_RE = /\b(find|search|jobs?|vacanc|opening|hiring|recruit|similar to|like|based on|matching|dubai|abu dhabi|sharjah|ajman|ras al khaimah|fujairah|umm al quwain|uae|emirates|remote|on-?site|hybrid|relocat|salary)\b/;
const ARABIC_SEARCH_RE = /ابحث|وظيف|بحث/;

/**
 * Whether a timed-out request should be retried once as a job search (and show
 * "Retrying search…"). Broad job-search detection that still excludes pure
 * profile/self-reference questions ("what is my current role?" — TC-11 item 7)
 * and applied/saved/opened lifecycle lists ("show my saved jobs"). CV-based,
 * career-role, comparison-to-current-role, and subscription-word job searches
 * ("find jobs with relocation package") are all still retried. Preserves the
 * Arabic search tokens.
 */
export function isRetryableJobSearchIntent(text: string): boolean {
  if (ARABIC_SEARCH_RE.test(text)) return true;
  const lc = text.toLowerCase();
  if (!JOB_SEARCH_SIGNAL_RE.test(lc)) return false;
  if (LIFECYCLE_LIST_RE.test(lc)) return false;
  // A pure self-referential profile question is not a search — but the same
  // "my role/position" wording *with* search context (a location, "similar to",
  // "based on", an explicit search verb) is a real search.
  if (PROFILE_SELF_RE.test(lc) && !SEARCH_CONTEXT_RE.test(lc)) return false;
  return true;
}
