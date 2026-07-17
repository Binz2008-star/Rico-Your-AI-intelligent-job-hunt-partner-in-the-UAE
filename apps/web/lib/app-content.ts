/**
 * App content — bilingual dictionary for the Rico workspace surfaces.
 * Arabic is authored fresh for GCC/UAE product tone — not translated.
 */
import { useLanguage } from "@/contexts/LanguageContext";

export type AppContent = {
  nav: {
    command: string;
    profile: string;
    applications: string;
    upload: string;
    settings: string;
    support: string;
    signOut: string;
    workspace: string;
  };
  common: {
    sample: string;
    preview: string;
    save: string;
    cancel: string;
    continue: string;
    back: string;
    next: string;
    optional: string;
    required: string;
    loading: string;
    tryAgain: string;
    signIn: string;
    signUp: string;
    email: string;
    password: string;
    fullName: string;
    or: string;
  };
  auth: {
    signInTitle: string;
    signInSub: string;
    signUpTitle: string;
    signUpSub: string;
    verifyTitle: string;
    verifySub: string;
    codeLabel: string;
    resend: string;
    switchToSignUp: string;
    switchToSignIn: string;
    disclaimer: string;
    google: string;
    demoNotice: string;
    forgotLink: string;
    forgotTitle: string;
    forgotSub: string;
    forgotCta: string;
    forgotSentTitle: string;
    forgotSentSub: string;
    forgotSentBody: string;
    backToSignIn: string;
    resetTitle: string;
    resetSub: string;
    resetNewLabel: string;
    resetConfirmLabel: string;
    resetCta: string;
    resetMismatch: string;
    resetDoneTitle: string;
    resetDoneSub: string;
    resetDoneCta: string;
  };
  onboarding: {
    stepLabel: (i: number, n: number) => string;
    title: string;
    step1Title: string;
    step1Sub: string;
    step1Options: string[];
    step2Title: string;
    step2Sub: string;
    step2Cities: string[];
    step3Title: string;
    step3Sub: string;
    step3Skip: string;
    finish: string;
  };
  profile: {
    eyebrow: string;
    title: string;
    editCta: string;
    summary: string;
    experience: string;
    skills: string;
    languages: string;
    education: string;
    present: string;
    demoName: string;
    demoRole: string;
    demoLocation: string;
    demoSummary: string;
  };
  settings: {
    eyebrow: string;
    title: string;
    tabs: { account: string; prefs: string; notif: string; danger: string };
    account: {
      name: string;
      email: string;
      phone: string;
      timezone: string;
    };
    prefs: {
      language: string;
      theme: string;
      themeLight: string;
      themeDark: string;
      density: string;
    };
    notif: {
      telegram: string;
      email: string;
      weekly: string;
      priority: string;
    };
    danger: {
      exportTitle: string;
      exportBody: string;
      exportCta: string;
      deleteTitle: string;
      deleteBody: string;
      deleteCta: string;
    };
  };
  apps: {
    eyebrow: string;
    title: string;
    subtitle: string;
    viewBoard: string;
    viewList: string;
    columns: {
      saved: string;
      applied: string;
      interview: string;
      offer: string;
      closed: string;
    };
    thCompany: string;
    thRole: string;
    thStatus: string;
    thUpdated: string;
    thFit: string;
    emptyTitle: string;
    emptyBody: string;
    emptyCta: string;
  };
  upload: {
    eyebrow: string;
    title: string;
    subtitle: string;
    dropTitle: string;
    dropBody: string;
    browse: string;
    accepted: string;
    parsing: string;
    parsedTitle: string;
    parsedBody: string;
    reviewCta: string;
    fieldName: string;
    fieldHeadline: string;
    fieldSummary: string;
    saveCta: string;
  };
  status: {
    saved: string;
    applied: string;
    interview: string;
    offer: string;
    closed: string;
  };
  dashboard: {
    eyebrow: string;
    title: string;
    greeting: string;
    subtitle: string;
    completeness: {
      title: string;
      value: string;
      body: string;
      checklist: { label: string; done: boolean }[];
      cta: string;
    };
    stats: { label: string; value: string; hint: string }[];
    quickActionsTitle: string;
    quickActions: { key: "upload" | "profile" | "command" | "apps" | "settings"; label: string; body: string }[];
    activityTitle: string;
    activityEmpty: string;
    activity: { when: string; text: string }[];
    savedTitle: string;
    savedViewAll: string;
    savedEmpty: string;
    saved: { company: string; role: string; fit: string; status: string }[];
  };
};


const EN: AppContent = {
  nav: {
    command: "Command",
    profile: "Profile",
    applications: "Applications",
    upload: "Upload CV",
    settings: "Settings",
    support: "Support",
    signOut: "Sign out",
    workspace: "Workspace",
  },
  common: {
    sample: "SAMPLE",
    preview: "PREVIEW",
    save: "Save",
    cancel: "Cancel",
    continue: "Continue",
    back: "Back",
    next: "Next",
    optional: "Optional",
    required: "Required",
    loading: "Loading…",
    tryAgain: "Try again",
    signIn: "Sign in",
    signUp: "Create account",
    email: "Email",
    password: "Password",
    fullName: "Full name",
    or: "or",
  },
  auth: {
    signInTitle: "Welcome back.",
    signInSub: "Sign in to continue your conversation with Rico.",
    signUpTitle: "Begin with Rico.",
    signUpSub: "One quiet account. Bilingual by design.",
    verifyTitle: "Check your inbox.",
    verifySub: "We sent a six-digit code to confirm it's you.",
    codeLabel: "Verification code",
    resend: "Resend code",
    switchToSignUp: "No account yet? Create one",
    switchToSignIn: "Already have an account? Sign in",
    disclaimer:
      "By continuing you agree to our terms and privacy notice.",
    google: "Continue with Google",
    demoNotice: "Preview screen — no account is created.",
    forgotLink: "Forgot password?",
    forgotTitle: "Forgot your password?",
    forgotSub: "Enter your email and we'll send a reset link.",
    forgotCta: "Send reset link",
    forgotSentTitle: "Check your inbox.",
    forgotSentSub: "If an account exists, a reset link is on its way.",
    forgotSentBody:
      "Follow the link in the email to set a new password. The link expires in 30 minutes.",
    backToSignIn: "Back to sign in",
    resetTitle: "Set a new password.",
    resetSub: "Choose a password you haven't used here before.",
    resetNewLabel: "New password",
    resetConfirmLabel: "Confirm new password",
    resetCta: "Update password",
    resetMismatch: "Passwords don't match yet.",
    resetDoneTitle: "Password updated.",
    resetDoneSub: "You can sign in with your new password now.",
    resetDoneCta: "Continue to sign in",
  },
  onboarding: {
    stepLabel: (i, n) => `Step ${i} of ${n}`,
    title: "Set the tone.",
    step1Title: "What brings you here?",
    step1Sub: "Rico adapts its rhythm to how you're searching.",
    step1Options: [
      "Actively looking now",
      "Open, but selective",
      "Just curious about the market",
    ],
    step2Title: "Where should Rico watch?",
    step2Sub: "Pick one or more UAE markets.",
    step2Cities: ["Dubai", "Abu Dhabi", "Sharjah", "Remote (UAE)"],
    step3Title: "Bring your CV.",
    step3Sub: "Upload a PDF or DOCX. You can also do this later.",
    step3Skip: "Skip for now",
    finish: "Enter Rico",
  },
  profile: {
    eyebrow: "CV profile",
    title: "Your working portrait.",
    editCta: "Edit",
    summary: "Summary",
    experience: "Experience",
    skills: "Skills",
    languages: "Languages",
    education: "Education",
    present: "Present",
    demoName: "Layla Al-Marri",
    demoRole: "Senior Product Manager · Fintech",
    demoLocation: "Dubai, UAE",
    demoSummary:
      "Six years shaping payments and consumer products across the GCC. Bilingual operator. Comfortable between design, engineering, and the boardroom.",
  },
  settings: {
    eyebrow: "Settings",
    title: "Preferences.",
    tabs: {
      account: "Account",
      prefs: "Preferences",
      notif: "Notifications",
      danger: "Danger zone",
    },
    account: {
      name: "Display name",
      email: "Email",
      phone: "Phone",
      timezone: "Timezone",
    },
    prefs: {
      language: "Language",
      theme: "Theme",
      themeLight: "Light",
      themeDark: "Dark",
      density: "Density",
    },
    notif: {
      telegram: "Telegram alerts",
      email: "Email digest",
      weekly: "Weekly market briefing",
      priority: "Priority-only alerts",
    },
    danger: {
      exportTitle: "Export your data",
      exportBody:
        "Download a copy of your profile, applications, and conversation history.",
      exportCta: "Request export",
      deleteTitle: "Delete account",
      deleteBody:
        "Permanent. Removes your profile, saved jobs, and conversation history.",
      deleteCta: "Delete account",
    },
  },
  apps: {
    eyebrow: "Applications",
    title: "Your pipeline.",
    subtitle: "Every conversation Rico has started on your behalf.",
    viewBoard: "Board",
    viewList: "List",
    columns: {
      saved: "Saved",
      applied: "Applied",
      interview: "Interview",
      offer: "Offer",
      closed: "Closed",
    },
    thCompany: "Company",
    thRole: "Role",
    thStatus: "Status",
    thUpdated: "Updated",
    thFit: "Fit",
    emptyTitle: "No applications yet.",
    emptyBody:
      "When Rico surfaces a role you approve, it will appear here.",
    emptyCta: "Open Command",
  },
  upload: {
    eyebrow: "Upload CV",
    title: "Bring your CV.",
    subtitle:
      "PDF or DOCX. Rico reads it, structures it, and never shares it.",
    dropTitle: "Drop your file here",
    dropBody: "or",
    browse: "Browse files",
    accepted: "PDF · DOCX · up to 10 MB",
    parsing: "Reading your CV…",
    parsedTitle: "Structured.",
    parsedBody: "Review the fields Rico extracted before saving.",
    reviewCta: "Review fields",
    fieldName: "Full name",
    fieldHeadline: "Headline",
    fieldSummary: "Summary",
    saveCta: "Save profile",
  },
  status: {
    saved: "Saved",
    applied: "Applied",
    interview: "Interview",
    offer: "Offer",
    closed: "Closed",
  },
  dashboard: {
    eyebrow: "Dashboard",
    title: "Good to see you.",
    greeting: "Layla,",
    subtitle:
      "A quiet overview of your workspace. Everything below is sample data for preview.",
    completeness: {
      title: "Profile completeness",
      value: "72%",
      body: "A stronger profile helps Rico surface sharper matches.",
      checklist: [
        { label: "CV uploaded", done: true },
        { label: "Headline confirmed", done: true },
        { label: "Preferred markets set", done: true },
        { label: "Salary range added", done: false },
        { label: "Availability confirmed", done: false },
      ],
      cta: "Complete profile",
    },
    stats: [
      { label: "Saved roles", value: "8", hint: "curated by Rico" },
      { label: "In pipeline", value: "3", hint: "applied · interview" },
      { label: "New this week", value: "5", hint: "matches surfaced" },
    ],
    quickActionsTitle: "Quick actions",
    quickActions: [
      { key: "upload", label: "Upload CV", body: "Refresh what Rico reads about you." },
      { key: "profile", label: "Review profile", body: "Check the working portrait." },
      { key: "command", label: "Open Command", body: "Return to the conversation." },
      { key: "apps", label: "View applications", body: "See every open thread." },
      { key: "settings", label: "Settings", body: "Language, theme, notifications." },
    ],
    activityTitle: "Recent activity",
    activityEmpty: "Nothing to show yet.",
    activity: [
      { when: "Today · 09:12", text: "Rico surfaced 2 new roles in Dubai." },
      { when: "Yesterday", text: "You saved \"Senior PM · Noon\" for review." },
      { when: "3 days ago", text: "Interview brief prepared for Careem." },
      { when: "Last week", text: "CV summary updated after upload." },
    ],
    savedTitle: "Saved roles",
    savedViewAll: "View all",
    savedEmpty: "You haven't saved anything yet.",
    saved: [
      { company: "Noon", role: "Senior Product Manager", fit: "91", status: "Saved" },
      { company: "Careem", role: "Product Lead, Payments", fit: "87", status: "Interview" },
      { company: "e&", role: "Principal PM, Enterprise", fit: "82", status: "Applied" },
    ],
  },
};


const AR: AppContent = {
  nav: {
    command: "المحادثة",
    profile: "الملف",
    applications: "الطلبات",
    upload: "رفع السيرة",
    settings: "الإعدادات",
    support: "الدعم",
    signOut: "تسجيل الخروج",
    workspace: "مساحة العمل",
  },
  common: {
    sample: "عيّنة",
    preview: "معاينة",
    save: "حفظ",
    cancel: "إلغاء",
    continue: "متابعة",
    back: "رجوع",
    next: "التالي",
    optional: "اختياري",
    required: "إلزامي",
    loading: "جارٍ التحميل…",
    tryAgain: "أعد المحاولة",
    signIn: "تسجيل الدخول",
    signUp: "إنشاء حساب",
    email: "البريد الإلكتروني",
    password: "كلمة المرور",
    fullName: "الاسم الكامل",
    or: "أو",
  },
  auth: {
    signInTitle: "مرحبًا بعودتك.",
    signInSub: "سجّل دخولك لتستأنف حوارك مع ريكو.",
    signUpTitle: "ابدأ مع ريكو.",
    signUpSub: "حسابٌ واحدٌ هادئ، ثنائيّ اللغة بالتصميم.",
    verifyTitle: "تفقّد بريدك.",
    verifySub: "أرسلنا رمزًا مكوّنًا من ستّة أرقام للتحقّق من هويّتك.",
    codeLabel: "رمز التحقّق",
    resend: "أعد إرسال الرمز",
    switchToSignUp: "لا تملك حسابًا؟ أنشئ واحدًا",
    switchToSignIn: "لديك حساب؟ سجّل دخولك",
    disclaimer: "بمتابعتك فأنت توافق على الشروط وسياسة الخصوصيّة.",
    google: "المتابعة عبر جوجل",
    demoNotice: "شاشة معاينة — لا يُنشأ حسابٌ فعليّ.",
    forgotLink: "نسيت كلمة المرور؟",
    forgotTitle: "نسيت كلمة المرور؟",
    forgotSub: "أدخل بريدك وسنُرسل لك رابط إعادة التعيين.",
    forgotCta: "أرسل رابط الاستعادة",
    forgotSentTitle: "تفقّد بريدك.",
    forgotSentSub: "إن كان لديك حساب، فرابط الاستعادة في طريقه إليك.",
    forgotSentBody:
      "اتبع الرابط في البريد لضبط كلمة مرور جديدة. تنتهي صلاحيّة الرابط خلال ٣٠ دقيقة.",
    backToSignIn: "العودة إلى تسجيل الدخول",
    resetTitle: "اضبط كلمة مرور جديدة.",
    resetSub: "اختر كلمة مرور لم تستخدمها هنا من قبل.",
    resetNewLabel: "كلمة المرور الجديدة",
    resetConfirmLabel: "تأكيد كلمة المرور",
    resetCta: "تحديث كلمة المرور",
    resetMismatch: "كلمتا المرور لا تتطابقان بعد.",
    resetDoneTitle: "تم تحديث كلمة المرور.",
    resetDoneSub: "يمكنك تسجيل الدخول بها الآن.",
    resetDoneCta: "المتابعة لتسجيل الدخول",
  },
  onboarding: {
    stepLabel: (i, n) => `الخطوة ${i} من ${n}`,
    title: "لِنَضبط الإيقاع.",
    step1Title: "ما الذي جاء بك إلى هنا؟",
    step1Sub: "يُكيّف ريكو أسلوبه حسب طريقة بحثك.",
    step1Options: [
      "أبحث بجديّة الآن",
      "متفتّح، لكنّي انتقائيّ",
      "أستكشف السوق فقط",
    ],
    step2Title: "أين نُتابع الفرص؟",
    step2Sub: "اختر سوقًا أو أكثر داخل الإمارات.",
    step2Cities: ["دبي", "أبوظبي", "الشارقة", "عن بُعد (الإمارات)"],
    step3Title: "أحضِر سيرتك الذاتيّة.",
    step3Sub: "ارفع ملفًا بصيغة PDF أو DOCX. يمكنك تأجيل ذلك لاحقًا.",
    step3Skip: "تخطَّ الآن",
    finish: "ادخل ريكو",
  },
  profile: {
    eyebrow: "ملف السيرة",
    title: "صورتك المهنيّة.",
    editCta: "تعديل",
    summary: "نبذة",
    experience: "الخبرات",
    skills: "المهارات",
    languages: "اللغات",
    education: "التعليم",
    present: "حتى الآن",
    demoName: "ليلى المرّي",
    demoRole: "مديرة منتَج أوّل · تقنية ماليّة",
    demoLocation: "دبي، الإمارات",
    demoSummary:
      "ستّ سنوات في تصميم منتجات المدفوعات والتجزئة عبر الخليج. تعمل بلغتين، وتتنقّل بارتياحٍ بين التصميم والهندسة وقاعات القرار.",
  },
  settings: {
    eyebrow: "الإعدادات",
    title: "التفضيلات.",
    tabs: {
      account: "الحساب",
      prefs: "التفضيلات",
      notif: "التنبيهات",
      danger: "منطقة حسّاسة",
    },
    account: {
      name: "الاسم الظاهر",
      email: "البريد الإلكتروني",
      phone: "الهاتف",
      timezone: "المنطقة الزمنيّة",
    },
    prefs: {
      language: "اللغة",
      theme: "المظهر",
      themeLight: "فاتح",
      themeDark: "داكن",
      density: "الكثافة",
    },
    notif: {
      telegram: "تنبيهات تيليجرام",
      email: "ملخّص بريديّ",
      weekly: "موجز السوق الأسبوعيّ",
      priority: "التنبيهات ذات الأولويّة فقط",
    },
    danger: {
      exportTitle: "تصدير بياناتك",
      exportBody: "احصل على نسخةٍ من ملفّك وطلباتك ومحادثاتك.",
      exportCta: "اطلب التصدير",
      deleteTitle: "حذف الحساب",
      deleteBody:
        "إجراءٌ نهائيّ. يُزيل ملفّك والوظائف المحفوظة وسجلّ محادثاتك.",
      deleteCta: "احذف الحساب",
    },
  },
  apps: {
    eyebrow: "الطلبات",
    title: "خطّ سيرك.",
    subtitle: "كلّ محادثةٍ بدأها ريكو نيابةً عنك.",
    viewBoard: "لوحة",
    viewList: "قائمة",
    columns: {
      saved: "محفوظ",
      applied: "مُقدَّم",
      interview: "مقابلة",
      offer: "عرض",
      closed: "مُغلَق",
    },
    thCompany: "الشركة",
    thRole: "الدور",
    thStatus: "الحالة",
    thUpdated: "آخر تحديث",
    thFit: "الملاءمة",
    emptyTitle: "لا توجد طلباتٌ بعد.",
    emptyBody: "حين يعرض ريكو دورًا توافق عليه سيظهر هنا.",
    emptyCta: "افتح المحادثة",
  },
  upload: {
    eyebrow: "رفع السيرة",
    title: "أحضِر سيرتك.",
    subtitle: "بصيغة PDF أو DOCX. يقرأها ريكو وينظّمها، ولا يُشاركها.",
    dropTitle: "أفلِت ملفّك هنا",
    dropBody: "أو",
    browse: "تصفّح الملفّات",
    accepted: "PDF · DOCX · حتى ١٠ ميغابايت",
    parsing: "يقرأ ريكو سيرتك…",
    parsedTitle: "تمّت البنية.",
    parsedBody: "راجع الحقول التي استخرجها ريكو قبل الحفظ.",
    reviewCta: "راجع الحقول",
    fieldName: "الاسم الكامل",
    fieldHeadline: "العنوان المهنيّ",
    fieldSummary: "نبذة",
    saveCta: "احفظ الملف",
  },
  status: {
    saved: "محفوظ",
    applied: "مُقدَّم",
    interview: "مقابلة",
    offer: "عرض",
    closed: "مُغلَق",
  },
  dashboard: {
    eyebrow: "اللوحة",
    title: "سعيدون بعودتك.",
    greeting: "ليلى،",
    subtitle:
      "نظرةٌ هادئة على مساحة عملك. جميع البيانات أدناه عيّنةٌ للمعاينة فقط.",
    completeness: {
      title: "اكتمال الملف",
      value: "٧٢٪",
      body: "كلّما اكتمل ملفّك، جاءتك مطابقات ريكو أدقّ.",
      checklist: [
        { label: "رفعت السيرة الذاتيّة", done: true },
        { label: "أكّدت العنوان المهنيّ", done: true },
        { label: "حدّدت الأسواق المفضّلة", done: true },
        { label: "أضفت نطاق الراتب", done: false },
        { label: "أكّدت تاريخ التوفّر", done: false },
      ],
      cta: "أكمِل الملف",
    },
    stats: [
      { label: "أدوارٌ محفوظة", value: "٨", hint: "من اختيار ريكو" },
      { label: "في المسار", value: "٣", hint: "مُقدَّم · مقابلة" },
      { label: "جديد هذا الأسبوع", value: "٥", hint: "مطابقاتٌ ظهرت" },
    ],
    quickActionsTitle: "إجراءاتٌ سريعة",
    quickActions: [
      { key: "upload", label: "رفع السيرة", body: "حدّث ما يقرأه ريكو عنك." },
      { key: "profile", label: "راجع الملف", body: "اطّلع على صورتك المهنيّة." },
      { key: "command", label: "افتح المحادثة", body: "عُد إلى الحوار مع ريكو." },
      { key: "apps", label: "الطلبات", body: "تابع كلّ خيطٍ مفتوح." },
      { key: "settings", label: "الإعدادات", body: "اللغة والمظهر والتنبيهات." },
    ],
    activityTitle: "آخر النشاط",
    activityEmpty: "لا شيء لعرضه بعد.",
    activity: [
      { when: "اليوم · ٠٩:١٢", text: "عرض ريكو دورَين جديدَين في دبي." },
      { when: "أمس", text: "حفظت «مدير منتَج أوّل · نون» للمراجعة." },
      { when: "قبل ٣ أيام", text: "جهّز ريكو ملخّص مقابلة لكريم." },
      { when: "الأسبوع الماضي", text: "حُدّثت نبذة السيرة بعد الرفع." },
    ],
    savedTitle: "الأدوار المحفوظة",
    savedViewAll: "عرض الكلّ",
    savedEmpty: "لم تحفظ أيّ شيءٍ بعد.",
    saved: [
      { company: "نون", role: "مدير منتَج أوّل", fit: "٩١", status: "محفوظ" },
      { company: "كريم", role: "قائد منتَج — المدفوعات", fit: "٨٧", status: "مقابلة" },
      { company: "e&", role: "مدير منتَج رئيس — قطاع المؤسّسات", fit: "٨٢", status: "مُقدَّم" },
    ],
  },
};


const DICT: Record<"en" | "ar", AppContent> = { en: EN, ar: AR };

export function useAppContent(): AppContent {
  const { language } = useLanguage();
  return DICT[language];
}
