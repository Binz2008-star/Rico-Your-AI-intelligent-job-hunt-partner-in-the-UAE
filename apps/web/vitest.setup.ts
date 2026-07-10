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

// jsdom does not implement Element.prototype.scrollTo. Components that scroll a
// container via a ref (e.g. the command page's scrollMessagesPane calling
// pane.scrollTo(...)) otherwise throw "scrollTo is not a function" inside a
// requestAnimationFrame callback, which surfaces as a cross-file flake in the
// full-suite run. Stub it so those scroll calls are no-ops in tests.
Object.defineProperty(HTMLElement.prototype, "scrollTo", {
  writable: true,
  value: vi.fn(),
});
Object.defineProperty(window, "scrollTo", {
  writable: true,
  value: vi.fn(),
});
