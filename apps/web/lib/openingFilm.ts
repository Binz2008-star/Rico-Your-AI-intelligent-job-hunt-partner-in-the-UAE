/**
 * Official-site opening film.
 *
 * Owner directive (2026-07-16): EVERY guest visit to ricohunt.com runs the
 * film chooser — the old once-per-browser-session gate is retired. The
 * chooser (/explainer/index.html) draws from a randomized non-repeating
 * cycle persisted in localStorage (option-2 / option-3 / option-3b: all
 * three play before any repeats) and renders the film in place, so its URL
 * stays on the chooser and reloads re-enter the rotation.
 *
 * The waitlist funnel is retired: the films' Skip/CTA target /signup (open
 * registration), not the old Jotform waitlist.
 */

// Explicit index.html: bare "/explainer" relies on host-level directory-index
// resolution (Vercel does it, `next dev` 404s).
export const OPENING_FILM_PATH = "/explainer/index.html";

/**
 * Hard navigation — /explainer is a static file in public/, not an app route,
 * so the Next client router cannot soft-navigate to it. replace() keeps the
 * redirect hop out of history (Back from the film returns to the real
 * referrer, never to a "/" entry that would bounce straight back into the
 * chooser).
 */
export function goToOpeningFilm(): void {
    window.location.replace(OPENING_FILM_PATH);
}
