"use client";

/**
 * SubscriptionCta — the structured "View plans" affordance rendered under a
 * /command reply that directs the user to the subscription surface
 * (fix/command-subscription-cta, owner directive 2026-07-19).
 *
 * A real Next.js Link to the internal /subscription route — the model's
 * raw-text URL is never the navigation affordance, and /subscription stays
 * the single source of truth for plan names and prices (this component
 * carries no plan copy). Styled with currentColor only, so it renders
 * correctly in both the authenticated Atelier scope and the public surface,
 * light or dark, without depending on either scope's CSS variables. RTL:
 * the arrow flips with the language.
 */

import Link from "next/link";
import { useLanguage } from "@/contexts/LanguageContext";
import { SUBSCRIPTION_PATH } from "@/lib/subscriptionCta";

export function SubscriptionCta() {
    const { language } = useLanguage();
    const isAr = language === "ar";
    return (
        <div className="mt-2.5" data-testid="subscription-cta-row">
            <Link
                href={SUBSCRIPTION_PATH}
                data-testid="subscription-cta"
                className="inline-flex items-center gap-1.5 rounded-lg border border-current px-3.5 py-1.5 text-[12.5px] font-semibold transition-opacity hover:opacity-75"
                style={{ textDecoration: "none", color: "inherit" }}
            >
                {isAr ? "عرض الباقات" : "View plans"}
                <span aria-hidden="true">{isAr ? "←" : "→"}</span>
            </Link>
        </div>
    );
}
