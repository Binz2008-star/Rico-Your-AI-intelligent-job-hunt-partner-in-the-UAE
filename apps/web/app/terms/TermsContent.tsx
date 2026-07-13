"use client";

/**
 * /terms — Atelier V2 light-first island (PR C1 pilot).
 *
 * This page is the first visible production surface converted to the Atelier
 * design direction. It is a self-contained light-first "island" rendered UNDER
 * the otherwise dark (Nocturne) app:
 *
 *  - Visible content is wrapped in `<div className="atelier" data-atl-theme="light">`,
 *    and all styling flows through the shared, scoped `.atelier` token layer in
 *    app/_atelier/atelier-tokens.css. Nothing global is touched.
 *  - Language still comes from the existing global useLanguage() (LanguageContext);
 *    dir/lang are mirrored onto the `.atelier` wrapper so the island's RTL is
 *    self-contained. We do NOT read/write localStorage or ThemeContext here, and
 *    we do NOT change the global dark default.
 *  - All EN/AR legal copy is preserved verbatim from the previous version.
 *
 * SEO metadata lives in ./page.tsx and is unchanged.
 */

import { useLanguage } from "@/contexts/LanguageContext";
import Link from "next/link";
import "../_atelier/atelier-tokens.css";

export function TermsContent() {
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
          <Link href="/privacy" className="atl-doc-navlink">{isAr ? "الخصوصية" : "Privacy"}</Link>
          <Link href="/refund-policy" className="atl-doc-navlink">{isAr ? "الاسترداد" : "Refunds"}</Link>
        </nav>
      </header>

      <main className="atl-doc-main">
        <article className="atl-doc-panel">
          <h1 className="atl-doc-title">
            {isAr ? "شروط الخدمة" : "Terms of Service"}
          </h1>
          <p className="atl-doc-sub">
            {isAr
              ? "آخر تحديث: يونيو 2026 · تنطبق هذه الشروط على جميع مستخدمي ريكو هانت."
              : "Last updated: June 2026 · These terms apply to all users of Rico Hunt."}
          </p>

          <div className="atl-doc-body">
            <section>
              <h2>{isAr ? "١. قبول الشروط" : "1. Acceptance of Terms"}</h2>
              <p>
                {isAr
                  ? "بالوصول إلى ريكو هانت أو استخدامها، توافق على الالتزام بشروط الخدمة هذه. إذا كنت لا توافق، فلا يحق لك استخدام الخدمة. تُشكّل هذه الشروط اتفاقية ملزمة قانونيًا بينك وبين ريكو هانت، التي تشغّلها شركة إيكو تكنولوجي لحماية البيئة ذ.م.م."
                  : "By accessing or using Rico Hunt, you agree to be bound by these Terms of Service. If you do not agree, you may not use the service. These terms constitute a legally binding agreement between you and Rico Hunt, operated by Eco Technology Environment Protection Services L.L.C."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٢. وصف الخدمة" : "2. Description of Service"}</h2>
              <p>
                {isAr
                  ? "ريكو هانت منصة مهنية مدعومة بالذكاء الاصطناعي تساعد المهنيين في الإمارات ودول الخليج على اكتشاف فرص العمل وإدارة الطلبات وتحسين استراتيجية البحث عن وظيفة. تشمل الخدمة تحليل السيرة الذاتية ومطابقة الوظائف وتتبع الطلبات والإرشاد المهني المدعوم بالذكاء الاصطناعي."
                  : "Rico Hunt is an AI-powered career platform that helps professionals in the UAE and GCC discover job opportunities, manage applications, and improve their job search strategy. The service includes CV analysis, job matching, application tracking, and AI-powered career guidance."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٣. قيود الخدمة وإخلاء المسؤولية" : "3. Service Limitations and Disclaimers"}</h2>
              <p>
                {isAr ? "قبل استخدام ريكو هانت، اقرأ القيود المهمة التالية:" : "Before using Rico Hunt, please read the following important limitations:"}
              </p>
              <ul>
                <li>
                  <strong>{isAr ? "لا ضمان توظيف." : "No employment guarantee."}</strong>{" "}
                  {isAr
                    ? "لا تضمن ريكو هانت الحصول على عمل أو مقابلات أو نجاح الطلبات. استخدام المنصة لا يكفل الحصول على عرض وظيفة."
                    : "Rico Hunt does not guarantee employment, job interviews, or application success. Using the platform does not ensure you will receive a job offer."}
                </li>
                <li>
                  <strong>{isAr ? "ليست صاحب عمل أو وكالة توظيف." : "Not an employer or recruitment agency."}</strong>{" "}
                  {isAr
                    ? "ريكو هانت منصة برمجية وليست صاحب عمل أو وكالة توظيف أو تعيين. لا نمثل أصحاب العمل ولا نتفاوض نيابةً عنك ولا نضع المرشحين في وظائف."
                    : "Rico Hunt is a software platform, not an employer, staffing agency, or recruitment agency. We do not represent employers, negotiate on your behalf, or place candidates in roles."}
                </li>
                <li>
                  <strong>{isAr ? "وظائف من مصادر خارجية." : "Jobs from external sources."}</strong>{" "}
                  {isAr
                    ? "قد تأتي الوظائف المعروضة من مزودي بيانات خارجيين ومصادر عامة. لا نتحقق بشكل مستقل من جميع القوائم. دقة الوظيفة وتوفرها وشرعيتها هي مسؤولية صاحب العمل الناشر."
                    : "Job listings shown on Rico Hunt may come from external job data providers and public job sources. We do not independently verify all listings. Job availability, accuracy, and legitimacy are the responsibility of the posting employer."}
                </li>
                <li>
                  <strong>{isAr ? "التحقق قبل التقديم." : "Verify before applying."}</strong>{" "}
                  {isAr
                    ? "يجب عليك التحقق بشكل مستقل من جميع تفاصيل الوظيفة — بما في ذلك صاحب العمل والدور والراتب والموقع ومتطلبات التقديم — قبل التقديم. ريكو هانت غير مسؤولة عن الإعلانات غير الدقيقة أو القديمة."
                    : "You must independently verify all job details — including the employer, role, salary, location, and application requirements — before applying. Rico Hunt is not liable for inaccurate or outdated job listings."}
                </li>
                <li>
                  <strong>{isAr ? "قد تكون مخرجات الذكاء الاصطناعي غير دقيقة." : "AI outputs may be inaccurate."}</strong>{" "}
                  {isAr
                    ? "يستخدم ريكو محتوى مولّداً بالذكاء الاصطناعي لتحليل السيرة الذاتية ومطابقة الوظائف والإرشاد المهني. قد تحتوي هذه المخرجات على أخطاء أو إغفالات أو معلومات قديمة. لا تعتمد كليًا على المحتوى المولّد بالذكاء الاصطناعي في قراراتك المهنية."
                    : "Rico uses AI-generated content for CV analysis, job matching, and career guidance. AI outputs can contain errors, omissions, or outdated information. Do not rely solely on AI-generated content for career decisions."}
                </li>
                <li>
                  <strong>{isAr ? "موافقتك مطلوبة قبل التقديم." : "Your approval is required before applications."}</strong>{" "}
                  {isAr
                    ? "لن تُقدّم ريكو هانت على أي وظيفة نيابةً عنك دون تأكيدك الصريح. أنت في سيطرة كاملة على جميع إجراءات التقديم."
                    : "Rico Hunt will not submit a job application on your behalf without your explicit confirmation. You remain in full control of all application actions."}
                </li>
              </ul>
            </section>

            <section>
              <h2>{isAr ? "٤. حسابات المستخدمين" : "4. User Accounts"}</h2>
              <p>
                {isAr
                  ? "يجب عليك تقديم معلومات دقيقة عند إنشاء حساب. أنت مسؤول عن الحفاظ على أمان بيانات اعتماد حسابك. أخطرنا فوراً بأي وصول غير مصرح به. نحتفظ بالحق في تعليق الحسابات التي تنتهك هذه الشروط."
                  : "You must provide accurate information when creating an account. You are responsible for maintaining the security of your account credentials. Notify us immediately of any unauthorized access. We reserve the right to suspend accounts that violate these terms."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٥. الاشتراك والمدفوعات" : "5. Subscription and Payments"}</h2>
              <p>
                {isAr
                  ? "تتطلب بعض الميزات اشتراكاً مدفوعاً. تُعالج المدفوعات عبر Paddle. تتجدد الاشتراكات تلقائياً ما لم يتم إلغاؤها. يمكنك الإلغاء في أي وقت عبر بوابة إدارة الاشتراكات. لا استرداد للأشهر الجزئية ما لم يقتضِ ذلك القانون."
                  : "Some features require a paid subscription. Payments are processed through Paddle. Subscriptions auto-renew unless cancelled. You may cancel at any time through the subscription management portal. No refunds for partial months unless required by law."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٦. محتوى المستخدم" : "6. User Content"}</h2>
              <p>
                {isAr
                  ? "تحتفظ بملكية سيرتك الذاتية وبيانات ملفك الشخصي. بتحميل المحتوى، تمنح ريكو هانت ترخيصاً لمعالجته بغرض تقديم الخدمة. لا نبيع بياناتك لأطراف ثالثة. يمكنك طلب حذف حسابك وبياناتك في أي وقت بمراسلة info@ricohunt.com."
                  : "You retain ownership of your CV and profile data. By uploading content, you grant Rico Hunt a license to process it for the purpose of providing the service. We do not sell your data to third parties. You may request deletion of your account and data at any time by contacting info@ricohunt.com."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٧. الأنشطة المحظورة" : "7. Prohibited Activities"}</h2>
              <p>
                {isAr
                  ? "لا يجوز لك: (أ) استخدام الخدمة لأغراض غير مشروعة؛ (ب) محاولة الوصول إلى الأنظمة أو البيانات دون تصريح؛ (ج) التدخل في وصول المستخدمين الآخرين؛ (د) تحميل رمز خبيث؛ (هـ) إعادة بيع الخدمة أو توزيعها دون إذن؛ (و) تزوير هويتك أو مؤهلاتك."
                  : "You may not: (a) use the service for illegal purposes; (b) attempt to access systems or data without authorization; (c) interfere with other users' access; (d) upload malicious code; (e) resell or redistribute the service without permission; (f) misrepresent your identity or qualifications."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٨. تحديد المسؤولية" : "8. Limitation of Liability"}</h2>
              <p>
                {isAr
                  ? "تقدم ريكو هانت الخدمة \"كما هي\" دون ضمانات من أي نوع. إلى أقصى حد تسمح به القوانين المعمول بها، لا نتحمل المسؤولية عن:"
                  : "Rico Hunt provides the service \"as is\" without warranties of any kind. To the fullest extent permitted by law, we are not liable for:"}
              </p>
              <ul>
                <li>{isAr ? "نتائج طلبات التوظيف أو قرارات التوظيف التي يتخذها أصحاب العمل" : "Job application outcomes or employment decisions made by employers"}</li>
                <li>{isAr ? "دقة قوائم الوظائف الخارجية أو اكتمالها أو توفرها" : "Accuracy, completeness, or availability of third-party job listings"}</li>
                <li>{isAr ? "الأخطاء أو الإغفالات أو عدم الدقة في المحتوى المولّد بالذكاء الاصطناعي" : "Errors, omissions, or inaccuracies in AI-generated content"}</li>
                <li>{isAr ? "انقطاع الخدمة أو فقدان البيانات أو الأعطال التقنية" : "Service interruptions, data loss, or technical failures"}</li>
                <li>{isAr ? "أي اعتماد على قوائم الوظائف دون التحقق منها بشكل مستقل" : "Any reliance placed on job listings without independent verification"}</li>
              </ul>
              <p>
                {isAr
                  ? "تقتصر مسؤوليتنا الإجمالية تجاهك على المبالغ التي دفعتها لريكو هانت خلال 12 شهراً قبل المطالبة."
                  : "Our total liability to you is limited to amounts you have paid to Rico Hunt in the 12 months preceding the claim."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٩. القانون الحاكم" : "9. Governing Law"}</h2>
              <p>
                {isAr
                  ? "تخضع هذه الشروط لقوانين الإمارات العربية المتحدة. تُحسم أي نزاعات أمام محاكم الإمارات العربية المتحدة. إذا كنت مستهلكاً في الاتحاد الأوروبي، فقد تنطبق قوانين حماية المستهلك الإلزامية في بلد إقامتك."
                  : "These terms are governed by the laws of the United Arab Emirates. Any disputes shall be resolved in the courts of the United Arab Emirates. If you are a consumer in the EU, mandatory consumer protection laws of your country of residence may apply."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "١٠. التغييرات على الشروط" : "10. Changes to Terms"}</h2>
              <p>
                {isAr
                  ? "قد نحدّث هذه الشروط من وقت لآخر. سيُبلَّغ عن التغييرات الجوهرية عبر البريد الإلكتروني أو من خلال الخدمة. استمرار استخدامها بعد التغييرات يُعدّ قبولاً لها."
                  : "We may update these terms from time to time. Material changes will be notified via email or through the service. Continued use after changes constitutes acceptance."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "١١. التواصل" : "11. Contact"}</h2>
              <p>{isAr ? "للاستفسارات حول هذه الشروط، تواصل معنا:" : "For questions about these terms, contact us:"}</p>
              <ul className="atl-doc-plain">
                <li><strong>{isAr ? "الشركة:" : "Company:"}</strong> {isAr ? "شركة إيكو تكنولوجي لحماية البيئة ذ.م.م" : "Eco Technology Environment Protection Services L.L.C"}</li>
                <li><strong>{isAr ? "الموقع:" : "Location:"}</strong> {isAr ? "الإمارات العربية المتحدة" : "United Arab Emirates"}</li>
                <li>
                  <strong>{isAr ? "البريد الإلكتروني:" : "Email:"}</strong>{" "}
                  <a href="mailto:info@ricohunt.com">info@ricohunt.com</a>
                </li>
                <li>
                  <strong>{isAr ? "الهاتف / واتساب:" : "Phone / WhatsApp:"}</strong>{" "}
                  <a href="https://wa.me/971585989080">+971 58 598 9080</a>
                </li>
                <li>
                  <strong>{isAr ? "لينكدإن الشركة:" : "LinkedIn:"}</strong>{" "}
                  <a href="https://www.linkedin.com/company/eco-technology-environment-protection-services-l-l-c/" target="_blank" rel="noopener noreferrer">
                    {isAr ? "لينكدإن الشركة" : "Company LinkedIn"}
                  </a>
                </li>
              </ul>
            </section>
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
          <span className="atl-doc-current">{isAr ? "الشروط" : "Terms"}</span>
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
