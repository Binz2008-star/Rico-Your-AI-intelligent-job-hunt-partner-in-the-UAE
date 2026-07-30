"use client";

/**
 * /about — Atelier V2 public island.
 *
 * Migrated from legacy GlassPanel/AuraGlow styling to the approved
 * paper/ink/sun-red Atelier public-page language, matching the shipped
 * /contact, /faq, /terms and /privacy islands. All copy (EN + AR) and links
 * are preserved verbatim.
 */

import "@/app/_atelier/atelier-support.css";
import "@/app/_atelier/atelier-tokens.css";
import { useLanguage } from "@/contexts/LanguageContext";
import Link from "next/link";

export function AboutContent() {
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
          <span>
            Rico<span className="atl-doc-brand-accent"> Hunt</span>
          </span>
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
          <span className="atl-doc-current">
            {isAr ? "عن ريكو" : "About"}
          </span>
          <Link href="/contact" className="atl-doc-navlink">
            {isAr ? "تواصل" : "Contact"}
          </Link>
          <Link href="/faq" className="atl-doc-navlink">
            {isAr ? "الأسئلة الشائعة" : "FAQ"}
          </Link>
          <Link href="/terms" className="atl-doc-navlink">
            {isAr ? "الشروط" : "Terms"}
          </Link>
          <Link href="/privacy" className="atl-doc-navlink">
            {isAr ? "الخصوصية" : "Privacy"}
          </Link>
        </nav>
      </header>

      <main className="atl-doc-main">
        <article className="atl-doc-panel">
          <p className="atl-doc-callout-label" style={{ marginBottom: 10 }}>
            {isAr ? "قصتنا" : "Our Story"}
          </p>
          <h1 className="atl-doc-title">
            {isAr
              ? "بُني لسوق العمل في الإمارات. بُني حول سيرتك الذاتية."
              : "Built for the UAE job market. Built around your CV."}
          </h1>
          <p className="atl-doc-lede">
            {isAr
              ? <>
                ريكو هانت منصة مهنية مدعومة بالذكاء الاصطناعي تهدف إلى مساعدة المهنيين في الإمارات ودول الخليج على اكتشاف الفرص المناسبة وتحسين استراتيجية البحث عن عمل وإدارة الطلبات بكفاءة أعلى. تشغّل ريكو هانت{" "}
                <span style={{ fontWeight: 500 }}>شركة إيكو تكنولوجي لحماية البيئة ذ.م.م</span>، وهي شركة مسجلة في الإمارات العربية المتحدة.
              </>
              : <>
                Rico Hunt is an AI-powered career platform focused on helping professionals in the UAE and GCC discover relevant opportunities, improve their job search strategy, and manage applications more effectively. Rico Hunt is operated by{" "}
                <span style={{ fontWeight: 500 }}>Eco Technology Environment Protection Services L.L.C</span>, a UAE-registered company.
              </>}
          </p>

          <section style={{ marginTop: 42 }}>
            <h2 className="atl-doc-callout-label" style={{ marginBottom: 10 }}>
              {isAr ? "المشكلة التي نحلها" : "The Problem We\'re Solving"}
            </h2>
            <p className="atl-doc-lede">
              {isAr
                ? "سوق العمل في الإمارات متسارع وتنافسي للغاية. يقضي معظم الباحثين عن عمل وقتهم في إدارة لوجستيات البحث بدلاً من التحضير للفرص الفعلية. تعرض المنصات العامة مئات الوظائف غير الملائمة، وتُلزم المستخدمين بخطوات إعداد مطولة، وتقدم إرشادات محدودة حول الأدوار التي تتناسب فعلاًَ مع خلفياتهم."
                : "The UAE job market is fast-moving and highly competitive. Most job seekers spend more time managing the logistics of job hunting than actually preparing for opportunities. Generic platforms surface hundreds of mismatched listings, force users through lengthy setup wizards, and offer little guidance on which roles actually fit their background."}
            </p>
            <p className="atl-doc-lede" style={{ marginTop: 14 }}>
              {isAr
                ? "ريكو هو إجابتنا على تلك المشكلة: مساعد مهني يعمل بالذكاء الاصطناعي يقرأ سيرتك الذاتية مرة واحدة، يبني فهماً منظماً لخبرتك، ثم يعمل باستمرار في الخلفية ليكشف الفرص المناسبة في الإمارات التي تتوافق مع من أنت فعلاً — لا مجرد كلمات مفتاحية."
                : "Rico is our answer to that problem: an AI career companion that reads your CV once, builds a structured understanding of your experience, and then works continuously in the background to surface UAE-specific opportunities that match who you actually are — not just keywords."}
            </p>
          </section>

          <section style={{ marginTop: 42 }}>
            <h2 className="atl-doc-callout-label" style={{ marginBottom: 10 }}>
              {isAr ? "كيف يجد ريكو الوظائف" : "How Rico Finds Jobs"}
            </h2>
            <p className="atl-doc-lede">
              {isAr
                ? <>
                  يجمع ريكو الوظائف المباشرة من أنحاء الإمارات باستخدام{" "}
                  <span style={{ fontWeight: 500 }}>JSearch API</span> (مدعومة من RapidAPI)، التي تسحب بيانات في الوقت الفعلي من لينكدإن وإنديد وغلاسدور وبيت وغيرها من اللوحات الكبرى النشطة في المنطقة. تُفلتر الوظائف وتُرتَّب وفق سيرتك الذاتية وملفك المهني — لترى فقط الأدوار التي تتناسب فعلاً مع خلفيتك.
                </>
                : <>
                  Rico aggregates live job listings from across the UAE using the{" "}
                  <span style={{ fontWeight: 500 }}>JSearch API</span> (powered by RapidAPI), which pulls real-time data from LinkedIn, Indeed, Glassdoor, Bayt, and other major job boards active in the region. Listings are filtered and scored against your CV and profile — so you only see roles where your background is genuinely relevant.
                </>}
            </p>
            <p className="atl-doc-lede" style={{ marginTop: 14 }}>
              {isAr
                ? "لن يتقدم ريكو لأي وظيفة نيابةً عنك دون موافقتك الصريحة. كل إجراء تقديم يتطلب تأكيدك. أنت في السيطرة الكاملة في كل خطوة."
                : "Rico does not apply to jobs on your behalf without your explicit approval. Every application requires your confirmation. You stay in control at every step."}
            </p>
          </section>

          <section style={{ marginTop: 42 }}>
            <h2 className="atl-doc-callout-label" style={{ marginBottom: 10 }}>
              {isAr ? "ما يتذكره ريكو" : "What Rico Remembers"}
            </h2>
            <p className="atl-doc-lede">
              {isAr
                ? "على عكس محرك البحث، يحتفظ ريكو بملف مهني دائم لأهدافك: الأدوار المستهدفة والقطاعات المفضلة وتوقعات الراتب وتاريخ التوظيف. هذا يعني أن كل جلسة بحث تبدأ من حيث انتهيت — دون الحاجة إلى إعادة إدخال تفضيلاتك أو فقدان سياقك."
                : "Unlike a search engine, Rico maintains a persistent profile of your career goals: your target roles, preferred sectors, salary expectations, and job history. This means every search session picks up where the last one left off — no re-entering your preferences, no losing your context."}
            </p>
          </section>

          <section style={{ marginTop: 42 }}>
            <h2 className="atl-doc-callout-label" style={{ marginBottom: 10 }}>
              {isAr ? "مبادئنا" : "Our Principles"}
            </h2>
            <ul className="atl-doc-lede" style={{ paddingInlineStart: 20, marginTop: 8 }}>
              <li>
                <span style={{ fontWeight: 600 }}>{isAr ? "الشفافية أولاً:" : "Transparency first:"}</span>{" "}
                {isAr
                  ? "نخبرك من أين تأتي بيانات الوظائف وكيف تُحسب درجات التطابق."
                  : "We tell you where job data comes from and how your match scores are calculated."}
              </li>
              <li style={{ marginTop: 10 }}>
                <span style={{ fontWeight: 600 }}>{isAr ? "بياناتك ملكك:" : "Your data is yours:"}</span>{" "}
                {isAr
                  ? "لا نبيع سيرتك الذاتية أو ملفك الشخصي لأصحاب العمل أو المجندين أو الأطراف الثالثة."
                  : "We do not sell your CV or profile to employers, recruiters, or third parties."}
              </li>
              <li style={{ marginTop: 10 }}>
                <span style={{ fontWeight: 600 }}>{isAr ? "لا إجراءات صامتة:" : "No silent actions:"}</span>{" "}
                {isAr
                  ? "لن يتقدم ريكو أو يرسل رسالة أو يتخذ أي إجراء عالي التأثير دون تأكيدك."
                  : "Rico never applies, sends a message, or takes a high-impact action without your confirmation."}
              </li>
              <li style={{ marginTop: 10 }}>
                <span style={{ fontWeight: 600 }}>{isAr ? "تركيز على الإمارات:" : "UAE-focused:"}</span>{" "}
                {isAr
                  ? "كل ميزة مصممة لسوق العمل الإماراتي — القطاعات ومتطلبات التأشيرات ومعايير الرواتب وتوقعات أصحاب العمل."
                  : "Every feature is designed for the UAE job market — sectors, visa requirements, salary norms, and employer expectations."}
              </li>
            </ul>
          </section>

          <section style={{ marginTop: 42 }}>
            <h2 className="atl-doc-callout-label" style={{ marginBottom: 10 }}>
              {isAr ? "أين نحن" : "Where We Are"}
            </h2>
            <p className="atl-doc-lede">
              {isAr
                ? <>
                  <span style={{ fontWeight: 500 }}>شركة إيكو تكنولوجي لحماية البيئة ذ.م.م</span>، شركة مسجلة في الإمارات العربية المتحدة، تشغّل ريكو هانت. تخدم المنصة المهنيين في الإمارات ومنطقة الخليج الأشمل.
                </>
                : <>
                  Rico Hunt is operated by{" "}
                  <span style={{ fontWeight: 500 }}>Eco Technology Environment Protection Services L.L.C</span>, a UAE-registered company. The platform serves professionals across the UAE and the wider GCC region.
                </>}
            </p>
            <p className="atl-doc-lede" style={{ marginTop: 14 }}>
              {isAr
                ? "المنصة في مرحلة التطوير النشط حالياً. نُطلق تحديثات بانتظام بناءً على ملاحظات المستخدمين. إذا واجهت مشكلة أو لديك اقتراح، نودّ سماعه."
                : "The platform is currently in active development. We ship updates regularly based on user feedback. If you encounter a problem or have a suggestion, we want to hear from you."}
            </p>
          </section>

          <section style={{ marginTop: 48 }} className="atl-doc-callout">
            <h2 className="atl-doc-callout-label" style={{ marginBottom: 10 }}>
              {isAr ? "تواصل معنا" : "Get in Touch"}
            </h2>
            <p className="atl-doc-lede">
              {isAr ? "نحن فريق صغير ونقرأ كل رسالة." : "We\'re a small team and we read every message."}
            </p>
            <div
              className="atl-doc-lede"
              style={{
                marginTop: 18,
                display: "flex",
                flexWrap: "wrap",
                gap: 12,
              }}
            >
              <a
                href="mailto:info@ricohunt.com"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "10px 14px",
                  border: "1px solid var(--rule)",
                  borderRadius: "var(--atl-radius-sm)",
                  color: "var(--ink)",
                  textDecoration: "none",
                  fontSize: 14,
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#cf3d17" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <rect x="2" y="4" width="20" height="16" rx="2" />
                  <path d="m22 7-10 6L2 7" />
                </svg>
                info@ricohunt.com
              </a>
              <a
                href="https://wa.me/971585989080?text=Hi%2C%20I%27d%20like%20to%20know%20more%20about%20Rico%20Hunt"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "10px 14px",
                  border: "1px solid var(--rule)",
                  borderRadius: "var(--atl-radius-sm)",
                  color: "var(--ink)",
                  textDecoration: "none",
                  fontSize: 14,
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#cf3d17" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                WhatsApp
              </a>
              <a
                href="https://www.linkedin.com/company/eco-technology-environment-protection-services-l-l-c/"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "10px 14px",
                  border: "1px solid var(--rule)",
                  borderRadius: "var(--atl-radius-sm)",
                  color: "var(--ink)",
                  textDecoration: "none",
                  fontSize: 14,
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#cf3d17" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <rect x="2" y="7" width="20" height="14" rx="2" />
                  <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
                </svg>
                {isAr ? "لينكدإن الشركة" : "Company LinkedIn"}
              </a>
              <Link
                href="/contact"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "10px 14px",
                  borderRadius: "var(--atl-radius-sm)",
                  background: "var(--sun)",
                  color: "var(--paper)",
                  textDecoration: "none",
                  fontWeight: 600,
                  fontSize: 14,
                }}
              >
                {isAr ? "أرسل رسالة ←" : "Send a message →"}
              </Link>
            </div>
          </section>
        </article>
      </main>

      <footer className="atl-doc-footer">
        <p className="atl-doc-footer-brand">Rico Hunt</p>
        <p>Powered by Eco Technology Environment Protection Services L.L.C</p>
        <p>{isAr ? "الإمارات العربية المتحدة" : "United Arab Emirates"}</p>
        <div className="atl-doc-footer-links">
          <span className="atl-doc-current">{isAr ? "عن ريكو" : "About"}</span>
          <Link href="/contact">{isAr ? "تواصل" : "Contact"}</Link>
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
