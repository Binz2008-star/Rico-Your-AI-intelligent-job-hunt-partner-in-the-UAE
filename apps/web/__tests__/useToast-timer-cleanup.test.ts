import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { renderHook, act } = await import("@testing-library/react");
const { useToast } = await import("@/hooks/useToast");

// Regression guard for the useToast auto-dismiss timer leak: a toast schedules a
// setTimeout that calls setToasts after `duration` ms. If the component unmounts
// before the timer fires and the timer is not cleared, the callback runs after
// teardown — in jsdom that throws "ReferenceError: window is not defined" and
// fails the whole run; in the browser it is a setState-on-unmounted-component leak.
describe("useToast timer cleanup on unmount", () => {
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
});
