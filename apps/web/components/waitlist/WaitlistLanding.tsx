"use client";

import { useEffect, useRef } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import Link from "next/link";
import { WaitlistForm } from "./WaitlistForm";

import "@/app/_atelier/atelier-tokens.css";
import "@/app/_atelier/atelier-waitlist.css";

const COPY = {
  en: {
    eyebrow: "PRIVATE PREVIEW · UAE",
    title: "Rico is preparing your career operating system.",
    body:
      "Early access will open in controlled waves while we finish the final reliability and onboarding gates.",
    signals: [
      "AI career intelligence",
      "Opportunity discovery",
      "Application operations",
      "Human approval remains in control",
    ],
    login: "Internal access",
    privacy: "Privacy",
    terms: "Terms",
    note: "No CV, payment, or password is required to join the waitlist.",
  },
  ar: {
    eyebrow: "معاينة خاصة · الإمارات",
    title: "ريكو يجهّز نظام التشغيل المهني الخاص بك.",
    body:
      "سيفتح الوصول المبكر على دفعات محدودة إلى أن نُكمل بوابات الاعتمادية والإعداد النهائي.",
    signals: [
      "ذكاء مهني مدعوم بالذكاء الاصطناعي",
      "اكتشاف الفرص المناسبة",
      "إدارة عمليات التقديم",
      "الموافقة البشرية تبقى صاحبة القرار",
    ],
    login: "دخول الفريق",
    privacy: "الخصوصية",
    terms: "الشروط",
    note: "لا نطلب سيرة ذاتية أو دفعًا أو كلمة مرور للانضمام إلى قائمة الانتظار.",
  },
};

export function WaitlistLanding() {
  const { language, setLanguage } = useLanguage();
  const copy = COPY[language];
  const panelRef = useRef<HTMLElement | null>(null);

  // The embedded launch film posts "rico:waitlist" (its CTA/Skip) instead of
  // navigating away to /signup; bring the on-page waitlist form into view.
  useEffect(() => {
    function onMessage(event: MessageEvent) {
      if (event.data !== "rico:waitlist") return;
      const panel = panelRef.current;
      if (!panel) return;
      panel.scrollIntoView({ behavior: "smooth", block: "center" });
      const email = panel.querySelector<HTMLInputElement>('input[type="email"]');
      if (email) window.setTimeout(() => email.focus(), 400);
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  return (
    <main className="atelier atl-waitlist" dir={language === "ar" ? "rtl" : "ltr"}>
      <header className="atl-waitlist-header">
        <Link className="atl-waitlist-brand" href="/" aria-label="Rico Hunt">
          <span className="atl-waitlist-mark">R</span>
          <span>Rico Hunt</span>
        </Link>
        <nav aria-label="Pre-launch navigation">
          <button
            type="button"
            className="atl-waitlist-lang"
            onClick={() => setLanguage(language === "en" ? "ar" : "en")}
          >
            {language === "en" ? "العربية" : "EN"}
          </button>
          <Link href="/login">{copy.login}</Link>
        </nav>
      </header>

      <section className="atl-waitlist-main">
        <div className="atl-waitlist-copy">
          <div className="atl-waitlist-film" aria-label="Rico launch film">
            <iframe
              src="/explainer/index.html"
              title="Rico — Launch Film"
              loading="lazy"
              allow="autoplay; fullscreen"
            />
          </div>
          <p className="atl-waitlist-eyebrow">{copy.eyebrow}</p>
          <h1>{copy.title}</h1>
          <p className="atl-waitlist-lead">{copy.body}</p>
          <ul>
            {copy.signals.map((signal) => (
              <li key={signal}>
                <span aria-hidden="true">◆</span>
                {signal}
              </li>
            ))}
          </ul>
        </div>

        <aside className="atl-waitlist-panel" aria-label="Early access" ref={panelRef}>
          <WaitlistForm />
          <p className="atl-waitlist-note">{copy.note}</p>
        </aside>
      </section>

      <footer className="atl-waitlist-footer">
        <span>© 2026 Rico Hunt</span>
        <div>
          <Link href="/privacy">{copy.privacy}</Link>
          <Link href="/terms">{copy.terms}</Link>
        </div>
      </footer>
    </main>
  );
}
