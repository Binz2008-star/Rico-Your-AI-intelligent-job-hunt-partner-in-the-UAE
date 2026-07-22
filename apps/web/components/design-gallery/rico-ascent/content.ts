export type Lang = "en" | "ar";

export interface StepCopy {
  label: string;
  detail: string;
}

export interface OutcomeCopy {
  label: string;
  detail: string;
}

export interface EvidenceItem {
  claim: string;
  source: string;
  verdict: string;
  confirmed: boolean;
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
    userQuestion: string;
    replyLabel: string;
    tabs: { working: string; loading: string; error: string; failedMedia: string };
    steps: StepCopy[];
    outcomes: {
      completion: OutcomeCopy;
      uncertainty: OutcomeCopy;
      recovery: OutcomeCopy;
    };
    loadingNote: string;
    errorState: { label: string; detail: string; retry: string };
    failedMediaState: { label: string; detail: string };
    finalReply: string;
    copyLabel: string;
    regenerateLabel: string;
    referenceOnlyNote: string;
  };
  evidence: {
    badge: string;
    heading: string;
    subtext: string;
    items: EvidenceItem[];
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
      userQuestion: "Find me a senior product role in Dubai, above 30k.",
      replyLabel: "Rico",
      tabs: { working: "Working", loading: "Loading", error: "Error", failedMedia: "Failed upload" },
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
      loadingNote: "Rico hasn't started yet — this is what the wait looks like.",
      errorState: {
        label: "Something went wrong",
        detail: "The job board didn't respond in time. Nothing was sent.",
        retry: "Try again",
      },
      failedMediaState: {
        label: "Couldn't read that file",
        detail: "The CV upload didn't come through clearly — try a clearer copy.",
      },
      finalReply:
        "Applied to Senior Product Manager at Noon — exactly as you approved. I'll let you know when they respond.",
      copyLabel: "Copy",
      regenerateLabel: "Regenerate",
      referenceOnlyNote: "Reference only — not wired in this prototype",
    },
    evidence: {
      badge: "Sample verification — synthetic data",
      heading: "What verification actually looks like",
      subtext: "Three real checks Rico runs before it tells you a role fits.",
      items: [
        {
          claim: "“5+ years product experience required”",
          source: "Matched against your CV: 6 years at two UAE fintechs.",
          verdict: "Confirmed",
          confirmed: true,
        },
        {
          claim: "“Arabic fluency”",
          source: "Marked on your profile as native — no evidence needed.",
          verdict: "Confirmed",
          confirmed: true,
        },
        {
          claim: "“Team lead experience” (as advertised)",
          source: "Your CV shows individual contributor roles only.",
          verdict: "Not confirmed — flagged for you",
          confirmed: false,
        },
      ],
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
      userQuestion: "ابحث لي عن وظيفة أولى في المنتجات بدبي، فوق 30 ألف.",
      replyLabel: "Rico",
      tabs: { working: "قيد العمل", loading: "التحميل", error: "خطأ", failedMedia: "فشل الرفع" },
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
      loadingNote: "لم يبدأ ريكو بعد — هكذا يبدو الانتظار.",
      errorState: {
        label: "حدث خطأ ما",
        detail: "لم يستجب موقع الوظائف في الوقت المناسب. لم يُرسل شيء.",
        retry: "أعد المحاولة",
      },
      failedMediaState: {
        label: "تعذّرت قراءة هذا الملف",
        detail: "لم يصل ملف السيرة الذاتية بوضوح — جرّب نسخة أوضح.",
      },
      finalReply: "تم التقديم على وظيفة مدير منتج أول في نون — تمامًا كما وافقت. سأخبرك عند ردهم.",
      copyLabel: "نسخ",
      regenerateLabel: "إعادة توليد",
      referenceOnlyNote: "مرجعي فقط — غير مفعّل في هذا النموذج",
    },
    evidence: {
      badge: "تحقق توضيحي — بيانات تجريبية",
      heading: "هكذا يبدو التحقق فعليًا",
      subtext: "ثلاثة تحققات حقيقية يجريها ريكو قبل أن يخبرك أن الوظيفة مناسبة.",
      items: [
        {
          claim: "«مطلوب خبرة 5 سنوات فأكثر في المنتجات»",
          source: "تمت المطابقة مع سيرتك الذاتية: 6 سنوات في شركتين تقنيتين ماليتين بالإمارات.",
          verdict: "مؤكد",
          confirmed: true,
        },
        {
          claim: "«إجادة اللغة العربية»",
          source: "مُسجّلة في ملفك كلغة أم — لا حاجة لدليل إضافي.",
          verdict: "مؤكد",
          confirmed: true,
        },
        {
          claim: "«خبرة في قيادة فريق» (كما ورد بالإعلان)",
          source: "سيرتك الذاتية تُظهر أدوارًا فردية فقط.",
          verdict: "غير مؤكد — تم إبلاغك",
          confirmed: false,
        },
      ],
    },
    closing: {
      headline: "مبني ليعمل، لا ليتحدث فقط.",
      subtext: "هذا هو شكل كل إجراء حقيقي يقوم به ريكو: بحث، قراءة، تحقق، سؤال، تنفيذ.",
      cta: "افتح Command",
    },
  },
};
