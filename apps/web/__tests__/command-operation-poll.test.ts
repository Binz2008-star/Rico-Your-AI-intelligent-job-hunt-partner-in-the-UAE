/**
 * pollOperationUntilSettled + mintOperationId — poll decision semantics.
 *
 * Exercises the REAL lib/api implementation against a mocked global fetch:
 * verdict mapping (completed / terminal / still_running / unavailable /
 * aborted), the 404→terminal rule, the consecutive-error fallback, budget
 * exhaustion while active, and abort responsiveness. Uses tiny
 * interval/budget options so no fake timers are needed.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { mintOperationId, pollOperationUntilSettled } from "@/lib/api";

type ResponseLike = {
    ok: boolean;
    status: number;
    json: () => Promise<Record<string, unknown>>;
};

function jsonResponse(body: Record<string, unknown>, status = 200): ResponseLike {
    return { ok: status >= 200 && status < 300, status, json: async () => body };
}

function opStatus(status: string, extra: Record<string, unknown> = {}): ResponseLike {
    return jsonResponse({
        operation_id: "op_web_x",
        status,
        active: status === "running",
        terminal: status === "completed" || status === "failed",
        result_count: null,
        age_seconds: 1,
        ...extra,
    });
}

const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<ResponseLike>>();

beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
});

const FAST = { intervalMs: 1, budgetMs: 250 };

describe("pollOperationUntilSettled", () => {
    it("resolves 'completed' as soon as the operation finishes", async () => {
        fetchMock
            .mockResolvedValueOnce(opStatus("running"))
            .mockResolvedValueOnce(opStatus("running"))
            .mockResolvedValueOnce(opStatus("completed"));
        await expect(pollOperationUntilSettled("op_web_x", undefined, FAST)).resolves.toBe("completed");
        expect(fetchMock).toHaveBeenCalledTimes(3);
        expect(String(fetchMock.mock.calls[0][0])).toContain("/api/v1/rico/operations/op_web_x");
    });

    it("resolves 'terminal' for a failed operation — retry becomes legitimate", async () => {
        fetchMock.mockResolvedValueOnce(opStatus("failed"));
        await expect(pollOperationUntilSettled("op_web_x", undefined, FAST)).resolves.toBe("terminal");
    });

    it("resolves 'terminal' when the server no longer treats a running record as live", async () => {
        // status running but active:false — the server-side orphan ceiling.
        fetchMock.mockResolvedValueOnce(opStatus("running", { active: false }));
        await expect(pollOperationUntilSettled("op_web_x", undefined, FAST)).resolves.toBe("terminal");
    });

    it("resolves 'terminal' on 404 (operation unknown — state lost)", async () => {
        fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "Operation not found" }, 404));
        await expect(pollOperationUntilSettled("op_web_x", undefined, FAST)).resolves.toBe("terminal");
    });

    it("resolves 'unavailable' after three consecutive transport errors", async () => {
        fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
        await expect(pollOperationUntilSettled("op_web_x", undefined, FAST)).resolves.toBe("unavailable");
        expect(fetchMock).toHaveBeenCalledTimes(3);
    });

    it("resolves 'still_running' when the budget ends while active — never a re-send signal", async () => {
        fetchMock.mockImplementation(async () => opStatus("running"));
        await expect(
            pollOperationUntilSettled("op_web_x", undefined, { intervalMs: 5, budgetMs: 40 }),
        ).resolves.toBe("still_running");
    });

    it("resolves 'aborted' when the signal fires mid-wait", async () => {
        fetchMock.mockImplementation(async () => opStatus("running"));
        const controller = new AbortController();
        const verdict = pollOperationUntilSettled("op_web_x", controller.signal, {
            intervalMs: 5_000,
            budgetMs: 60_000,
        });
        setTimeout(() => controller.abort(), 10);
        await expect(verdict).resolves.toBe("aborted");
    });

    it("a transient error followed by completion still resolves 'completed'", async () => {
        fetchMock
            .mockRejectedValueOnce(new TypeError("Failed to fetch"))
            .mockResolvedValueOnce(opStatus("completed"));
        await expect(pollOperationUntilSettled("op_web_x", undefined, FAST)).resolves.toBe("completed");
    });
});

describe("mintOperationId", () => {
    it("mints backend-valid, per-turn-unique ids", () => {
        const a = mintOperationId();
        const b = mintOperationId();
        expect(a).toMatch(/^op_web_[0-9a-f]+$/);
        expect(a.length).toBeGreaterThanOrEqual(8);
        expect(a.length).toBeLessThanOrEqual(80);
        expect(a).not.toBe(b);
    });
});
