"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import Link from "next/link";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { AuraGlow } from "@/components/ui/AuraGlow";

export function RefundPolicyContent() {
  const { language, setLanguage } = useLanguage();
  const isAr = language === "ar";

  return (
    <div dir={isAr ? "rtl" : "ltr"} className="relative min-h-screen overflow-x-hidden bg-[#0a0a1a]">
      <AuraGlow aria-hidden="true" variant="magenta" position="top-left" />
      <AuraGlow aria-hidden="true" variant="cyan" position="bottom-right" />

      <header className="relative z-10 flex items-center justify-between border-b border-border-subtle bg-black/50 px-5 py-4 backdrop-blur-xl md:px-10">
        <Link href="/" className="flex items-center gap-2 text-lg font-black tracking-tight text-white">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#f5a623] text-[#0a0a1a] text-sm font-black shadow-[0_0_28px_rgba(245,166,35,0.28)]">
            R
          </span>
          <span>
            Rico<span className="text-[#f5a623]"> Hunt</span>
          </span>
        </Link>
        <nav className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setLanguage(isAr ? "en" : "ar")}
            aria-label={isAr ? "Switch to English" : "Switch to Arabic"}
            className="text-[12px] font-semibold px-2.5 py-1 rounded-lg border border-border-subtle text-text-secondary hover:text-white hover:border-[#f5a623]/50 transition-colors"
          >
            {isAr ? "EN" : "عربي"}
          </button>
          <Link href="/about" className="text-sm text-text-secondary transition-colors hover:text-white">{isAr ? "عن ريكو" : "About"}</Link>
          <Link href="/contact" className="text-sm text-text-secondary transition-colors hover:text-white">{isAr ? "تواصل" : "Contact"}</Link>
          <Link href="/terms" className="text-sm text-text-secondary transition-colors hover:text-white">{isAr ? "الشروط" : "Terms"}</Link>
          <Link href="/privacy" className="text-sm text-text-secondary transition-colors hover:text-white">{isAr ? "الخصوصية" : "Privacy"}</Link>
        </nav>
      </header>

      <main className="relative z-10 mx-auto max-w-4xl px-5 py-16 md:px-10">
        <GlassPanel className="rounded-2xl border border-white/10 p-8 md:p-12">
          <h1 className="mb-2 text-3xl font-semibold text-white md:text-4xl">
            {isAr ? "سياسة الاسترداد والإلغاء" : "Refund and Cancellation Policy"}
          </h1>
          <p className="mb-8 text-sm text-text-secondary">
            {isAr
              ? "آخر تحديث: مايو 2026 · شروط واضحة لإدارة الاشتراكات."
              : "Last updated: May 2026 · Clear terms for subscription management."}
          </p>

          <div className="space-y-8 text-sm leading-7 text-text-secondary">
            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "١. إلغاء الاشتراك" : "1. Subscription Cancellation"}
              </h2>
              <p>
                {isAr
                  ? "يمكنك إلغاء اشتراكك في أي وقت عبر بوابة إدارة الاشتراكات أو بالتواصل مع الدعم. يُنفّذ الإلغاء في نهاية فترة الفوترة الحالية. ستستمر في الوصول إلى الميزات المدفوعة حتى انتهاء الفترة."
                  : "You may cancel your subscription at any time through the subscription management portal or by contacting support. Cancellation takes effect at the end of your current billing period. You will continue to have access to paid features until the period ends."}
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "٢. أهلية الاسترداد" : "2. Refund Eligibility"}
              </h2>
              <div className="space-y-3">
                <p>
                  <strong className="text-white">{isAr ? "الخطة المجانية:" : "Free Plan:"}</strong>{" "}
                  {isAr
                    ? "لا تُطبق استردادات حيث أن الخطة المجانية لا تتضمن رسوماً."
                    : "No refunds apply as the Free plan has no charges."}
                </p>
                <p>
                  <strong className="text-white">{isAr ? "الاشتراكات المدفوعة (برو/بريميوم):" : "Paid Subscriptions (Pro/Premium):"}</strong>
                </p>
                <ul className="ml-4 list-disc space-y-2">
                  <li>
                    <strong className="text-white">{isAr ? "فترة الإلغاء خلال ١٤ يوماً (مستهلكو الإمارات والاتحاد الأوروبي):" : "14-Day Cooling-Off Period (UAE & EU consumers):"}</strong>{" "}
                    {isAr
                      ? "إذا كنت مستهلكاً في الإمارات أو الاتحاد الأوروبي، يمكنك طلب استرداد كامل خلال ١٤ يوماً من شراء الاشتراك الأولي، بشرط ألا تكون قد استخدمت الخدمة بشكل جوهري."
                      : "If you are a consumer in the UAE or EU, you may request a full refund within 14 days of your initial subscription purchase, provided you have not substantially used the service."}
                  </li>
                  <li>
                    <strong className="text-white">{isAr ? "الأعطال التقنية:" : "Technical Failures:"}</strong>{" "}
                    {isAr
                      ? "إذا كانت الخدمة غير متاحة أو غير وظيفية مادياً بسبب بنيتنا التحتية لأكثر من ٤٨ ساعة متتالية خلال فترة الفوترة، يمكنك طلب استرداد نسبي لتلك الفترة."
                      : "If the service is unavailable or materially non-functional due to our infrastructure for more than 48 consecutive hours within a billing period, you may request a prorated refund for that period."}
                  </li>
                  <li>
                    <strong className="text-white">{isAr ? "أخطاء الفوترة:" : "Billing Errors:"}</strong>{" "}
                    {isAr
                      ? "إذا تم تحصيل رسوم منك بشكل غير صحيح بسبب خطأ في النظام، سنسترد المبلغ غير الصحيح فوراً عند التحقق."
                      : "If you were incorrectly charged due to a system error, we will refund the incorrect amount immediately upon verification."}
                  </li>
                </ul>
              </div>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "٣. حالات غير مستردة" : "3. Non-Refundable Situations"}
              </h2>
              <ul className="ml-4 list-disc space-y-2">
                <li>{isAr ? "الأشهر الجزئية بعد فترة الإلغاء" : "Partial months after the cooling-off period"}</li>
                <li>{isAr ? "الترقيات من مستوى أعلى إلى أقل منتصف الدورة" : "Downgrades from a higher to lower tier mid-cycle"}</li>
                <li>{isAr ? "الرسائل غير المستخدمة أو التحسينات أو حصص الميزات" : "Unused messages, optimizations, or feature quotas"}</li>
                <li>{isAr ? "حذف الحساب طوعاً قبل انتهاء فترة الاشتراك" : "Voluntary account deletion before subscription period ends"}</li>
                <li>{isAr ? "انتهاكات شروط الخدمة المؤدية إلى إنهاء الحساب" : "Violations of Terms of Service resulting in account termination"}</li>
              </ul>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "٤. كيفية طلب استرداد" : "4. How to Request a Refund"}
              </h2>
              <p>
                {isAr
                  ? "لطلب استرداد، أرسل بريداً إلكترونياً إلى"
                  : "To request a refund, email"}{" "}
                <a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">info@ricohunt.com</a>{" "}
                {isAr ? "مع:" : "with:"}
              </p>
              <ul className="ml-4 mt-2 list-disc space-y-2">
                <li>{isAr ? "عنوان بريدك الإلكتروني المسجل" : "Your registered email address"}</li>
                <li>{isAr ? "خطة الاشتراك وتاريخ الشراء" : "Subscription plan and purchase date"}</li>
                <li>{isAr ? "سبب طلب الاسترداد" : "Reason for refund request"}</li>
                <li>{isAr ? "أي لقطات شاشة أو مستندات ذات صلة" : "Any relevant screenshots or documentation"}</li>
              </ul>
              <p className="mt-3">
                {isAr
                  ? "تُعالج طلبات الاسترداد خلال ٥-٧ أيام عمل. يُصدر الاستردادات المعتمدة إلى طريقة الدفع الأصلية وقد تستغرق ٥-١٠ أيام عمل للظهور، حسب بنكك أو جهة إصدار البطاقة."
                  : "Refund requests are processed within 5-7 business days. Approved refunds are issued to the original payment method and may take 5-10 business days to appear, depending on your bank or card issuer."}
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "٥. تغييرات الخطة" : "5. Plan Changes"}
              </h2>
              <p>
                <strong className="text-white">{isAr ? "الترقيات:" : "Upgrades:"}</strong>{" "}
                {isAr
                  ? "عند الترقية من برو إلى بريميوم، يدخل السعر الجديد حيز التنفيذ فوراً. سيتم تحصيل مبلغ نسبي للبقية من دورة الفوترة."
                  : "When upgrading from Pro to Premium, the new rate takes effect immediately. You will be charged a prorated amount for the remainder of the billing cycle."}
              </p>
              <p className="mt-2">
                <strong className="text-white">{isAr ? "الترقيات إلى أسفل:" : "Downgrades:"}</strong>{" "}
                {isAr
                  ? "عند الترقية إلى أسفل، يدخل المستوى الأدنى حيز التنفيذ في بداية دورة الفوترة التالية. لا يتم تقديم استردادات جزئية للدورة الحالية."
                  : "When downgrading, the lower tier takes effect at the start of the next billing cycle. No partial refunds are provided for the current cycle."}
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "٦. المدفوعات الفاشلة" : "6. Failed Payments"}
              </h2>
              <p>
                {isAr
                  ? "إذا فشلت عملية دفع، سنحاول إعادة محاولة الشحن. سيكون لديك فترة سماح ٧ أيام لتحديث طريقة الدفع. بعد ٧ أيام، سيتم تعليق اشتراكك ونقله إلى الخطة المجانية. لا يتم تقديم استردادات للاشتراكات المعلقة."
                  : "If a payment fails, we will attempt to retry the charge. You will have a 7-day grace period to update your payment method. After 7 days, your subscription will be suspended and moved to the Free plan. No refunds are provided for suspended subscriptions."}
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "٧. ظروف خاصة" : "7. Special Circumstances"}
              </h2>
              <p>
                {isAr
                  ? "نحتفظ بالحق في إصدار استردادات خارج هذه السياسة في الظروف الاستثنائية، مثل حالات الطوارئ الطبية الموثقة أو أحداث القوة القاهرة. تُقّيم هذه الحالات على أساس كل حالة على حدة."
                  : "We reserve the right to issue refunds outside this policy in exceptional circumstances, such as documented medical emergencies or force majeure events. These are evaluated on a case-by-case basis."}
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "٨. التواصل" : "8. Contact"}
              </h2>
              <p>
                {isAr
                  ? "لاستفسارات متعلقة بالاسترداد، أرسل بريداً إلكترونياً إلى"
                  : "For refund-related questions, email"}{" "}
                <a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">info@ricohunt.com</a>
                {isAr ? "\. نهدف للرد خلال ٤٨ ساعة." : ". We aim to respond within 48 hours."}
              </p>
            </section>
          </div>
        </GlassPanel>
      </main>

      <footer className="relative z-10 border-t border-white/10 bg-black/30 px-5 py-8 text-center">
        <p className="mb-1 text-sm font-semibold text-white">Rico Hunt</p>
        <p className="mb-1 text-xs text-text-tertiary">
          {isAr ? "شركة إيكو تكنولوجي لحماية البيئة ذ.م.م" : "Powered by Eco Technology Environment Protection Services L.L.C"}
        </p>
        <p className="mb-3 text-xs text-text-tertiary">{isAr ? "الإمارات العربية المتحدة" : "United Arab Emirates"}</p>
        <div className="mb-3 flex flex-wrap items-center justify-center gap-5">
          <Link href="/about" className="text-xs text-text-tertiary transition-colors hover:text-white">{isAr ? "عن ريكو" : "About"}</Link>
          <Link href="/contact" className="text-xs text-text-tertiary transition-colors hover:text-white">{isAr ? "تواصل" : "Contact"}</Link>
          <Link href="/terms" className="text-xs text-text-tertiary transition-colors hover:text-white">{isAr ? "الشروط" : "Terms"}</Link>
          <Link href="/privacy" className="text-xs text-text-tertiary transition-colors hover:text-white">{isAr ? "الخصوصية" : "Privacy"}</Link>
          <span className="text-xs font-medium text-white">{isAr ? "الاسترداد" : "Refunds"}</span>
          <Link href="/faq" className="text-xs text-text-tertiary transition-colors hover:text-white">{isAr ? "الأسئلة الشائعة" : "FAQ"}</Link>
        </div>
        <p className="mb-1 text-xs text-text-tertiary">
          <a href="mailto:info@ricohunt.com" className="text-[#f5a623] transition-colors hover:opacity-80">info@ricohunt.com</a>
          {" · "}
          <a href="https://wa.me/971585989080" className="text-[#f5a623] transition-colors hover:opacity-80">+971 58 598 9080</a>
        </p>
        <p className="text-xs text-text-tertiary">{isAr ? "© 2026 ريكو هانت. جميع الحقوق محفوظة." : "© 2026 Rico Hunt. All rights reserved."}</p>
      </footer>
    </div>
  );
}
