import { beforeEach, describe, expect, it, vi } from "vitest";

type JsonValue = Record<string, unknown>;

type ResponseLike = {
  ok: boolean;
  status: number;
  json: () => Promise<JsonValue>;
};

function jsonResponse(body: JsonValue, status = 200): ResponseLike {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<ResponseLike>>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

describe("getJobs", () => {
  it("preserves match_explanation from the jobs API response", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        jobs: [
          {
            id: "job-1",
            title: "Senior Python Developer",
            company: "Acme",
            location: "Remote",
            score: 84,
            link: "https://example.com/jobs/1",
            match_explanation: {
              verdict: "strong_fit",
              summary: "Strong fit for Senior Python Developer at Acme.",
              why_this_fits: ["Matches your skills: Python, SQL."],
              worth_checking: ["Salary is not listed."],
              recommended_next_step: "Apply or ask Rico to tailor your CV for this role.",
              confidence: "high",
            },
          },
        ],
        total: 1,
        page: 1,
        limit: 20,
        pages: 1,
      })
    );

    const { getJobs } = await import("@/lib/api");
    const result = await getJobs();

    expect(String(fetchMock.mock.calls[0]?.[0])).toBe("/proxy/api/v1/jobs?page=1&limit=20&min_score=0");
    expect(result.jobs[0]?.match_explanation?.verdict).toBe("strong_fit");
    expect(result.jobs[0]?.match_explanation?.why_this_fits).toEqual([
      "Matches your skills: Python, SQL.",
    ]);
  });
});
