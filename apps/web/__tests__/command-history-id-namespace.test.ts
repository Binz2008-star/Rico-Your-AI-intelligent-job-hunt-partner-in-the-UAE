/**
 * Identity-safety invariant for history-replay animation suppression.
 *
 * hydratedIds (page.tsx) accumulates the ids of every message hydrated from
 * bulk history — initial load, Sessions-rail switch, and guest/public restore
 * all funnel through historyRowId(idx) (lib/commandMessageIds.ts), which
 * assigns ids in a reserved negative namespace (-(idx+2); -1 is the welcome
 * sentinel, WELCOME_MESSAGE_ID). Live messages (user sends, streamed replies)
 * always get ids from nextId(), a monotonically increasing counter starting
 * at 1.
 *
 * hydratedIds is never cleared on a session switch — it only ever grows. That
 * is only safe because the two id namespaces can never overlap. This test
 * locks in that invariant: it must hold across ANY sequence of session
 * switches (including switches where two different sessions' history rows
 * happen to land on the same negative id number, e.g. both sessions' first
 * row mapping to id -2), and it must hold no matter how many live messages
 * were sent in between.
 *
 * This is a direct, deterministic proof of the invariant rather than a single
 * hand-picked integration scenario — it is strictly stronger evidence that a
 * stale hydratedIds entry from a previous session can never suppress the
 * entrance animation of an unrelated future live message, and cheaper than
 * simulating a full page mount with multi-session + SSE mocking.
 */

import { describe, expect, it } from "vitest";
import { historyRowId, nextId, WELCOME_MESSAGE_ID } from "@/lib/commandMessageIds";

describe("history-hydration id namespace vs. live-message id namespace", () => {
    it("historyRowId always produces ids <= -2, regardless of session content or row count", () => {
        const sessionA = [0, 1].map(historyRowId); // one session's 2 rows
        const sessionB = [0, 1].map(historyRowId); // an unrelated session's 2 rows

        // Same row count → same numeric ids reused across unrelated sessions
        // (this is expected and harmless: see the next test).
        expect(sessionA).toEqual([-2, -3]);
        expect(sessionB).toEqual([-2, -3]);

        for (const id of [...sessionA, ...sessionB]) {
            expect(id).toBeLessThanOrEqual(-2);
        }
    });

    it("WELCOME_MESSAGE_ID and every historyRowId output are strictly negative and disjoint from each other", () => {
        expect(WELCOME_MESSAGE_ID).toBe(-1);
        for (let idx = 0; idx < 10; idx++) {
            const id = historyRowId(idx);
            expect(id).toBeLessThan(0);
            expect(id).not.toBe(WELCOME_MESSAGE_ID);
        }
    });

    it("nextId() always produces strictly positive ids, disjoint from any history id ever seen", () => {
        // Simulate: session A hydrates (2 rows), a live message is sent,
        // session B hydrates (reusing the same negative id numbers as
        // session A), then another live message is sent — the exact sequence
        // a real session-switch produces in the app.
        const sessionA = [0, 1].map(historyRowId);
        const liveIdAfterA = nextId();
        const sessionB = [0, 1].map(historyRowId);
        const liveIdAfterB = nextId();

        const historyIds = new Set([...sessionA, ...sessionB]);

        // Session B's history ids numerically collide with session A's (both
        // are [-2, -3]) — that is fine, since both are legitimately-hydrated
        // rows in their own session and correctly skip animation either way.
        expect(sessionA).toEqual(sessionB);

        // What must NEVER happen: a live id landing inside the (accumulated,
        // never-cleared) set of history ids — that would wrongly suppress
        // entrance animation on a genuinely new message.
        expect(historyIds.has(liveIdAfterA)).toBe(false);
        expect(historyIds.has(liveIdAfterB)).toBe(false);
        expect(liveIdAfterA).toBeGreaterThan(0);
        expect(liveIdAfterB).toBeGreaterThan(0);
        expect(liveIdAfterB).toBeGreaterThan(liveIdAfterA);
    });

    it("nextId() ids never collide with history ids even across many interleaved session switches", () => {
        const allHistoryIds = new Set<number>();
        const allLiveIds = new Set<number>();

        for (let session = 0; session < 25; session++) {
            const rowCount = (session % 4) + 1;
            for (let idx = 0; idx < rowCount; idx++) allHistoryIds.add(historyRowId(idx));
            allLiveIds.add(nextId());
        }

        for (const liveId of allLiveIds) {
            expect(allHistoryIds.has(liveId)).toBe(false);
            expect(liveId).toBeGreaterThan(0);
        }
        for (const historyId of allHistoryIds) {
            expect(historyId).toBeLessThan(0);
        }
    });
});
