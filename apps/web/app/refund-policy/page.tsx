import type { Metadata } from "next";
import { RefundPolicyContent } from "./RefundPolicyContent";

export const metadata: Metadata = {
    title: "Refund & Cancellation Policy | Rico Hunt",
    description: "Refund and cancellation policy for Rico Hunt subscriptions.",
};

export default function RefundPolicyPage() {
    return <RefundPolicyContent />;
}
