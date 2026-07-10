"use client";

/**
 * /faq — Atelier V2 light-first island.
 *
 * Migrated to the approved /design-preview paper/ink/sun-red language, matching
 * the shipped /terms and /privacy Atelier islands (shared `.atelier` + `atl-doc`
 * chrome). All FAQ copy (EN + AR) is preserved verbatim from the previous
 * version; only the presentation changed. SEO metadata lives in ./page.tsx.
 */

import { useLanguage } from "@/contexts/LanguageContext";
import Link from "next/link";
import "../_atelier/atelier-tokens.css";
import "../_atelier/atelier-support.css";

export function FAQContent() {
  const { language, setLanguage } = useLanguage();
  const isAr = language === "ar";

  const faqs = isAr
    ? [
        {
          question: "من أين تأتي الوظائف على ريكو هانت؟",
          answer: (
            <>
              <p>تستقطب ريكو هانت الوظائف المباشرة باستخدام <strong>JSearch API</strong> (مدعومة من RapidAPI)، التي تجمع بيانات الوظائف في الوقت الفعلي من كبريات لوحات التوظيف النشطة في الإمارات ودول الخليج — بما فيها لينكدإن وإنديد وغلاسدور وبيت وغيرها.</p>
              <p>لا نملك القوائم الأساسية ولا نتحكم فيها. تُسحب بيانات الوظائف من هذه المصادر الخارجية وتُفلتر وتُرتَّب وفق سيرتك الذاتية وملفك المهني لعرض أكثر الفرص صلةً بك.</p>
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
              <p><strong>يجب عليك دائمًا التحقق من تفاصيل الوظيفة مباشرةً</strong> — بما في ذلك صاحب العمل والمسمى الوظيفي والراتب والموقع ومتطلبات التأشيرة وإجراءات التقديم — قبل التقديم. ريكو هانت غير مسؤولة عن الإعلانات غير الدقيقة أو القديمة.</p>
            </>
          ),
        },
        {
          question: "هل يمكن أن يخطئ الذكاء الاصطناعي في ريكو؟",
          answer: (
            <>
              <p>نعم. يستخدم ريكو الذكاء الاصطناعي لتحليل السيرة الذاتية ومطابقة الوظائف والإرشاد المهني. قد تحتوي مخرجات الذكاء الاصطناعي على أخطاء أو إغفالات أو معلومات قديمة. درجات التطابق ومقترحات الأدوار هي تقديرات — وليست ضمانات للملاءمة.</p>
              <p>استخدم رؤى الذكاء الاصطناعي كمدخل واحد ضمن عوامل متعددة. راجع الأدوار دائمًا بنفسك وطبّق حكمك الشخصي قبل اتخاذ أي إجراء.</p>
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
              <p>لا نبيع بياناتك الشخصية لأصحاب العمل أو المجندين أو الأطراف الثالثة. يمكنك طلب حذف بياناتك في أي وقت بمراسلة{" "}<a href="mailto:info@ricohunt.com">info@ricohunt.com</a>. للاطلاع على التفاصيل الكاملة، راجع{" "}<Link href="/privacy">سياسة الخصوصية</Link>.</p>
            </>
          ),
        },
        {
          question: "هل ريكو هانت في مرحلة الوصول المبكر؟",
          answer: (
            <>
              <p>نعم. ريكو هانت في مرحلة التطوير النشط والوصول المبكر حاليًا. تُضاف الميزات وتُحسَّن بناءً على ملاحظات المستخدمين. قد تصادف بعض القيود أو الجوانب غير المكتملة بينما تتطور المنصة.</p>
              <p>إذا واجهت مشكلة أو لديك اقتراح، نودّ سماعه —{" "}<Link href="/contact">تواصل معنا</Link>{" "}أو أرسل بريداً إلى{" "}<a href="mailto:info@ricohunt.com">info@ricohunt.com</a>.</p>
            </>
          ),
        },
        {
          question: "من يدير ريكو هانت؟",
          answer: (
            <p>تشغّل ريكو هانت <strong>شركة إيكو تكنولوجي لحماية البيئة ذ.م.م</strong>، وهي شركة مسجلة في الإمارات العربية المتحدة. للاستفسار أو الدعم، تواصل معنا على{" "}<a href="mailto:info@ricohunt.com">info@ricohunt.com</a>{" "}أو عبر{" "}<a href="https://wa.me/971585989080">واتساب</a>.</p>
          ),
        },
      ]
    : [
        {
          question: "Where do the jobs on Rico Hunt come from?",
          answer: (
            <>
              <p>Rico Hunt sources live job listings using the <strong>JSearch API</strong> (powered by RapidAPI), which aggregates real-time job data from major job boards active in the UAE and GCC region — including LinkedIn, Indeed, Glassdoor, Bayt, and others.</p>
              <p>We do not own or control the underlying listings. Job data is pulled from these external sources, filtered, and scored against your CV and career profile to surface the most relevant opportunities.</p>
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
              <p><strong>You should always verify job details directly</strong> — including the employer, role title, salary, location, visa requirements, and application process — before applying. Rico Hunt is not liable for inaccurate or outdated listings.</p>
            </>
          ),
        },
        {
          question: "Can Rico's AI make mistakes?",
          answer: (
            <>
              <p>Yes. Rico uses AI for CV analysis, job matching, and career guidance. AI-generated outputs can contain errors, omissions, or outdated information. Match scores and role suggestions are estimates — not guarantees of fit.</p>
              <p>Use AI insights as one input among many. Always review roles yourself and apply your own judgment before taking action.</p>
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
              <p>We do not sell your personal data to employers, recruiters, or third parties. You can request deletion of your data at any time by emailing{" "}<a href="mailto:info@ricohunt.com">info@ricohunt.com</a>. For full details, see our{" "}<Link href="/privacy">Privacy Policy</Link>.</p>
            </>
          ),
        },
        {
          question: "Is Rico Hunt in early access?",
          answer: (
            <>
              <p>Yes. Rico Hunt is currently in active development and early access. Features are being added and refined based on user feedback. You may encounter rough edges or limitations as the platform evolves.</p>
              <p>If you encounter a problem or have a suggestion, we want to hear from you —{" "}<Link href="/contact">contact us</Link>{" "}or email{" "}<a href="mailto:info@ricohunt.com">info@ricohunt.com</a>.</p>
            </>
          ),
        },
        {
          question: "Who operates Rico Hunt?",
          answer: (
            <p>Rico Hunt is operated by <strong>Eco Technology Environment Protection Services L.L.C</strong>, a company registered in the United Arab Emirates. For questions or support, contact us at{" "}<a href="mailto:info@ricohunt.com">info@ricohunt.com</a>{" "}or via{" "}<a href="https://wa.me/971585989080">WhatsApp</a>.</p>
          ),
        },
      ];

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
          <p className="atl-doc-callout-label" style={{ marginBottom: 10 }}>
            {isAr ? "مساعدة وشفافية" : "Help & Transparency"}
          </p>
          <h1 className="atl-doc-title">
            {isAr ? "الأسئلة الشائعة" : "Frequently Asked Questions"}
          </h1>
          <p className="atl-doc-lede">
            {isAr
              ? "إجابات على الأسئلة الشائعة حول مصادر الوظائف وكيفية عمل ريكو وما يمكن توقعه من المنصة."
              : "Answers to common questions about where jobs come from, how Rico works, and what to expect from the platform."}
          </p>

          <div className="atl-faq" style={{ marginTop: 28 }}>
            {faqs.map((faq, index) => (
              <details key={index} className="atl-faq-item">
                <summary>
                  <span>{faq.question}</span>
                  <span className="atl-faq-mark" aria-hidden="true">+</span>
                </summary>
                <div className="atl-faq-answer">{faq.answer}</div>
              </details>
            ))}
          </div>

          <div className="atl-doc-callout" style={{ margin: "36px 0 0" }}>
            <p className="atl-doc-callout-label">
              {isAr ? "لديك سؤال آخر؟" : "Still have a question?"}
            </p>
            <p style={{ margin: "6px 0 0" }}>
              {isAr
                ? "نقرأ كل رسالة. راسلنا على "
                : "We read every message. Reach us at "}
              <a href="mailto:info@ricohunt.com">info@ricohunt.com</a>
              {isAr ? " أو عبر صفحة " : " or via the "}
              <Link href="/contact">{isAr ? "التواصل" : "contact page"}</Link>.
            </p>
          </div>
        </article>
      </main>

      <footer className="atl-doc-footer">
        <p className="atl-doc-footer-brand">Rico Hunt</p>
        <p>Powered by Eco Technology Environment Protection Services L.L.C</p>
        <p>{isAr ? "الإمارات العربية المتحدة" : "United Arab Emirates"}</p>
        <div className="atl-doc-footer-links">
          <Link href="/about">{isAr ? "عن ريكو" : "About"}</Link>
          <Link href="/contact">{isAr ? "تواصل" : "Contact"}</Link>
          <Link href="/terms">{isAr ? "الشروط" : "Terms"}</Link>
          <Link href="/privacy">{isAr ? "الخصوصية" : "Privacy"}</Link>
          <Link href="/refund-policy">{isAr ? "الاسترداد" : "Refunds"}</Link>
          <span className="atl-doc-current">{isAr ? "الأسئلة الشائعة" : "FAQ"}</span>
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
