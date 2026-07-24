"use client";

/**
 * PricingContent — the public /pricing view.
 *
 * Read-only surface for logged-out visitors. It reuses the authoritative plan
 * catalog (GET /api/v1/subscription/plans, shared planCatalog fallback) and the
 * atelier-kit design tokens so it matches the production landing (LandingPageV2)
 * it is linked from. No checkout happens here — the CTA sends guests to sign-up
 * and authenticated users to the real /subscription surface. EN/AR + RTL.
 */

import { atelierFraunces as fraunces } from "@/components/atelier-kit/fonts";
import { Mono } from "@/components/atelier-kit/primitives";
import { ATELIER as C, ATELIER_FONT } from "@/components/atelier-kit/tokens";
import {
  FALLBACK_PLANS,
  PLAN_DESC_KEY,
  PLAN_FEATURE_KEY,
  PLAN_NAME_KEY,
} from "@/components/subscription/planCatalog";
import { useLanguage } from "@/contexts/LanguageContext";
import {
  fetchMe,
  getSubscriptionPlans,
  recordSubscriptionIntent,
  type SubscriptionPlan,
} from "@/lib/api";
import { useTranslation } from "@/lib/translations";
import Link from "next/link";
import { useEffect, useState } from "react";

const SERIF = ATELIER_FONT.serif;
const MONO = ATELIER_FONT.mono;

export function PricingContent() {
  const { language, setLanguage } = useLanguage();
  const isAr = language === "ar";
  const t = useTranslation(language);

  const [plans, setPlans] = useState<SubscriptionPlan[]>(FALLBACK_PLANS);
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    let active = true;

    // Authoritative plan catalog is the backend; fall back to the shared
    // planCatalog constant only when the call is unavailable (fail-safe, never
    // a login redirect — this page is public).
    getSubscriptionPlans()
      .then((res) => {
        if (active && res.plans && res.plans.length > 0) setPlans(res.plans);
      })
      .catch(() => {
        /* keep FALLBACK_PLANS */
      });

    // Tailor the CTA without ever redirecting a guest away from the page.
    fetchMe(ctrl.signal)
      .then((me) => {
        if (active) setAuthed(!!(me.authenticated && me.email));
      })
      .catch(() => {
        if (active) setAuthed(false);
      });

    return () => {
      active = false;
      ctrl.abort();
    };
  }, []);

  const proPlan =
    plans.find((p) => p.plan === "pro") ?? FALLBACK_PLANS[0];

  const localName = (name: string) =>
    PLAN_NAME_KEY[name] ? t(PLAN_NAME_KEY[name]) : name;
  const localDesc = (desc?: string | null) =>
    desc ? (PLAN_DESC_KEY[desc] ? t(PLAN_DESC_KEY[desc]) : desc) : "";
  const localFeature = (f: string) =>
    PLAN_FEATURE_KEY[f] ? t(PLAN_FEATURE_KEY[f]) : f;

  // Free-tier bullets are derived from the existing authoritative freePlanDesc
  // string ("10 AI messages/day · 10 saved jobs · …") — no invented copy.
  const freeBullets = t("freePlanDesc")
    .split("·")
    .map((s) => s.trim())
    .filter(Boolean);

  const proHref = authed ? "/subscription" : "/signup";
  const proCta = authed
    ? isAr
      ? "إدارة الاشتراك"
      : "Manage subscription"
    : isAr
      ? "ابدأ الآن"
      : "Get started";

  const freeHref = authed ? "/command" : "/signup";
  const freeCta = authed
    ? isAr
      ? "افتح ريكو"
      : "Open Rico"
    : isAr
      ? "ابدأ مجانًا"
      : "Start free";

  const onProCta = () => {
    // Fire-and-forget upgrade-intent analytics (public endpoint; anonymous OK).
    void recordSubscriptionIntent("pro", "paddle", "/pricing");
  };

  return (
    <div
      dir={isAr ? "rtl" : "ltr"}
      className={`rp-root min-h-screen overflow-x-hidden ${fraunces.variable}`}
      style={{ background: C.bg, color: C.ink, fontFamily: ATELIER_FONT.body }}
    >
      <style>{`
        .rp-root a:focus-visible,
        .rp-root button:focus-visible { outline: 2px solid ${C.red}; outline-offset: 3px; border-radius: 2px; }
        .rp-root .rp-cta { transition: background-color .2s ease, color .2s ease, border-color .2s ease; }
        .rp-root .rp-cta-primary:hover { background-color: ${C.ink}; }
        .rp-root .rp-cta-ghost:hover { border-color: ${C.ink}; color: ${C.ink}; }
        .rp-root .rp-nav:hover { color: ${C.ink}; }
      `}</style>

      {/* Masthead — mirrors the landing masthead so /pricing reads as the same site */}
      <header style={{ borderBottom: `1px solid ${C.hair}` }}>
        <div className="max-w-6xl mx-auto px-5 sm:px-8">
          <div className="flex items-center justify-between py-4 gap-4">
            <div className="flex items-baseline gap-3 min-w-0">
              <Link
                href="/"
                className="text-[1.35rem] leading-none tracking-tight"
                style={{ fontFamily: SERIF, color: C.ink }}
              >
                Rico Hunt
              </Link>
              <Mono
                className="hidden sm:inline"
                style={{ color: C.ink55, letterSpacing: "0.18em" }}
              >
                {isAr ? "الأسعار" : "Pricing"}
              </Mono>
            </div>

            <div className="flex items-center gap-3">
              <span
                className="hidden sm:inline-flex items-center rounded-[3px] overflow-hidden"
                style={{ border: `1px solid ${C.hair}` }}
              >
                <button
                  type="button"
                  onClick={() => setLanguage("en")}
                  aria-pressed={!isAr}
                  aria-label="Switch to English"
                  style={{ fontFamily: MONO, fontSize: 10, padding: "3px 7px", background: !isAr ? C.ink : "transparent", color: !isAr ? C.panel : C.ink40, cursor: "pointer" }}
                >
                  EN
                </button>
                <button
                  type="button"
                  onClick={() => setLanguage("ar")}
                  aria-pressed={isAr}
                  aria-label="التحويل إلى العربية"
                  style={{ fontFamily: MONO, fontSize: 10, padding: "3px 7px", background: isAr ? C.ink : "transparent", color: isAr ? C.panel : C.ink40, cursor: "pointer" }}
                >
                  عر
                </button>
              </span>
              {!authed && (
                <Link
                  href="/login"
                  className="rp-nav text-sm"
                  style={{ color: C.ink55 }}
                >
                  {t("signIn")}
                </Link>
              )}
              <Link
                href="/command"
                className="whitespace-nowrap text-sm"
                style={{ borderBottom: `1px solid ${C.ink}`, color: C.ink, paddingBottom: 2 }}
              >
                {isAr ? "افتح ريكو" : "Open Rico"}
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-5 sm:px-8 py-14 sm:py-20">
        {/* Hero */}
        <div className="max-w-2xl">
          <Mono style={{ color: C.red }}>
            {isAr ? "الأسعار" : "Pricing"}
          </Mono>
          <h1
            className="mt-4 text-3xl sm:text-5xl leading-[1.05] tracking-tight"
            style={{ fontFamily: SERIF, color: C.ink }}
          >
            {isAr
              ? "خطة واحدة بسيطة. لا مفاجآت."
              : "One simple plan. No surprises."}
          </h1>
          <p
            className="mt-5 text-base sm:text-lg leading-7"
            style={{ color: C.ink70 }}
          >
            {isAr
              ? "ابدأ مجانًا واكتشف كيف يعمل ريكو. عندما تكون جاهزًا للبحث الجاد عن عمل، ترقّى إلى الخطة الشهرية — يمكنك الإلغاء في أي وقت."
              : "Start free and see how Rico works. When you're ready for a serious job search, upgrade to the monthly plan — cancel anytime."}
          </p>
        </div>

        {/* Plans */}
        <div className="mt-10 sm:mt-14 grid gap-5 sm:grid-cols-2 max-w-4xl">
          {/* Free */}
          <section
            aria-label={t("freePlan")}
            className="rounded-[6px] p-6 sm:p-8 flex flex-col"
            style={{ background: C.panel, border: `1px solid ${C.hair}` }}
          >
            <Mono style={{ color: C.ink55 }}>{t("freePlan")}</Mono>
            <div className="mt-4 flex items-baseline gap-2">
              <span
                className="text-4xl"
                style={{ fontFamily: SERIF, color: C.ink }}
              >
                {isAr ? "٠ $" : "$0"}
              </span>
              <span className="text-sm" style={{ color: C.ink40 }}>
                {isAr ? "شهريًا" : "/ month"}
              </span>
            </div>
            <p className="mt-3 text-sm leading-6" style={{ color: C.ink70 }}>
              {isAr
                ? "جرّب ريكو دون التزام."
                : "Try Rico with no commitment."}
            </p>
            <ul className="mt-6 space-y-3 flex-1">
              {freeBullets.map((b, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2.5 text-sm leading-6"
                  style={{ color: C.ink70 }}
                >
                  <span aria-hidden="true" style={{ color: C.red, fontWeight: 700 }}>
                    ✓
                  </span>
                  <span>{b}</span>
                </li>
              ))}
            </ul>
            <Link
              href={freeHref}
              className="rp-cta rp-cta-ghost mt-8 inline-flex items-center justify-center rounded-[4px] px-4 py-3 text-sm font-semibold"
              style={{ border: `1px solid ${C.hair}`, color: C.ink }}
            >
              {freeCta}
            </Link>
          </section>

          {/* Rico Monthly (paid, popular) */}
          <section
            aria-label={localName(proPlan.name)}
            className="relative rounded-[6px] p-6 sm:p-8 flex flex-col"
            style={{ background: C.panel, border: `1px solid ${C.red}` }}
          >
            {proPlan.is_popular && (
              <span
                className="absolute top-0 -translate-y-1/2 inline-flex items-center rounded-full px-3 py-1 text-[10px] font-bold uppercase"
                style={{
                  insetInlineStart: 24,
                  background: C.red,
                  color: "#fff",
                  letterSpacing: isAr ? "0" : "0.12em",
                  fontFamily: isAr ? ATELIER_FONT.body : MONO,
                }}
              >
                {t("mostPopular")}
              </span>
            )}
            <Mono style={{ color: C.red }}>{localName(proPlan.name)}</Mono>
            <div className="mt-4 flex items-baseline gap-2">
              <span
                className="text-4xl"
                style={{ fontFamily: SERIF, color: C.ink }}
              >
                {proPlan.currency} {proPlan.price_monthly.toFixed(2)}
              </span>
              <span className="text-sm" style={{ color: C.ink40 }}>
                {isAr ? "شهريًا" : "/ month"}
              </span>
            </div>
            <p className="mt-3 text-sm leading-6" style={{ color: C.ink70 }}>
              {localDesc(proPlan.description)}
            </p>
            <ul className="mt-6 space-y-3 flex-1">
              {proPlan.features.map((f, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2.5 text-sm leading-6"
                  style={{ color: C.ink70 }}
                >
                  <span aria-hidden="true" style={{ color: C.red, fontWeight: 700 }}>
                    ✓
                  </span>
                  <span>{localFeature(f)}</span>
                </li>
              ))}
            </ul>
            <Link
              href={proHref}
              onClick={onProCta}
              className="rp-cta rp-cta-primary mt-8 inline-flex items-center justify-center rounded-[4px] px-4 py-3 text-sm font-semibold"
              style={{ background: C.red, color: "#fff" }}
            >
              {proCta}
            </Link>
          </section>
        </div>

        {/* Reassurance */}
        <p className="mt-8 text-xs leading-6 max-w-4xl" style={{ color: C.ink40 }}>
          {isAr ? (
            <>
              الفوترة شهريًا بالدولار الأمريكي · يمكنك الإلغاء في أي وقت · الدفع الآمن عبر Paddle. راجع{" "}
              <Link href="/refund-policy" className="rp-nav underline" style={{ color: C.ink55 }}>
                سياسة الاسترداد
              </Link>{" "}
              و{" "}
              <Link href="/terms" className="rp-nav underline" style={{ color: C.ink55 }}>
                الشروط
              </Link>
              .
            </>
          ) : (
            <>
              Billed monthly in USD · Cancel anytime · Secure payment via Paddle. See our{" "}
              <Link href="/refund-policy" className="rp-nav underline" style={{ color: C.ink55 }}>
                refund policy
              </Link>{" "}
              and{" "}
              <Link href="/terms" className="rp-nav underline" style={{ color: C.ink55 }}>
                terms
              </Link>
              .
            </>
          )}
        </p>
      </main>

      {/* Footer */}
      <footer style={{ background: C.footer, color: C.footerInk }}>
        <div className="max-w-6xl mx-auto px-5 sm:px-8 py-8 flex flex-wrap items-center justify-between gap-4">
          <span style={{ fontFamily: SERIF, fontSize: "1.15rem" }}>Rico Hunt</span>
          <nav className="flex items-center gap-5 text-sm" style={{ color: C.footerInk60 }}>
            <Link href="/about" className="rp-nav" style={{ color: C.footerInk60 }}>
              {isAr ? "من نحن" : "About"}
            </Link>
            <Link href="/contact" className="rp-nav" style={{ color: C.footerInk60 }}>
              {isAr ? "الدعم" : "Support"}
            </Link>
            <Link href="/faq" className="rp-nav" style={{ color: C.footerInk60 }}>
              {isAr ? "الأسئلة" : "FAQ"}
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
