"use client";

/**
 * /refund-policy — Atelier V2 light-first island (PR C2).
 *
 * Same scoped-island pattern as /terms (C1) and /privacy: content wrapped in
 * `.atelier` + shared token layer, existing useLanguage() kept, dir/lang mirrored
 * on the wrapper for self-contained RTL, all EN/AR copy preserved. No
 * localStorage, no ThemeContext, no global default change. SEO metadata lives in
 * ./page.tsx (unchanged).
 */

import { useLanguage } from "@/contexts/LanguageContext";
import Link from "next/link";
import "../_atelier/atelier-tokens.css";

export function RefundPolicyContent() {
  const { language, setLanguage } = useLanguage();
  const isAr = language === "ar";

  return (
    <div
      className="atelier atl-doc"
      data-atl-theme="light"
      dir={isAr ? "rtl" : "ltr"}
      lang={isAr ? "ar" : "en"}
    >
      <header className="atl-doc-header">
        <Link href="/" className="atl-doc-brand">
          <span className="atl-doc-brand-mark">R</span>
          <span>Rico<span className="atl-doc-brand-accent"> Hunt</span></span>
        </Link>
        <nav className="atl-doc-nav">
          <button
            type="button"
            onClick={() => setLanguage(isAr ? "en" : "ar")}
            aria-label={isAr ? "Switch to English" : "Switch to Arabic"}
            className="atl-doc-toggle"
          >
            {isAr ? "EN" : "عربي"}
          </button>
          <Link href="/about" className="atl-doc-navlink">{isAr ? "عن ريكو" : "About"}</Link>
          <Link href="/contact" className="atl-doc-navlink">{isAr ? "تواصل" : "Contact"}</Link>
          <Link href="/terms" className="atl-doc-navlink">{isAr ? "الشروط" : "Terms"}</Link>
          <Link href="/privacy" className="atl-doc-navlink">{isAr ? "الخصوصية" : "Privacy"}</Link>
        </nav>
      </header>

      <main className="atl-doc-main">
        <article className="atl-doc-panel">
          <h1 className="atl-doc-title">
            {isAr ? "سياسة الاسترداد والإلغاء" : "Refund and Cancellation Policy"}
          </h1>
          <p className="atl-doc-sub">
            {isAr
              ? "آخر تحديث: مايو 2026 · شروط واضحة لإدارة الاشتراكات."
              : "Last updated: May 2026 · Clear terms for subscription management."}
          </p>

          <div className="atl-doc-body">
            <section>
              <h2>{isAr ? "١. إلغاء الاشتراك" : "1. Subscription Cancellation"}</h2>
              <p>
                {isAr
                  ? "يمكنك إلغاء اشتراكك في أي وقت عبر بوابة إدارة الاشتراكات أو بالتواصل مع الدعم. يُنفّذ الإلغاء في نهاية فترة الفوترة الحالية. ستستمر في الوصول إلى الميزات المدفوعة حتى انتهاء الفترة."
                  : "You may cancel your subscription at any time through the subscription management portal or by contacting support. Cancellation takes effect at the end of your current billing period. You will continue to have access to paid features until the period ends."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٢. أهلية الاسترداد" : "2. Refund Eligibility"}</h2>
              <p>
                <strong>{isAr ? "الخطة المجانية:" : "Free Plan:"}</strong>{" "}
                {isAr
                  ? "لا تُطبق استردادات حيث أن الخطة المجانية لا تتضمن رسوماً."
                  : "No refunds apply as the Free plan has no charges."}
              </p>
              <p>
                <strong>{isAr ? "الاشتراكات المدفوعة (برو/بريميوم):" : "Paid Subscriptions (Pro/Premium):"}</strong>
              </p>
              <ul>
                <li>
                  <strong>{isAr ? "فترة الإلغاء خلال ١٤ يوماً (مستهلكو الإمارات والاتحاد الأوروبي):" : "14-Day Cooling-Off Period (UAE & EU consumers):"}</strong>{" "}
                  {isAr
                    ? "إذا كنت مستهلكاً في الإمارات أو الاتحاد الأوروبي، يمكنك طلب استرداد كامل خلال ١٤ يوماً من شراء الاشتراك الأولي، بشرط ألا تكون قد استخدمت الخدمة بشكل جوهري."
                    : "If you are a consumer in the UAE or EU, you may request a full refund within 14 days of your initial subscription purchase, provided you have not substantially used the service."}
                </li>
                <li>
                  <strong>{isAr ? "الأعطال التقنية:" : "Technical Failures:"}</strong>{" "}
                  {isAr
                    ? "إذا كانت الخدمة غير متاحة أو غير وظيفية مادياً بسبب بنيتنا التحتية لأكثر من ٤٨ ساعة متتالية خلال فترة الفوترة، يمكنك طلب استرداد نسبي لتلك الفترة."
                    : "If the service is unavailable or materially non-functional due to our infrastructure for more than 48 consecutive hours within a billing period, you may request a prorated refund for that period."}
                </li>
                <li>
                  <strong>{isAr ? "أخطاء الفوترة:" : "Billing Errors:"}</strong>{" "}
                  {isAr
                    ? "إذا تم تحصيل رسوم منك بشكل غير صحيح بسبب خطأ في النظام، سنسترد المبلغ غير الصحيح فوراً عند التحقق."
                    : "If you were incorrectly charged due to a system error, we will refund the incorrect amount immediately upon verification."}
                </li>
              </ul>
            </section>

            <section>
              <h2>{isAr ? "٣. حالات غير مستردة" : "3. Non-Refundable Situations"}</h2>
              <ul>
                <li>{isAr ? "الأشهر الجزئية بعد فترة الإلغاء" : "Partial months after the cooling-off period"}</li>
                <li>{isAr ? "الترقيات من مستوى أعلى إلى أقل منتصف الدورة" : "Downgrades from a higher to lower tier mid-cycle"}</li>
                <li>{isAr ? "الرسائل غير المستخدمة أو التحسينات أو حصص الميزات" : "Unused messages, optimizations, or feature quotas"}</li>
                <li>{isAr ? "حذف الحساب طوعاً قبل انتهاء فترة الاشتراك" : "Voluntary account deletion before subscription period ends"}</li>
                <li>{isAr ? "انتهاكات شروط الخدمة المؤدية إلى إنهاء الحساب" : "Violations of Terms of Service resulting in account termination"}</li>
              </ul>
            </section>

            <section>
              <h2>{isAr ? "٤. كيفية طلب استرداد" : "4. How to Request a Refund"}</h2>
              <p>
                {isAr
                  ? "لطلب استرداد, أرسل بريداً إلكترونياً إلى"
                  : "To request a refund, email"}{" "}
                <a href="mailto:info@ricohunt.com">info@ricohunt.com</a>{" "}
                {isAr ? "مع:" : "with:"}
              </p>
              <ul>
                <li>{isAr ? "عنوان بريدك الإلكتروني المسجل" : "Your registered email address"}</li>
                <li>{isAr ? "خطة الاشتراك وتاريخ الشراء" : "Subscription plan and purchase date"}</li>
                <li>{isAr ? "سبب طلب الاسترداد" : "Reason for refund request"}</li>
                <li>{isAr ? "أي لقطات شاشة أو مستندات ذات صلة" : "Any relevant screenshots or documentation"}</li>
              </ul>
              <p>
                {isAr
                  ? "تُعالج طلبات الاسترداد خلال ٥-٧ أيام عمل. يُصدر الاستردادات المعتمدة إلى طريقة الدفع الأصلية وقد تستغرق ٥-١٠ أيام عمل للظهور، حسب بنكك أو جهة إصدار البطاقة."
                  : "Refund requests are processed within 5-7 business days. Approved refunds are issued to the original payment method and may take 5-10 business days to appear, depending on your bank or card issuer."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٥. تغييرات الخطة" : "5. Plan Changes"}</h2>
              <p>
                <strong>{isAr ? "الترقيات:" : "Upgrades:"}</strong>{" "}
                {isAr
                  ? "عند الترقية من برو إلى بريميوم، يدخل السعر الجديد حيز التنفيذ فوراً. سيتم تحصيل مبلغ نسبي للبقية من دورة الفوترة."
                  : "When upgrading from Pro to Premium, the new rate takes effect immediately. You will be charged a prorated amount for the remainder of the billing cycle."}
              </p>
              <p>
                <strong>{isAr ? "الترقيات إلى أسفل:" : "Downgrades:"}</strong>{" "}
                {isAr
                  ? "عند الترقية إلى أسفل، يدخل المستوى الأدنى حيز التنفيذ في بداية دورة الفوترة التالية. لا يتم تقديم استردادات جزئية للدورة الحالية."
                  : "When downgrading, the lower tier takes effect at the start of the next billing cycle. No partial refunds are provided for the current cycle."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٦. المدفوعات الفاشلة" : "6. Failed Payments"}</h2>
              <p>
                {isAr
                  ? "إذا فشلت عملية دفع، سنحاول إعادة محاولة الشحن. سيكون لديك فترة سماح ٧ أيام لتحديث طريقة الدفع. بعد ٧ أيام، سيتم تعليق اشتراكك ونقله إلى الخطة المجانية. لا يتم تقديم استردادات للاشتراكات المعلقة."
                  : "If a payment fails, we will attempt to retry the charge. You will have a 7-day grace period to update your payment method. After 7 days, your subscription will be suspended and moved to the Free plan. No refunds are provided for suspended subscriptions."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٧. ظروف خاصة" : "7. Special Circumstances"}</h2>
              <p>
                {isAr
                  ? "نحتفظ بالحق في إصدار استردادات خارج هذه السياسة في الظروف الاستثنائية، مثل حالات الطوارئ الطبية الموثقة أو أحداث القوة القاهرة. تُقّيم هذه الحالات على أساس كل حالة على حدة."
                  : "We reserve the right to issue refunds outside this policy in exceptional circumstances, such as documented medical emergencies or force majeure events. These are evaluated on a case-by-case basis."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٨. التواصل" : "8. Contact"}</h2>
              <p>
                {isAr
                  ? "لاستفسارات متعلقة بالاسترداد، أرسل بريداً إلكترونياً إلى"
                  : "For refund-related questions, email"}{" "}
                <a href="mailto:info@ricohunt.com">info@ricohunt.com</a>
                {isAr ? "\. نهدف للرد خلال ٤٨ ساعة." : ". We aim to respond within 48 hours."}
              </p>
            </section>
          </div>
        </article>
      </main>

      <footer className="atl-doc-footer">
        <p className="atl-doc-footer-brand">Rico Hunt</p>
        <p>{isAr ? "شركة إيكو تكنولوجي لحماية البيئة ذ.م.م" : "Powered by Eco Technology Environment Protection Services L.L.C"}</p>
        <p>{isAr ? "الإمارات العربية المتحدة" : "United Arab Emirates"}</p>
        <div className="atl-doc-footer-links">
          <Link href="/about">{isAr ? "عن ريكو" : "About"}</Link>
          <Link href="/contact">{isAr ? "تواصل" : "Contact"}</Link>
          <Link href="/terms">{isAr ? "الشروط" : "Terms"}</Link>
          <Link href="/privacy">{isAr ? "الخصوصية" : "Privacy"}</Link>
          <span className="atl-doc-current">{isAr ? "الاسترداد" : "Refunds"}</span>
          <Link href="/faq">{isAr ? "الأسئلة الشائعة" : "FAQ"}</Link>
        </div>
        <p>
          <a href="mailto:info@ricohunt.com">info@ricohunt.com</a>
          {" · "}
          <a href="https://wa.me/971585989080">+971 58 598 9080</a>
        </p>
        <p>{isAr ? "© 2026 ريكو هانت. جميع الحقوق محفوظة." : "© 2026 Rico Hunt. All rights reserved."}</p>
      </footer>
    </div>
  );
}
