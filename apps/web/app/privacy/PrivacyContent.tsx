"use client";

/**
 * /privacy — Atelier V2 light-first island (C2).
 *
 * Converted from the previous dark (Nocturne) GlassPanel/AuraGlow layout to the
 * shared Atelier "document island" primitives, matching the /terms pilot. It is a
 * self-contained light-first island rendered UNDER the otherwise dark app:
 *
 *  - Visible content is wrapped in `<div className="atelier atl-doc" data-atl-theme="light">`,
 *    and all styling flows through the shared, scoped `.atelier` token layer in
 *    app/_atelier/atelier-tokens.css. Nothing global is touched.
 *  - Language still comes from the existing global useLanguage() (LanguageContext);
 *    dir/lang are mirrored onto the `.atelier` wrapper so the island's RTL is
 *    self-contained. We do NOT read/write localStorage or ThemeContext here.
 *  - All EN/AR legal copy is preserved verbatim from the previous version.
 *
 * SEO metadata lives in ./page.tsx and is unchanged.
 */

import { useLanguage } from "@/contexts/LanguageContext";
import Link from "next/link";
import "../_atelier/atelier-tokens.css";

export function PrivacyContent() {
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
          <Link href="/refund-policy" className="atl-doc-navlink">{isAr ? "الاسترداد" : "Refunds"}</Link>
        </nav>
      </header>

      <main className="atl-doc-main">
        <article className="atl-doc-panel">
          <h1 className="atl-doc-title">
            {isAr ? "سياسة الخصوصية" : "Privacy Policy"}
          </h1>
          <p className="atl-doc-sub">
            {isAr
              ? "آخر تحديث: يونيو 2026 · نلتزم بحماية بياناتك الشخصية."
              : "Last updated: June 2026 · We are committed to protecting your personal data."}
          </p>

          <div className="atl-doc-body">
            <section>
              <h2>{isAr ? "المتحكم في البيانات" : "Data Controller"}</h2>
              <ul className="atl-doc-plain">
                <li><strong>{isAr ? "الشركة:" : "Company:"}</strong> {isAr ? "شركة إيكو تكنولوجي لحماية البيئة ذ.م.م" : "Eco Technology Environment Protection Services L.L.C"}</li>
                <li><strong>{isAr ? "الموقع:" : "Location:"}</strong> {isAr ? "الإمارات العربية المتحدة" : "United Arab Emirates"}</li>
              </ul>
              <p>
                {isAr ? "لطلبات الخصوصية أو حذف البيانات:" : "For privacy requests or data deletion:"}{" "}
                <a href="mailto:info@ricohunt.com">info@ricohunt.com</a>
                {" · "}
                <a href="https://wa.me/971585989080">+971 58 598 9080</a>
              </p>
            </section>

            <section>
              <h2>{isAr ? "١. البيانات التي نجمعها" : "1. Data We Collect"}</h2>
              <p>{isAr ? "نجمع المعلومات التالية عند استخدامك ريكو هانت:" : "We collect the following information when you use Rico Hunt:"}</p>
              <ul>
                <li><strong>{isAr ? "البيانات الحسابية:" : "Account data:"}</strong> {isAr ? "الاسم وعنوان البريد الإلكتروني وبيانات اعتماد المصادقة." : "Name, email address, and authentication credentials."}</li>
                <li><strong>{isAr ? "بيانات التواصل:" : "Contact data:"}</strong> {isAr ? "رقم الهاتف أو واتساب إن وُجد." : "Phone number or WhatsApp number, if provided."}</li>
                <li><strong>{isAr ? "ملفات السيرة الذاتية:" : "CV and resume files:"}</strong> {isAr ? "المستندات المرفوعة بأي صيغة." : "Uploaded documents in any format."}</li>
                <li><strong>{isAr ? "محتوى السيرة الذاتية المستخرج:" : "Extracted CV content:"}</strong> {isAr ? "النص والمهارات وخبرة العمل والتعليم وغيرها من المعلومات المستخرجة من سيرتك الذاتية." : "Text, skills, work experience, education, and other information parsed from your CV."}</li>
                <li><strong>{isAr ? "التفضيلات المهنية:" : "Career preferences:"}</strong> {isAr ? "الأدوار المستهدفة والقطاعات المفضلة وتوقعات الراتب وتفضيلات الموقع." : "Target roles, preferred sectors, salary expectations, and location preferences."}</li>
                <li><strong>{isAr ? "رسائل المحادثة:" : "Chat messages:"}</strong> {isAr ? "الرسائل التي ترسلها إلى ريكو والردود التي تتلقاها." : "Messages you send to Rico and the responses you receive."}</li>
                <li><strong>{isAr ? "نشاط الوظائف:" : "Job activity:"}</strong> {isAr ? "الوظائف التي تحفظها أو تعرضها أو تتقدم إليها أو تحددها بأي طريقة." : "Jobs you save, view, apply for, or mark in any way."}</li>
                <li><strong>{isAr ? "بيانات الطلبات:" : "Application data:"}</strong> {isAr ? "الحالة والملاحظات الخاصة بطلبات التوظيف التي تتابعها عبر المنصة." : "Status and notes for job applications you track through the platform."}</li>
                <li><strong>{isAr ? "البيانات التقنية:" : "Technical data:"}</strong> {isAr ? "عنوان IP ونوع المتصفح ومعلومات الجهاز وملفات تعريف الجلسة." : "IP address, browser type, device information, and session cookies."}</li>
              </ul>
            </section>

            <section>
              <h2>{isAr ? "٢. كيف نستخدم بياناتك" : "2. How We Use Your Data"}</h2>
              <ul>
                <li>{isAr ? "إنشاء حسابك وملفك المهني والحفاظ عليهما" : "To create and maintain your account and career profile"}</li>
                <li>{isAr ? "تحليل سيرتك الذاتية واقتراح الأدوار الملائمة" : "To analyze your CV and suggest relevant job roles"}</li>
                <li>{isAr ? "البحث في قوائم الوظائف وفلترتها وتقييمها بناءً على ملفك" : "To search, filter, and score job listings based on your profile"}</li>
                <li>{isAr ? "تقديم إرشاد مهني مدعوم بالذكاء الاصطناعي ورؤى مطابقة الوظائف" : "To provide AI-powered career guidance and job-match insights"}</li>
                <li>{isAr ? "تتبع طلبات التوظيف وإدارتها" : "To track and manage your job applications"}</li>
                <li>{isAr ? "إرسال إشعارات حول الفرص ذات الصلة" : "To send notifications about relevant opportunities"}</li>
                <li>{isAr ? "معالجة المدفوعات وإدارة الاشتراكات" : "To process payments and manage subscriptions"}</li>
                <li>{isAr ? "تحسين جودة المنصة وإصلاح المشكلات" : "To improve platform quality and fix issues"}</li>
                <li>{isAr ? "الامتثال للالتزامات القانونية ومنع إساءة الاستخدام" : "To comply with legal obligations and prevent misuse"}</li>
              </ul>
            </section>

            <section>
              <h2>{isAr ? "٣. تخزين السيرة الذاتية وتحليل الذكاء الاصطناعي" : "3. CV Storage and AI Analysis"}</h2>
              <p>
                {isAr
                  ? "قد يخزن ريكو ملف سيرتك الذاتية المرفوع و/أو النص المستخرج منها. تُستخدم هذه البيانات لبناء ملفك المهني وتشغيل مطابقة الوظائف."
                  : "Rico may store your uploaded CV file and/or the text extracted from it. This data is used to build your career profile and power job matching."}
              </p>
              <p>
                {isAr
                  ? "قد يستخدم ريكو أدوات الذكاء الاصطناعي لتحليل السير الذاتية واستخراج المهارات والخبرات واقتراح الأدوار المستهدفة وتقديم رؤى مطابقة الوظائف. قد تُرسل سيرتك الذاتية وبيانات ملفك إلى مزودي خدمات الذكاء الاصطناعي لتوليد هذه النتائج. لا نستخدم بياناتك الشخصية لتدريب نماذج ذكاء اصطناعي عامة."
                  : "Rico may use AI tools to analyze CVs, extract skills and experience, suggest target roles, and provide job-match insights. Your CV and profile data may be sent to AI service providers to generate these results. We do not use your personal data to train public AI models."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٤. مزودو الخدمات من أطراف ثالثة" : "4. Third-Party Providers"}</h2>
              <p>
                {isAr ? "قد يستخدم ريكو مزودي خدمات موثوقين من أطراف ثالثة لتقديم الخدمة، منهم:" : "Rico may use trusted third-party providers to deliver the service, including:"}
              </p>
              <ul>
                <li><strong>{isAr ? "استضافة سحابية وبنية تحتية" : "Cloud hosting and infrastructure"}</strong> — {isAr ? "لتشغيل المنصة" : "for running the platform"}</li>
                <li><strong>{isAr ? "مزودو قواعد البيانات" : "Database providers"}</strong> — {isAr ? "لتخزين بيانات حسابك وملفك" : "for storing your account and profile data"}</li>
                <li><strong>{isAr ? "مزودو المصادقة" : "Authentication providers"}</strong> — {isAr ? "لتسجيل الدخول الآمن" : "for secure login"}</li>
                <li><strong>{isAr ? "مزودو خدمات الذكاء الاصطناعي" : "AI service providers"}</strong> — {isAr ? "لتحليل السيرة الذاتية ومطابقة الوظائف والمحادثة" : "for CV analysis, job matching, and chat"}</li>
                <li><strong>{isAr ? "مزودو التحليلات" : "Analytics providers"}</strong> — {isAr ? "لفهم استخدام المنصة" : "for understanding platform usage"}</li>
                <li><strong>{isAr ? "مزودو البريد الإلكتروني والرسائل" : "Email and messaging providers"}</strong> — {isAr ? "للإشعارات والدعم" : "for notifications and support"}</li>
                <li><strong>{isAr ? "معالجو المدفوعات" : "Payment processors"}</strong> — {isAr ? "لفواتير الاشتراك" : "for subscription billing"}</li>
                <li><strong>{isAr ? "مزودو بيانات الوظائف" : "Job data providers"}</strong> — {isAr ? "لاستقطاب قوائم الوظائف المباشرة" : "for sourcing live job listings"}</li>
              </ul>
              <p>
                {isAr
                  ? "لا نشارك سوى الحد الأدنى من البيانات الضرورية لكل مزود للقيام بوظيفته. لا نبيع معلوماتك الشخصية لأي طرف ثالث."
                  : "We share only the minimum data necessary for each provider to perform their function. We do not sell your personal information to any third party."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٥. إخلاء مسؤولية مصادر الوظائف" : "5. Job Source Disclaimer"}</h2>
              <p>
                {isAr
                  ? "قد تأتي الوظائف المعروضة على ريكو هانت من مزودي بيانات وظائف خارجيين ومصادر عامة. نبذل قصارى جهدنا لعرض قوائم ملائمة ودقيقة، لكننا لا نضمن دقة أي إعلان وظيفي أو توفره أو شرعيته. يجب عليك التحقق من جميع تفاصيل الوظيفة — بما في ذلك صاحب العمل والدور والشروط — قبل التقديم."
                  : "Jobs shown on Rico Hunt may come from external job data providers and public job sources. We do our best to surface relevant and accurate listings, but we cannot guarantee the accuracy, availability, or legitimacy of any individual job posting. You should verify all job details — including the employer, role, and terms — before applying."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٦. لا نبيع بياناتك" : "6. We Do Not Sell Your Data"}</h2>
              <p>
                {isAr
                  ? "لا يبيع ريكو معلوماتك الشخصية ولا يؤجرها ولا يتاجر بها مع المعلنين أو المجندين أو أصحاب العمل أو أي أطراف ثالثة أخرى لأغراض تجارية."
                  : "Rico does not sell, rent, or trade your personal information to advertisers, recruiters, employers, or any other third parties for commercial purposes."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٧. حذف البيانات" : "7. Data Deletion"}</h2>
              <p>
                {isAr ? (
                  <>يمكنك طلب حذف حسابك وبياناتك الشخصية في أي وقت بمراسلة{" "}<a href="mailto:info@ricohunt.com">info@ricohunt.com</a>{" "}من عنوان بريدك الإلكتروني المسجل. سنعالج طلبك ونؤكد الحذف خلال فترة زمنية معقولة.</>
                ) : (
                  <>You can request deletion of your account and personal data at any time by emailing{" "}<a href="mailto:info@ricohunt.com">info@ricohunt.com</a>{" "}from your registered account email address. We will process your request and confirm deletion within a reasonable timeframe.</>
                )}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٨. الاحتفاظ بالبيانات" : "8. Data Retention"}</h2>
              <p>
                {isAr
                  ? "نحتفظ ببياناتك طالما حسابك نشطاً وحسب الحاجة لتقديم الخدمة. قد تُحتفظ البيانات أيضاً للامتثال القانوني وأمن المنصة ومنع إساءة الاستخدام ولأسباب تشغيلية مشروعة، حتى بعد حذف الحساب. تُحتفظ السجلات المالية وفقاً لما يقتضيه القانون المعمول به."
                  : "We retain your data while your account is active and as needed to provide the service. Data may also be retained for legal compliance, security, abuse prevention, and legitimate operational reasons, even after an account is deleted. Financial records are retained as required by applicable law."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "٩. الأمان" : "9. Security"}</h2>
              <p>
                {isAr
                  ? "نطبّق تدابير تقنية وتنظيمية معقولة لحماية بياناتك، بما في ذلك التشفير أثناء النقل (TLS) وضوابط الوصول. غير أن أي خدمة إلكترونية لا تستطيع ضمان الأمان الكامل. أنت مسؤول عن الحفاظ على أمان بيانات اعتماد حسابك."
                  : "We implement reasonable technical and organizational measures to protect your data, including encryption in transit (TLS) and access controls. However, no online service can guarantee complete security. You are responsible for keeping your account credentials safe."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "١٠. ملفات تعريف الارتباط" : "10. Cookies"}</h2>
              <p>
                {isAr
                  ? "نستخدم ملفات تعريف الارتباط والتقنيات المشابهة للمصادقة وإدارة الجلسات والتحليلات الأساسية. يمكنك تعطيل ملفات تعريف الارتباط في إعدادات متصفحك، وإن كان ذلك قد يؤثر على وظائف المنصة."
                  : "We use cookies and similar technologies for authentication, session management, and basic analytics. You may disable cookies in your browser settings, though this may affect the functionality of the platform."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "١١. حقوقك" : "11. Your Rights"}</h2>
              <p>{isAr ? "وفقاً لولايتك القضائية، قد يحق لك:" : "Depending on your jurisdiction, you may have the right to:"}</p>
              <ul>
                <li>{isAr ? "الاطلاع على نسخة من بياناتك الشخصية" : "Access a copy of your personal data"}</li>
                <li>{isAr ? "تصحيح البيانات غير الدقيقة أو غير المكتملة" : "Correct inaccurate or incomplete data"}</li>
                <li>{isAr ? "طلب حذف حسابك وبياناتك" : "Request deletion of your account and data"}</li>
                <li>{isAr ? "الاعتراض على معالجة معينة أو تقييدها" : "Object to or restrict certain processing"}</li>
                <li>{isAr ? "تصدير بياناتك بصيغة قابلة للنقل" : "Export your data in a portable format"}</li>
              </ul>
              <p>
                {isAr ? (
                  <>لممارسة أي من هذه الحقوق، تواصل معنا على{" "}<a href="mailto:info@ricohunt.com">info@ricohunt.com</a>.</>
                ) : (
                  <>To exercise any of these rights, contact us at{" "}<a href="mailto:info@ricohunt.com">info@ricohunt.com</a>.</>
                )}
              </p>
            </section>

            <section>
              <h2>{isAr ? "١٢. التغييرات على هذه السياسة" : "12. Changes to This Policy"}</h2>
              <p>
                {isAr
                  ? "قد نحدّث سياسة الخصوصية هذه من وقت لآخر. سيُبلَّغ عن التغييرات الجوهرية عبر البريد الإلكتروني أو إشعار داخل المنصة. استمرار استخدامك لريكو هانت بعد التغييرات يُعدّ قبولاً للسياسة المحدّثة."
                  : "We may update this Privacy Policy from time to time. Material changes will be communicated via email or a notice within the platform. Continued use of Rico Hunt after changes constitutes acceptance of the updated policy."}
              </p>
            </section>

            <section>
              <h2>{isAr ? "١٣. التواصل" : "13. Contact"}</h2>
              <p>{isAr ? "للاستفسارات المتعلقة بالخصوصية أو لممارسة حقوقك:" : "For privacy-related questions or to exercise your rights:"}</p>
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
          <Link href="/terms">{isAr ? "الشروط" : "Terms"}</Link>
          <span className="atl-doc-current">{isAr ? "الخصوصية" : "Privacy"}</span>
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
