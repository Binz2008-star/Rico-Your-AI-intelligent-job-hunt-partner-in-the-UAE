import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

const {
  getApplicationsMock,
  getApplicationStatsMock,
  getJobsMock,
  getSettingsMock,
} = vi.hoisted(() => ({
  getApplicationsMock: vi.fn(),
  getApplicationStatsMock: vi.fn(),
  getJobsMock: vi.fn(),
  getSettingsMock: vi.fn(),
}));

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {
    statusCode: number;

    constructor(message: string, statusCode: number) {
      super(message);
      this.statusCode = statusCode;
    }
  },
  getApplications: getApplicationsMock,
  getApplicationStats: getApplicationStatsMock,
  getJobs: getJobsMock,
  getSettings: getSettingsMock,
}));

import { DashboardStats } from "@/components/DashboardStats";

beforeEach(() => {
  vi.useFakeTimers();
  getApplicationsMock.mockReset();
  getApplicationStatsMock.mockReset();
  getJobsMock.mockReset();
  getSettingsMock.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("Dashboard overview cards", () => {
  it("shows an explicit timeout message when the jobs request stalls", async () => {
    getJobsMock.mockImplementation(
      (_page?: number, _limit?: number, _minScore?: number, _source?: string, signal?: AbortSignal) =>
        new Promise((_, reject) => {
          signal?.addEventListener("abort", () => {
            const error = new Error("Aborted");
            error.name = "AbortError";
            reject(error);
          });
        })
    );
    getApplicationsMock.mockResolvedValue({
      applications: [],
      total: 0,
      page: 1,
      limit: 1,
      pages: 1,
    });
    getApplicationStatsMock.mockResolvedValue({
      total: 0,
      by_status: {},
      applied: 0,
      saved: 0,
      interview: 0,
      rejected: 0,
      offer: 0,
    });
    getSettingsMock.mockResolvedValue({
      include_keywords: [],
      exclude_keywords: [],
      min_score: 50,
      max_daily_applies: 0,
      telegram_chat_id: "",
      score_threshold_apply: 75,
      score_threshold_watch: 50,
    });

    render(<DashboardStats />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(screen.getByText("Jobs request timed out after 5s.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry jobs" })).toBeInTheDocument();
    expect(screen.getByText("Applications tracked")).toBeInTheDocument();
    expect(screen.getByText("No tracked applications yet.")).toBeInTheDocument();
    expect(screen.getByText("Daily reviewed actions")).toBeInTheDocument();
    expect(screen.getByText("Daily reviewed actions limit not set.")).toBeInTheDocument();
  }, 10000);
});
