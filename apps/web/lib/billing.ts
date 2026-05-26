/**
 * Billing mode helpers and WhatsApp upgrade URL builder.
 *
 * NEXT_PUBLIC_BILLING_MODE=manual  → WhatsApp-assisted activation (default)
 * NEXT_PUBLIC_BILLING_MODE=stripe  → Stripe checkout
 */

export function isManualBillingMode(): boolean {
    return (process.env.NEXT_PUBLIC_BILLING_MODE ?? "manual").trim().toLowerCase() !== "stripe";
}

/**
 * Build the WhatsApp deep-link for the upgrade flow.
 * Opens a pre-filled conversation with the Rico support number.
 */
export function buildWhatsAppUpgradeUrl(plan?: string): string {
    const number =
        process.env.NEXT_PUBLIC_RICO_WHATSAPP_NUMBER ?? "971585989080";
    const planLabel = plan ? plan.charAt(0).toUpperCase() + plan.slice(1) : "Pro";
    const text = `I want to upgrade to Rico ${planLabel}. My account email is:`;
    return `https://wa.me/${number}?text=${encodeURIComponent(text)}`;
}

/**
 * Build the WhatsApp deep-link for subscription management requests.
 */
export function buildWhatsAppManageUrl(): string {
    const number =
        process.env.NEXT_PUBLIC_RICO_WHATSAPP_NUMBER ?? "971585989080";
    const text = "I want to manage my Rico subscription. My account email is:";
    return `https://wa.me/${number}?text=${encodeURIComponent(text)}`;
}
