"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import Link from "next/link";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { AuraGlow } from "@/components/ui/AuraGlow";

export function ContactContent() {
  const { language, setLanguage } = useLanguage();
  const isAr = language === "ar";

  return (
    <div dir={isAr ? "rtl" : "ltr"} className="relative min-h-screen overflow-x-hidden bg-[#0a0a1a]">
      <AuraGlow aria-hidden="true" variant="magenta" position="top-left" />
      <AuraGlow aria-hidden="true" variant="cyan" position="bottom-right" />

      <header className="relative z-10 flex items-center justify-between border-b border-border-subtle bg-black/50 px-5 py-4 backdrop-blur-xl md:px-10">
        <Link href="/" className="flex items-center gap-2 text-lg font-black tracking-tight text-white">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#f5a623] text-[#0a0a1a] text-sm font-black shadow-[0_0_28px_rgba(245,166,35,0.28)]">R</span>
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
          <Link href="/about" className="text-sm text-text-secondary transition-colors hover:text-white">{isAr ? "عن ريكو" : "About"}</Link>
          <Link href="/terms" className="text-sm text-text-secondary transition-colors hover:text-white">{isAr ? "الشروط" : "Terms"}</Link>
          <Link href="/privacy" className="text-sm text-text-secondary transition-colors hover:text-white">{isAr ? "الخصوصية" : "Privacy"}</Link>
        </nav>
      </header>

      <main className="relative z-10 mx-auto max-w-4xl px-5 py-16 md:px-10">
        <GlassPanel className="rounded-2xl border border-white/10 p-8 md:p-12">
          <div className="mb-10">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#f5a623]">
              {isAr ? "تواصل معنا" : "Get in Touch"}
            </p>
            <h1 className="mb-4 text-3xl font-semibold text-white md:text-4xl">
              {isAr ? "نقرأ كل رسالة." : "We read every message."}
            </h1>
            <p className="text-base leading-7 text-text-secondary">
              {isAr
                ? "سواء كان لديك سؤال حول حسابك، ملاحظة على المنتج، استفسار تجاري، أو أي شيء آخر — تواصل معنا وسنرد في أقرب وقت ممكن."
                : "Whether you have a question about your account, feedback on the product, a business enquiry, or something else entirely — reach out and we'll respond as soon as possible."}
            </p>
            <div className="mt-5 rounded-xl border border-white/10 bg-white/5 px-5 py-4">
              <p className="text-sm font-semibold text-white">
                {isAr ? "شركة إيكو تكنولوجي لحماية البيئة ذ.م.م" : "Eco Technology Environment Protection Services L.L.C"}
              </p>
              <p className="mt-0.5 text-xs text-text-tertiary">
                {isAr ? "شركة مسجلة في الإمارات · الرقم الضريبي متاح عند الطلب" : "UAE-registered company · TRN available upon request"}
              </p>
            </div>
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <a href="mailto:info@ricohunt.com" className="group flex flex-col gap-3 rounded-xl border border-white/10 bg-white/5 p-6 transition-colors hover:bg-white/10">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#f5a623]/10 text-[#f5a623]">
                <span className="material-symbols-outlined">mail</span>
              </div>
              <div>
                <p className="mb-1 text-sm font-semibold text-white">{isAr ? "البريد الإلكتروني" : "Email"}</p>
                <p className="text-sm text-text-secondary">info@ricohunt.com</p>
                <p className="mt-2 text-xs text-text-tertiary">
                  {isAr
                    ? "للاستفسارات العامة والدعم والتواصل التجاري. نهدف للرد خلال 24 ساعة."
                    : "For general enquiries, support, and business communication. We aim to respond within 24 hours."}
                </p>
              </div>
            </a>

            <a href="https://wa.me/971585989080?text=Hi%2C%20I%27d%20like%20to%20get%20in%20touch%20with%20Rico%20Hunt" target="_blank" rel="noopener noreferrer" className="group flex flex-col gap-3 rounded-xl border border-white/10 bg-white/5 p-6 transition-colors hover:bg-white/10">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#f5a623]/10 text-[#f5a623]">
                <span className="material-symbols-outlined">chat</span>
              </div>
              <div>
                <p className="mb-1 text-sm font-semibold text-white">WhatsApp</p>
                <p className="text-sm text-text-secondary">+971 58 598 9080</p>
                <p className="mt-2 text-xs text-text-tertiary">
                  {isAr
                    ? "أسئلة سريعة ودعم مباشر. متاح خلال ساعات عمل الإمارات، الأحد – الخميس."
                    : "Quick questions and live support. Available during UAE business hours, Sunday–Thursday."}
                </p>
              </div>
            </a>

            <div className="flex flex-col gap-3 rounded-xl border border-white/10 bg-white/5 p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#f5a623]/10 text-[#f5a623]">
                <span className="material-symbols-outlined">location_on</span>
              </div>
              <div>
                <p className="mb-1 text-sm font-semibold text-white">{isAr ? "الموقع" : "Location"}</p>
                <p className="text-sm text-text-secondary">{isAr ? "الإمارات العربية المتحدة" : "United Arab Emirates"}</p>
                <p className="mt-1 text-xs text-text-secondary">
                  {isAr ? "شركة إيكو تكنولوجي لحماية البيئة ذ.م.م" : "Eco Technology Environment Protection Services L.L.C"}
                </p>
                <p className="mt-2 text-xs text-text-tertiary">
                  {isAr
                    ? "ريكو هانت منصة مسجلة في الإمارات تخدم المهنيين في الإمارات ومنطقة الخليج الأشمل."
                    : "Rico Hunt is a UAE-registered platform serving professionals across the UAE and the wider GCC region."}
                </p>
              </div>
            </div>

            <div className="flex flex-col gap-3 rounded-xl border border-white/10 bg-white/5 p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#f5a623]/10 text-[#f5a623]">
                <span className="material-symbols-outlined">schedule</span>
              </div>
              <div>
                <p className="mb-1 text-sm font-semibold text-white">{isAr ? "وقت الاستجابة" : "Response Time"}</p>
                <p className="text-sm text-text-secondary">{isAr ? "خلال 24 ساعة" : "Within 24 hours"}</p>
                <p className="mt-2 text-xs text-text-tertiary">
                  {isAr
                    ? "نحن فريق صغير نأخذ الدعم بجدية. إذا لم تتلقَّ رداً خلال 24 ساعة، يرجى إعادة إرسال رسالتك."
                    : "We're a small team that takes support seriously. If you don't hear back within 24 hours, please resend your message."}
                </p>
              </div>
            </div>

            <a href="https://www.linkedin.com/company/eco-technology-environment-protection-services-l-l-c/" target="_blank" rel="noopener noreferrer" className="group flex flex-col gap-3 rounded-xl border border-white/10 bg-white/5 p-6 transition-colors hover:bg-white/10 sm:col-span-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#f5a623]/10 text-[#f5a623]">
                <span className="material-symbols-outlined">business</span>
              </div>
              <div>
                <p className="mb-1 text-sm font-semibold text-white">{isAr ? "لينكدإن الشركة" : "Company LinkedIn"}</p>
                <p className="text-sm text-text-secondary">
                  {isAr ? "شركة إيكو تكنولوجي لحماية البيئة ذ.م.م" : "Eco Technology Environment Protection Services L.L.C"}
                </p>
                <p className="mt-2 text-xs text-text-tertiary">
                  {isAr
                    ? "اطلع على ملف الشركة على لينكدإن للتحقق من التسجيل ومعرفة المزيد."
                    : "View the company profile on LinkedIn to verify registration and learn more."}
                </p>
              </div>
            </a>
          </div>

          <div className="mt-10 rounded-xl border border-[#f5a623]/20 bg-[#f5a623]/5 p-6">
            <h2 className="mb-2 text-base font-semibold text-white">
              {isAr ? "تستخدم ريكو بالفعل؟" : "Already using Rico?"}
            </h2>
            <p className="mb-4 text-sm text-text-secondary">
              {isAr
                ? "للمساعدة الخاصة بحسابك، الطريقة الأسرع هي مراسلة ريكو مباشرة داخل التطبيق — أو مراسلتنا بالبريد الإلكتروني المسجل حتى نتمكن من الاطلاع على حسابك."
                : "For account-specific help, the fastest path is to message Rico directly inside the app — or email us with your registered email address so we can look up your account."}
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/login" className="inline-flex items-center gap-1.5 rounded-lg bg-[#f5a623] px-4 py-2 text-sm font-semibold text-[#0a0a1a] transition-opacity hover:opacity-90">
                {isAr ? "تسجيل الدخول لحسابك ←" : "Sign in to your account →"}
              </Link>
              <Link href="/chat" className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-white transition-colors hover:bg-white/10">
                {isAr ? "جرّب المحادثة العامة" : "Try the public chat"}
              </Link>
            </div>
          </div>
        </GlassPanel>
      </main>

      <footer className="relative z-10 border-t border-white/10 bg-black/30 px-5 py-8 text-center">
        <p className="mb-1 text-sm font-semibold text-white">Rico Hunt</p>
        <p className="mb-1 text-xs text-text-tertiary">Powered by Eco Technology Environment Protection Services L.L.C</p>
        <p className="mb-3 text-xs text-text-tertiary">{isAr ? "الإمارات العربية المتحدة" : "United Arab Emirates"}</p>
        <div className="mb-3 flex flex-wrap items-center justify-center gap-5">
          <Link href="/about" className="text-xs text-text-tertiary transition-colors hover:text-white">{isAr ? "عن ريكو" : "About"}</Link>
          <span className="text-xs font-medium text-white">{isAr ? "تواصل" : "Contact"}</span>
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
