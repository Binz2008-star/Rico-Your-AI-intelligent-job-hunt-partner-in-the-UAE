"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import Link from "next/link";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { AuraGlow } from "@/components/ui/AuraGlow";

export function AboutContent() {
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
          <span>Rico<span className="text-[#f5a623]"> Hunt</span></span>
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
          <Link href="/contact" className="text-sm text-text-secondary transition-colors hover:text-white">
            {isAr ? "تواصل" : "Contact"}
          </Link>
          <Link href="/terms" className="text-sm text-text-secondary transition-colors hover:text-white">
            {isAr ? "الشروط" : "Terms"}
          </Link>
          <Link href="/privacy" className="text-sm text-text-secondary transition-colors hover:text-white">
            {isAr ? "الخصوصية" : "Privacy"}
          </Link>
        </nav>
      </header>

      <main className="relative z-10 mx-auto max-w-4xl px-5 py-16 md:px-10">
        <GlassPanel className="rounded-2xl border border-white/10 p-8 md:p-12">
          <div className="mb-10">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#f5a623]">
              {isAr ? "قصتنا" : "Our Story"}
            </p>
            <h1 className="mb-4 text-3xl font-semibold text-white md:text-4xl">
              {isAr
                ? "بُني لسوق العمل في الإمارات. بُني حول سيرتك الذاتية."
                : <>Built for the UAE job market.<br />Built around your CV.</>}
            </h1>
            <p className="text-base leading-7 text-text-secondary">
              {isAr
                ? <>ريكو هانت منصة مهنية مدعومة بالذكاء الاصطناعي تهدف إلى مساعدة المهنيين في الإمارات ودول الخليج على اكتشاف الفرص المناسبة وتحسين استراتيجية البحث عن عمل وإدارة الطلبات بكفاءة أعلى. تشغّل ريكو هانت <span className="text-white font-medium">شركة إيكو تكنولوجي لحماية البيئة ذ.م.م</span>، وهي شركة مسجلة في الإمارات العربية المتحدة.</>
                : <>Rico Hunt is an AI-powered career platform focused on helping professionals in the UAE and GCC discover relevant opportunities, improve their job search strategy, and manage applications more effectively. Rico Hunt is operated by{" "}<span className="text-white font-medium">Eco Technology Environment Protection Services L.L.C</span>, a UAE-registered company.</>}
            </p>
          </div>

          <div className="space-y-10 text-sm leading-7 text-text-secondary">
            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "المشكلة التي نحلها" : "The Problem We're Solving"}
              </h2>
              {isAr ? (
                <>
                  <p>سوق العمل في الإمارات متسارع وتنافسي للغاية. يقضي معظم الباحثين عن عمل وقتهم في إدارة لوجستيات البحث بدلاً من التحضير للفرص الفعلية. تعرض المنصات العامة مئات الوظائف غير الملائمة، وتُلزم المستخدمين بخطوات إعداد مطولة، وتقدم إرشادات محدودة حول الأدوار التي تتناسب فعلاً مع خلفياتهم.</p>
                  <p className="mt-3">ريكو هو إجابتنا على تلك المشكلة: مساعد مهني يعمل بالذكاء الاصطناعي يقرأ سيرتك الذاتية مرة واحدة، يبني فهماً منظماً لخبرتك، ثم يعمل باستمرار في الخلفية ليكشف الفرص المناسبة في الإمارات التي تتوافق مع من أنت فعلاً — لا مجرد كلمات مفتاحية.</p>
                </>
              ) : (
                <>
                  <p>The UAE job market is fast-moving and highly competitive. Most job seekers spend more time managing the logistics of job hunting than actually preparing for opportunities. Generic platforms surface hundreds of mismatched listings, force users through lengthy setup wizards, and offer little guidance on which roles actually fit their background.</p>
                  <p className="mt-3">Rico is our answer to that problem: an AI career companion that reads your CV once, builds a structured understanding of your experience, and then works continuously in the background to surface UAE-specific opportunities that match who you actually are — not just keywords.</p>
                </>
              )}
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "كيف يجد ريكو الوظائف" : "How Rico Finds Jobs"}
              </h2>
              {isAr ? (
                <>
                  <p>يجمع ريكو الوظائف المباشرة من أنحاء الإمارات باستخدام <span className="text-white">JSearch API</span> (مدعومة من RapidAPI)، التي تسحب بيانات في الوقت الفعلي من لينكدإن وإنديد وغلاسدور وبيت وغيرها من اللوحات الكبرى النشطة في المنطقة. تُفلتر الوظائف وتُرتَّب وفق سيرتك الذاتية وملفك المهني — لترى فقط الأدوار التي تتناسب فعلاً مع خلفيتك.</p>
                  <p className="mt-3">لن يتقدم ريكو لأي وظيفة نيابةً عنك دون موافقتك الصريحة. كل إجراء تقديم يتطلب تأكيدك. أنت في السيطرة الكاملة في كل خطوة.</p>
                </>
              ) : (
                <>
                  <p>Rico aggregates live job listings from across the UAE using the{" "}<span className="text-white">JSearch API</span> (powered by RapidAPI), which pulls real-time data from LinkedIn, Indeed, Glassdoor, Bayt, and other major job boards active in the region. Listings are filtered and scored against your CV and profile — so you only see roles where your background is genuinely relevant.</p>
                  <p className="mt-3">Rico does not apply to jobs on your behalf without your explicit approval. Every application requires your confirmation. You stay in control at every step.</p>
                </>
              )}
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "ما يتذكره ريكو" : "What Rico Remembers"}
              </h2>
              <p>
                {isAr
                  ? "على عكس محرك البحث، يحتفظ ريكو بملف مهني دائم لأهدافك: الأدوار المستهدفة والقطاعات المفضلة وتوقعات الراتب وتاريخ التوظيف. هذا يعني أن كل جلسة بحث تبدأ من حيث انتهيت — دون الحاجة إلى إعادة إدخال تفضيلاتك أو فقدان سياقك."
                  : "Unlike a search engine, Rico maintains a persistent profile of your career goals: your target roles, preferred sectors, salary expectations, and job history. This means every search session picks up where the last one left off — no re-entering your preferences, no losing your context."}
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "مبادئنا" : "Our Principles"}
              </h2>
              <ul className="ml-4 list-disc space-y-2">
                <li>
                  <strong className="text-white">{isAr ? "الشفافية أولاً:" : "Transparency first:"}</strong>{" "}
                  {isAr
                    ? "نخبرك من أين تأتي بيانات الوظائف وكيف تُحسب درجات التطابق."
                    : "We tell you where job data comes from and how your match scores are calculated."}
                </li>
                <li>
                  <strong className="text-white">{isAr ? "بياناتك ملكك:" : "Your data is yours:"}</strong>{" "}
                  {isAr
                    ? "لا نبيع سيرتك الذاتية أو ملفك الشخصي لأصحاب العمل أو المجندين أو الأطراف الثالثة."
                    : "We do not sell your CV or profile to employers, recruiters, or third parties."}
                </li>
                <li>
                  <strong className="text-white">{isAr ? "لا إجراءات صامتة:" : "No silent actions:"}</strong>{" "}
                  {isAr
                    ? "لن يتقدم ريكو أو يرسل رسالة أو يتخذ أي إجراء عالي التأثير دون تأكيدك."
                    : "Rico never applies, sends a message, or takes a high-impact action without your confirmation."}
                </li>
                <li>
                  <strong className="text-white">{isAr ? "تركيز على الإمارات:" : "UAE-focused:"}</strong>{" "}
                  {isAr
                    ? "كل ميزة مصممة لسوق العمل الإماراتي — القطاعات ومتطلبات التأشيرات ومعايير الرواتب وتوقعات أصحاب العمل."
                    : "Every feature is designed for the UAE job market — sectors, visa requirements, salary norms, and employer expectations."}
                </li>
              </ul>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "أين نحن" : "Where We Are"}
              </h2>
              <p>
                {isAr
                  ? <><span className="text-white font-medium">شركة إيكو تكنولوجي لحماية البيئة ذ.م.م</span>، شركة مسجلة في الإمارات العربية المتحدة، تشغّل ريكو هانت. تخدم المنصة المهنيين في الإمارات ومنطقة الخليج الأشمل.</>
                  : <>Rico Hunt is operated by{" "}<span className="text-white font-medium">Eco Technology Environment Protection Services L.L.C</span>, a UAE-registered company. The platform serves professionals across the UAE and the wider GCC region.</>}
              </p>
              <p className="mt-3">
                {isAr
                  ? "المنصة في مرحلة التطوير النشط حالياً. نُطلق تحديثات بانتظام بناءً على ملاحظات المستخدمين. إذا واجهت مشكلة أو لديك اقتراح، نودّ سماعه."
                  : "The platform is currently in active development. We ship updates regularly based on user feedback. If you encounter a problem or have a suggestion, we want to hear from you."}
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "تواصل معنا" : "Get in Touch"}
              </h2>
              <p>{isAr ? "نحن فريق صغير ونقرأ كل رسالة." : "We're a small team and we read every message."}</p>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
                <a href="mailto:info@ricohunt.com" className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white transition-colors hover:bg-white/10">
                  <span className="material-symbols-outlined text-base text-[#f5a623]">mail</span>
                  info@ricohunt.com
                </a>
                <a href="https://wa.me/971585989080?text=Hi%2C%20I%27d%20like%20to%20know%20more%20about%20Rico%20Hunt" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white transition-colors hover:bg-white/10">
                  <span className="material-symbols-outlined text-base text-[#f5a623]">chat</span>
                  WhatsApp
                </a>
                <a href="https://www.linkedin.com/company/eco-technology-environment-protection-services-l-l-c/" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white transition-colors hover:bg-white/10">
                  <span className="material-symbols-outlined text-base text-[#f5a623]">business</span>
                  {isAr ? "لينكدإن الشركة" : "Company LinkedIn"}
                </a>
                <Link href="/contact" className="inline-flex items-center gap-2 rounded-lg bg-[#f5a623] px-4 py-2.5 text-sm font-semibold text-[#0a0a1a] transition-opacity hover:opacity-90">
                  {isAr ? "أرسل رسالة ←" : "Send a message →"}
                </Link>
              </div>
            </section>
          </div>
        </GlassPanel>
      </main>

      <footer className="relative z-10 border-t border-white/10 bg-black/30 px-5 py-8 text-center">
        <p className="mb-1 text-sm font-semibold text-white">Rico Hunt</p>
        <p className="mb-1 text-xs text-text-tertiary">Powered by Eco Technology Environment Protection Services L.L.C</p>
        <p className="mb-3 text-xs text-text-tertiary">{isAr ? "الإمارات العربية المتحدة" : "United Arab Emirates"}</p>
        <div className="mb-3 flex flex-wrap items-center justify-center gap-5">
          <span className="text-xs font-medium text-white">{isAr ? "عن ريكو" : "About"}</span>
          <Link href="/contact" className="text-xs text-text-tertiary transition-colors hover:text-white">{isAr ? "تواصل" : "Contact"}</Link>
          <Link href="/terms" className="text-xs text-text-tertiary transition-colors hover:text-white">{isAr ? "الشروط" : "Terms"}</Link>
          <Link href="/privacy" className="text-xs text-text-tertiary transition-colors hover:text-white">{isAr ? "الخصوصية" : "Privacy"}</Link>
          <Link href="/refund-policy" className="text-xs text-text-tertiary transition-colors hover:text-white">{isAr ? "الاسترداد" : "Refunds"}</Link>
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
