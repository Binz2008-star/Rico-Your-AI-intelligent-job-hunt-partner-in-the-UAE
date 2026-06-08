"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import Link from "next/link";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { AuraGlow } from "@/components/ui/AuraGlow";

export function FAQContent() {
  const { language, setLanguage } = useLanguage();
  const isAr = language === "ar";

  const faqs = isAr
    ? [
        {
          question: "من أين تأتي الوظائف على ريكو هانت؟",
          answer: (
            <>
              <p>تستقطب ريكو هانت الوظائف المباشرة باستخدام <strong className="text-white">JSearch API</strong> (مدعومة من RapidAPI)، التي تجمع بيانات الوظائف في الوقت الفعلي من كبريات لوحات التوظيف النشطة في الإمارات ودول الخليج — بما فيها لينكدإن وإنديد وغلاسدور وبيت وغيرها.</p>
              <p className="mt-3">لا نملك القوائم الأساسية ولا نتحكم فيها. تُسحب بيانات الوظائف من هذه المصادر الخارجية وتُفلتر وتُرتَّب وفق سيرتك الذاتية وملفك المهني لعرض أكثر الفرص صلةً بك.</p>
            </>
          ),
        },
        {
          question: "هل يضمن ريكو حصولي على وظيفة؟",
          answer: (
            <p>لا. ريكو هانت أداة للبحث عن عمل — وليست وكالة توظيف أو مجندًا أو خدمة تعيين. نساعدك على اكتشاف الأدوار المناسبة وإدارة طلباتك وتحسين استراتيجيتك. نتيجة الحصول على مقابلة أو عرض عمل تعتمد كليًا على صاحب العمل. لا نضمن أي نتيجة توظيفية.</p>
          ),
        },
        {
          question: "هل إعلانات الوظائف موثقة ودقيقة؟",
          answer: (
            <>
              <p>تعرض ريكو هانت بيانات الوظائف المصدرة من مزودين خارجيين. نبذل قصارى جهدنا لعرض قوائم ملائمة وحديثة، لكننا لا نستطيع التحقق بشكل مستقل من دقة أو توفر أو شرعية كل إعلان.</p>
              <p className="mt-3"><strong className="text-white">يجب عليك دائمًا التحقق من تفاصيل الوظيفة مباشرةً</strong> — بما في ذلك صاحب العمل والمسمى الوظيفي والراتب والموقع ومتطلبات التأشيرة وإجراءات التقديم — قبل التقديم. ريكو هانت غير مسؤولة عن الإعلانات غير الدقيقة أو القديمة.</p>
            </>
          ),
        },
        {
          question: "هل يمكن أن يخطئ الذكاء الاصطناعي في ريكو؟",
          answer: (
            <>
              <p>نعم. يستخدم ريكو الذكاء الاصطناعي لتحليل السيرة الذاتية ومطابقة الوظائف والإرشاد المهني. قد تحتوي مخرجات الذكاء الاصطناعي على أخطاء أو إغفالات أو معلومات قديمة. درجات التطابق ومقترحات الأدوار هي تقديرات — وليست ضمانات للملاءمة.</p>
              <p className="mt-3">استخدم رؤى الذكاء الاصطناعي كمدخل واحد ضمن عوامل متعددة. راجع الأدوار دائمًا بنفسك وطبّق حكمك الشخصي قبل اتخاذ أي إجراء.</p>
            </>
          ),
        },
        {
          question: "هل سيتقدم ريكو للوظائف دون إذني؟",
          answer: (
            <p>لا. لن تُقدّم ريكو هانت أبدًا على أي وظيفة نيابةً عنك دون تأكيدك الصريح. كل إجراء تقديم يستلزم موافقتك قبل المتابعة. أنت في سيطرة كاملة في كل خطوة.</p>
          ),
        },
        {
          question: "هل ريكو هانت وكالة توظيف؟",
          answer: (
            <p>لا. ريكو هانت منصة برمجية، وليست صاحب عمل أو وكالة توظيف أو وكالة تعيين. لا نمثل أصحاب العمل ولا نتفاوض على العروض ولا نضع المرشحين في وظائف. نحن أداة تساعدك على إدارة بحثك الوظيفي بفاعلية أكبر.</p>
          ),
        },
        {
          question: "ما البيانات التي يخزنها ريكو عني؟",
          answer: (
            <>
              <p>قد يخزن ريكو تفاصيل حسابك والسيرة الذاتية المرفوعة ومحتوى السيرة الذاتية المحلل وتفضيلاتك المهنية ورسائل المحادثة ونشاطك الوظيفي. تُستخدم هذه البيانات لتخصيص تجربتك وتشغيل مطابقة الوظائف.</p>
              <p className="mt-3">لا نبيع بياناتك الشخصية لأصحاب العمل أو المجندين أو الأطراف الثالثة. يمكنك طلب حذف بياناتك في أي وقت بمراسلة{" "}<a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">info@ricohunt.com</a>. للاطلاع على التفاصيل الكاملة، راجع{" "}<Link href="/privacy" className="text-[#f5a623] hover:opacity-80">سياسة الخصوصية</Link>.</p>
            </>
          ),
        },
        {
          question: "هل ريكو هانت في مرحلة الوصول المبكر؟",
          answer: (
            <>
              <p>نعم. ريكو هانت في مرحلة التطوير النشط والوصول المبكر حاليًا. تُضاف الميزات وتُحسَّن بناءً على ملاحظات المستخدمين. قد تصادف بعض القيود أو الجوانب غير المكتملة بينما تتطور المنصة.</p>
              <p className="mt-3">إذا واجهت مشكلة أو لديك اقتراح، نودّ سماعه —{" "}<Link href="/contact" className="text-[#f5a623] hover:opacity-80">تواصل معنا</Link>{" "}أو أرسل بريداً إلى{" "}<a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">info@ricohunt.com</a>.</p>
            </>
          ),
        },
        {
          question: "من يدير ريكو هانت؟",
          answer: (
            <p>تشغّل ريكو هانت <strong className="text-white">شركة إيكو تكنولوجي لحماية البيئة ذ.م.م</strong>، وهي شركة مسجلة في الإمارات العربية المتحدة. للاستفسار أو الدعم، تواصل معنا على{" "}<a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">info@ricohunt.com</a>{" "}أو عبر{" "}<a href="https://wa.me/971585989080" className="text-[#f5a623] hover:opacity-80">واتساب</a>.</p>
          ),
        },
      ]
    : [
        {
          question: "Where do the jobs on Rico Hunt come from?",
          answer: (
            <>
              <p>Rico Hunt sources live job listings using the <strong className="text-white">JSearch API</strong> (powered by RapidAPI), which aggregates real-time job data from major job boards active in the UAE and GCC region — including LinkedIn, Indeed, Glassdoor, Bayt, and others.</p>
              <p className="mt-3">We do not own or control the underlying listings. Job data is pulled from these external sources, filtered, and scored against your CV and career profile to surface the most relevant opportunities.</p>
            </>
          ),
        },
        {
          question: "Does Rico guarantee I will get a job?",
          answer: (
            <p>No. Rico Hunt is a job search tool — not an employment agency, recruiter, or placement service. We help you discover relevant roles, manage your applications, and improve your strategy. Whether you receive an interview or a job offer depends entirely on the employer. We make no guarantee of any employment outcome.</p>
          ),
        },
        {
          question: "Are the job listings verified or accurate?",
          answer: (
            <>
              <p>Rico Hunt displays job data sourced from third-party providers. We do our best to surface relevant and timely listings, but we cannot independently verify the accuracy, current availability, or legitimacy of every posting.</p>
              <p className="mt-3"><strong className="text-white">You should always verify job details directly</strong> — including the employer, role title, salary, location, visa requirements, and application process — before applying. Rico Hunt is not liable for inaccurate or outdated listings.</p>
            </>
          ),
        },
        {
          question: "Can Rico's AI make mistakes?",
          answer: (
            <>
              <p>Yes. Rico uses AI for CV analysis, job matching, and career guidance. AI-generated outputs can contain errors, omissions, or outdated information. Match scores and role suggestions are estimates — not guarantees of fit.</p>
              <p className="mt-3">Use AI insights as one input among many. Always review roles yourself and apply your own judgment before taking action.</p>
            </>
          ),
        },
        {
          question: "Will Rico apply to jobs without my permission?",
          answer: (
            <p>No. Rico Hunt will never submit a job application on your behalf without your explicit confirmation. Every application action requires your approval before it proceeds. You remain in full control at every step.</p>
          ),
        },
        {
          question: "Is Rico Hunt a recruitment agency?",
          answer: (
            <p>No. Rico Hunt is a software platform, not an employer, staffing agency, or recruitment agency. We do not represent employers, negotiate offers, or place candidates in roles. We are a tool to help you run your own job search more effectively.</p>
          ),
        },
        {
          question: "What data does Rico store about me?",
          answer: (
            <>
              <p>Rico may store your account details, uploaded CV, parsed CV content, career preferences, chat messages, and job activity. This data is used to personalise your experience and power job matching.</p>
              <p className="mt-3">We do not sell your personal data to employers, recruiters, or third parties. You can request deletion of your data at any time by emailing{" "}<a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">info@ricohunt.com</a>. For full details, see our{" "}<Link href="/privacy" className="text-[#f5a623] hover:opacity-80">Privacy Policy</Link>.</p>
            </>
          ),
        },
        {
          question: "Is Rico Hunt in early access?",
          answer: (
            <>
              <p>Yes. Rico Hunt is currently in active development and early access. Features are being added and refined based on user feedback. You may encounter rough edges or limitations as the platform evolves.</p>
              <p className="mt-3">If you encounter a problem or have a suggestion, we want to hear from you —{" "}<Link href="/contact" className="text-[#f5a623] hover:opacity-80">contact us</Link>{" "}or email{" "}<a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">info@ricohunt.com</a>.</p>
            </>
          ),
        },
        {
          question: "Who operates Rico Hunt?",
          answer: (
            <p>Rico Hunt is operated by <strong className="text-white">Eco Technology Environment Protection Services L.L.C</strong>, a company registered in the United Arab Emirates. For questions or support, contact us at{" "}<a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">info@ricohunt.com</a>{" "}or via{" "}<a href="https://wa.me/971585989080" className="text-[#f5a623] hover:opacity-80">WhatsApp</a>.</p>
          ),
        },
      ];

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
          <Link href="/contact" className="text-sm text-text-secondary transition-colors hover:text-white">{isAr ? "تواصل" : "Contact"}</Link>
          <Link href="/terms" className="text-sm text-text-secondary transition-colors hover:text-white">{isAr ? "الشروط" : "Terms"}</Link>
          <Link href="/privacy" className="text-sm text-text-secondary transition-colors hover:text-white">{isAr ? "الخصوصية" : "Privacy"}</Link>
        </nav>
      </header>

      <main className="relative z-10 mx-auto max-w-4xl px-5 py-16 md:px-10">
        <GlassPanel className="rounded-2xl border border-white/10 p-8 md:p-12">
          <div className="mb-10">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#f5a623]">
              {isAr ? "مساعدة وشفافية" : "Help & Transparency"}
            </p>
            <h1 className="mb-4 text-3xl font-semibold text-white md:text-4xl">
              {isAr ? "الأسئلة الشائعة" : "Frequently Asked Questions"}
            </h1>
            <p className="text-base leading-7 text-text-secondary">
              {isAr
                ? "إجابات على الأسئلة الشائعة حول مصادر الوظائف وكيفية عمل ريكو وما يمكن توقعه من المنصة."
                : "Answers to common questions about where jobs come from, how Rico works, and what to expect from the platform."}
            </p>
          </div>

          <div className="space-y-6">
            {faqs.map((faq, index) => (
              <div key={index} className="rounded-xl border border-white/10 bg-white/5 p-6">
                <h2 className="mb-3 text-base font-semibold text-white">{faq.question}</h2>
                <div className="text-sm leading-7 text-text-secondary">{faq.answer}</div>
              </div>
            ))}
          </div>

          <div className="mt-10 rounded-xl border border-[#f5a623]/20 bg-[#f5a623]/5 p-6">
            <h2 className="mb-2 text-base font-semibold text-white">
              {isAr ? "لديك سؤال آخر؟" : "Still have a question?"}
            </h2>
            <p className="mb-4 text-sm text-text-secondary">
              {isAr
                ? "نقرأ كل رسالة. تواصل معنا وسنرد في أقرب وقت."
                : "We read every message. Reach out and we'll respond as soon as possible."}
            </p>
            <div className="flex flex-wrap gap-3">
              <a href="mailto:info@ricohunt.com" className="inline-flex items-center gap-1.5 rounded-lg bg-[#f5a623] px-4 py-2 text-sm font-semibold text-[#0a0a1a] transition-opacity hover:opacity-90">
                {isAr ? "راسلنا ←" : "Email us →"}
              </a>
              <Link href="/contact" className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-white transition-colors hover:bg-white/10">
                {isAr ? "صفحة التواصل" : "Contact page"}
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
          <Link href="/contact" className="text-xs text-text-tertiary transition-colors hover:text-white">{isAr ? "تواصل" : "Contact"}</Link>
          <Link href="/terms" className="text-xs text-text-tertiary transition-colors hover:text-white">{isAr ? "الشروط" : "Terms"}</Link>
          <Link href="/privacy" className="text-xs text-text-tertiary transition-colors hover:text-white">{isAr ? "الخصوصية" : "Privacy"}</Link>
          <Link href="/refund-policy" className="text-xs text-text-tertiary transition-colors hover:text-white">{isAr ? "الاسترداد" : "Refunds"}</Link>
          <span className="text-xs font-medium text-white">{isAr ? "الأسئلة الشائعة" : "FAQ"}</span>
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
