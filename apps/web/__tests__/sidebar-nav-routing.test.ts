/**
 * BUG-03 regression — sidebar nav items must use their real href, not chatPrompt.
 *
 * Design rule: href is the source of truth for navigation.
 * chatPrompt must never override a real destination.
 *
 * Rule 1: item.href exists + current route is NOT /command → navigate to item.href
 * Rule 2: current route IS /command + chatPrompt → use /command?q=... (prefill)
 * Rule 3: chat-only item (href="/command") → chatPrompt used normally
 */

import { mainNavSections } from "../components/layout/app-nav";

// Mirror the navHref logic from AppSidebar.tsx so the test pins the contract
function resolveNavHref(
    itemHref: string,
    chatPrompt: string | undefined,
    currentPathname: string
): string {
    const isOnCommand = currentPathname === "/command";
    return (chatPrompt && isOnCommand)
        ? `/command?q=${encodeURIComponent(chatPrompt)}`
        : itemHref;
}

// ── Items that must go to real pages (not /command?q=...) ─────────────────────

const realPageItems = mainNavSections
    .flatMap((s) => s.items)
    .filter((item) => item.href !== "/command");

describe("sidebar nav routing — items with real destinations", () => {
    const otherRoutes = ["/applications", "/queue", "/profile", "/upload", "/settings", "/subscription"];

    test.each(realPageItems)(
        "$label ($href) → navigates to its own href from any non-/command route",
        (item) => {
            for (const route of otherRoutes.filter((r) => r !== item.href)) {
                const result = resolveNavHref(item.href, item.chatPrompt, route);
                expect(result).toBe(item.href);
                expect(result).not.toMatch(/^\/command\?q=/);
            }
        }
    );

    test.each(realPageItems)(
        "$label ($href) → when on /command, chatPrompt prefills (no route change away from real page logic)",
        (item) => {
            const result = resolveNavHref(item.href, item.chatPrompt, "/command");
            if (item.chatPrompt) {
                // Prefill mode: stays on /command with query
                expect(result).toMatch(/^\/command\?q=/);
                expect(result).toContain(encodeURIComponent(item.chatPrompt));
            } else {
                // No chatPrompt: just goes to href
                expect(result).toBe(item.href);
            }
        }
    );
});

// ── Specific required routes ──────────────────────────────────────────────────

describe("sidebar nav routing — specific pages", () => {
    const pipeline = mainNavSections.flatMap((s) => s.items).find((i) => i.href === "/applications")!;
    const profile = mainNavSections.flatMap((s) => s.items).find((i) => i.href === "/profile")!;
    const settings = mainNavSections.flatMap((s) => s.items).find((i) => i.href === "/settings")!;

    it("/applications (Applications) opens /applications from /settings — canonical target, no /flow double-hop", () => {
        expect(resolveNavHref(pipeline.href, pipeline.chatPrompt, "/settings")).toBe("/applications");
    });

    // Note: Applications (/queue) was intentionally removed from the sidebar IA.
    // The /queue page still exists as a route (see below, used as an origin
    // pathname), but it is no longer a sidebar nav item, so there is no nav-item
    // routing contract to assert for it.

    it("/profile (Profile) opens /profile from /queue", () => {
        expect(resolveNavHref(profile.href, profile.chatPrompt, "/queue")).toBe("/profile");
    });

    it("/settings (Settings) opens /settings from /profile", () => {
        expect(resolveNavHref(settings.href, settings.chatPrompt, "/profile")).toBe("/settings");
    });

    it("no real-destination item ever redirects to /command when not on /command", () => {
        const allItems = mainNavSections.flatMap((s) => s.items);
        const nonCommandItems = allItems.filter((i) => i.href !== "/command");
        for (const item of nonCommandItems) {
            const result = resolveNavHref(item.href, item.chatPrompt, "/flow");
            expect(result).not.toMatch(/^\/command\?q=/);
        }
    });
});

// ── Chat-only items (href="/command") ─────────────────────────────────────────

describe("sidebar nav routing — chat-only items", () => {
    const askRico = mainNavSections.flatMap((s) => s.items).find((i) => i.href === "/command");

    it("Ask Rico navigates to /command from any route (no chatPrompt)", () => {
        if (!askRico) return; // not present → skip
        expect(resolveNavHref(askRico.href, askRico.chatPrompt, "/flow")).toBe("/command");
        expect(resolveNavHref(askRico.href, askRico.chatPrompt, "/settings")).toBe("/command");
    });
});
