"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import Link from "next/link";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { AuraGlow } from "@/components/ui/AuraGlow";

export function TermsContent() {
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
          <Link href="/contact" className="text-sm text-text-secondary transition-colors hover:text-white">{isAr ? "تواصل" : "Contact"}</Link>
          <Link href="/privacy" className="text-sm text-text-secondary transition-colors hover:text-white">{isAr ? "الخصوصية" : "Privacy"}</Link>
          <Link href="/refund-policy" className="text-sm text-text-secondary transition-colors hover:text-white">{isAr ? "الاسترداد" : "Refunds"}</Link>
        </nav>
      </header>

      <main className="relative z-10 mx-auto max-w-4xl px-5 py-16 md:px-10">
        <GlassPanel className="rounded-2xl border border-white/10 p-8 md:p-12">
          <h1 className="mb-2 text-3xl font-semibold text-white md:text-4xl">
            {isAr ? "شروط الخدمة" : "Terms of Service"}
          </h1>
          <p className="mb-8 text-sm text-text-secondary">
            {isAr
              ? "آخر تحديث: يونيو 2026 · تنطبق هذه الشروط على جميع مستخدمي ريكو هانت."
              : "Last updated: June 2026 · These terms apply to all users of Rico Hunt."}
          </p>

          <div className="space-y-8 text-sm leading-7 text-text-secondary">
            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "١. قبول الشروط" : "1. Acceptance of Terms"}
              </h2>
              <p>
                {isAr
                  ? "بالوصول إلى ريكو هانت أو استخدامها، توافق على الالتزام بشروط الخدمة هذه. إذا كنت لا توافق، فلا يحق لك استخدام الخدمة. تُشكّل هذه الشروط اتفاقية ملزمة قانونيًا بينك وبين ريكو هانت، التي تشغّلها شركة إيكو تكنولوجي لحماية البيئة ذ.م.م."
                  : "By accessing or using Rico Hunt, you agree to be bound by these Terms of Service. If you do not agree, you may not use the service. These terms constitute a legally binding agreement between you and Rico Hunt, operated by Eco Technology Environment Protection Services L.L.C."}
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "٢. وصف الخدمة" : "2. Description of Service"}
              </h2>
              <p>
                {isAr
                  ? "ريكو هانت منصة مهنية مدعومة بالذكاء الاصطناعي تساعد المهنيين في الإمارات ودول الخليج على اكتشاف فرص العمل وإدارة الطلبات وتحسين استراتيجية البحث عن وظيفة. تشمل الخدمة تحليل السيرة الذاتية ومطابقة الوظائف وتتبع الطلبات والإرشاد المهني المدعوم بالذكاء الاصطناعي."
                  : "Rico Hunt is an AI-powered career platform that helps professionals in the UAE and GCC discover job opportunities, manage applications, and improve their job search strategy. The service includes CV analysis, job matching, application tracking, and AI-powered career guidance."}
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "٣. قيود الخدمة وإخلاء المسؤولية" : "3. Service Limitations and Disclaimers"}
              </h2>
              <p className="mb-3">
                {isAr ? "قبل استخدام ريكو هانت، اقرأ القيود المهمة التالية:" : "Before using Rico Hunt, please read the following important limitations:"}
              </p>
              <ul className="ml-4 list-disc space-y-3">
                <li>
                  <strong className="text-white">{isAr ? "لا ضمان توظيف." : "No employment guarantee."}</strong>{" "}
                  {isAr
                    ? "لا تضمن ريكو هانت الحصول على عمل أو مقابلات أو نجاح الطلبات. استخدام المنصة لا يكفل الحصول على عرض وظيفة."
                    : "Rico Hunt does not guarantee employment, job interviews, or application success. Using the platform does not ensure you will receive a job offer."}
                </li>
                <li>
                  <strong className="text-white">{isAr ? "ليست صاحب عمل أو وكالة توظيف." : "Not an employer or recruitment agency."}</strong>{" "}
                  {isAr
                    ? "ريكو هانت منصة برمجية وليست صاحب عمل أو وكالة توظيف أو تعيين. لا نمثل أصحاب العمل ولا نتفاوض نيابةً عنك ولا نضع المرشحين في وظائف."
                    : "Rico Hunt is a software platform, not an employer, staffing agency, or recruitment agency. We do not represent employers, negotiate on your behalf, or place candidates in roles."}
                </li>
                <li>
                  <strong className="text-white">{isAr ? "وظائف من مصادر خارجية." : "Jobs from external sources."}</strong>{" "}
                  {isAr
                    ? "قد تأتي الوظائف المعروضة من مزودي بيانات خارجيين ومصادر عامة. لا نتحقق بشكل مستقل من جميع القوائم. دقة الوظيفة وتوفرها وشرعيتها هي مسؤولية صاحب العمل الناشر."
                    : "Job listings shown on Rico Hunt may come from external job data providers and public job sources. We do not independently verify all listings. Job availability, accuracy, and legitimacy are the responsibility of the posting employer."}
                </li>
                <li>
                  <strong className="text-white">{isAr ? "التحقق قبل التقديم." : "Verify before applying."}</strong>{" "}
                  {isAr
                    ? "يجب عليك التحقق بشكل مستقل من جميع تفاصيل الوظيفة — بما في ذلك صاحب العمل والدور والراتب والموقع ومتطلبات التقديم — قبل التقديم. ريكو هانت غير مسؤولة عن الإعلانات غير الدقيقة أو القديمة."
                    : "You must independently verify all job details — including the employer, role, salary, location, and application requirements — before applying. Rico Hunt is not liable for inaccurate or outdated job listings."}
                </li>
                <li>
                  <strong className="text-white">{isAr ? "قد تكون مخرجات الذكاء الاصطناعي غير دقيقة." : "AI outputs may be inaccurate."}</strong>{" "}
                  {isAr
                    ? "يستخدم ريكو محتوى مولّداً بالذكاء الاصطناعي لتحليل السيرة الذاتية ومطابقة الوظائف والإرشاد المهني. قد تحتوي هذه المخرجات على أخطاء أو إغفالات أو معلومات قديمة. لا تعتمد كليًا على المحتوى المولّد بالذكاء الاصطناعي في قراراتك المهنية."
                    : "Rico uses AI-generated content for CV analysis, job matching, and career guidance. AI outputs can contain errors, omissions, or outdated information. Do not rely solely on AI-generated content for career decisions."}
                </li>
                <li>
                  <strong className="text-white">{isAr ? "موافقتك مطلوبة قبل التقديم." : "Your approval is required before applications."}</strong>{" "}
                  {isAr
                    ? "لن تُقدّم ريكو هانت على أي وظيفة نيابةً عنك دون تأكيدك الصريح. أنت في سيطرة كاملة على جميع إجراءات التقديم."
                    : "Rico Hunt will not submit a job application on your behalf without your explicit confirmation. You remain in full control of all application actions."}
                </li>
              </ul>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "٤. حسابات المستخدمين" : "4. User Accounts"}
              </h2>
              <p>
                {isAr
                  ? "يجب عليك تقديم معلومات دقيقة عند إنشاء حساب. أنت مسؤول عن الحفاظ على أمان بيانات اعتماد حسابك. أخطرنا فوراً بأي وصول غير مصرح به. نحتفظ بالحق في تعليق الحسابات التي تنتهك هذه الشروط."
                  : "You must provide accurate information when creating an account. You are responsible for maintaining the security of your account credentials. Notify us immediately of any unauthorized access. We reserve the right to suspend accounts that violate these terms."}
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "٥. الاشتراك والمدفوعات" : "5. Subscription and Payments"}
              </h2>
              <p>
                {isAr
                  ? "تتطلب بعض الميزات اشتراكاً مدفوعاً. تُعالج المدفوعات عبر Stripe. تتجدد الاشتراكات تلقائياً ما لم يتم إلغاؤها. يمكنك الإلغاء في أي وقت عبر بوابة إدارة الاشتراكات. لا استرداد للأشهر الجزئية ما لم يقتضِ ذلك القانون."
                  : "Some features require a paid subscription. Payments are processed through Stripe. Subscriptions auto-renew unless cancelled. You may cancel at any time through the subscription management portal. No refunds for partial months unless required by law."}
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "٦. محتوى المستخدم" : "6. User Content"}
              </h2>
              <p>
                {isAr
                  ? "تحتفظ بملكية سيرتك الذاتية وبيانات ملفك الشخصي. بتحميل المحتوى، تمنح ريكو هانت ترخيصاً لمعالجته بغرض تقديم الخدمة. لا نبيع بياناتك لأطراف ثالثة. يمكنك طلب حذف حسابك وبياناتك في أي وقت بمراسلة info@ricohunt.com."
                  : "You retain ownership of your CV and profile data. By uploading content, you grant Rico Hunt a license to process it for the purpose of providing the service. We do not sell your data to third parties. You may request deletion of your account and data at any time by contacting info@ricohunt.com."}
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "٧. الأنشطة المحظورة" : "7. Prohibited Activities"}
              </h2>
              <p>
                {isAr
                  ? "لا يجوز لك: (أ) استخدام الخدمة لأغراض غير مشروعة؛ (ب) محاولة الوصول إلى الأنظمة أو البيانات دون تصريح؛ (ج) التدخل في وصول المستخدمين الآخرين؛ (د) تحميل رمز خبيث؛ (هـ) إعادة بيع الخدمة أو توزيعها دون إذن؛ (و) تزوير هويتك أو مؤهلاتك."
                  : "You may not: (a) use the service for illegal purposes; (b) attempt to access systems or data without authorization; (c) interfere with other users' access; (d) upload malicious code; (e) resell or redistribute the service without permission; (f) misrepresent your identity or qualifications."}
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "٨. تحديد المسؤولية" : "8. Limitation of Liability"}
              </h2>
              <p className="mb-3">
                {isAr
                  ? "تقدم ريكو هانت الخدمة \"كما هي\" دون ضمانات من أي نوع. إلى أقصى حد تسمح به القوانين المعمول بها، لا نتحمل المسؤولية عن:"
                  : "Rico Hunt provides the service \"as is\" without warranties of any kind. To the fullest extent permitted by law, we are not liable for:"}
              </p>
              <ul className="ml-4 list-disc space-y-2">
                <li>{isAr ? "نتائج طلبات التوظيف أو قرارات التوظيف التي يتخذها أصحاب العمل" : "Job application outcomes or employment decisions made by employers"}</li>
                <li>{isAr ? "دقة قوائم الوظائف الخارجية أو اكتمالها أو توفرها" : "Accuracy, completeness, or availability of third-party job listings"}</li>
                <li>{isAr ? "الأخطاء أو الإغفالات أو عدم الدقة في المحتوى المولّد بالذكاء الاصطناعي" : "Errors, omissions, or inaccuracies in AI-generated content"}</li>
                <li>{isAr ? "انقطاع الخدمة أو فقدان البيانات أو الأعطال التقنية" : "Service interruptions, data loss, or technical failures"}</li>
                <li>{isAr ? "أي اعتماد على قوائم الوظائف دون التحقق منها بشكل مستقل" : "Any reliance placed on job listings without independent verification"}</li>
              </ul>
              <p className="mt-3">
                {isAr
                  ? "تقتصر مسؤوليتنا الإجمالية تجاهك على المبالغ التي دفعتها لريكو هانت خلال 12 شهراً قبل المطالبة."
                  : "Our total liability to you is limited to amounts you have paid to Rico Hunt in the 12 months preceding the claim."}
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "٩. القانون الحاكم" : "9. Governing Law"}
              </h2>
              <p>
                {isAr
                  ? "تخضع هذه الشروط لقوانين الإمارات العربية المتحدة. تُحسم أي نزاعات أمام محاكم الإمارات العربية المتحدة. إذا كنت مستهلكاً في الاتحاد الأوروبي، فقد تنطبق قوانين حماية المستهلك الإلزامية في بلد إقامتك."
                  : "These terms are governed by the laws of the United Arab Emirates. Any disputes shall be resolved in the courts of the United Arab Emirates. If you are a consumer in the EU, mandatory consumer protection laws of your country of residence may apply."}
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "١٠. التغييرات على الشروط" : "10. Changes to Terms"}
              </h2>
              <p>
                {isAr
                  ? "قد نحدّث هذه الشروط من وقت لآخر. سيُبلَّغ عن التغييرات الجوهرية عبر البريد الإلكتروني أو من خلال الخدمة. استمرار استخدامها بعد التغييرات يُعدّ قبولاً لها."
                  : "We may update these terms from time to time. Material changes will be notified via email or through the service. Continued use after changes constitutes acceptance."}
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold text-white">
                {isAr ? "١١. التواصل" : "11. Contact"}
              </h2>
              <p className="mb-3">{isAr ? "للاستفسارات حول هذه الشروط، تواصل معنا:" : "For questions about these terms, contact us:"}</p>
              <ul className="ml-4 list-none space-y-1">
                <li><strong className="text-white">{isAr ? "الشركة:" : "Company:"}</strong> {isAr ? "شركة إيكو تكنولوجي لحماية البيئة ذ.م.م" : "Eco Technology Environment Protection Services L.L.C"}</li>
                <li><strong className="text-white">{isAr ? "الموقع:" : "Location:"}</strong> {isAr ? "الإمارات العربية المتحدة" : "United Arab Emirates"}</li>
                <li>
                  <strong className="text-white">{isAr ? "البريد الإلكتروني:" : "Email:"}</strong>{" "}
                  <a href="mailto:info@ricohunt.com" className="text-[#f5a623] hover:opacity-80">info@ricohunt.com</a>
                </li>
                <li>
                  <strong className="text-white">{isAr ? "الهاتف / واتساب:" : "Phone / WhatsApp:"}</strong>{" "}
                  <a href="https://wa.me/971585989080" className="text-[#f5a623] hover:opacity-80">+971 58 598 9080</a>
                </li>
                <li>
                  <strong className="text-white">{isAr ? "لينكدإن الشركة:" : "LinkedIn:"}</strong>{" "}
                  <a href="https://www.linkedin.com/company/eco-technology-environment-protection-services-l-l-c/" target="_blank" rel="noopener noreferrer" className="text-[#f5a623] hover:opacity-80">
                    {isAr ? "لينكدإن الشركة" : "Company LinkedIn"}
                  </a>
                </li>
              </ul>
            </section>
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
          <span className="text-xs font-medium text-white">{isAr ? "الشروط" : "Terms"}</span>
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
