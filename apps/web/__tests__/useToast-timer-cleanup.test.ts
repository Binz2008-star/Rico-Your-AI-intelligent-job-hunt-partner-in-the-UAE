import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { renderHook, act } = await import("@testing-library/react");
const { useToast } = await import("@/hooks/useToast");

// Regression guards for useToast auto-dismiss timers. Timers must be cleaned
// up on unmount and managed per toast so refreshing one notification never
// cancels the auto-dismiss timer of another notification.
describe("useToast timer management", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("does not invoke the auto-dismiss callback after unmounting before 3.5s", () => {
    const { result, unmount } = renderHook(() => useToast());

    act(() => {
      result.current.toast("hello", "info", 3500);
    });
    expect(result.current.toasts).toHaveLength(1);

    // Unmount before the 3.5s auto-dismiss timer fires.
    unmount();

    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    // Advancing past the duration must not throw or emit a React
    // setState-after-unmount warning — the timer should have been cleared.
    expect(() => {
      act(() => {
        vi.advanceTimersByTime(5000);
      });
    }).not.toThrow();

    expect(errorSpy).not.toHaveBeenCalled();
  });

  it("still auto-dismisses the toast while mounted", () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast("hello", "success", 3500);
    });
    expect(result.current.toasts).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(3500);
    });
    expect(result.current.toasts).toHaveLength(0);
  });

  it("refreshes only the duplicate toast timer and preserves unrelated timers", () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast("first", "info", 1000);
      result.current.toast("second", "success", 2000);
    });
    expect(result.current.toasts).toHaveLength(2);

    act(() => {
      vi.advanceTimersByTime(500);
      result.current.toast("first", "info", 1000);
    });

    // The duplicate is not stacked, and its refreshed timer must not cancel
    // the independently scheduled auto-dismiss for "second".
    expect(result.current.toasts).toHaveLength(2);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.toasts.map((toast) => toast.message)).toEqual([
      "second",
    ]);

    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(result.current.toasts).toHaveLength(0);
  });
});
