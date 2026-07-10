import "@testing-library/jest-dom";
import { vi, beforeEach } from "vitest";

// Default `next/navigation` mock. Many components call useRouter()/usePathname()
// etc.; without a mounted App Router context jsdom throws
// "invariant expected app router to be mounted". Providing stable, clearable
// router spies here fixes that for every test file. Individual tests may still
// `vi.mock("next/navigation")` locally to override this default.
const { nextNavigationRouter } = vi.hoisted(() => ({
  nextNavigationRouter: {
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => nextNavigationRouter,
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
  redirect: vi.fn(),
  notFound: vi.fn(),
  useServerInsertedHTML: vi.fn(),
}));

beforeEach(() => {
  Object.values(nextNavigationRouter).forEach((fn) => fn.mockClear());
});

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
