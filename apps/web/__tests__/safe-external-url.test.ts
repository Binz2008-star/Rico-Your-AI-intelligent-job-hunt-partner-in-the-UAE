/**
 * LOW-1 (security audit refresh 2026-07-21): open-redirect guard for the
 * backend-supplied navigation targets in SubscriptionAtelier
 * (`req.whatsapp_url`, `portal_url`). Pins the https + host-allowlist contract
 * that both nav sinks now route through. Pre-fix the component navigated to
 * these URLs unconditionally.
 */
import { describe, it, expect } from "vitest";
import { safeExternalUrl } from "../lib/safe-external-url";

const WHATSAPP = ["wa.me", "whatsapp.com"];
const PADDLE = ["paddle.com"];

describe("safeExternalUrl", () => {
    it("accepts an exact allowed host over https", () => {
        expect(safeExternalUrl("https://wa.me/971585989080?text=Hi", WHATSAPP))
            .toBe("https://wa.me/971585989080?text=Hi");
        expect(safeExternalUrl("https://paddle.com/portal", PADDLE))
            .toBe("https://paddle.com/portal");
    });

    it("accepts a subdomain of an allowed host", () => {
        expect(safeExternalUrl("https://api.whatsapp.com/send?x=1", WHATSAPP))
            .toBe("https://api.whatsapp.com/send?x=1");
        expect(safeExternalUrl("https://customer-portal.paddle.com/abc", PADDLE))
            .toBe("https://customer-portal.paddle.com/abc");
        expect(safeExternalUrl("https://sandbox-customer-portal.paddle.com/abc", PADDLE))
            .toBe("https://sandbox-customer-portal.paddle.com/abc");
    });

    it("rejects a non-https scheme", () => {
        expect(safeExternalUrl("http://paddle.com/portal", PADDLE)).toBeNull();
    });

    it("rejects a disallowed host", () => {
        expect(safeExternalUrl("https://evil.example.com/steal", PADDLE)).toBeNull();
        expect(safeExternalUrl("https://evil.example.com/steal", WHATSAPP)).toBeNull();
    });

    it("rejects look-alike hosts (no substring/suffix bypass)", () => {
        expect(safeExternalUrl("https://evilpaddle.com/x", PADDLE)).toBeNull();
        expect(safeExternalUrl("https://paddle.com.evil.com/x", PADDLE)).toBeNull();
        expect(safeExternalUrl("https://evilwa.me/x", WHATSAPP)).toBeNull();
        expect(safeExternalUrl("https://whatsapp.com.attacker.io/x", WHATSAPP)).toBeNull();
    });

    it("rejects dangerous schemes", () => {
        expect(safeExternalUrl("javascript:alert(1)", PADDLE)).toBeNull();
        expect(safeExternalUrl("data:text/html,<script>alert(1)</script>", PADDLE)).toBeNull();
    });

    it("rejects empty / malformed / non-string input", () => {
        expect(safeExternalUrl("", PADDLE)).toBeNull();
        expect(safeExternalUrl("not a url", PADDLE)).toBeNull();
        expect(safeExternalUrl(null, PADDLE)).toBeNull();
        expect(safeExternalUrl(undefined, PADDLE)).toBeNull();
        expect(safeExternalUrl(12345, PADDLE)).toBeNull();
    });
});
