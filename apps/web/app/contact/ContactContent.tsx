"use client";

/**
 * /contact — Atelier V2 light-first island.
 *
 * Migrated to the approved /design-preview paper/ink/sun-red language, matching
 * the shipped /terms, /privacy and /faq Atelier islands.
 *
 * IMPORTANT: production has NO contact-form backend endpoint, and the approved
 * reference marks its contact form "SAMPLE FORM — PREVIEW ONLY". Per the design
 * rules ("do not invent a contact backend endpoint; unsupported forms must not
 * pretend to submit successfully"), this page keeps the REAL, working channels —
 * email, WhatsApp, LinkedIn — rather than shipping a form that cannot submit.
 * All contact copy (EN + AR) is preserved verbatim.
 */

import { useLanguage } from "@/contexts/LanguageContext";
import Link from "next/link";
import "../_atelier/atelier-tokens.css";
import "../_atelier/atelier-support.css";

export function ContactContent() {
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
          <Link href="/faq" className="atl-doc-navlink">{isAr ? "الأسئلة الشائعة" : "FAQ"}</Link>
          <Link href="/terms" className="atl-doc-navlink">{isAr ? "الشروط" : "Terms"}</Link>
          <Link href="/privacy" className="atl-doc-navlink">{isAr ? "الخصوصية" : "Privacy"}</Link>
        </nav>
      </header>

      <main className="atl-doc-main">
        <article className="atl-doc-panel">
          <p className="atl-doc-callout-label" style={{ marginBottom: 10 }}>
            {isAr ? "تواصل معنا" : "Get in Touch"}
          </p>
          <h1 className="atl-doc-title">
            {isAr ? "نقرأ كل رسالة." : "We read every message."}
          </h1>
          <p className="atl-doc-lede">
            {isAr
              ? "سواء كان لديك سؤال حول حسابك، ملاحظة على المنتج، استفسار تجاري، أو أي شيء آخر — تواصل معنا وسنرد في أقرب وقت ممكن."
              : "Whether you have a question about your account, feedback on the product, a business enquiry, or something else entirely — reach out and we'll respond as soon as possible."}
          </p>

          <div className="atl-org-plate" style={{ marginTop: 22 }}>
            <p className="atl-org-name">
              {isAr ? "شركة إيكو تكنولوجي لحماية البيئة ذ.م.م" : "Eco Technology Environment Protection Services L.L.C"}
            </p>
            <p className="atl-org-meta">
              {isAr ? "شركة مسجلة في الإمارات · الرقم الضريبي متاح عند الطلب" : "UAE-registered company · TRN available upon request"}
            </p>
          </div>

          <div className="atl-contact-grid">
            <a href="mailto:info@ricohunt.com" className="atl-contact-card">
              <p className="atl-contact-label">{isAr ? "البريد الإلكتروني" : "Email"}</p>
              <p className="atl-contact-value">info@ricohunt.com</p>
              <p className="atl-contact-note">
                {isAr
                  ? "للاستفسارات العامة والدعم والتواصل التجاري. نهدف للرد خلال 24 ساعة."
                  : "For general enquiries, support, and business communication. We aim to respond within 24 hours."}
              </p>
            </a>

            <a href="https://wa.me/971585989080?text=Hi%2C%20I%27d%20like%20to%20get%20in%20touch%20with%20Rico%20Hunt" target="_blank" rel="noopener noreferrer" className="atl-contact-card">
              <p className="atl-contact-label">WhatsApp</p>
              <p className="atl-contact-value">+971 58 598 9080</p>
              <p className="atl-contact-note">
                {isAr
                  ? "أسئلة سريعة ودعم مباشر. متاح خلال ساعات عمل الإمارات، الأحد – الخميس."
                  : "Quick questions and live support. Available during UAE business hours, Sunday–Thursday."}
              </p>
            </a>

            <div className="atl-contact-card">
              <p className="atl-contact-label">{isAr ? "الموقع" : "Location"}</p>
              <p className="atl-contact-value">{isAr ? "الإمارات العربية المتحدة" : "United Arab Emirates"}</p>
              <p className="atl-contact-note">
                {isAr
                  ? "شركة إيكو تكنولوجي لحماية البيئة ذ.م.م — منصة مسجلة في الإمارات تخدم المهنيين في الإمارات ومنطقة الخليج الأشمل."
                  : "Eco Technology Environment Protection Services L.L.C — a UAE-registered platform serving professionals across the UAE and the wider GCC region."}
              </p>
            </div>

            <div className="atl-contact-card">
              <p className="atl-contact-label">{isAr ? "وقت الاستجابة" : "Response Time"}</p>
              <p className="atl-contact-value">{isAr ? "خلال 24 ساعة" : "Within 24 hours"}</p>
              <p className="atl-contact-note">
                {isAr
                  ? "نحن فريق صغير نأخذ الدعم بجدية. إذا لم تتلقَّ رداً خلال 24 ساعة، يرجى إعادة إرسال رسالتك."
                  : "We're a small team that takes support seriously. If you don't hear back within 24 hours, please resend your message."}
              </p>
            </div>

            <a href="https://www.linkedin.com/company/eco-technology-environment-protection-services-l-l-c/" target="_blank" rel="noopener noreferrer" className="atl-contact-card is-wide">
              <p className="atl-contact-label">{isAr ? "لينكدإن الشركة" : "Company LinkedIn"}</p>
              <p className="atl-contact-value">
                {isAr ? "شركة إيكو تكنولوجي لحماية البيئة ذ.م.م" : "Eco Technology Environment Protection Services L.L.C"}
              </p>
              <p className="atl-contact-note">
                {isAr
                  ? "اطلع على ملف الشركة على لينكدإن للتحقق من التسجيل ومعرفة المزيد."
                  : "View the company profile on LinkedIn to verify registration and learn more."}
              </p>
            </a>
          </div>

          <div className="atl-doc-callout" style={{ margin: "36px 0 0" }}>
            <p className="atl-doc-callout-label">
              {isAr ? "تستخدم ريكو بالفعل؟" : "Already using Rico?"}
            </p>
            <p style={{ margin: "6px 0 14px" }}>
              {isAr
                ? "للمساعدة الخاصة بحسابك، الطريقة الأسرع هي مراسلة ريكو مباشرة داخل التطبيق — أو مراسلتنا بالبريد الإلكتروني المسجل حتى نتمكن من الاطلاع على حسابك."
                : "For account-specific help, the fastest path is to message Rico directly inside the app — or email us with your registered email address so we can look up your account."}
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
              <Link href="/login" style={{ color: "var(--sun)", fontSize: 14, textDecoration: "underline", textUnderlineOffset: 2 }}>
                {isAr ? "تسجيل الدخول لحسابك ←" : "Sign in to your account →"}
              </Link>
              <Link href="/chat" style={{ color: "var(--ink-soft)", fontSize: 14, textDecoration: "underline", textUnderlineOffset: 2 }}>
                {isAr ? "جرّب المحادثة العامة" : "Try the public chat"}
              </Link>
            </div>
          </div>
        </article>
      </main>

      <footer className="atl-doc-footer">
        <p className="atl-doc-footer-brand">Rico Hunt</p>
        <p>Powered by Eco Technology Environment Protection Services L.L.C</p>
        <p>{isAr ? "الإمارات العربية المتحدة" : "United Arab Emirates"}</p>
        <div className="atl-doc-footer-links">
          <Link href="/about">{isAr ? "عن ريكو" : "About"}</Link>
          <span className="atl-doc-current">{isAr ? "تواصل" : "Contact"}</span>
          <Link href="/terms">{isAr ? "الشروط" : "Terms"}</Link>
          <Link href="/privacy">{isAr ? "الخصوصية" : "Privacy"}</Link>
          <Link href="/refund-policy">{isAr ? "الاسترداد" : "Refunds"}</Link>
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
