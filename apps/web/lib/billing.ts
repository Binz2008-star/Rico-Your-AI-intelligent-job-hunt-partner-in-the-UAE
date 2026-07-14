/**
 * Billing mode helpers and WhatsApp upgrade URL builder.
 *
 * The current public release is Paddle-only. Keep these helpers explicit so a
 * stale Vercel NEXT_PUBLIC_BILLING_MODE=manual value cannot silently switch the
 * subscription UI back to WhatsApp-assisted activation.
 *
 * SECURITY: PADDLE_API_KEY must NEVER appear in NEXT_PUBLIC_* variables or
 * any client-side code. All Paddle server-side API calls go through the
 * backend proxy. The only public Paddle key is NEXT_PUBLIC_PADDLE_CLIENT_TOKEN
 * (a read-only Paddle.js token used solely to initialize the checkout widget).
 */

export function isManualBillingMode(): boolean {
    return false;
}

export function isPaddleBillingMode(): boolean {
    return true;
}

/**
 * Build the WhatsApp deep-link for the upgrade flow.
 * Retained only for support/rollback code paths; not used by the active
 * subscription checkout UI.
 */
export function buildWhatsAppUpgradeUrl(plan?: string, email?: string | null, priceMonthly?: number | null): string {
    const raw = process.env.NEXT_PUBLIC_RICO_WHATSAPP_NUMBER ?? "971585989080";
    const number = raw.replace(/\D/g, "");
    const planLabel = plan ? plan.charAt(0).toUpperCase() + plan.slice(1) : "Pro";
    const priceStr = priceMonthly ? ` (AED ${priceMonthly}/month)` : "";
    const emailStr = email ? ` ${email}` : "";
    const text = `I want to upgrade to Rico ${planLabel}${priceStr}. My account email is:${emailStr}`;
    return `https://wa.me/${number}?text=${encodeURIComponent(text)}`;
}

/**
 * Build the WhatsApp deep-link for support requests.
 */
export function buildWhatsAppManageUrl(): string {
    const raw = process.env.NEXT_PUBLIC_RICO_WHATSAPP_NUMBER ?? "971585989080";
    const number = raw.replace(/\D/g, "");
    const text = "I want to manage my Rico subscription. My account email is:";
    return `https://wa.me/${number}?text=${encodeURIComponent(text)}`;
}
