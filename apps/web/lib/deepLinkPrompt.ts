/**
 * Deep-link prompt parsing for the /command chat surface.
 *
 * The chat page accepts a one-shot action prompt via the URL query string:
 *   - ?prompt=…  (legacy)
 *   - ?q=…       (CAREER-OS-10 deep-links / action-card navigation)
 *
 * These are consumed exactly once to seed a chat send. BUG-18: if they are left
 * in the URL, a page refresh or back-navigation re-fires the same prompt and
 * re-injects it into an already-active thread. Callers use `cleanSearch` +
 * `history.replaceState` to strip them after capture, preserving every other
 * param (e.g. cv=ready).
 */

export interface DeepLinkPromptResult {
    /** The captured one-shot prompt from ?prompt= or ?q=, or null when absent. */
    prompt: string | null;
    /** The search string with prompt/q removed — "" or "?rest=…" (leading "?"). */
    cleanSearch: string;
    /** True when a prompt/q param was present and should be stripped from the URL. */
    changed: boolean;
}

/**
 * Parse the one-shot deep-link prompt from a URL search string and return a
 * cleaned search string with the prompt/q params removed. Pure; never throws.
 *
 * @param search Raw `window.location.search` (may include or omit the leading "?").
 */
export function stripDeepLinkParams(search: string): DeepLinkPromptResult {
    const params = new URLSearchParams(search);
    const prompt = params.get("prompt") ?? params.get("q") ?? null;
    const changed = params.has("prompt") || params.has("q");
    params.delete("prompt");
    params.delete("q");
    const qs = params.toString();
    return { prompt, cleanSearch: qs ? `?${qs}` : "", changed };
}
