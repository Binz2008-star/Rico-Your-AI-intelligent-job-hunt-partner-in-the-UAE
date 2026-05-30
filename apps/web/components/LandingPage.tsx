"use client";

import { MotionConfig, motion } from "framer-motion";
import Link from "next/link";
import type { ReactNode } from "react";
import { useLanguage } from "@/contexts/LanguageContext";

function RicoCardPanel({
  children,
  className = "",
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 22 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, delay, ease: "easeOut" }}
      whileHover={{ y: -4 }}
      className={`rico-card rounded-[28px] p-5 transition-all duration-300 hover:border-[rgba(0,229,255,0.22)] hover:shadow-[0_28px_80px_rgba(0,0,0,0.38),0_0_50px_rgba(0,229,255,0.055)] md:p-6 ${className}`}
    >
      <div className="relative z-10 h-full">{children}</div>
    </motion.div>
  );
}

function SectionHeading({
  eyebrow,
  title,
  body,
}: {
  eyebrow: string;
  title: string;
  body: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, ease: "easeOut" }}
      className="mx-auto mb-10 max-w-3xl text-center"
    >
      <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.28em] text-cyan">
        {eyebrow}
      </p>
      <h2 className="font-display text-3xl font-semibold text-white md:text-5xl">
        {title}
      </h2>
      <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-text-secondary md:text-lg">
        {body}
      </p>
    </motion.div>
  );
}

export default function LandingPage() {
  const { language, setLanguage } = useLanguage();
  const isAr = language === "ar";

  // ── Inline translations ────────────────────────────────────────────────────
  const t = {
    // Header
    signIn: isAr ? "تسجيل الدخول" : "Sign in",
    signUpFree: isAr ? "سجّل مجانًا" : "Sign up free",
    langToggle: isAr ? "EN" : "عربي",
    langToggleLabel: isAr ? "Switch to English" : "Switch to Arabic",
    // Hero
    heroBadge: isAr ? "شريكك الذكي في البحث عن عمل بالإمارات" : "Your AI job-hunt partner in the UAE",
    heroH1Line1: isAr ? "ارفع سيرتك الذاتية." : "Upload your CV.",
    heroH1Line2: isAr
      ? "ودع ريكو يدير رحلة البحث عن العمل في الإمارات."
      : "Let Rico run your job search smarter.",
    heroBody: isAr
      ? "يقرأ ريكو سيرتك الذاتية، ويبحث عن الوظائف المناسبة في الإمارات، ويتابع طلباتك، ويرشدك في خطوتك المهنية التالية."
      : "Rico reads your CV, finds matching UAE jobs, tracks your applications, and guides your next career move — in English and Arabic.",
    heroTagline: isAr
      ? "لن يتقدم ريكو بصمت. أنت توافق على كل إجراء مهم."
      : "Rico never applies silently. You approve every important action.",
    ctaUploadCV: isAr ? "ارفع سيرتك الذاتية" : "Upload your CV",
    ctaStartFree: isAr ? "ابدأ مجانًا" : "Start free",
    // Intelligence card (hero right column)
    cardLabel: isAr ? "ما يفعله ريكو لك" : "What Rico does for you",
    cardTitle: isAr ? "يعمل ريكو على بحثك الوظيفي" : "Working on your job search",
    online: isAr ? "متصل" : "Online",
    ready: isAr ? "جاهز" : "ready",
    watching: isAr ? "يراقب" : "watching",
    // How Rico works section
    howWorksEyebrow: isAr ? "كيف يعمل ريكو" : "How Rico works",
    howWorksTitle: isAr ? "من السيرة الذاتية إلى فرص عمل أفضل" : "From CV to better job opportunities",
    howWorksBody: isAr
      ? "ارفع سيرتك الذاتية مرة واحدة. يقرأ ريكو خبرتك ويبدأ في إيجاد وظائف مناسبة في الإمارات فورًا."
      : "Upload your CV once. Rico reads your experience and starts finding matching UAE jobs right away.",
    // Memory section
    memoryEyebrow: isAr ? "ريكو يتذكر أهدافك المهنية" : "Rico remembers your career goals",
    memoryTitle: isAr ? "كل بحث يصبح أذكى" : "Every search gets smarter",
    memoryBody: isAr
      ? "كل بحث يصبح أذكى لأن ريكو يتذكر سيرتك الذاتية والأدوار المستهدفة والمواقع المفضلة وسجل التقديم."
      : "Every search gets smarter because Rico remembers your CV, target roles, preferred locations, and application history.",
    // Job matching section
    matchingEyebrow: isAr ? "مطابقة وظائف ذكية" : "Smart job matching",
    matchingTitle: isAr ? "وظائف تناسب سيرتك الذاتية، لا ضجيج عشوائي" : "Jobs that fit your CV, not random job-board noise",
    uaeJobsBadge: isAr ? "وظائف الإمارات" : "UAE jobs",
    fitLabel: isAr ? "ملاءمة" : "fit",
    // Alert section
    alertEyebrow: isAr ? "تنبيهات عند تغيّر شيء مهم" : "Job alerts when something important changes",
    alertTitle: isAr ? "ريكو يخبرك متى تتصرف" : "Rico tells you when to act",
    alertBody: isAr
      ? "يراقب ريكو وظائفك المحفوظة والمطابقات الجديدة وحالة الطلبات — وينبهك عندما يستحق الأمر انتباهك."
      : "Rico watches your saved jobs, new matches, and application status — and alerts you when something is worth your attention.",
    latestAlert: isAr ? "آخر تنبيه" : "Latest alert",
    alertMessage: isAr
      ? "توجد وظيفة جديدة تناسب سيرتك الذاتية وراتبك المستهدف. ريكو مستعد لعرضها لك."
      : "A new job matches your CV and target salary. Rico is ready to show it to you.",
    // Control section
    controlEyebrow: isAr ? "أنت تتحكم" : "You stay in control",
    controlTitle: isAr ? "ريكو يعمل لك، لا بدلاً عنك" : "Rico works for you, not instead of you",
    controlBody: isAr
      ? "ريكو يبحث عن الوظائف ويرتبها ويتتبع تقدمك. أنت تقرر متى تتقدم، ومتى توقف، وأين تتجه في مسيرتك."
      : "Rico finds jobs, ranks them, and tracks your progress. You decide when to apply, when to pause, and which direction to take your career.",
    // Pricing section
    pricingEyebrow: isAr ? "التسعير" : "Pricing",
    pricingTitle: isAr ? "خطط بسيطة للحركات المهنية الجادة" : "Simple plans for serious career moves",
    pricingBody: isAr
      ? "ابدأ مجانًا مع 50 رسالة ذكاء اصطناعي و10 وظائف محفوظة. ترقَّ عندما تحتاج المزيد."
      : "Start free with 50 AI messages and 10 saved jobs. Upgrade when you need more.",
    pricingPopular: isAr ? "الأكثر شعبية" : "Popular",
    pricingPro: isAr ? "احترافي" : "Pro",
    pricingPremium: isAr ? "مميز" : "Premium",
    pricingPerMonth: isAr ? "/شهر" : "/month",
    pricingProFeatures: isAr
      ? ["300 رسالة ذكاء اصطناعي شهريًا", "100 وظيفة محفوظة", "20 تحسين ملف شخصي شهريًا", "توصيات أدوار ذكية", "نظام مطابقة متقدم"]
      : ["300 AI messages per month", "100 saved jobs", "20 profile optimisations per month", "Smart AI role recommendations", "Advanced match scoring"],
    pricingPremiumFeatures: isAr
      ? ["1500 رسالة ذكاء اصطناعي شهريًا", "وظائف محفوظة غير محدودة", "100 تحسين ملف شخصي شهريًا", "كل ما في الاحترافي", "نظام التقديم التلقائي", "توصيات مميزة"]
      : ["1500 AI messages per month", "Unlimited saved jobs", "100 profile optimisations per month", "Everything in Pro", "Auto-apply system", "Premium recommendations"],
    upgradePro: isAr ? "ترقية إلى احترافي" : "Upgrade to Pro",
    upgradePremium: isAr ? "ترقية إلى مميز" : "Upgrade to Premium",
    freePlan: isAr ? "مجاني" : "Free",
    freePlanDesc: isAr
      ? "50 رسالة ذكاء اصطناعي · 10 وظائف محفوظة · 1 تحسين ملف شخصي/شهر"
      : "50 AI messages · 10 saved jobs · 1 profile optimisation/mo",
    signUpFreeArrow: isAr ? "سجّل مجانًا ←" : "Sign up free →",
    // CTA section (bottom)
    ctaSectionEyebrow: isAr ? "ابدأ مجانًا" : "Start free",
    ctaSectionTitle: isAr
      ? "ارفع سيرتك الذاتية. دع ريكو يجد وظيفتك التالية."
      : "Upload your CV. Let Rico find your next job.",
    ctaSectionBody: isAr
      ? "ارفع سيرتك الذاتية وريكو يعمل على الفور. يقرأ خبرتك ويبحث عن وظائف مناسبة في الإمارات ويخبرك بما عليك فعله — بالعربية والإنجليزية."
      : "Upload your CV and Rico goes to work. It reads your experience, finds matching UAE jobs, and tells you what to do next — in English and Arabic.",
    // Footer
    footerTerms: isAr ? "الشروط" : "Terms",
    footerPrivacy: isAr ? "الخصوصية" : "Privacy",
    footerRefunds: isAr ? "الاسترداد" : "Refunds",
    footerRights: isAr ? "© 2026 ريكو هانت. جميع الحقوق محفوظة." : "© 2026 Rico Hunt. All rights reserved.",
  };

  // ── Language-reactive arrays ───────────────────────────────────────────────
  const intelligenceLoop = isAr
    ? [
        "قراءة سيرتك الذاتية",
        "فهم خبرتك",
        "البحث عن وظائف مناسبة في الإمارات",
        "تتبع طلباتك",
        "إرسال تنبيهات الوظائف",
      ]
    : [
        "Reading your CV",
        "Understanding your experience",
        "Finding matching UAE jobs",
        "Tracking your applications",
        "Sending job alerts",
      ];

  const productFlow = isAr
    ? [
        {
          step: "01",
          title: "ارفع سيرتك الذاتية",
          body: "يقرأ ريكو خبرتك ومهاراتك وتعليمك وتاريخك المهني.",
          icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 16V4M12 4 8 8M12 4l4 4" />
              <path d="M4 14v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" />
            </svg>
          ),
        },
        {
          step: "02",
          title: "بناء ملفك المهني",
          body: "يحول ريكو سيرتك الذاتية إلى ملف حي يستخدمه لمطابقتك مع وظائف أفضل.",
          icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="12" cy="8" r="4" />
              <path d="M4 21a8 8 0 0 1 16 0" />
            </svg>
          ),
        },
        {
          step: "03",
          title: "البحث عن وظائف مناسبة في الإمارات",
          body: "يبحث ريكو عن أدوار تناسب خبرتك وهدفك ومرتبك وموقعك.",
          icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="11" cy="11" r="7" />
              <path d="m21 21-4.3-4.3" />
            </svg>
          ),
        },
        {
          step: "04",
          title: "تتبع طلباتك",
          body: "احتفظ بوظائفك المحفوظة والروابط المفتوحة والطلبات والمتابعات في مكان واحد.",
          icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M9 11l3 3L22 4" />
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
            </svg>
          ),
        },
        {
          step: "05",
          title: "الحصول على إرشادات وتنبيهات",
          body: "يخبرك ريكو بما يهم الآن — مطابقة جديدة، مهارة ناقصة، أو تذكير بالمتابعة.",
          icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M3 12h4l2 6 4-12 2 6h6" />
            </svg>
          ),
        },
      ]
    : [
        {
          step: "01",
          title: "Upload your CV",
          body: "Rico reads your experience, skills, education, and career history.",
          icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 16V4M12 4 8 8M12 4l4 4" />
              <path d="M4 14v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" />
            </svg>
          ),
        },
        {
          step: "02",
          title: "Build your career profile",
          body: "Rico turns your CV into a living profile it can use to match you with better jobs.",
          icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="12" cy="8" r="4" />
              <path d="M4 21a8 8 0 0 1 16 0" />
            </svg>
          ),
        },
        {
          step: "03",
          title: "Find matching UAE jobs",
          body: "Rico searches for roles that fit your experience, target role, salary, and location.",
          icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="11" cy="11" r="7" />
              <path d="m21 21-4.3-4.3" />
            </svg>
          ),
        },
        {
          step: "04",
          title: "Track your applications",
          body: "Keep your saved jobs, opened links, applications, and follow-ups in one place.",
          icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M9 11l3 3L22 4" />
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
            </svg>
          ),
        },
        {
          step: "05",
          title: "Get guidance and alerts",
          body: "Rico tells you what matters next — a new job match, a missing skill, or a follow-up reminder.",
          icon: (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M3 12h4l2 6 4-12 2 6h6" />
            </svg>
          ),
        },
      ];

  const memoryItems = isAr
    ? [
        "سيرتك الذاتية وخبرتك",
        "الأدوار المستهدفة والمواقع المفضلة",
        "توقعات الراتب",
        "سجل الطلبات",
        "تذكيرات المتابعة",
      ]
    : [
        "Your CV and experience",
        "Target roles and preferred locations",
        "Salary expectations",
        "Application history",
        "Follow-up reminders",
      ];

  const liveMatches = isAr
    ? [
        { role: "مدير السلامة والصحة المهنية", score: "94", signal: "تطابق قوي مع خبرتك في السلامة والامتثال" },
        { role: "مدير العمليات", score: "89", signal: "تطابق جيد مع خبرتك في الإمارات" },
        { role: "مسؤول الامتثال البيئي", score: "86", signal: "يتطابق مع خلفيتك التنظيمية والتفتيشية" },
      ]
    : [
        { role: "HSE Manager", score: "94", signal: "Strong match with your safety and compliance experience" },
        { role: "Operations Manager", score: "89", signal: "Good match with your UAE experience" },
        { role: "Environmental Compliance Officer", score: "86", signal: "Matches your regulatory and inspection background" },
      ];

  const pillars = isAr
    ? [
        { label: "بحث وظيفي متخصص في الإمارات", icon: "AE" },
        { label: "مطابقة تعتمد على السيرة الذاتية", icon: "CV" },
        { label: "بحث وظيفي بالدردشة", icon: "AI" },
        { label: "دعم عبر واتساب والبريد الإلكتروني", icon: "✉" },
      ]
    : [
        { label: "UAE-focused job search", icon: "AE" },
        { label: "CV-first matching", icon: "CV" },
        { label: "Chat-based job search", icon: "AI" },
        { label: "WhatsApp & email support", icon: "✉" },
      ];

  const audienceCards = isAr
    ? [
        {
          heading: "مصمم للمهنيين في الإمارات",
          body: "السلامة والبيئة، الامتثال، الهندسة، المالية، وأدوار أخرى عبر دبي وأبوظبي والإمارات.",
        },
        {
          heading: "مبني حول سيرتك الذاتية",
          body: "ارفع مرة واحدة. يقرأ ريكو خبرتك ويحولها إلى إجراءات بحث وظيفي داخل المحادثة — بدون نماذج أو معالج.",
        },
        {
          heading: "الوصول المبكر — تجمع آراء المستخدمين",
          body: "نجمع التقييمات من أول مستخدمينا. إذا جربت ريكو، يسعدنا سماع رأيك.",
          ctas: [
            { label: "راسلنا", href: "mailto:info@ricohunt.ae?subject=Rico%20feedback" },
            { label: "واتساب", href: "https://wa.me/971585989080?text=Hi%2C%20I%27d%20like%20to%20share%20feedback%20about%20Rico" },
          ],
        },
      ]
    : [
        {
          heading: "Built for UAE professionals",
          body: "HSE, ESG, operations, compliance, engineering, and finance roles across Dubai, Abu Dhabi, and the wider UAE.",
        },
        {
          heading: "Designed around your CV",
          body: "Upload once. Rico reads your experience and turns it into job-search actions inside chat — no forms, no wizard.",
        },
        {
          heading: "Early access — beta feedback coming",
          body: "We're collecting feedback from our first users. If you try Rico, we'd love to hear what worked.",
          ctas: [
            { label: "Email us", href: "mailto:info@ricohunt.ae?subject=Rico%20feedback" },
            { label: "WhatsApp", href: "https://wa.me/971585989080?text=Hi%2C%20I%27d%20like%20to%20share%20feedback%20about%20Rico" },
          ],
        },
      ];

  const noItems = isAr
    ? ["لا معالج إعداد", "لا نماذج مؤسسية", "لا تقديم صامت"]
    : ["No setup wizard", "No enterprise forms", "No silent applying"];

  return (
    <MotionConfig reducedMotion="user">
      {/* dir switches the entire document layout to RTL for Arabic */}
      <div dir={isAr ? "rtl" : "ltr"} className="relative min-h-screen overflow-x-hidden bg-background text-white">
        <div className="fixed inset-0 pointer-events-none z-0">
          <motion.div
            aria-hidden="true"
            animate={{ opacity: [0.45, 0.8, 0.45], scale: [1, 1.04, 1] }}
            transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
            className="absolute -left-32 -top-40 h-[560px] w-[560px] rounded-full bg-magenta-dim blur-[140px]"
          />
          <motion.div
            aria-hidden="true"
            animate={{ opacity: [0.35, 0.72, 0.35], scale: [1.02, 1, 1.02] }}
            transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
            className="absolute -right-28 top-[20%] h-[520px] w-[520px] rounded-full bg-cyan-dim blur-[140px]"
          />
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.04)_0%,rgba(255,255,255,0)_18%,rgba(255,255,255,0.025)_100%)]" />
        </div>

        <header className="relative z-10 flex items-center justify-between border-b border-border-subtle bg-black/50 px-5 py-4 backdrop-blur-xl md:px-10">
          <Link
            href="/"
            className="flex items-center gap-2 text-lg font-black tracking-tight text-white"
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#f5a623] text-sm font-black text-[#0a0a1a] shadow-[0_0_28px_rgba(245,166,35,0.35)]">
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
              aria-label={t.langToggleLabel}
              className="text-[12px] font-semibold px-2.5 py-1 rounded-lg border border-border-subtle text-text-secondary hover:text-white hover:border-[#f5a623]/50 transition-colors"
            >
              {t.langToggle}
            </button>
            <Link
              href="/login"
              className="text-sm text-text-secondary transition-colors hover:text-white"
            >
              {t.signIn}
            </Link>
            <Link
              href="/signup"
              className="rounded-full border border-magenta/40 bg-magenta/10 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-magenta/25"
            >
              {t.signUpFree}
            </Link>
          </nav>
        </header>

        <main className="relative z-10">
          {/* Hero */}
          <section className="mx-auto grid min-h-[calc(100vh-73px)] max-w-7xl items-center gap-12 px-5 py-16 md:grid-cols-[1fr_0.88fr] md:px-10 lg:px-16">
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.75, ease: "easeOut" }}
              className="max-w-3xl"
            >
              <p className="mb-5 inline-flex rounded-full border border-cyan/25 bg-cyan/10 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.26em] text-cyan">
                {t.heroBadge}
              </p>
              <h1 className="font-display text-[clamp(2.5rem,7vw,5.5rem)] font-semibold leading-[1.02] tracking-tight text-text-primary">
                {t.heroH1Line1}{" "}
                <span className="bg-gradient-to-r from-magenta to-cyan bg-clip-text text-transparent">
                  {t.heroH1Line2}
                </span>
              </h1>
              <p className="mt-5 max-w-2xl text-lg leading-8 text-text-secondary md:text-xl">
                {t.heroBody}
              </p>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-text-tertiary">
                {t.heroTagline}
              </p>
              <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
                  <Link
                    href="/upload"
                    className="inline-flex w-full items-center justify-center rounded-full bg-gradient-to-r from-magenta to-cyan px-7 py-4 text-base font-semibold text-black transition-opacity hover:opacity-90 sm:w-auto"
                  >
                    {t.ctaUploadCV}
                  </Link>
                </motion.div>
                <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
                  <Link
                    href="/signup"
                    className="inline-flex w-full items-center justify-center rounded-full border border-white/10 bg-white/[0.04] px-7 py-4 text-base font-semibold text-white backdrop-blur-xl transition-colors hover:bg-white/[0.08] sm:w-auto"
                  >
                    {t.ctaStartFree}
                  </Link>
                </motion.div>
              </div>
            </motion.div>

            <RicoCardPanel
              delay={0.15}
              className="mx-auto w-full max-w-[560px]"
            >
              <div className="mb-6 flex items-center justify-between gap-4">
                <div>
                  <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-text-tertiary">
                    {t.cardLabel}
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold text-white">
                    {t.cardTitle}
                  </h2>
                </div>
                <span className="rounded-full border border-cyan/30 bg-cyan/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.2em] text-cyan">
                  {t.online}
                </span>
              </div>
              <div className="space-y-4">
                {intelligenceLoop.map((item, index) => (
                  <div
                    key={item}
                    className="border-b border-white/5 pb-4 last:border-b-0 last:pb-0"
                  >
                    <div className="mb-2 flex items-center justify-between gap-4">
                      <p className="text-sm font-medium text-white">{item}</p>
                      <p className="font-mono text-[11px] text-text-tertiary">
                        {index === 0 ? t.ready : t.watching}
                      </p>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.08]">
                      <motion.div
                        initial={{ width: "18%" }}
                        animate={{ width: `${92 - index * 9}%` }}
                        transition={{
                          duration: 1.1,
                          delay: 0.25 + index * 0.1,
                          ease: "easeOut",
                        }}
                        className="h-full rounded-full bg-gradient-to-r from-magenta to-cyan"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </RicoCardPanel>
          </section>

          {/* Pillars strip */}
          <section className="border-y border-border-subtle/50 bg-surface/30 px-5 py-6 md:px-10 lg:px-16">
            <div className="mx-auto max-w-7xl">
              <div className="flex flex-wrap justify-center gap-4 sm:gap-8">
                {pillars.map((p, i) => (
                  <motion.div
                    key={p.label}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: i * 0.07, ease: "easeOut" }}
                    className="flex items-center gap-2.5"
                  >
                    <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-border-subtle bg-surface-elevated font-mono text-[10px] font-bold text-cyan shrink-0">
                      {p.icon}
                    </span>
                    <span className="text-[13px] font-medium text-text-secondary">
                      {p.label}
                    </span>
                  </motion.div>
                ))}
              </div>
            </div>
          </section>

          {/* How Rico works */}
          <section className="px-5 py-16 md:px-10 lg:px-16">
            <SectionHeading
              eyebrow={t.howWorksEyebrow}
              title={t.howWorksTitle}
              body={t.howWorksBody}
            />
            <div className="mx-auto max-w-7xl">
              <div className="relative grid gap-4 md:grid-cols-5">
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute left-0 right-0 top-[34px] hidden h-px bg-gradient-to-r from-magenta/40 via-cyan/40 to-magenta/40 md:block"
                />
                {productFlow.map((node, index) => (
                  <motion.div
                    key={node.step}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: index * 0.08, ease: "easeOut" }}
                    className="relative flex flex-col items-center text-center"
                  >
                    <div className="relative z-10 flex h-[68px] w-[68px] items-center justify-center rounded-2xl border border-border-soft bg-surface-elevated shadow-[0_12px_40px_rgba(0,0,0,0.35)]">
                      <span className="h-7 w-7 text-cyan [&>svg]:h-full [&>svg]:w-full">
                        {node.icon}
                      </span>
                      <span className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-gradient-to-br from-magenta to-cyan font-mono text-[10px] font-bold text-black">
                        {index + 1}
                      </span>
                    </div>
                    <h3 className="mt-5 text-base font-semibold text-text-primary">
                      {node.title}
                    </h3>
                    <p className="mt-2 text-sm leading-6 text-text-secondary">
                      {node.body}
                    </p>
                    {index < productFlow.length - 1 && (
                      <div
                        aria-hidden="true"
                        className="my-3 h-5 w-px bg-gradient-to-b from-cyan/50 to-transparent md:hidden"
                      />
                    )}
                  </motion.div>
                ))}
              </div>
            </div>
          </section>

          {/* Memory section */}
          <section className="px-5 py-16 md:px-10 lg:px-16">
            <div className="mx-auto grid max-w-7xl gap-5 lg:grid-cols-[0.9fr_1.1fr]">
              <RicoCardPanel>
                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-magenta">
                  {t.memoryEyebrow}
                </p>
                <h2 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
                  {t.memoryTitle}
                </h2>
                <p className="mt-5 text-base leading-7 text-text-secondary">
                  {t.memoryBody}
                </p>
              </RicoCardPanel>
              <RicoCardPanel delay={0.08}>
                <div className="grid gap-3 sm:grid-cols-2">
                  {memoryItems.map((item) => (
                    <div
                      key={item}
                      className="rounded-lg border border-white/[0.08] bg-white/[0.03] p-4"
                    >
                      <div className="mb-4 h-1 w-10 rounded-full bg-gradient-to-r from-magenta to-cyan" />
                      <p className="text-sm font-medium text-white">{item}</p>
                    </div>
                  ))}
                </div>
              </RicoCardPanel>
            </div>
          </section>

          {/* Job matching section */}
          <section className="px-5 py-16 md:px-10 lg:px-16">
            <div className="mx-auto grid max-w-7xl gap-5 lg:grid-cols-[1.1fr_0.9fr]">
              <RicoCardPanel>
                <div className="mb-6 flex items-center justify-between gap-4">
                  <div>
                    <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-cyan">
                      {t.matchingEyebrow}
                    </p>
                    <h2 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
                      {t.matchingTitle}
                    </h2>
                  </div>
                  <span className="hidden rounded-full border border-magenta/30 bg-magenta/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-magenta sm:inline-flex">
                    {t.uaeJobsBadge}
                  </span>
                </div>
                <div className="space-y-3">
                  {liveMatches.map((match) => (
                    <div
                      key={match.role}
                      className="rounded-lg border border-white/[0.08] bg-white/[0.03] p-4"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h3 className="text-base font-semibold text-white">
                            {match.role}
                          </h3>
                          <p className="mt-1 text-sm text-text-tertiary">
                            {match.signal}
                          </p>
                        </div>
                        <div className={isAr ? "text-left" : "text-right"}>
                          <p className="font-mono text-2xl text-cyan">
                            {match.score}
                          </p>
                          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
                            {t.fitLabel}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </RicoCardPanel>
              <RicoCardPanel delay={0.08}>
                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-magenta">
                  {t.alertEyebrow}
                </p>
                <h2 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
                  {t.alertTitle}
                </h2>
                <p className="mt-5 text-base leading-7 text-text-secondary">
                  {t.alertBody}
                </p>
                <div className="mt-8 rounded-lg border border-cyan/[0.18] bg-cyan/10 p-4">
                  <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-cyan">
                    {t.latestAlert}
                  </p>
                  <p className="mt-3 text-sm leading-6 text-white">
                    {t.alertMessage}
                  </p>
                </div>
              </RicoCardPanel>
            </div>
          </section>

          {/* Control section */}
          <section className="px-5 py-16 md:px-10 lg:px-16">
            <div className="mx-auto grid max-w-7xl gap-5 lg:grid-cols-[0.9fr_1.1fr]">
              <RicoCardPanel>
                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-cyan">
                  {t.controlEyebrow}
                </p>
                <h2 className="mt-4 text-3xl font-semibold text-white md:text-4xl">
                  {t.controlTitle}
                </h2>
                <p className="mt-5 text-base leading-7 text-text-secondary">
                  {t.controlBody}
                </p>
              </RicoCardPanel>
              <RicoCardPanel delay={0.08}>
                <div className="grid gap-4 md:grid-cols-3">
                  {noItems.map((item) => (
                    <div
                      key={item}
                      className="rounded-lg border border-white/[0.08] bg-white/[0.03] p-4"
                    >
                      <p className="text-sm font-semibold text-white">{item}</p>
                      <div className="mt-5 h-1 rounded-full bg-gradient-to-r from-magenta to-cyan" />
                    </div>
                  ))}
                </div>
              </RicoCardPanel>
            </div>
          </section>

          {/* Audience cards */}
          <section className="px-5 py-12 md:px-10 lg:px-16">
            <div className="mx-auto grid max-w-7xl gap-4 sm:grid-cols-3">
              {audienceCards.map((card, i) => (
                <motion.div
                  key={card.heading}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.55, delay: i * 0.1, ease: "easeOut" }}
                >
                  <RicoCardPanel>
                    <h3 className="text-base font-semibold text-white">{card.heading}</h3>
                    <p className="mt-3 text-sm leading-6 text-text-secondary">{card.body}</p>
                    {"ctas" in card && card.ctas && (
                      <div className="mt-4 flex gap-3">
                        {card.ctas.map((cta) => (
                          <a
                            key={cta.label}
                            href={cta.href}
                            className="text-[12px] font-medium text-magenta hover:underline"
                          >
                            {cta.label}
                          </a>
                        ))}
                      </div>
                    )}
                  </RicoCardPanel>
                </motion.div>
              ))}
            </div>
          </section>

          {/* Pricing */}
          <section className="px-5 py-16 md:px-10 lg:px-16">
            <SectionHeading
              eyebrow={t.pricingEyebrow}
              title={t.pricingTitle}
              body={t.pricingBody}
            />
            <div className="mx-auto grid max-w-5xl gap-4 md:grid-cols-2">
              <RicoCardPanel
                delay={0.08}
                className="border-magenta/30 bg-magenta/[0.03]"
              >
                <div className="mb-4 inline-flex rounded-full border border-magenta/30 bg-magenta/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-magenta">
                  {t.pricingPopular}
                </div>
                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-text-tertiary">
                  {t.pricingPro}
                </p>
                <h3 className="mt-4 text-4xl font-semibold text-white">
                  AED 29
                </h3>
                <p className="mt-2 text-sm text-text-secondary">{t.pricingPerMonth}</p>
                <ul className="mt-6 space-y-3 text-sm text-text-secondary">
                  {t.pricingProFeatures.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
                <Link
                  href="/subscription"
                  className="mt-8 inline-flex w-full items-center justify-center rounded-full bg-gradient-to-r from-magenta to-cyan px-6 py-3 text-sm font-semibold text-black transition-opacity hover:opacity-90"
                >
                  {t.upgradePro}
                </Link>
              </RicoCardPanel>
              <RicoCardPanel delay={0.16}>
                <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-text-tertiary">
                  {t.pricingPremium}
                </p>
                <h3 className="mt-4 text-4xl font-semibold text-white">
                  AED 49
                </h3>
                <p className="mt-2 text-sm text-text-secondary">{t.pricingPerMonth}</p>
                <ul className="mt-6 space-y-3 text-sm text-text-secondary">
                  {t.pricingPremiumFeatures.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
                <Link
                  href="/subscription"
                  className="mt-8 inline-flex w-full items-center justify-center rounded-full border border-white/10 bg-white/[0.04] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/[0.08]"
                >
                  {t.upgradePremium}
                </Link>
              </RicoCardPanel>
            </div>
            <div className="mx-auto mt-6 max-w-5xl">
              <div className="flex items-center justify-between rounded-xl border border-white/[0.05] bg-white/[0.03] px-5 py-4">
                <div>
                  <span className="text-[13px] font-semibold text-[#c0c0d8]">
                    {t.freePlan}
                  </span>
                  <span className="ml-3 text-[12px] text-[#5a5a7a]">
                    {t.freePlanDesc}
                  </span>
                </div>
                <Link
                  href="/signup"
                  className="text-[12px] font-semibold text-[#7b6fff] hover:underline whitespace-nowrap"
                >
                  {t.signUpFreeArrow}
                </Link>
              </div>
            </div>
          </section>

          {/* Bottom CTA */}
          <section className="px-5 pb-20 pt-10 md:px-10 lg:px-16">
            <RicoCardPanel className="mx-auto max-w-5xl text-center">
              <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-magenta">
                {t.ctaSectionEyebrow}
              </p>
              <h2 className="mx-auto mt-4 max-w-3xl text-3xl font-semibold text-white md:text-5xl">
                {t.ctaSectionTitle}
              </h2>
              <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-text-secondary">
                {t.ctaSectionBody}
              </p>
              <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
                <Link
                  href="/upload"
                  className="inline-flex items-center justify-center rounded-full bg-gradient-to-r from-magenta to-cyan px-7 py-4 text-base font-semibold text-black transition-opacity hover:opacity-90"
                >
                  {t.ctaUploadCV}
                </Link>
                <Link
                  href="/signup"
                  className="inline-flex items-center justify-center rounded-full border border-white/10 bg-white/[0.04] px-7 py-4 text-base font-semibold text-white transition-colors hover:bg-white/[0.08]"
                >
                  {t.ctaStartFree}
                </Link>
              </div>
            </RicoCardPanel>
          </section>
        </main>

        <footer className="relative z-10 border-t border-white/10 bg-black/30 px-5 py-8 text-center">
          <div className="mb-3 flex items-center justify-center gap-6">
            <Link
              href="/terms"
              className="text-xs text-text-tertiary transition-colors hover:text-white"
            >
              {t.footerTerms}
            </Link>
            <Link
              href="/privacy"
              className="text-xs text-text-tertiary transition-colors hover:text-white"
            >
              {t.footerPrivacy}
            </Link>
            <Link
              href="/refund-policy"
              className="text-xs text-text-tertiary transition-colors hover:text-white"
            >
              {t.footerRefunds}
            </Link>
          </div>
          <p className="text-xs text-text-tertiary">
            {t.footerRights}
          </p>
        </footer>
      </div>
    </MotionConfig>
  );
}
