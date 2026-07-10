import "@testing-library/jest-dom";
import { vi } from "vitest";

// Default next/navigation mock so any component under test that calls
// useRouter/usePathname/useSearchParams/useParams doesn't crash with
// "invariant expected app router to be mounted" when a test doesn't render
// inside Next's App Router. Test files that need router behavior (e.g.
// asserting router.push calls, or a specific pathname) still declare their
// own vi.mock("next/navigation", ...), which overrides this default.
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
  redirect: vi.fn(),
  notFound: vi.fn(),
}));

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
  writable: true,
  value: vi.fn(),
});
