import type { Metadata } from "next";
import { RefundPolicyContent } from "./RefundPolicyContent";

export const metadata: Metadata = {
    title: "Refund & Cancellation Policy",
    description: "Refund and cancellation policy for Rico Hunt subscriptions.",
    alternates: { canonical: "/refund-policy" },
};

export default function RefundPolicyPage() {
    return <RefundPolicyContent />;
}
