/**
 * fix/command-subscription-cta — subscription-mention helpers for /command
 * replies.
 *
 * Product contract (owner directive, 2026-07-19): when a Rico reply directs
 * the user to the subscription surface, the navigation affordance is a REAL
 * localized CTA to the internal /subscription route — never a raw-text URL
 * the model happened to write. /subscription itself remains the single
 * source of truth for plan names and prices; these helpers never generate
 * plan copy.
 *
 * Detection is deliberately conservative: explicit references to the
 * subscription URL/path only (bare `ricohunt.com/subscription`, with or
 * without scheme/www, or a standalone `/subscription` path token). No
 * keyword heuristics — a reply merely *discussing* plans without pointing
 * at the page gets no CTA.
 */

export const SUBSCRIPTION_PATH = "/subscription";

/** Bare or schemed mentions of the production subscription URL. The left
 *  guard (start or a non-domain char) keeps look-alike domains such as
 *  `notricohunt.com` from matching — no lookbehind (older-Safari safety). */
const SUBSCRIPTION_URL_RE = /(?:^|[^\w.-])(?:https?:\/\/)?(?:www\.)?ricohunt\.com\/subscription\b/i;

/** A standalone in-app path token (start of text, whitespace, or an opening
 *  bracket/paren before it — i.e. plain text or a markdown link target). */
const SUBSCRIPTION_PATH_RE = /(?:^|[\s([])\/subscription\b/;

export function mentionsSubscription(text: string): boolean {
    if (!text) return false;
    return SUBSCRIPTION_URL_RE.test(text) || SUBSCRIPTION_PATH_RE.test(text);
}

const LINKIFY_RE = /(^|[^\w.-])((?:https?:\/\/)?(?:www\.)?ricohunt\.com\/subscription\b)/gi;

/**
 * Rewrite bare `ricohunt.com/subscription` mentions into markdown links
 * targeting the INTERNAL /subscription route, so the rendered text is never
 * a dead string. Mentions already inside a markdown link (label or target —
 * preceded by `[`, `(`, or `/`) are left untouched; the visible label keeps
 * the model's original text. The captured prefix guard replaces lookbehind
 * (older-Safari safety) and also blocks look-alike domains.
 */
export function linkifySubscriptionMentions(text: string): string {
    if (!text) return text;
    return text.replace(LINKIFY_RE, (match: string, pre: string, url: string) => {
        if (pre === "[" || pre === "(" || pre === "/") return match;
        return `${pre}[${url}](${SUBSCRIPTION_PATH})`;
    });
}
