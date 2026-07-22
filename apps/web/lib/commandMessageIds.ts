// Shared id-namespace helpers for the /command transcript (app/command/page.tsx).
//
// Two disjoint id ranges are load-bearing for history-replay animation
// suppression (hydratedIds in page.tsx): every history-hydrated row (initial
// load, Sessions-rail switch, guest/public restore) gets a reserved negative
// id via historyRowId()/WELCOME_MESSAGE_ID, while every live message (a new
// user send, a streamed reply) gets a positive id via nextId(), a
// monotonically increasing counter that never resets except on a fresh page
// load. Because the ranges never overlap, hydratedIds can safely accumulate
// across session switches without ever risking a false match against a
// genuinely new/live message — see command-history-id-namespace.test.ts.

let _id = 0;
export function nextId() {
    return ++_id;
}

// Welcome turns get a reserved negative id so they can never collide with
// nextId()-generated ids (streamId in particular — see the fresh-page-load
// token-append bug this guards against).
export const WELCOME_MESSAGE_ID = -1;

// History rows are id'd in the reserved negative namespace starting at -2
// (WELCOME_MESSAGE_ID owns -1), so nextId()-generated ids (1, 2, …) can never
// collide with them. Shared by the initial history load, Sessions-rail thread
// switches, and the guest/public localStorage restore.
export function historyRowId(idx: number): number {
    return -(idx + 2);
}
