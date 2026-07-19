import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "./test-utils";

/**
 * fix/command-subscription-cta (owner directive 2026-07-19).
 *
 * Pins:
 *  - conservative detection of subscription mentions (URL/path only — no
 *    keyword heuristics);
 *  - bare `ricohunt.com/subscription` text is linkified to the INTERNAL
 *    /subscription route in BOTH markdown renderers (never a dead string,
 *    never an external navigation);
 *  - the structured CTA navigates to /subscription, localized EN/AR with a
 *    flipped RTL arrow;
 *  - no plan copy lives in the CTA (/subscription is the source of truth).
 */

vi.mock("next/link", () => ({
    default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

import { SubscriptionCta } from "@/components/command/SubscriptionCta";
import { RicoReplyMarkdown } from "@/components/command/RicoReplyMarkdown";
import { RicoMarkdownContent } from "@/components/ui/rico/RicoMarkdownContent";
import {
    linkifySubscriptionMentions,
    mentionsSubscription,
    SUBSCRIPTION_PATH,
} from "@/lib/subscriptionCta";

const AR_REPLY =
    "للترقية، يرجى زيارة الرابط التالي: ricohunt.com/subscription 🔗 وبعدها نقدر نكمل معًا.";

beforeEach(() => {
    window.localStorage.clear();
});

describe("mentionsSubscription (pure, conservative)", () => {
    it("detects bare, www, and schemed URL mentions — including mid-Arabic-sentence", () => {
        expect(mentionsSubscription("visit ricohunt.com/subscription now")).toBe(true);
        expect(mentionsSubscription("see https://ricohunt.com/subscription")).toBe(true);
        expect(mentionsSubscription("see http://www.ricohunt.com/subscription.")).toBe(true);
        expect(mentionsSubscription(AR_REPLY)).toBe(true);
    });

    it("detects standalone /subscription path tokens and markdown targets", () => {
        expect(mentionsSubscription("open /subscription to upgrade")).toBe(true);
        expect(mentionsSubscription("[عرض الباقات](/subscription)")).toBe(true);
    });

    it("stays silent for plan talk without a link, other domains, and glued words", () => {
        expect(mentionsSubscription("the free plan includes 50 messages")).toBe(false);
        expect(mentionsSubscription("visit evil.com/subscription")).toBe(false);
        expect(mentionsSubscription("notricohunt.com/subscription")).toBe(false);
        expect(mentionsSubscription("")).toBe(false);
    });
});

describe("linkifySubscriptionMentions (pure)", () => {
    it("wraps a bare mention into an internal markdown link, keeping the visible label", () => {
        expect(linkifySubscriptionMentions("زر ricohunt.com/subscription الآن")).toBe(
            "زر [ricohunt.com/subscription](/subscription) الآن",
        );
    });

    it("leaves existing markdown links untouched (label and target)", () => {
        const already = "[ricohunt.com/subscription](https://ricohunt.com/subscription)";
        expect(linkifySubscriptionMentions(already)).toBe(already);
    });

    it("passes unrelated text through unchanged", () => {
        expect(linkifySubscriptionMentions("no links here")).toBe("no links here");
    });
});

describe("markdown renderers — the mention is never a dead string", () => {
    it("RicoReplyMarkdown renders the bare Arabic mention as an internal /subscription anchor", () => {
        render(<RicoReplyMarkdown text={AR_REPLY} />);
        const link = screen.getByRole("link", { name: "ricohunt.com/subscription" });
        expect(link).toHaveAttribute("href", SUBSCRIPTION_PATH);
    });

    it("RicoMarkdownContent renders it as an internal same-tab anchor (no target=_blank)", () => {
        render(<RicoMarkdownContent>{AR_REPLY}</RicoMarkdownContent>);
        const link = screen.getByRole("link", { name: "ricohunt.com/subscription" });
        expect(link).toHaveAttribute("href", SUBSCRIPTION_PATH);
        expect(link).not.toHaveAttribute("target");
    });

    it("RicoMarkdownContent still forces new-tab + noopener for external links", () => {
        render(<RicoMarkdownContent>{"see [docs](https://example.com/x)"}</RicoMarkdownContent>);
        const link = screen.getByRole("link", { name: "docs" });
        expect(link).toHaveAttribute("target", "_blank");
        expect(link).toHaveAttribute("rel", "noopener noreferrer");
    });
});

describe("SubscriptionCta — the structured affordance", () => {
    it("navigates to the internal /subscription route with the English label", () => {
        renderWithProviders(<SubscriptionCta />);
        const cta = screen.getByTestId("subscription-cta");
        expect(cta).toHaveAttribute("href", SUBSCRIPTION_PATH);
        expect(cta).toHaveTextContent("View plans");
        expect(cta).toHaveTextContent("→");
    });

    it("renders the Arabic label with a flipped arrow in Arabic mode", async () => {
        window.localStorage.setItem("rico-language", "ar");
        renderWithProviders(<SubscriptionCta />);
        const cta = await screen.findByTestId("subscription-cta");
        expect(cta).toHaveTextContent("عرض الباقات");
        expect(cta).toHaveTextContent("←");
    });

    it("carries no plan copy — /subscription stays the source of truth", () => {
        renderWithProviders(<SubscriptionCta />);
        const row = screen.getByTestId("subscription-cta-row");
        expect(row.textContent).not.toMatch(/21\.50|79|Monthly|درهم/);
    });
});
