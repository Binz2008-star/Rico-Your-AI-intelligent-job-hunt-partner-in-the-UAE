/**
 * Billing mode helpers and WhatsApp upgrade URL builder.
 *
 * NEXT_PUBLIC_BILLING_MODE=manual  → WhatsApp-assisted activation (default)
 * NEXT_PUBLIC_BILLING_MODE=stripe  → Stripe checkout
 */

export function isManualBillingMode(): boolean {
    return (process.env.NEXT_PUBLIC_BILLING_MODE ?? "manual") !== "stripe";
}

/**
 * Build the WhatsApp deep-link for the upgrade flow.
 * Opens a pre-filled conversation with the Rico support number.
 */
export function buildWhatsAppUpgradeUrl(plan?: string): string {
    const number =
        process.env.NEXT_PUBLIC_RICO_WHATSAPP_NUMBER ?? "971585989080";
    const planLabel = plan ? ` (${plan.charAt(0).toUpperCase() + plan.slice(1)})` : "";
    const text = `I want to upgrade to Rico Pro${planLabel}. My account email is:`;
    return `https://wa.me/${number}?text=${encodeURIComponent(text)}`;
}
