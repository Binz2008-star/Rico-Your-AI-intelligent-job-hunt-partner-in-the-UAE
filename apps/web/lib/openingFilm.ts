/**
 * Official-site opening film.
 *
 * Guests opening ricohunt.com are greeted by the cinematic launch film once
 * per browser session: /explainer/index.html picks one of the three approved
 * films at random on every load (option-2 / option-3 / option-3b). Returning
 * to "/" within the same session (film's Back/History) renders the landing
 * page — the session flag prevents a redirect loop.
 *
 * The waitlist funnel is retired: the films' Skip/CTA target /signup (open
 * registration), not the old Jotform waitlist.
 */

export const OPENING_FILM_SESSION_FLAG = "rico-opening-film-shown";
// Explicit index.html: bare "/explainer" relies on host-level directory-index
// resolution (Vercel does it, `next dev` 404s). index.html itself immediately
// location.replace()s to a random option film, so this URL is transient.
export const OPENING_FILM_PATH = "/explainer/index.html";

/**
 * True exactly once per browser session: sets the flag and tells the caller
 * to hand off to the film. Storage failures (privacy modes) skip the film
 * rather than blocking the landing.
 */
export function claimOpeningFilm(): boolean {
    try {
        if (window.sessionStorage.getItem(OPENING_FILM_SESSION_FLAG)) {
            return false;
        }
        window.sessionStorage.setItem(OPENING_FILM_SESSION_FLAG, "1");
        return true;
    } catch {
        return false;
    }
}

/**
 * Hard navigation — /explainer is a static file in public/, not an app route,
 * so the Next client router cannot soft-navigate to it. replace() keeps the
 * redirect hop out of history (Back from the film returns to the real
 * referrer, or to "/" which now shows the landing thanks to the flag).
 */
export function goToOpeningFilm(): void {
    window.location.replace(OPENING_FILM_PATH);
}
