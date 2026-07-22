export type Lang = "en" | "ar";

export interface StepCopy {
  label: string;
  detail: string;
}

export interface OutcomeCopy {
  label: string;
  detail: string;
}

export interface RicoAscentCopy {
  dir: "ltr" | "rtl";
  langToggleLabel: string;
  hero: {
    headline: string;
    subtext: string;
    cta: string;
  };
  moment: {
    badge: string;
    heading: string;
    subtext: string;
    steps: StepCopy[];
    outcomes: {
      completion: OutcomeCopy;
      uncertainty: OutcomeCopy;
      recovery: OutcomeCopy;
    };
  };
  closing: {
    headline: string;
    subtext: string;
    cta: string;
  };
}

export const RICO_ASCENT_COPY: Record<Lang, RicoAscentCopy> = {
  en: {
    dir: "ltr",
    langToggleLabel: "العربية",
    hero: {
      headline: "Your career, actively worked.",
      subtext:
        "Rico searches real roles, reads the postings, checks the evidence, and moves only with your approval.",
      cta: "Open Command",
    },
    moment: {
      badge: "Sample sequence — illustrates real Rico behavior",
      heading: "What happens when you ask Rico something",
      subtext: "Seven real steps. Not a chat animation — Rico's actual working order.",
      steps: [
        { label: "Context", detail: "Loading your session and profile." },
        { label: "Understanding", detail: "Working out what you actually need." },
        { label: "Searching", detail: "Scanning live roles that match." },
        { label: "Reading", detail: "Opening each posting in full." },
        { label: "Verifying", detail: "Checking claims against real evidence." },
        { label: "Approval", detail: "Nothing is sent without your say." },
        { label: "Outcome", detail: "One of three honest endings." },
      ],
      outcomes: {
        completion: { label: "Done", detail: "Applied, exactly as approved." },
        uncertainty: { label: "Not sure — asking you", detail: "Confidence too low to act alone." },
        recovery: { label: "Recovered", detail: "Hit a snag, retried safely." },
      },
    },
    closing: {
      headline: "Built to act, not just chat.",
      subtext: "This is the shape of every real Rico action: search, read, verify, ask, act.",
      cta: "Open Command",
    },
  },
  ar: {
    dir: "rtl",
    langToggleLabel: "English",
    hero: {
      headline: "مسيرتك المهنية، تُدار الآن فعليًا.",
      subtext:
        "يبحث ريكو عن وظائف حقيقية، يقرأ الإعلانات، يتحقق من الأدلة، ولا يتحرك إلا بموافقتك.",
      cta: "افتح Command",
    },
    moment: {
      badge: "تسلسل توضيحي — يعكس سلوك ريكو الفعلي",
      heading: "ما يحدث عندما تطلب من ريكو شيئًا",
      subtext: "سبع خطوات حقيقية. ليست رسومًا متحركة — بل ترتيب عمل ريكو الفعلي.",
      steps: [
        { label: "السياق", detail: "تحميل جلستك وملفك الشخصي." },
        { label: "الفهم", detail: "تحديد ما تحتاجه فعليًا." },
        { label: "البحث", detail: "مسح الوظائف المتاحة المطابقة." },
        { label: "القراءة", detail: "فتح كل إعلان بالكامل." },
        { label: "التحقق", detail: "مطابقة الادعاءات بالأدلة الحقيقية." },
        { label: "الموافقة", detail: "لا شيء يُرسل دون إذنك." },
        { label: "النتيجة", detail: "واحدة من ثلاث نتائج صادقة." },
      ],
      outcomes: {
        completion: { label: "تم", detail: "تم التقديم تمامًا كما وافقت." },
        uncertainty: { label: "غير متأكد — يسأل", detail: "الثقة غير كافية للتصرف وحده." },
        recovery: { label: "تمت المعالجة", detail: "واجه عائقًا، وأعاد المحاولة بأمان." },
      },
    },
    closing: {
      headline: "مبني ليعمل، لا ليتحدث فقط.",
      subtext: "هذا هو شكل كل إجراء حقيقي يقوم به ريكو: بحث، قراءة، تحقق، سؤال، تنفيذ.",
      cta: "افتح Command",
    },
  },
};
