/**
 * planCatalog — the single client-side definition of Rico's plan-catalog
 * fallback and the string→TranslationKey localization maps.
 *
 * The RUNTIME source of truth for plan names / prices / features is the
 * backend: GET /api/v1/subscription/plans (src/subscription_plans.py). These
 * constants are (a) the fail-safe fallback rendered when that call is
 * unavailable, and (b) the maps that let API-returned English feature strings
 * render in Arabic (issue #1067).
 *
 * Extracted verbatim from SubscriptionAtelier.tsx so the authenticated
 * /subscription surface and the public /pricing surface share ONE definition —
 * there must never be two drifting copies of "Rico Monthly, USD 21.50". Per
 * lib/subscriptionCta.ts, plan copy has exactly one owner; this module keeps
 * that guarantee when a second consumer (the public page) reuses it.
 */

import type { SubscriptionPlan } from "@/lib/api";
import type { TranslationKey } from "@/lib/translations";

export const FALLBACK_PLANS: SubscriptionPlan[] = [
    {
        id: "rico_monthly",
        plan: "pro",
        name: "Rico Monthly",
        price_monthly: 21.50,
        currency: "USD",
        description: "Smart AI job hunting for active UAE professionals.",
        // Must match src/subscription_plans.py RICO_MONTHLY_PLAN.features (issue #1067).
        features: [
            "300 AI messages per month",
            "20 CV & profile optimizations per month",
            "Smart AI role recommendations",
            "Advanced match scoring",
            "Saved searches",
            "Priority support",
        ],
        entitlements: {
            monthly_ai_message_limit: 300,
            saved_jobs_limit: 100,
            profile_optimization_limit: 20,
            cv_storage_limit: 5,
            other_document_limit: 10,
            premium_recommendations_enabled: false,
            application_automation_enabled: false,
        },
        is_popular: true,
    },
];

export const PLAN_TIER: Record<string, number> = { free: 0, pro: 1 };

export const PLAN_NAME_KEY: Record<string, TranslationKey> = {
    "Rico Monthly": "planProName",
};

export const PLAN_DESC_KEY: Record<string, TranslationKey> = {
    "Smart AI job hunting for active UAE professionals.": "planProDesc",
};

// Keys MUST equal the backend feature strings (src/subscription_plans.py) so
// API-returned plans localize correctly (issue #1067).
export const PLAN_FEATURE_KEY: Record<string, TranslationKey> = {
    "300 AI messages per month": "planFeatureAiMessages",
    "20 CV & profile optimizations per month": "planFeatureCvAnalysis",
    "Smart AI role recommendations": "planFeatureSmartRec",
    "Advanced match scoring": "planFeatureAdvancedScoring",
    "Saved searches": "planFeatureSavedSearches",
    "Priority support": "planFeaturePrioritySupport",
};
