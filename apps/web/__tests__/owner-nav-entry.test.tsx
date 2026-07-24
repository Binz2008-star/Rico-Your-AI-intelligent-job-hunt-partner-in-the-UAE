import { screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "./test-utils";

/**
 * The owner-only navigation entry must be hidden from normal users: it renders
 * only when the server-computed /me.is_owner flag is true. This pins the
 * "frontend hides the route entry from normal users" requirement.
 */

const { fetchMe } = vi.hoisted(() => ({ fetchMe: vi.fn() }));

vi.mock("next/navigation", () => ({
    usePathname: () => "/dashboard",
}));
vi.mock("next/link", () => ({
    default: ({ children, href }: { children: ReactNode; href: string }) => <a href={href}>{children}</a>,
}));
vi.mock("@/lib/api", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api")>();
    return { ...actual, fetchMe };
});

import { OwnerNavEntry } from "@/components/admin/OwnerNavEntry";

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.clearAllMocks());

describe("OwnerNavEntry", () => {
    it("renders the /admin/subscribers link for the owner account", async () => {
        fetchMe.mockResolvedValue({ email: "o@x.com", role: "user", authenticated: true, is_owner: true });
        render(<OwnerNavEntry />);
        await waitFor(() => {
            const link = screen.getByRole("link");
            expect(link).toHaveAttribute("href", "/admin/subscribers");
        });
    });

    it("renders nothing for a normal (non-owner) authenticated user", async () => {
        fetchMe.mockResolvedValue({ email: "u@x.com", role: "user", authenticated: true, is_owner: false });
        const { container } = render(<OwnerNavEntry />);
        await waitFor(() => expect(fetchMe).toHaveBeenCalled());
        expect(screen.queryByRole("link")).toBeNull();
        expect(container).toBeEmptyDOMElement();
    });

    it("renders nothing for a guest", async () => {
        fetchMe.mockResolvedValue({ email: null, role: "guest", authenticated: false, guest: true });
        const { container } = render(<OwnerNavEntry />);
        await waitFor(() => expect(fetchMe).toHaveBeenCalled());
        expect(container).toBeEmptyDOMElement();
    });
});
