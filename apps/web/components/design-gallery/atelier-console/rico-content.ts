/**
 * Rico interior content — bilingual (EN + AR).
 *
 * Arabic is authored fresh for UAE / GCC career-assistant product tone
 * (فصحى معاصرة، بلا مبالغة تسويقية). It is NOT a literal translation of
 * the English strings — sentence order, idiom, and rhythm are rewritten
 * to read naturally to a GCC job-seeker.
 *
 * What stays English intentionally (kept verbatim across both languages):
 *   • Company / product names (ADNOC, ALEC, DP World, Aramex, Al Futtaim
 *     Carillion, ADCO Bab & Bu Hasa, Careem, Noon, e&, Emirates Global)
 *   • Certifications / standards (NEBOSH IGC, IOSH, ISO 45001, LEED,
 *     BREEAM, TRIR, LTI)
 *   • Function / tool identifiers (read_profile, search_jobs,
 *     score_matches, enrich_company, read_jd, read_cv, write_profile,
 *     write_cv, track_application, read_pipeline, score_conversion,
 *     rico.reply)
 *   • Pseudo-code tool arguments (they read as identifiers, not prose)
 *   • URLs, emails, filenames (adnoc.ae, careers@adnoc.ae,
 *     resume-adnoc-tailored.pdf)
 *   • Salary units and Western digits for AED amounts, scores, dates
 *   • CV proper nouns (name "Ahmed R.")
 *
 * `LIVE_KEY` stays "rico.live.v1" — the persisted schema is
 * language-agnostic (user text + jobs/text/error entries), so old
 * sessions restore cleanly under either language.
 */

import { useLang, type Lang } from "./i18n";

/* ------------------------------------------------------------------ */
/*  Step type — shared source of truth for the scripted transcript     */
/* ------------------------------------------------------------------ */

export type Step =
  | { kind: "user"; text: string }
  | { kind: "think"; text: string; ms?: number }
  | { kind: "say"; text: string; ms?: number }
  | {
      kind: "tool";
      name: string;
      arg: string;
      lines?: string[];
      ms?: number;
      note?: string;
    }
  | { kind: "decision"; label: string; picked: string; options: string[] }
  | { kind: "diff"; file: string; added: string[]; removed?: string[] }
  | { kind: "plan"; items: string[] }
  | { kind: "check"; item: string }
  | {
      kind: "error";
      name: string;
      arg: string;
      message: string;
      retryNote?: string;
    }
  | {
      kind: "ask";
      question: string;
      options: string[];
      /** Language-safe: index of the option Rico auto-picks after a beat. */
      autoPickIndex: number;
    }
  | {
      kind: "form";
      title: string;
      subject: string;
      fields: {
        label: string;
        value: string;
        kind?: "text" | "select" | "toggle";
      }[];
      confirm: string;
    }
  | {
      kind: "jobmatch";
      role: string;
      company: string;
      city: string;
      salary: string;
      posted: string;
      score: number;
      why: string[];
      gaps?: string[];
      recommended?: boolean;
    }
  | {
      kind: "cvdiff";
      jobRef: string;
      summary: { before: string; after: string; why: string };
      bullets: {
        role: string;
        before: string;
        after: string;
        why: string;
      }[];
      applyLabel: string;
    }
  | {
      kind: "tracker";
      jobRef: string;
      company: string;
      stages: string[];
      current: number;
      appliedOn: string;
      via: string;
      nextCheck: string;
      note?: string;
    }
  | {
      kind: "reminder";
      jobRef: string;
      dayLabel: string;
      headline: string;
      draftSubject: string;
      draftBody: string[];
      channel: string;
    }
  | {
      kind: "analytics";
      title: string;
      window: string;
      funnel: {
        stage: string;
        count: number;
        convFromPrev?: number;
        benchmark?: number;
      }[];
      stageTimes: {
        stage: string;
        avgDays: number;
        benchDays: number;
        slowest?: boolean;
      }[];
      insights: { tone: "good" | "warn" | "bad"; text: string }[];
      nextMoves: string[];
    }
  | { kind: "done"; text: string; suggestions?: string[] };

export type SessionItem = {
  id: string;
  title: string;
  when: string;
  active?: boolean;
};

/* ------------------------------------------------------------------ */
/*  UI dictionary                                                      */
/* ------------------------------------------------------------------ */

export type RicoUI = {
  head: { title: string; description: string };
  slug: {
    sessionPrefix: string;
    sampleDemo: string;
    sampleTooltip: string;
    jobHuntUAE: string;
    liveUAE: string;
  };
  top: {
    workspaceTag: string;
    toggleSessions: string;
    toggleShortlist: string;
  };
  status: {
    replying: string;
    working: string;
    live: string;
    ready: string;
  };
  sessions: {
    title: string;
    newBtn: string;
    threadsSuffix: string;
  };
  shortlistRail: {
    shortlist: string;
    empty: string;
    ricoPicks: string;
    pipeline: string;
    nextPrefix: string;
    signal: string;
  };
  gutter: {
    you: string;
    think: string;
    rico: string;
    run: string;
    done: string;
    choose: string;
    write: string;
    plan: string;
    check: string;
    fail: string;
    ask: string;
    match: string;
    cv: string;
    wrote: string;
    form: string;
    saved: string;
    track: string;
    nudge: string;
    sent: string;
    held: string;
    signal: string;
  };
  ask: { youPrefix: string };
  jobMatch: {
    ricoPicks: string;
    sampleData: string;
    sampleTooltip: string;
    whyFits: string;
    honestGaps: string;
    tailorApply: string;
    save: string;
    skip: string;
    fitLabel: string;
    postedPrefix: string;
  };
  scorePip: {
    strong: string;
    solid: string;
    stretch: string;
  };
  cvdiff: {
    tailoredFor: string;
    editsSuffix: string;
    summaryLabel: string;
    bulletPrefix: string;
    skip: string;
    include: string;
    written: string;
    skipped: string;
    why: string;
    applied: string;
    keepOriginal: string;
    profileUpdated: string;
    willApply: (n: number, total: number) => string;
  };
  form: {
    subjectPrefix: string;
    savedGutter: string;
    edit: string;
    committed: string;
  };
  tracker: {
    appliedBadge: string;
    viaPrefix: string;
    appliedMeta: string;
    nextCheckMeta: string;
    channelMeta: string;
    openThread: string;
    advanceStage: string;
    markRejected: string;
    reminderSet: string;
    stageNames: Record<string, string>;
  };
  reminder: {
    draftLabel: string;
    sendOnDay5: string;
    editDraft: string;
    holdCta: string;
    sent: string;
    queued: string;
    heldReview: string;
    autoHold: string;
  };
  analytics: {
    conversionFunnel: string;
    stageTime: string;
    whatMeans: string;
    doNext: string;
    vsBench: string;
    youLegend: string;
    benchLegend: string;
    daysSuffix: string;
    bottleneck: string;
    ppSuffix: string;
    /** Funnel stage names — map English stage → localized display */
    stageNames: Record<string, string>;
  };
  composer: {
    attachCV: string;
    stop: string;
    send: string;
    kCommands: string;
    slashHelp: string;
    reset: string;
    placeholderPending: string;
    placeholderRunning: string;
    placeholderIdle: string;
  };
  live: {
    reachError: (msg: string) => string;
    retryFromComposer: string;
    stoppedMarker: string;
    retryLabel: string;
    stoppedByUser: string;
  };
};

/* ------------------------------------------------------------------ */
/*  English UI                                                         */
/* ------------------------------------------------------------------ */

const UI_EN: RicoUI = {
  head: {
    title: "Rico — Your UAE job-hunt partner",
    description:
      "Rico reads your CV, finds jobs that actually fit, explains why, and tracks every application — in one conversation.",
  },
  slug: {
    sessionPrefix: "session · 07·07·26 · 14:22",
    sampleDemo: "sample data · demo",
    sampleTooltip:
      "Rico is showing sample UAE listings while the live job feed is still being wired up.",
    jobHuntUAE: "job hunt · UAE",
    liveUAE: "live · UAE",
  },
  top: {
    workspaceTag: "/ job hunt · UAE",
    toggleSessions: "toggle sessions",
    toggleShortlist: "toggle shortlist",
  },
  status: {
    replying: "Rico is replying",
    working: "Rico is working",
    live: "Live",
    ready: "Ready",
  },
  sessions: {
    title: "sessions",
    newBtn: "+ new",
    threadsSuffix: "threads · job hunt",
  },
  shortlistRail: {
    shortlist: "shortlist",
    empty: "Empty for now — Rico fills this as he scores matches.",
    ricoPicks: "rico picks",
    pipeline: "pipeline",
    nextPrefix: "next ·",
    signal: "signal",
  },
  gutter: {
    you: "you",
    think: "think",
    rico: "rico",
    run: "run",
    done: "done",
    choose: "choose",
    write: "write",
    plan: "plan",
    check: "✓",
    fail: "fail",
    ask: "ask",
    match: "match",
    cv: "cv",
    wrote: "wrote",
    form: "form",
    saved: "saved",
    track: "track",
    nudge: "nudge",
    sent: "sent",
    held: "held",
    signal: "signal",
  },
  ask: { youPrefix: "you ·" },
  jobMatch: {
    ricoPicks: "rico picks",
    sampleData: "sample data",
    sampleTooltip: "Demo data — no live listings yet",
    whyFits: "why it fits you",
    honestGaps: "honest gaps",
    tailorApply: "tailor cv & apply",
    save: "save",
    skip: "skip",
    fitLabel: "fit ·",
    postedPrefix: "·",
  },
  scorePip: {
    strong: "strong fit",
    solid: "solid fit",
    stretch: "stretch fit",
  },
  cvdiff: {
    tailoredFor: "tailored for",
    editsSuffix: "edits",
    summaryLabel: "summary",
    bulletPrefix: "bullet ·",
    skip: "skip",
    include: "↺ include",
    written: "✓ written",
    skipped: "skipped",
    why: "why",
    applied: "applied ✓",
    keepOriginal: "keep original",
    profileUpdated: "profile updated · original kept",
    willApply: (n, total) => `${n} of ${total} will apply`,
  },
  form: {
    subjectPrefix: "subject ·",
    savedGutter: "saved",
    edit: "edit",
    committed: "✓ committed",
  },
  tracker: {
    appliedBadge: "applied",
    viaPrefix: "· via",
    appliedMeta: "applied",
    nextCheckMeta: "next check",
    channelMeta: "channel",
    openThread: "open thread",
    advanceStage: "advance stage",
    markRejected: "mark rejected",
    reminderSet: "reminder set",
    stageNames: {
      queued: "queued",
      applied: "applied",
      shortlist: "shortlist",
      interview: "interview",
      offer: "offer",
    },
  },
  reminder: {
    draftLabel: "draft ·",
    sendOnDay5: "send on day 5",
    editDraft: "edit draft",
    holdCta: "hold — ping me first",
    sent: "sent ✓",
    queued: "queued for send",
    heldReview: "held for review",
    autoHold: "auto-hold enabled",
  },
  analytics: {
    conversionFunnel: "conversion funnel",
    stageTime: "stage time · you vs benchmark",
    whatMeans: "what this means",
    doNext: "do this next",
    vsBench: "vs bench",
    youLegend: "you",
    benchLegend: "benchmark",
    daysSuffix: "d",
    bottleneck: "bottleneck",
    ppSuffix: "pp",
    stageNames: {
      applied: "applied",
      shortlist: "shortlist",
      interview: "interview",
      offer: "offer",
      "applied → shortlist": "applied → shortlist",
      "shortlist → interview": "shortlist → interview",
      "interview → offer": "interview → offer",
    },
  },
  composer: {
    attachCV: "attach CV",
    stop: "stop",
    send: "send",
    kCommands: "K  commands",
    slashHelp: "/find /tailor /track /follow-up",
    reset: "↻ reset",
    placeholderPending: "Rico is replying…",
    placeholderRunning:
      "Send a message to skip the walkthrough and chat with Rico…",
    placeholderIdle:
      "Ask Rico — try 'find HSE jobs in Abu Dhabi' for sample UAE matches.",
  },
  live: {
    reachError: (msg) => `Rico couldn't reach the AI Gateway: ${msg}`,
    retryFromComposer: "Retry from the composer.",
    stoppedMarker: "Stopped.",
    retryLabel: "Retry",
    stoppedByUser: "You stopped this reply. The partial answer is kept above.",
  },
};

/* ------------------------------------------------------------------ */
/*  Arabic UI                                                          */
/* ------------------------------------------------------------------ */

const UI_AR: RicoUI = {
  head: {
    title: "ريكو — رفيقك في البحث عن وظيفة داخل الإمارات",
    description:
      "ريكو يقرأ سيرتك، ويجد الوظائف التي تناسبك فعلًا، يشرح لك السبب، ويتابع كل طلب — في محادثة واحدة.",
  },
  slug: {
    sessionPrefix: "الجلسة · ٠٧·٠٧·٢٦ · ١٤:٢٢",
    sampleDemo: "بيانات عيّنة · توضيحي",
    sampleTooltip:
      "ريكو يعرض إعلانات وظائف إماراتية توضيحية بينما تُهيَّأ التغذية الحيّة.",
    jobHuntUAE: "بحث الوظائف · الإمارات",
    liveUAE: "حيّ · الإمارات",
  },
  top: {
    workspaceTag: "/ بحث الوظائف · الإمارات",
    toggleSessions: "إظهار الجلسات",
    toggleShortlist: "إظهار القائمة المختصرة",
  },
  status: {
    replying: "ريكو يردّ",
    working: "ريكو يعمل",
    live: "حيّ",
    ready: "جاهز",
  },
  sessions: {
    title: "الجلسات",
    newBtn: "+ جديد",
    threadsSuffix: "محادثة · بحث الوظائف",
  },
  shortlistRail: {
    shortlist: "القائمة المختصرة",
    empty: "فارغة الآن — يملؤها ريكو مع كل تطابق يجده.",
    ricoPicks: "اختيار ريكو",
    pipeline: "مسار الطلبات",
    nextPrefix: "التالي ·",
    signal: "إشارات",
  },
  gutter: {
    you: "أنت",
    think: "يفكّر",
    rico: "ريكو",
    run: "يشغّل",
    done: "تم",
    choose: "اختر",
    write: "يكتب",
    plan: "الخطة",
    check: "✓",
    fail: "فشل",
    ask: "سؤال",
    match: "تطابق",
    cv: "سيرة",
    wrote: "كُتب",
    form: "نموذج",
    saved: "حُفظ",
    track: "تتبّع",
    nudge: "تذكير",
    sent: "أُرسل",
    held: "مؤجّل",
    signal: "إشارة",
  },
  ask: { youPrefix: "أنت ·" },
  jobMatch: {
    ricoPicks: "اختيار ريكو",
    sampleData: "بيانات عيّنة",
    sampleTooltip: "بيانات توضيحية — لا توجد إعلانات حيّة بعد",
    whyFits: "لماذا يناسبك",
    honestGaps: "فجوات بصراحة",
    tailorApply: "كيّف السيرة وقدّم",
    save: "احفظ",
    skip: "تخطَّ",
    fitLabel: "الملاءمة ·",
    postedPrefix: "·",
  },
  scorePip: {
    strong: "ملاءمة قوية",
    solid: "ملاءمة صلبة",
    stretch: "ملاءمة على الحد",
  },
  cvdiff: {
    tailoredFor: "مكيَّف لأجل",
    editsSuffix: "تعديلات",
    summaryLabel: "النبذة",
    bulletPrefix: "بند ·",
    skip: "تخطَّ",
    include: "↺ أدرج",
    written: "✓ كُتب",
    skipped: "مُتخطّى",
    why: "لماذا",
    applied: "طُبِّق ✓",
    keepOriginal: "أبقِ الأصل",
    profileUpdated: "حُدِّث الملف · الأصل محفوظ",
    willApply: (n, total) => `سيُطبَّق ${n} من ${total}`,
  },
  form: {
    subjectPrefix: "الموضوع ·",
    savedGutter: "حُفظ",
    edit: "تعديل",
    committed: "✓ اعتُمد",
  },
  tracker: {
    appliedBadge: "مقدَّم",
    viaPrefix: "· عبر",
    appliedMeta: "تاريخ التقديم",
    nextCheckMeta: "المراجعة القادمة",
    channelMeta: "القناة",
    openThread: "افتح المحادثة",
    advanceStage: "قدّم المرحلة",
    markRejected: "وسم بالرفض",
    reminderSet: "تذكير مضبوط",
    stageNames: {
      queued: "في الطابور",
      applied: "مقدَّم",
      shortlist: "قائمة مختصرة",
      interview: "مقابلة",
      offer: "عرض",
    },
  },
  reminder: {
    draftLabel: "مسودّة ·",
    sendOnDay5: "أرسِل في اليوم ٥",
    editDraft: "عدّل المسودّة",
    holdCta: "احتفظ — نبّهني أوّلًا",
    sent: "أُرسل ✓",
    queued: "في طابور الإرسال",
    heldReview: "محتجَز للمراجعة",
    autoHold: "الاحتجاز التلقائي مفعّل",
  },
  analytics: {
    conversionFunnel: "قمع التحويل",
    stageTime: "زمن المرحلة · أنت مقابل المرجع",
    whatMeans: "ماذا يعني هذا",
    doNext: "افعل هذا تاليًا",
    vsBench: "مقابل المرجع",
    youLegend: "أنت",
    benchLegend: "المرجع",
    daysSuffix: "يوم",
    bottleneck: "عنق الزجاجة",
    ppSuffix: "نقطة",
    stageNames: {
      applied: "مقدَّم",
      shortlist: "قائمة مختصرة",
      interview: "مقابلة",
      offer: "عرض",
      "applied → shortlist": "مقدَّم → قائمة مختصرة",
      "shortlist → interview": "قائمة مختصرة → مقابلة",
      "interview → offer": "مقابلة → عرض",
    },
  },
  composer: {
    attachCV: "إرفاق السيرة",
    stop: "إيقاف",
    send: "إرسال",
    kCommands: "K  الأوامر",
    slashHelp: "/find /tailor /track /follow-up",
    reset: "↻ إعادة",
    placeholderPending: "ريكو يردّ…",
    placeholderRunning:
      "أرسل رسالة لتخطّي الجولة التوضيحية والمحادثة مع ريكو…",
    placeholderIdle:
      "اسأل ريكو — جرّب «ابحث لي عن وظائف HSE في أبوظبي» لترى أمثلة إماراتية.",
  },
  live: {
    reachError: (msg) => `تعذّر على ريكو الوصول إلى بوّابة الذكاء: ${msg}`,
    retryFromComposer: "أعد المحاولة من مربّع الكتابة.",
    stoppedMarker: "أُوقف.",
    retryLabel: "إعادة",
    stoppedByUser: "أوقفتَ هذا الرد. الإجابة الجزئية محفوظة أعلاه.",
  },
};

/* ------------------------------------------------------------------ */
/*  Sessions rail                                                       */
/* ------------------------------------------------------------------ */

const SESSIONS_EN: SessionItem[] = [
  {
    id: "s1",
    title: "HSE Manager · Dubai + Abu Dhabi",
    when: "now",
    active: true,
  },
  { id: "s2", title: "Sharpen CV for oil & gas roles", when: "yesterday" },
  { id: "s3", title: "Follow-up · ADNOC application", when: "2d" },
  { id: "s4", title: "Salary check — HSE Lead, UAE", when: "Fri" },
  { id: "s5", title: "Translate CV to العربية", when: "Wed" },
  { id: "s6", title: "Interview prep — Emirates Global", when: "Jun 28" },
];

const SESSIONS_AR: SessionItem[] = [
  {
    id: "s1",
    title: "مدير HSE · دبي وأبوظبي",
    when: "الآن",
    active: true,
  },
  { id: "s2", title: "شحذ السيرة لوظائف النفط والغاز", when: "أمس" },
  { id: "s3", title: "متابعة · طلب ADNOC", when: "قبل يومين" },
  { id: "s4", title: "فحص الرواتب — HSE Lead، الإمارات", when: "الجمعة" },
  { id: "s5", title: "ترجمة السيرة إلى English", when: "الأربعاء" },
  {
    id: "s6",
    title: "تحضير مقابلة — Emirates Global",
    when: "٢٨ يونيو",
  },
];

/* ------------------------------------------------------------------ */
/*  Scripted transcript — English                                       */
/* ------------------------------------------------------------------ */

const SCRIPT_EN: Step[] = [
  {
    kind: "user",
    text: "Find me HSE Manager jobs in Dubai and Abu Dhabi. I want the ones that actually fit my CV — not just anything with the title.",
  },
  {
    kind: "think",
    text: "Pulling your profile first so I match against your real experience — not just keywords.",
  },
  {
    kind: "plan",
    items: [
      "Read your CV + profile",
      "Search UAE listings (Dubai, Abu Dhabi)",
      "Filter out weak matches",
      "Score the strong ones",
      "Explain why each one fits",
    ],
  },
  {
    kind: "tool",
    name: "read_profile",
    arg: "you · CV + preferences",
    ms: 900,
    lines: [
      "→ name:        Ahmed R.",
      "→ role:        HSE Manager · 9 yrs",
      "→ sectors:     oil & gas, construction, logistics",
      "→ certs:       NEBOSH IGC, IOSH, ISO 45001 lead auditor",
      "→ languages:   English, العربية",
      "→ location:    Dubai · open to Abu Dhabi",
    ],
    note: "profile loaded",
  },
  { kind: "check", item: "Read your CV + profile" },
  {
    kind: "tool",
    name: "search_jobs",
    arg: "\"HSE Manager\" city:Dubai,\"Abu Dhabi\"",
    ms: 1400,
    lines: [
      "→ scanned 4 boards · 312 postings",
      "→ 47 titled HSE Manager / HSE Lead",
      "→ 23 within 30 days",
      "→ 11 match your sector history",
    ],
    note: "11 candidates",
  },
  { kind: "check", item: "Search UAE listings (Dubai, Abu Dhabi)" },
  {
    kind: "error",
    name: "enrich_company",
    arg: "employer profiles",
    message: "1 listing missing salary band — provider timeout",
    retryNote: "Backfilled from a public range. Marked it low-confidence.",
  },
  {
    kind: "tool",
    name: "score_matches",
    arg: "cv ↔ 11 jobs",
    ms: 1200,
    lines: [
      "→ drop:    Junior HSE Officer (under-level)",
      "→ drop:    HSE Manager · marine only (no marine yrs)",
      "→ drop:    contract 3 mo · relocation Fujairah",
      "→ keep:    3 strong fits, 2 stretch, 3 backup",
    ],
    note: "3 strong fits",
  },
  { kind: "check", item: "Filter out weak matches" },
  {
    kind: "say",
    text: "Here are your top three. I'm ranking by CV fit, not by how loud the ad is — and I'll tell you exactly why each one made the cut.",
    ms: 20,
  },
  {
    kind: "jobmatch",
    role: "HSE Manager — Upstream Operations",
    company: "ADNOC Onshore",
    city: "Abu Dhabi · Ruwais",
    salary: "AED 32–38k / mo · housing + schooling",
    posted: "2d ago",
    score: 92,
    recommended: true,
    why: [
      "9 yrs upstream oil & gas — matches their required 7+",
      "ISO 45001 lead auditor is listed as \"strong plus\"",
      "Arabic + English matches the site-team requirement",
    ],
    gaps: ["No offshore rotation on your CV — role is 5/2 onshore, so fine"],
  },
  {
    kind: "jobmatch",
    role: "HSE Manager — Major Projects",
    company: "ALEC Engineering & Contracting",
    city: "Dubai · Business Bay",
    salary: "AED 26–32k / mo",
    posted: "5d ago",
    score: 84,
    why: [
      "Construction HSE — matches your 4 yrs at Al Futtaim Carillion",
      "NEBOSH IGC is the exact cert they require",
      "Dubai-based · no relocation needed",
    ],
    gaps: [
      "They want LEED familiarity — you have BREEAM, close enough to raise",
    ],
  },
  {
    kind: "jobmatch",
    role: "HSE Lead — Logistics Hub",
    company: "DP World",
    city: "Dubai · Jebel Ali",
    salary: "AED 24–28k / mo · low confidence",
    posted: "6d ago",
    score: 76,
    why: [
      "Logistics HSE overlap with your Aramex years",
      "IOSH + 45001 both required, both present",
    ],
    gaps: [
      "Salary band inferred — verify at first-round call",
      "Title is Lead, not Manager — slight step sideways",
    ],
  },
  { kind: "check", item: "Score the strong ones" },
  { kind: "check", item: "Explain why each one fits" },
  {
    kind: "ask",
    question:
      "Want me to line up the ADNOC one first? I'll tailor your CV for that JD before we send.",
    options: [
      "Yes — tailor CV and draft the application",
      "Show me the JD first",
      "Skip ADNOC, start with ALEC",
    ],
    autoPickIndex: 0,
  },
  {
    kind: "done",
    text: "Locked in. I'll rewrite the summary + top 3 bullets against the ADNOC JD, then queue it for your review.",
    suggestions: [
      "Tailor CV for ADNOC",
      "Track all 3 as applied",
      "Salary check — HSE Manager UAE",
      "Set alert for new HSE roles",
    ],
  },

  {
    kind: "user",
    text: "actually — update my profile. availability is now 2 weeks notice, and add Arabic as a working language, and set expected salary to AED 30k minimum.",
  },
  {
    kind: "think",
    text: "Three profile edits. I'll show them together so you can confirm before I write — and rescore the shortlist after.",
  },
  {
    kind: "tool",
    name: "read_profile",
    arg: "you · current",
    ms: 700,
    lines: [
      "→ notice_period:   1 month",
      "→ languages:       English",
      "→ salary_min:      AED 25,000",
    ],
    note: "loaded current profile",
  },
  {
    kind: "form",
    title: "profile · confirm changes",
    subject: "profile",
    fields: [
      { label: "notice period", value: "2 weeks", kind: "select" },
      { label: "languages", value: "English, العربية", kind: "text" },
      { label: "salary min", value: "AED 30,000 / mo", kind: "text" },
    ],
    confirm: "Save profile",
  },
  {
    kind: "tool",
    name: "write_profile",
    arg: "you · updated",
    ms: 900,
    lines: [
      "→ notice_period:   1 month → 2 weeks",
      "→ languages:       English → English, العربية",
      "→ salary_min:      25,000 → 30,000 AED",
    ],
    note: "3 fields updated",
  },
  {
    kind: "say",
    text: "Profile saved. Rescoring your shortlist against the new salary floor — DP World drops below your minimum, so I'll swap in the next best match.",
    ms: 20,
  },
  {
    kind: "done",
    text: "All set. Ready to tailor the ADNOC CV, or want to look at the swapped-in role first?",
    suggestions: [
      "Tailor CV for ADNOC now",
      "Show the new #3 match",
      "Set weekly alert · HSE UAE",
      "Track ADNOC as applied",
    ],
  },

  {
    kind: "user",
    text: "yes tailor my CV for the ADNOC one. show me exactly what you're changing before you touch my profile.",
  },
  {
    kind: "think",
    text: "Reading the ADNOC JD and your current CV, then rewriting the summary and the top three bullets to speak the exact language of that role — no invented experience.",
  },
  {
    kind: "plan",
    items: [
      "Load the ADNOC JD",
      "Load your current CV",
      "Rewrite summary against JD language",
      "Rewrite top 3 bullets · quantify + JD keywords",
      "Show the diff — you approve before I write",
    ],
  },
  {
    kind: "tool",
    name: "read_jd",
    arg: "ADNOC Onshore · HSE Manager · Ruwais",
    ms: 900,
    lines: [
      "→ must-have:   7+ yrs upstream HSE",
      "→ must-have:   ISO 45001 auditor",
      "→ strong plus: incident-reduction record (%)",
      "→ strong plus: contractor HSE governance",
      "→ language:    English + Arabic, site teams",
    ],
    note: "5 signals captured",
  },
  { kind: "check", item: "Load the ADNOC JD" },
  {
    kind: "tool",
    name: "read_cv",
    arg: "you · resume-v4.pdf",
    ms: 900,
    lines: [
      "→ summary:     generic — no sector words",
      "→ bullet #1:   verb-first, no metric",
      "→ bullet #2:   mentions ISO 45001 (good)",
      "→ bullet #3:   contractor work — not surfaced",
    ],
    note: "opened 2 pages",
  },
  { kind: "check", item: "Load your current CV" },
  {
    kind: "cvdiff",
    jobRef: "ADNOC Onshore · HSE Manager · Ruwais",
    summary: {
      before:
        "HSE professional with 9 years of experience in health, safety and environment across multiple industries in the UAE.",
      after:
        "HSE Manager with 9 yrs upstream oil & gas experience across UAE onshore sites. ISO 45001 lead auditor. Track record of cutting TRIR by 38% through contractor governance and site-team training — English + Arabic on site.",
      why: "Names the exact JD signals: upstream, 45001 auditor, contractor governance, bilingual site delivery.",
    },
    bullets: [
      {
        role: "Sr. HSE Officer · Al Futtaim Carillion · 2019–22",
        before:
          "Responsible for site safety across multiple construction projects in Dubai and Abu Dhabi.",
        after:
          "Led HSE on 4 concurrent UAE sites (240+ contractors) — drove TRIR from 1.4 → 0.87 in 18 months via daily contractor toolbox reviews and Arabic-language site briefings.",
        why: "Quantifies incident reduction + surfaces contractor governance, both JD 'strong plus' signals.",
      },
      {
        role: "HSE Lead · Aramex Logistics Hub · 2022–24",
        before:
          "Implemented ISO 45001 across the logistics hub and trained the team on new procedures.",
        after:
          "Ran ISO 45001 lead audit across 3 hubs (Dubai · Sharjah · Ruwais) — closed 47 non-conformities in one cycle, no repeat findings at re-audit.",
        why: "Turns the 45001 mention into a hard auditor record with a Ruwais reference — same site as the ADNOC role.",
      },
      {
        role: "HSE Officer · ADCO (early career) · 2016–19",
        before:
          "Assisted senior HSE staff with day-to-day work in upstream operations.",
        after:
          "3 yrs upstream HSE on ADCO Bab & Bu Hasa fields — permit-to-work coordination across 60+ daily jobs, zero LTIs across the assignment.",
        why: "Directly evidences the 7+ yrs upstream requirement and gives ADNOC-familiar site names.",
      },
    ],
    applyLabel: "Apply to profile & queue application",
  },
  { kind: "check", item: "Rewrite summary against JD language" },
  { kind: "check", item: "Rewrite top 3 bullets · quantify + JD keywords" },
  {
    kind: "ask",
    question:
      "Apply the rewrite to your profile — or keep both versions on file for now?",
    options: [
      "Apply — overwrite my CV",
      "Save as a tailored copy · keep original",
      "Change something first",
    ],
    autoPickIndex: 1,
  },
  {
    kind: "tool",
    name: "write_cv",
    arg: "you · resume-adnoc-tailored.pdf",
    ms: 1000,
    lines: [
      "→ new file:    resume-adnoc-tailored.pdf",
      "→ summary:     rewritten (1 paragraph)",
      "→ bullets:     3 rewritten · 11 preserved",
      "→ tagged:      target = ADNOC Onshore · HSE Manager",
    ],
    note: "tailored copy saved",
  },
  { kind: "check", item: "Show the diff — you approve before I write" },
  {
    kind: "done",
    text: "Tailored CV saved as a copy — original untouched. I've queued the ADNOC application against this version. Want me to send, or draft the cover note first?",
    suggestions: [
      "Draft the cover note",
      "Send application now",
      "Preview the tailored PDF",
      "Do the same for ALEC",
    ],
  },

  {
    kind: "user",
    text: "sent it. track ADNOC as applied and remind me when to follow up — draft the nudge for me so I don't have to think about it.",
  },
  {
    kind: "think",
    text: "Logging the ADNOC application, setting a Day-5 follow-up, and pre-drafting a polite nudge so it's ready when the time comes.",
  },
  {
    kind: "tool",
    name: "track_application",
    arg: "ADNOC Onshore · HSE Manager",
    ms: 900,
    lines: [
      "→ status:     queued → applied",
      "→ cv:         resume-adnoc-tailored.pdf",
      "→ channel:    adnoc.ae · careers portal",
      "→ SLA:        typical reply · 4–7 days",
      "→ reminder:   Day 5 · 12 Jul · 09:00",
    ],
    note: "1 application tracked · reminder set",
  },
  {
    kind: "tracker",
    jobRef: "HSE Manager — Upstream Operations",
    company: "ADNOC Onshore",
    stages: ["queued", "applied", "shortlist", "interview", "offer"],
    current: 1,
    appliedOn: "07 Jul · 14:31",
    via: "adnoc.ae · careers portal",
    nextCheck: "Day 5 · 12 Jul",
    note: "I'll check quietly each morning. If they reply, I move the stage and tell you. If Day 5 passes silent, I nudge — with the draft below.",
  },
  {
    kind: "reminder",
    jobRef: "ADNOC Onshore · HSE Manager",
    dayLabel: "Day 5 · 12 Jul · projected",
    headline:
      "If they haven't replied by Sunday morning, here's a nudge you can send in one tap.",
    draftSubject: "Following up · HSE Manager application (Ahmed R.)",
    draftBody: [
      "Dear Hiring Team,",
      "Following up on my application for the HSE Manager — Upstream Operations role at ADNOC Onshore (submitted 07 Jul). I remain very interested and wanted to confirm my materials reached you.",
      "Happy to share references or elaborate on my ISO 45001 audit work at Ruwais if useful. Available for a call at your convenience.",
      "Best regards,\nAhmed R.",
    ],
    channel: "email · careers@adnoc.ae",
  },
  {
    kind: "ask",
    question:
      "Sound right? I can send it automatically on Day 5, or hold it for your review first.",
    options: [
      "Hold for my review — ping me first",
      "Send automatically on Day 5",
      "Rewrite it — more casual",
    ],
    autoPickIndex: 0,
  },
  {
    kind: "done",
    text: "Done. ADNOC is in the pipeline, Day-5 nudge is drafted and held for your review. Want me to track ALEC and DP World the same way?",
    suggestions: [
      "Track ALEC as applied",
      "Track DP World as applied",
      "Show my pipeline",
      "Set weekly digest · Sunday 08:00",
    ],
  },

  {
    kind: "user",
    text: "give me pipeline analytics — my conversion rates and which stages are dragging. tell me what to actually do next.",
  },
  {
    kind: "think",
    text: "Pulling your last 30 days of applications, computing stage-to-stage conversion, and comparing your stage times against HSE Manager benchmarks in UAE.",
  },
  {
    kind: "tool",
    name: "read_pipeline",
    arg: "you · applications · last 30d",
    ms: 900,
    lines: [
      "→ scope:      01 Jun – 07 Jul · 26 applications",
      "→ sectors:    oil & gas, construction, logistics",
      "→ status:     3 offer · 5 interview · 9 shortlist · 26 applied",
    ],
    note: "26 applications loaded",
  },
  {
    kind: "tool",
    name: "score_conversion",
    arg: "you ↔ HSE Manager · UAE benchmark",
    ms: 1100,
    lines: [
      "→ applied → shortlist:    35% (bench 22%) ✓",
      "→ shortlist → interview:  56% (bench 48%) ✓",
      "→ interview → offer:      60% (bench 41%) ✓",
      "→ bottleneck stage:       shortlist → interview · 9.2 days",
    ],
    note: "1 bottleneck flagged",
  },
  {
    kind: "analytics",
    title: "your pipeline · last 30 days",
    window: "01 Jun – 07 Jul · 26 applications",
    funnel: [
      { stage: "applied", count: 26 },
      { stage: "shortlist", count: 9, convFromPrev: 0.35, benchmark: 0.22 },
      { stage: "interview", count: 5, convFromPrev: 0.56, benchmark: 0.48 },
      { stage: "offer", count: 3, convFromPrev: 0.6, benchmark: 0.41 },
    ],
    stageTimes: [
      { stage: "applied → shortlist", avgDays: 4.1, benchDays: 5.5 },
      {
        stage: "shortlist → interview",
        avgDays: 9.2,
        benchDays: 4.8,
        slowest: true,
      },
      { stage: "interview → offer", avgDays: 6.4, benchDays: 7.1 },
    ],
    insights: [
      {
        tone: "good",
        text: "Your CV is doing the heavy lifting — you're shortlisted at 35% vs. a 22% market average. The tailoring pass on ADNOC-style JDs is paying off.",
      },
      {
        tone: "warn",
        text: "Shortlist → interview is your bottleneck: 9.2 days vs. 4.8 benchmark. Recruiters are slow to schedule, usually a sign the follow-up cadence needs sharpening.",
      },
      {
        tone: "good",
        text: "When you do interview, you convert at 60% (bench 41%) — no coaching needed on interview delivery.",
      },
    ],
    nextMoves: [
      "Turn on Day-5 auto-nudge for every shortlisted application (not just ADNOC)",
      "Prioritize applications where recruiters are on LinkedIn — outreach cuts shortlist→interview by ~4 days",
      "Stop applying to logistics roles this week — 0/6 shortlisted, hurting your average",
    ],
  },
  {
    kind: "ask",
    question:
      "Want me to apply the top move now — turn on Day-5 auto-nudge for every shortlisted application?",
    options: [
      "Yes — enable across all applications",
      "Enable, but hold each nudge for my review",
      "Not yet · show me a sample nudge first",
    ],
    autoPickIndex: 1,
  },
  {
    kind: "done",
    text: "Auto-nudge is on, held-for-review. I'll flag every shortlisted app on Day 5 with a pre-drafted follow-up. Want me to also stop queuing logistics roles until the ratio improves?",
    suggestions: [
      "Pause logistics roles",
      "Show interview scheduling helpers",
      "Weekly digest · Sunday 08:00",
      "Focus next week on oil & gas only",
    ],
  },
];

/* ------------------------------------------------------------------ */
/*  Scripted transcript — Arabic (fresh authored, not translated)      */
/* ------------------------------------------------------------------ */

const SCRIPT_AR: Step[] = [
  {
    kind: "user",
    text: "ابحث لي عن وظائف مدير HSE في دبي وأبوظبي. أريد التي تناسب سيرتي فعلًا — لا كل ما يحمل المسمى.",
  },
  {
    kind: "think",
    text: "أسحب ملفك أولًا لأطابق خبرتك الحقيقية، لا مجرد كلمات مفتاحية.",
  },
  {
    kind: "plan",
    items: [
      "قراءة سيرتك وملفك",
      "البحث في السوق الإماراتي (دبي وأبوظبي)",
      "استبعاد التطابقات الضعيفة",
      "تقييم القوية منها",
      "شرح سبب مناسبة كل واحدة",
    ],
  },
  {
    kind: "tool",
    name: "read_profile",
    arg: "you · CV + preferences",
    ms: 900,
    lines: [
      "→ name:        Ahmed R.",
      "→ role:        HSE Manager · 9 yrs",
      "→ sectors:     oil & gas, construction, logistics",
      "→ certs:       NEBOSH IGC, IOSH, ISO 45001 lead auditor",
      "→ languages:   English, العربية",
      "→ location:    Dubai · open to Abu Dhabi",
    ],
    note: "حُمّل الملف",
  },
  { kind: "check", item: "قراءة سيرتك وملفك" },
  {
    kind: "tool",
    name: "search_jobs",
    arg: "\"HSE Manager\" city:Dubai,\"Abu Dhabi\"",
    ms: 1400,
    lines: [
      "→ scanned 4 boards · 312 postings",
      "→ 47 titled HSE Manager / HSE Lead",
      "→ 23 within 30 days",
      "→ 11 match your sector history",
    ],
    note: "١١ مرشّحًا",
  },
  { kind: "check", item: "البحث في السوق الإماراتي (دبي وأبوظبي)" },
  {
    kind: "error",
    name: "enrich_company",
    arg: "employer profiles",
    message: "إعلان واحد بلا نطاق راتب — انقطع المزوّد",
    retryNote: "عوّضتُه من نطاق علني، ووسمتُه بثقة منخفضة.",
  },
  {
    kind: "tool",
    name: "score_matches",
    arg: "cv ↔ 11 jobs",
    ms: 1200,
    lines: [
      "→ drop:    Junior HSE Officer (under-level)",
      "→ drop:    HSE Manager · marine only (no marine yrs)",
      "→ drop:    contract 3 mo · relocation Fujairah",
      "→ keep:    3 strong fits, 2 stretch, 3 backup",
    ],
    note: "٣ ملاءمات قوية",
  },
  { kind: "check", item: "استبعاد التطابقات الضعيفة" },
  {
    kind: "say",
    text: "هذه الثلاث الأفضل. أرتّبها حسب ملاءمتها لسيرتك، لا حسب ضجيج الإعلان — وسأخبرك بالضبط لماذا اجتازت كل واحدة.",
    ms: 20,
  },
  {
    kind: "jobmatch",
    role: "HSE Manager — Upstream Operations",
    company: "ADNOC Onshore",
    city: "أبوظبي · الرويس",
    salary: "AED 32–38k / شهريًا · سكن + تعليم",
    posted: "قبل يومين",
    score: 92,
    recommended: true,
    why: [
      "٩ سنوات في upstream نفط وغاز — يفوق شرطهم +٧",
      "شهادة ISO 45001 lead auditor مذكورة كـ «إضافة قوية»",
      "العربية والإنجليزية معًا يوافقان متطلب فريق الموقع",
    ],
    gaps: [
      "لا يوجد offshore rotation في سيرتك — الدور ٥/٢ onshore، فلا مشكلة",
    ],
  },
  {
    kind: "jobmatch",
    role: "HSE Manager — Major Projects",
    company: "ALEC Engineering & Contracting",
    city: "دبي · الخليج التجاري",
    salary: "AED 26–32k / شهريًا",
    posted: "قبل ٥ أيام",
    score: 84,
    why: [
      "HSE إنشائي — يوافق سنواتك الأربع في Al Futtaim Carillion",
      "NEBOSH IGC هو الشهادة المطلوبة بحرفها",
      "مقرّه دبي · لا انتقال",
    ],
    gaps: [
      "يريدون خبرة LEED — لديك BREEAM، قريبة بما يكفي لتُذكر",
    ],
  },
  {
    kind: "jobmatch",
    role: "HSE Lead — Logistics Hub",
    company: "DP World",
    city: "دبي · جبل علي",
    salary: "AED 24–28k / شهريًا · ثقة منخفضة",
    posted: "قبل ٦ أيام",
    score: 76,
    why: [
      "HSE لوجستي يتقاطع مع سنواتك في Aramex",
      "IOSH و 45001 كلاهما مطلوب، وكلاهما لديك",
    ],
    gaps: [
      "نطاق الراتب مستنتَج — تحقّق منه في المكالمة الأولى",
      "المسمى Lead لا Manager — خطوة جانبية طفيفة",
    ],
  },
  { kind: "check", item: "تقييم القوية منها" },
  { kind: "check", item: "شرح سبب مناسبة كل واحدة" },
  {
    kind: "ask",
    question:
      "أرتّب لك ADNOC أوّلًا؟ سأكيّف سيرتك لوصفهم الوظيفي قبل الإرسال.",
    options: [
      "نعم — كيّف السيرة واصنع المسودّة",
      "أرِني الوصف الوظيفي أوّلًا",
      "تخطَّ ADNOC، ابدأ بـ ALEC",
    ],
    autoPickIndex: 0,
  },
  {
    kind: "done",
    text: "تم. سأعيد صياغة النبذة وأفضل ٣ بنود مقابل وصف ADNOC، ثم أضعها بانتظار مراجعتك.",
    suggestions: [
      "كيّف السيرة لـ ADNOC",
      "تتبّع الثلاث كمقدَّمة",
      "فحص الرواتب — HSE Manager الإمارات",
      "اضبط تنبيهًا لوظائف HSE الجديدة",
    ],
  },

  {
    kind: "user",
    text: "في الواقع — حدّث ملفي. مهلة الإشعار صارت أسبوعين، وأضِف العربية كلغة عمل، واجعل الحدّ الأدنى للراتب AED 30k.",
  },
  {
    kind: "think",
    text: "ثلاثة تعديلات على الملف. سأعرضها معًا لتؤكّدها قبل الكتابة، ثم أعيد تقييم القائمة المختصرة.",
  },
  {
    kind: "tool",
    name: "read_profile",
    arg: "you · current",
    ms: 700,
    lines: [
      "→ notice_period:   1 month",
      "→ languages:       English",
      "→ salary_min:      AED 25,000",
    ],
    note: "حُمّل الملف الحالي",
  },
  {
    kind: "form",
    title: "الملف · تأكيد التعديلات",
    subject: "profile",
    fields: [
      { label: "مهلة الإشعار", value: "أسبوعان", kind: "select" },
      { label: "اللغات", value: "English, العربية", kind: "text" },
      { label: "الحدّ الأدنى للراتب", value: "AED 30,000 / شهريًا", kind: "text" },
    ],
    confirm: "احفظ الملف",
  },
  {
    kind: "tool",
    name: "write_profile",
    arg: "you · updated",
    ms: 900,
    lines: [
      "→ notice_period:   1 month → 2 weeks",
      "→ languages:       English → English, العربية",
      "→ salary_min:      25,000 → 30,000 AED",
    ],
    note: "٣ حقول محدَّثة",
  },
  {
    kind: "say",
    text: "حُفظ الملف. أُعيد تقييم قائمتك مقابل الحد الجديد للراتب — DP World يسقط تحت حدّك، فسأستبدله بأفضل بديل تالٍ.",
    ms: 20,
  },
  {
    kind: "done",
    text: "جاهز. أكيّف سيرة ADNOC الآن، أم تودّ رؤية الدور البديل أوّلًا؟",
    suggestions: [
      "كيّف السيرة لـ ADNOC الآن",
      "أرِني التطابق #٣ الجديد",
      "اضبط تنبيهًا أسبوعيًا · HSE الإمارات",
      "تتبّع ADNOC كمقدَّم",
    ],
  },

  {
    kind: "user",
    text: "نعم كيّف السيرة لـ ADNOC. أرِني بالضبط ما ستغيّره قبل أن تلمس ملفي.",
  },
  {
    kind: "think",
    text: "أقرأ الوصف الوظيفي لـ ADNOC وسيرتك الحالية، ثم أعيد صياغة النبذة وأفضل ثلاثة بنود بلغة الدور نفسه — بلا خبرات مختلقة.",
  },
  {
    kind: "plan",
    items: [
      "تحميل وصف ADNOC الوظيفي",
      "تحميل سيرتك الحالية",
      "إعادة صياغة النبذة بلغة الوصف",
      "إعادة صياغة أفضل ٣ بنود · تكميم + كلمات الوصف",
      "عرض الفرق — تعتمده قبل الكتابة",
    ],
  },
  {
    kind: "tool",
    name: "read_jd",
    arg: "ADNOC Onshore · HSE Manager · Ruwais",
    ms: 900,
    lines: [
      "→ must-have:   7+ yrs upstream HSE",
      "→ must-have:   ISO 45001 auditor",
      "→ strong plus: incident-reduction record (%)",
      "→ strong plus: contractor HSE governance",
      "→ language:    English + Arabic, site teams",
    ],
    note: "٥ إشارات مأخوذة",
  },
  { kind: "check", item: "تحميل وصف ADNOC الوظيفي" },
  {
    kind: "tool",
    name: "read_cv",
    arg: "you · resume-v4.pdf",
    ms: 900,
    lines: [
      "→ summary:     generic — no sector words",
      "→ bullet #1:   verb-first, no metric",
      "→ bullet #2:   mentions ISO 45001 (good)",
      "→ bullet #3:   contractor work — not surfaced",
    ],
    note: "فُتحت صفحتان",
  },
  { kind: "check", item: "تحميل سيرتك الحالية" },
  {
    kind: "cvdiff",
    jobRef: "ADNOC Onshore · HSE Manager · Ruwais",
    summary: {
      before:
        "HSE professional with 9 years of experience in health, safety and environment across multiple industries in the UAE.",
      after:
        "HSE Manager with 9 yrs upstream oil & gas experience across UAE onshore sites. ISO 45001 lead auditor. Track record of cutting TRIR by 38% through contractor governance and site-team training — English + Arabic on site.",
      why:
        "يذكر إشارات الوصف حرفيًا: upstream، مدقّق 45001، حوكمة المقاولين، عمل ميداني بلغتين.",
    },
    bullets: [
      {
        role: "Sr. HSE Officer · Al Futtaim Carillion · 2019–22",
        before:
          "Responsible for site safety across multiple construction projects in Dubai and Abu Dhabi.",
        after:
          "Led HSE on 4 concurrent UAE sites (240+ contractors) — drove TRIR from 1.4 → 0.87 in 18 months via daily contractor toolbox reviews and Arabic-language site briefings.",
        why:
          "يُكمّم خفض الحوادث ويُبرز حوكمة المقاولين، وكلاهما «إضافة قوية» في الوصف.",
      },
      {
        role: "HSE Lead · Aramex Logistics Hub · 2022–24",
        before:
          "Implemented ISO 45001 across the logistics hub and trained the team on new procedures.",
        after:
          "Ran ISO 45001 lead audit across 3 hubs (Dubai · Sharjah · Ruwais) — closed 47 non-conformities in one cycle, no repeat findings at re-audit.",
        why:
          "يحوّل ذكر 45001 إلى سجلّ تدقيق ملموس مع إشارة إلى الرويس — الموقع نفسه لدور ADNOC.",
      },
      {
        role: "HSE Officer · ADCO (early career) · 2016–19",
        before:
          "Assisted senior HSE staff with day-to-day work in upstream operations.",
        after:
          "3 yrs upstream HSE on ADCO Bab & Bu Hasa fields — permit-to-work coordination across 60+ daily jobs, zero LTIs across the assignment.",
        why:
          "يثبت شرط +٧ سنوات upstream ويذكر مواقع مألوفة لدى ADNOC.",
      },
    ],
    applyLabel: "طبّق على الملف وأضف الطلب إلى الطابور",
  },
  { kind: "check", item: "إعادة صياغة النبذة بلغة الوصف" },
  { kind: "check", item: "إعادة صياغة أفضل ٣ بنود · تكميم + كلمات الوصف" },
  {
    kind: "ask",
    question:
      "أطبّق إعادة الصياغة على ملفك — أم أحتفظ بالنسختين لديك حاليًا؟",
    options: [
      "طبّق — استبدل سيرتي",
      "احفظ نسخة مكيَّفة · وأبقِ الأصل",
      "غيّر شيئًا أوّلًا",
    ],
    autoPickIndex: 1,
  },
  {
    kind: "tool",
    name: "write_cv",
    arg: "you · resume-adnoc-tailored.pdf",
    ms: 1000,
    lines: [
      "→ new file:    resume-adnoc-tailored.pdf",
      "→ summary:     rewritten (1 paragraph)",
      "→ bullets:     3 rewritten · 11 preserved",
      "→ tagged:      target = ADNOC Onshore · HSE Manager",
    ],
    note: "حُفظت النسخة المكيَّفة",
  },
  { kind: "check", item: "عرض الفرق — تعتمده قبل الكتابة" },
  {
    kind: "done",
    text: "حُفظت السيرة المكيَّفة كنسخة — الأصل بلا مسّ. وضعتُ طلب ADNOC في الطابور مقابل هذه النسخة. أُرسل الآن، أم أصوغ خطاب التقديم أوّلًا؟",
    suggestions: [
      "اصنع خطاب التقديم",
      "أرسل الطلب الآن",
      "اعرض PDF المكيَّف",
      "افعل المثل لـ ALEC",
    ],
  },

  {
    kind: "user",
    text: "أرسلته. تتبّع ADNOC كمقدَّم، وذكّرني بموعد المتابعة — واصنع لي المسودّة كي لا أُفكّر فيها.",
  },
  {
    kind: "think",
    text: "أسجّل طلب ADNOC، أضبط متابعة يوم ٥، وأجهّز مسودّة تذكير مهذّبة تكون جاهزة حين يحين وقتها.",
  },
  {
    kind: "tool",
    name: "track_application",
    arg: "ADNOC Onshore · HSE Manager",
    ms: 900,
    lines: [
      "→ status:     queued → applied",
      "→ cv:         resume-adnoc-tailored.pdf",
      "→ channel:    adnoc.ae · careers portal",
      "→ SLA:        typical reply · 4–7 days",
      "→ reminder:   Day 5 · 12 Jul · 09:00",
    ],
    note: "طلب واحد متتبَّع · تذكير مضبوط",
  },
  {
    kind: "tracker",
    jobRef: "HSE Manager — Upstream Operations",
    company: "ADNOC Onshore",
    stages: ["queued", "applied", "shortlist", "interview", "offer"],
    current: 1,
    appliedOn: "٠٧ يوليو · ١٤:٣١",
    via: "adnoc.ae · careers portal",
    nextCheck: "اليوم ٥ · ١٢ يوليو",
    note: "أتفقّد بهدوء كل صباح. إن ردّوا، أُحرّك المرحلة وأخبرك. وإن مرّ اليوم ٥ بلا ردّ، أذكّرهم — بالمسودّة أدناه.",
  },
  {
    kind: "reminder",
    jobRef: "ADNOC Onshore · HSE Manager",
    dayLabel: "اليوم ٥ · ١٢ يوليو · متوقَّع",
    headline:
      "إن لم يردّوا صباح الأحد، إليك تذكيرًا تُرسله بضغطة واحدة.",
    draftSubject: "Following up · HSE Manager application (Ahmed R.)",
    draftBody: [
      "Dear Hiring Team,",
      "Following up on my application for the HSE Manager — Upstream Operations role at ADNOC Onshore (submitted 07 Jul). I remain very interested and wanted to confirm my materials reached you.",
      "Happy to share references or elaborate on my ISO 45001 audit work at Ruwais if useful. Available for a call at your convenience.",
      "Best regards,\nAhmed R.",
    ],
    channel: "email · careers@adnoc.ae",
  },
  {
    kind: "ask",
    question:
      "يبدو مناسبًا؟ أُرسله تلقائيًا في اليوم ٥، أم أحتفظ به لمراجعتك أوّلًا؟",
    options: [
      "احتفظ للمراجعة — نبّهني أوّلًا",
      "أرسل تلقائيًا في اليوم ٥",
      "أعد صياغته — بأسلوب أخفّ",
    ],
    autoPickIndex: 0,
  },
  {
    kind: "done",
    text: "تم. ADNOC في المسار، وتذكير اليوم ٥ مصاغ ومحفوظ للمراجعة. أتتبّع ALEC و DP World بالطريقة نفسها؟",
    suggestions: [
      "تتبّع ALEC كمقدَّم",
      "تتبّع DP World كمقدَّم",
      "اعرض مساري",
      "اضبط ملخّصًا أسبوعيًا · الأحد ٠٨:٠٠",
    ],
  },

  {
    kind: "user",
    text: "أعطني تحليلات المسار — نسب تحويلي والمراحل المتعثّرة. وقُل لي ما أفعله فعلًا بعدها.",
  },
  {
    kind: "think",
    text: "أسحب طلبات آخر ٣٠ يومًا، أحسب التحويل من مرحلة إلى أخرى، وأقارن أزمنة مراحلك بمعدّلات HSE Manager في الإمارات.",
  },
  {
    kind: "tool",
    name: "read_pipeline",
    arg: "you · applications · last 30d",
    ms: 900,
    lines: [
      "→ scope:      01 Jun – 07 Jul · 26 applications",
      "→ sectors:    oil & gas, construction, logistics",
      "→ status:     3 offer · 5 interview · 9 shortlist · 26 applied",
    ],
    note: "٢٦ طلبًا محمَّل",
  },
  {
    kind: "tool",
    name: "score_conversion",
    arg: "you ↔ HSE Manager · UAE benchmark",
    ms: 1100,
    lines: [
      "→ applied → shortlist:    35% (bench 22%) ✓",
      "→ shortlist → interview:  56% (bench 48%) ✓",
      "→ interview → offer:      60% (bench 41%) ✓",
      "→ bottleneck stage:       shortlist → interview · 9.2 days",
    ],
    note: "عنق زجاجة واحد مرصود",
  },
  {
    kind: "analytics",
    title: "مسارك · آخر ٣٠ يومًا",
    window: "٠١ يونيو – ٠٧ يوليو · ٢٦ طلبًا",
    funnel: [
      { stage: "applied", count: 26 },
      { stage: "shortlist", count: 9, convFromPrev: 0.35, benchmark: 0.22 },
      { stage: "interview", count: 5, convFromPrev: 0.56, benchmark: 0.48 },
      { stage: "offer", count: 3, convFromPrev: 0.6, benchmark: 0.41 },
    ],
    stageTimes: [
      { stage: "applied → shortlist", avgDays: 4.1, benchDays: 5.5 },
      {
        stage: "shortlist → interview",
        avgDays: 9.2,
        benchDays: 4.8,
        slowest: true,
      },
      { stage: "interview → offer", avgDays: 6.4, benchDays: 7.1 },
    ],
    insights: [
      {
        tone: "good",
        text: "سيرتك تحمل العبء — تُرشَّح في القائمة المختصرة بمعدل 35% مقابل 22% في السوق. تكييف السيرة على أنماط ADNOC يؤتي ثماره.",
      },
      {
        tone: "warn",
        text: "من القائمة المختصرة إلى المقابلة عنق الزجاجة عندك: 9.2 يوم مقابل 4.8 مرجعيًا. المسؤولون بطيئون في الجدولة، وغالبًا مؤشّر على أن إيقاع المتابعة يحتاج شحذًا.",
      },
      {
        tone: "good",
        text: "حين تصل إلى المقابلة، تحوّل بمعدل 60% مقابل 41% مرجعيًا — لا يلزمك تدريب على أداء المقابلة.",
      },
    ],
    nextMoves: [
      "فعّل التذكير التلقائي في اليوم ٥ لكل طلب في القائمة المختصرة (لا لـ ADNOC وحدها)",
      "أعطِ الأولوية للطلبات التي مسؤولوها على LinkedIn — التواصل يقلّص «قائمة مختصرة → مقابلة» بنحو ٤ أيام",
      "أوقِف التقديم على وظائف اللوجستيات هذا الأسبوع — 0/6 في القائمة المختصرة، وتُنزل معدّلك",
    ],
  },
  {
    kind: "ask",
    question:
      "أطبّق الخطوة الأولى الآن — أُفعّل تذكير اليوم ٥ التلقائي لكل طلب في القائمة المختصرة؟",
    options: [
      "نعم — فعّله على كل الطلبات",
      "فعّله، لكن احتفظ بكل تذكير لمراجعتي",
      "ليس بعد · أرِني مسودّة تذكير أوّلًا",
    ],
    autoPickIndex: 1,
  },
  {
    kind: "done",
    text: "التذكير التلقائي مفعّل ومحتجَز للمراجعة. سأُشير إلى كل طلب في القائمة المختصرة في اليوم ٥ بمسودّة جاهزة. أوقِف أيضًا وظائف اللوجستيات حتى تتحسّن النسبة؟",
    suggestions: [
      "أوقِف وظائف اللوجستيات",
      "أرِني مساعدات جدولة المقابلات",
      "ملخّص أسبوعي · الأحد ٠٨:٠٠",
      "ركّز الأسبوع القادم على النفط والغاز فقط",
    ],
  },
];

/* ------------------------------------------------------------------ */
/*  Assembled dictionary + hook                                         */
/* ------------------------------------------------------------------ */

export type RicoDict = {
  ui: RicoUI;
  sessions: SessionItem[];
  script: Step[];
};

const DICT: Record<Lang, RicoDict> = {
  en: { ui: UI_EN, sessions: SESSIONS_EN, script: SCRIPT_EN },
  ar: { ui: UI_AR, sessions: SESSIONS_AR, script: SCRIPT_AR },
};

export function useRicoDict(): RicoDict {
  const { lang } = useLang();
  return DICT[lang];
}

export function useRicoLang() {
  return useLang();
}
