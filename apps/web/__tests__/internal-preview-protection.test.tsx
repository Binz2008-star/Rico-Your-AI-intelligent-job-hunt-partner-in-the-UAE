/**
 * Production hygiene — internal preview surfaces must not be publicly
 * reachable in production (finding F-4, AI_WORKSPACE/ATELIER_FULL_SITE_MIGRATION.md §7).
 *
 * Contract pinned here:
 *  - production (VERCEL_ENV=production): every internal preview page 404s via
 *    notFound() — never a redirect, so no redirect loop is possible;
 *  - Vercel preview deployments (VERCEL_ENV=preview) and local development
 *    (VERCEL_ENV unset / "development") retain access for approved review;
 *  - no production navigation source links to an internal preview route;
 *  - robots disallow covers every internal preview route (defense in depth,
 *    not the only protection);
 *  - no next.config redirect touches an internal preview route.
 */
import { describe, expect, it, vi, afterEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";

const { notFoundMock } = vi.hoisted(() => ({
  notFoundMock: vi.fn((): never => {
    throw new Error("NEXT_NOT_FOUND");
  }),
}));
const { redirectMock } = vi.hoisted(() => ({
  redirectMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  notFound: notFoundMock,
  redirect: redirectMock,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
}));

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: any) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

// The pages under test wrap heavy client components — stub them so this suite
// exercises only the access gate, not the preview content.
vi.mock("@/app/design-preview/_client", () => ({
  default: () => <div data-testid="preview-client" />,
}));
vi.mock("@/app/rico-preview/_client", () => ({
  default: () => <div data-testid="preview-client" />,
}));
vi.mock("@/app/design-gallery/_client", () => ({
  default: () => <div data-testid="preview-client" />,
}));
vi.mock("@/app/design-gallery/atelier/_specimen", () => ({
  default: () => <div data-testid="preview-client" />,
}));
vi.mock("@/app/sandbox/command-primitives/_client", () => ({
  default: () => <div data-testid="preview-client" />,
}));

import {
  INTERNAL_PREVIEW_ROUTES,
  isInternalPreviewBlocked,
} from "@/lib/internalPreview";
import DesignPreviewPage from "@/app/design-preview/page";
import RicoPreviewPage from "@/app/rico-preview/page";
import DesignGalleryPage from "@/app/design-gallery/page";
import AtelierSpecimenPage from "@/app/design-gallery/atelier/page";
import CommandPrimitivesSandboxPage from "@/app/sandbox/command-primitives/page";
import robots from "@/app/robots";
import { mainNavSections, utilityNavItems } from "@/components/layout/app-nav";
import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";

const PAGES: Array<[string, () => JSX.Element]> = [
  ["/design-preview", DesignPreviewPage],
  ["/rico-preview", RicoPreviewPage],
  ["/design-gallery", DesignGalleryPage],
  ["/design-gallery/atelier", AtelierSpecimenPage],
  ["/sandbox/command-primitives", CommandPrimitivesSandboxPage],
];

function withVercelEnv(value: string | undefined, fn: () => void) {
  const prev = process.env.VERCEL_ENV;
  if (value === undefined) {
    delete process.env.VERCEL_ENV;
  } else {
    process.env.VERCEL_ENV = value;
  }
  try {
    fn();
  } finally {
    if (prev === undefined) {
      delete process.env.VERCEL_ENV;
    } else {
      process.env.VERCEL_ENV = prev;
    }
  }
}

const isInternalHref = (href: string) =>
  INTERNAL_PREVIEW_ROUTES.some(
    (route) => href === route || href.startsWith(`${route}/`),
  ) || href.startsWith("/sandbox");

afterEach(() => {
  notFoundMock.mockClear();
  redirectMock.mockClear();
});

describe("internal preview gate — environment semantics", () => {
  it("blocks only real production", () => {
    expect(isInternalPreviewBlocked("production")).toBe(true);
    expect(isInternalPreviewBlocked("preview")).toBe(false);
    expect(isInternalPreviewBlocked("development")).toBe(false);
    expect(isInternalPreviewBlocked(undefined)).toBe(false);
  });
});

describe("internal preview pages — anonymous production access is blocked (404, not redirect)", () => {
  it.each(PAGES)("%s calls notFound() when VERCEL_ENV=production", (_route, Page) => {
    withVercelEnv("production", () => {
      expect(() => Page()).toThrow("NEXT_NOT_FOUND");
    });
    expect(notFoundMock).toHaveBeenCalledTimes(1);
    // 404 must come from notFound(), never a redirect → no redirect loop.
    expect(redirectMock).not.toHaveBeenCalled();
  });
});

describe("internal preview pages — approved review access is retained", () => {
  it.each(PAGES)("%s renders on Vercel preview deployments", (_route, Page) => {
    withVercelEnv("preview", () => {
      renderWithProviders(Page());
    });
    expect(screen.getByTestId("preview-client")).toBeInTheDocument();
    expect(notFoundMock).not.toHaveBeenCalled();
  });

  it.each(PAGES)("%s renders in local development (VERCEL_ENV unset)", (_route, Page) => {
    withVercelEnv(undefined, () => {
      renderWithProviders(Page());
    });
    expect(screen.getByTestId("preview-client")).toBeInTheDocument();
    expect(notFoundMock).not.toHaveBeenCalled();
  });
});

describe("robots — defense in depth", () => {
  it("disallows every internal preview route for the default crawler rule", () => {
    const config = robots();
    const rules = Array.isArray(config.rules) ? config.rules : [config.rules];
    const defaultRule = rules.find((rule) => rule?.userAgent === "*");
    expect(defaultRule).toBeDefined();
    const disallow = Array.isArray(defaultRule!.disallow)
      ? defaultRule!.disallow
      : [defaultRule!.disallow];
    // /sandbox covers /sandbox/command-primitives by prefix.
    expect(disallow).toEqual(
      expect.arrayContaining([
        "/design-preview",
        "/rico-preview",
        "/design-gallery",
        "/sandbox",
      ]),
    );
    const allow = Array.isArray(defaultRule!.allow)
      ? defaultRule!.allow
      : [defaultRule!.allow];
    for (const entry of allow) {
      expect(isInternalHref(String(entry))).toBe(false);
    }
  });
});

describe("no public navigation exposes an internal preview route", () => {
  it("legacy AppSidebar nav config (app-nav.ts) has no internal preview hrefs", () => {
    const hrefs = [
      ...mainNavSections.flatMap((section) => section.items.map((item) => item.href)),
      ...utilityNavItems.map((item) => item.href),
    ];
    for (const href of hrefs) {
      expect(isInternalHref(href)).toBe(false);
    }
  });

  it("WorkspaceShell canonical nav renders no internal preview links", () => {
    withVercelEnv(undefined, () => {
      renderWithProviders(
        <WorkspaceShell>
          <div />
        </WorkspaceShell>,
      );
    });
    const anchors = Array.from(document.querySelectorAll("a"));
    expect(anchors.length).toBeGreaterThan(0);
    for (const anchor of anchors) {
      expect(isInternalHref(anchor.getAttribute("href") ?? "")).toBe(false);
    }
  });
});

describe("next.config redirects — no internal preview route involved", () => {
  it("no redirect source or destination touches an internal preview route", async () => {
    const nextConfig = (await import("../next.config.js")).default;
    const redirects = await nextConfig.redirects();
    for (const rule of redirects) {
      expect(isInternalHref(rule.source)).toBe(false);
      expect(isInternalHref(String(rule.destination ?? ""))).toBe(false);
    }
  });
});
