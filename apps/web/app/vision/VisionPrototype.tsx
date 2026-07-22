"use client";

/**
 * The Rico Bureau — vision prototype (2026-07-22 owner directive:
 * maximum creative autonomy, working prototype as the deliverable).
 *
 * Design thesis: Rico is not a dashboard — it is a precision instrument
 * that WRITES in front of you. The whole interface is a living ledger:
 * paper, ink, one hot signal. Motion is never decoration; every AI state
 * owns one distinct ink mark, so a user can read Rico's mind from motion
 * alone:
 *
 *   understanding — a pen underline draws beneath your words
 *   context       — your file rises and its lines fill
 *   searching     — an ink radar arc sweeps
 *   reading       — page lines fill top-to-bottom
 *   verifying     — a red check stamp LANDS (scale-down, like a real stamp)
 *   evidence      — numbered reasons write themselves in
 *   uncertainty   — the line turns dotted and wavers
 *   recovery      — the same line re-draws solid
 *   approval      — a wax seal you must PRESS AND HOLD (nothing auto-sends)
 *   completion    — the ledger rules itself off and is stamped FILED
 *
 * Entirely synthetic data. No backend calls. EN + AR RTL. Reduced motion
 * renders every mark settled. This route changes nothing in production.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { atelierFraunces, atelierNaskhArabic, atelierSansArabic } from "@/components/atelier-kit/fonts";
import { ATELIER as C, ATELIER_FONT } from "@/components/atelier-kit/tokens";

const SERIF = ATELIER_FONT.serif;
const MONO = ATELIER_FONT.mono;

type Lang = "en" | "ar";

/* ------------------------------------------------------------------ */
/*  The state vocabulary — the product's motion language               */
/* ------------------------------------------------------------------ */

const STATE_IDS = [
    "understanding",
    "context",
    "searching",
    "reading",
    "verifying",
    "evidence",
    "uncertainty",
    "recovery",
    "approval",
    "completion",
] as const;
type StateId = (typeof STATE_IDS)[number];

const STATE_COPY: Record<StateId, { en: string; ar: string; enSub: string; arSub: string }> = {
    understanding: { en: "Understanding", ar: "فهم", enSub: "your words, underlined as read", arSub: "كلماتك تُسطَّر وهي تُقرأ" },
    context: { en: "Context", ar: "سياق", enSub: "your CV rises and fills", arSub: "سيرتك تنهض وتمتلئ" },
    searching: { en: "Searching", ar: "بحث", enSub: "an ink arc sweeps the market", arSub: "قوس حبرٍ يمسح السوق" },
    reading: { en: "Reading", ar: "قراءة", enSub: "listings fill line by line", arSub: "الإعلانات تمتلئ سطرًا سطرًا" },
    verifying: { en: "Verifying", ar: "تحقق", enSub: "a stamp lands on what survives", arSub: "ختمٌ يهبط على ما يصمد" },
    evidence: { en: "Evidence", ar: "دليل", enSub: "reasons write themselves in", arSub: "الأسباب تكتب نفسها" },
    uncertainty: { en: "Uncertainty", ar: "تردد", enSub: "the line goes dotted, honestly", arSub: "الخط يتقطّع بصدق" },
    recovery: { en: "Recovery", ar: "تعافٍ", enSub: "the same line re-draws solid", arSub: "الخط ذاته يُرسم من جديد" },
    approval: { en: "Approval", ar: "موافقة", enSub: "a seal only your hand can press", arSub: "ختمٌ لا يضغطه إلا كفك" },
    completion: { en: "Filed", ar: "أُنجز", enSub: "ruled off, stamped, kept", arSub: "يُسطَّر ويُختَم ويُحفَظ" },
};

/* Each mark is a small self-animating SVG. `active` restarts its story. */
function StateMark({ id, active }: { id: StateId; active: boolean }) {
    const common = {
        viewBox: "0 0 64 64",
        fill: "none",
        stroke: "currentColor",
        strokeWidth: 2,
        strokeLinecap: "round" as const,
        strokeLinejoin: "round" as const,
        className: `vp-mark ${active ? "vp-mark-on" : ""}`,
        "aria-hidden": true,
    };
    switch (id) {
        case "understanding":
            return (
                <svg {...common}>
                    <path d="M12 24 h40 M12 32 h28" opacity={0.45} pathLength={100} />
                    <path className="vp-anim vp-draw" d="M12 42 C 26 38, 40 42, 52 39" stroke={C.red} strokeWidth={2.6} pathLength={100} />
                </svg>
            );
        case "context":
            return (
                <svg {...common}>
                    <rect className="vp-anim vp-rise" x="18" y="14" width="28" height="38" rx="2" pathLength={100} />
                    <path className="vp-anim vp-fill-1" d="M24 24 h16" opacity={0.8} pathLength={100} />
                    <path className="vp-anim vp-fill-2" d="M24 32 h16" opacity={0.6} pathLength={100} />
                    <path className="vp-anim vp-fill-3" d="M24 40 h10" opacity={0.5} pathLength={100} />
                </svg>
            );
        case "searching":
            return (
                <svg {...common}>
                    <circle cx="32" cy="32" r="19" opacity={0.3} pathLength={100} />
                    <circle cx="32" cy="32" r="11" opacity={0.2} pathLength={100} />
                    <circle cx="32" cy="32" r="1.8" fill="currentColor" stroke="none" />
                    <path className="vp-anim vp-sweep" d="M32 32 L32 12 A20 20 0 0 1 49 22 z" fill={C.red} stroke="none" opacity={0.55} />
                </svg>
            );
        case "reading":
            return (
                <svg {...common}>
                    <rect x="16" y="12" width="32" height="40" rx="2" pathLength={100} />
                    {[0, 1, 2, 3, 4].map((i) => (
                        <path key={i} className={`vp-anim vp-line-${i}`} d={`M22 ${20 + i * 7} h20`} opacity={0.7} pathLength={100} />
                    ))}
                </svg>
            );
        case "verifying":
            return (
                <svg {...common}>
                    <path d="M14 50 h36" opacity={0.4} pathLength={100} />
                    <g className="vp-anim vp-stamp">
                        <circle cx="32" cy="30" r="13" stroke={C.red} pathLength={100} />
                        <path d="M26 30 l4.5 4.5 8-9" stroke={C.red} pathLength={100} />
                    </g>
                </svg>
            );
        case "evidence":
            return (
                <svg {...common}>
                    {[0, 1, 2].map((i) => (
                        <g key={i}>
                            <text className={`vp-anim vp-ev-${i}`} x="14" y={24 + i * 13} fontSize="10" fill={C.red} stroke="none" fontFamily="ui-monospace, monospace">{`0${i + 1}`}</text>
                            <path className={`vp-anim vp-ev-${i}`} d={`M28 ${20 + i * 13} h22`} opacity={0.75} pathLength={100} />
                        </g>
                    ))}
                </svg>
            );
        case "uncertainty":
            return (
                <svg {...common}>
                    <path className="vp-anim vp-waver" d="M12 36 C 22 32, 30 40, 40 35 S 50 33, 52 34" strokeDasharray="3 6" pathLength={100} />
                    <text x="46" y="24" fontSize="16" fill={C.red} stroke="none" fontFamily={"Georgia, serif"} className="vp-anim vp-qmark">?</text>
                </svg>
            );
        case "recovery":
            return (
                <svg {...common}>
                    <path d="M12 36 C 22 32, 30 40, 40 35 S 50 33, 52 34" strokeDasharray="3 6" opacity={0.25} pathLength={100} />
                    <path className="vp-anim vp-draw" d="M12 36 C 22 32, 30 40, 40 35 S 50 33, 52 34" pathLength={100} />
                </svg>
            );
        case "approval":
            return (
                <svg {...common}>
                    <circle cx="32" cy="32" r="15" stroke={C.red} pathLength={100} />
                    <circle className="vp-anim vp-seal" cx="32" cy="32" r="9" fill={C.red} stroke="none" opacity={0.9} />
                    <path d="M20 54 h24" opacity={0.4} pathLength={100} />
                </svg>
            );
        case "completion":
            return (
                <svg {...common}>
                    <path d="M14 20 h36 M14 28 h28" opacity={0.5} pathLength={100} />
                    <path className="vp-anim vp-draw" d="M14 40 h36" strokeWidth={2.4} pathLength={100} />
                    <g className="vp-anim vp-stamp">
                        <rect x="34" y="44" width="18" height="10" rx="1.5" stroke={C.red} pathLength={100} />
                    </g>
                </svg>
            );
    }
}

/* ------------------------------------------------------------------ */
/*  Copy                                                               */
/* ------------------------------------------------------------------ */

const T: Record<Lang, Record<string, string>> = {
    en: {
        kicker: "The Bureau — a vision prototype",
        titleA: "An intelligence",
        titleB: "that writes in front of you.",
        lede: "Rico's next interface is a living ledger. No dashboards, no glow — paper, ink, and one hot signal. Every state of the machine owns one honest mark, so you can read Rico's mind from motion alone.",
        vocabKicker: "§ The vocabulary",
        vocabTitle: "Ten states, ten marks.",
        vocabLede: "Watch the film — each mark is the interface telling the truth about what the machine is doing.",
        simKicker: "§ The command room",
        simTitle: "Run a hunt.",
        simLede: "Synthetic data, real interaction. Pick a request, watch the spine work, and notice that nothing is ever sent without your seal.",
        chip1: "Find me a senior product role in Dubai",
        chip2: "What is missing from my CV?",
        chip3: "Prepare me for a fintech interview",
        you: "You",
        rico: "Rico",
        holdToSeal: "Hold to approve",
        sealed: "Approved — filed",
        newHunt: "New hunt",
        reply1: "I read your CV again — five years of product depth, Arabic fluency, and one gap I can argue around. The market moved this morning: three listings survive verification. The strongest one is below, with my reasons. Nothing goes out without your seal.",
        evTitle: "Senior Product Manager",
        evCompany: "Noon · Dubai",
        evSalary: "AED 32–42k",
        evWhy: "Why this fits",
        evR1: "Five years of product depth — the exact seniority asked.",
        evR2: "UAE e-commerce background reads as a domain signal.",
        evR3: "Arabic fluency is listed as a requirement — you match.",
        evWorth: "Worth knowing",
        evConcern: "Occasional on-site weeks in Riyadh.",
        filedLine: "Filed. I will watch this application and speak only when there is news.",
        closingKicker: "Colophon",
        closingTitle: "This is a prototype, not a promise.",
        closingBody: "Everything above is synthetic and interactive. The marks, the spine, and the seal are the candidate motion language for the production Command room.",
        back: "Back to Rico",
        reduced: "Reduced motion honored — every mark renders settled.",
    },
    ar: {
        kicker: "المكتب — نموذج رؤية",
        titleA: "ذكاءٌ",
        titleB: "يكتب أمام عينيك.",
        lede: "واجهة ريكو القادمة دفترُ قيدٍ حي. لا لوحات تحكم ولا وهج — ورقٌ وحبرٌ وإشارةٌ ساخنة واحدة. كل حالةٍ للآلة تملك علامةً صادقة واحدة، فتقرأ ذهن ريكو من الحركة وحدها.",
        vocabKicker: "§ المفردات",
        vocabTitle: "عشر حالات، عشر علامات.",
        vocabLede: "شاهد الفيلم — كل علامة هي الواجهة وهي تقول الحقيقة عمّا تفعله الآلة.",
        simKicker: "§ غرفة القيادة",
        simTitle: "أطلق صيدًا.",
        simLede: "بياناتٌ صناعية وتفاعلٌ حقيقي. اختر طلبًا، وراقب العمود الفقري يعمل، ولاحظ أن شيئًا لا يُرسل أبدًا بلا ختمك.",
        chip1: "دوّر لي دور مدير منتج أول في دبي",
        chip2: "ما الذي ينقص سيرتي الذاتية؟",
        chip3: "جهّزني لمقابلة في التقنية المالية",
        you: "أنت",
        rico: "ريكو",
        holdToSeal: "اضغط مطوّلًا للموافقة",
        sealed: "تمت الموافقة — قُيّد",
        newHunt: "صيدٌ جديد",
        reply1: "أعدت قراءة سيرتك — خمس سنوات من عمق المنتج، وإجادة للعربية، وثغرة واحدة أعرف كيف أدافع عنها. تحرّك السوق هذا الصباح: ثلاثة إعلانات صمدت أمام التحقق. أقواها تحت، مع أسبابي. لا شيء يخرج بلا ختمك.",
        evTitle: "مدير منتج أول",
        evCompany: "نون · دبي",
        evSalary: "٣٢–٤٢ ألف درهم",
        evWhy: "لماذا يناسبك",
        evR1: "خمس سنوات من عمق المنتج — الأقدمية المطلوبة بالضبط.",
        evR2: "خلفيتك في التجارة الإلكترونية الإماراتية إشارةُ مجال.",
        evR3: "إجادة العربية شرطٌ مذكور — وأنت تُتقنها.",
        evWorth: "جديرٌ بالانتباه",
        evConcern: "أسابيع دوامٍ حضوري متقطعة في الرياض.",
        filedLine: "قُيّد. سأراقب هذا الطلب ولن أتكلم إلا حين يكون هناك خبر.",
        closingKicker: "الهوية",
        closingTitle: "هذا نموذجٌ لا وعد.",
        closingBody: "كل ما فوق صناعيٌّ وتفاعلي. العلامات والعمود الفقري والختم هي لغة الحركة المرشحة لغرفة القيادة الفعلية.",
        back: "عودة إلى ريكو",
        reduced: "احترامٌ كامل لتقليل الحركة — كل علامة تظهر مستقرة.",
    },
};

/* The simulation's spine sequence (uncertainty/recovery branch included). */
const SIM_SEQUENCE: { id: StateId; ms: number }[] = [
    { id: "understanding", ms: 1500 },
    { id: "context", ms: 1600 },
    { id: "searching", ms: 2200 },
    { id: "reading", ms: 1900 },
    { id: "uncertainty", ms: 1400 },
    { id: "recovery", ms: 1300 },
    { id: "verifying", ms: 1500 },
    { id: "evidence", ms: 1600 },
];

/* ------------------------------------------------------------------ */
/*  Prototype                                                          */
/* ------------------------------------------------------------------ */

export function VisionPrototype() {
    const [lang, setLang] = useState<Lang>("en");
    const isAr = lang === "ar";
    const t = useCallback((k: string) => T[lang][k] ?? k, [lang]);
    const reduced = usePrefersReducedMotion();

    return (
        <div
            className={`vp-root min-h-screen overflow-x-hidden ${atelierFraunces.variable} ${atelierNaskhArabic.variable} ${atelierSansArabic.variable}`}
            dir={isAr ? "rtl" : "ltr"}
            lang={lang}
            style={{ background: C.bg, color: C.ink, fontFamily: ATELIER_FONT.body }}
        >
            <style dangerouslySetInnerHTML={{ __html: VP_CSS }} />
            <Masthead lang={lang} setLang={setLang} t={t} />
            <main>
                <Hero t={t} isAr={isAr} />
                <Vocabulary t={t} isAr={isAr} reduced={reduced} />
                <CommandSim t={t} isAr={isAr} reduced={reduced} />
                <Closing t={t} reduced={reduced} />
            </main>
        </div>
    );
}

function usePrefersReducedMotion() {
    const [reduced, setReduced] = useState(false);
    useEffect(() => {
        const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
        setReduced(mq.matches);
        const on = () => setReduced(mq.matches);
        mq.addEventListener("change", on);
        return () => mq.removeEventListener("change", on);
    }, []);
    return reduced;
}

function Masthead({ lang, setLang, t }: { lang: Lang; setLang: (l: Lang) => void; t: (k: string) => string }) {
    const isAr = lang === "ar";
    return (
        <header style={{ borderBottom: `1px solid ${C.hair}` }}>
            <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
                <div className="flex items-baseline gap-3">
                    <Link href="/" className="text-[1.3rem] leading-none tracking-tight" style={{ fontFamily: SERIF, color: C.ink }}>Rico Hunt</Link>
                    <span className="hidden sm:inline" style={{ fontFamily: MONO, fontSize: 10, letterSpacing: isAr ? 0 : "0.2em", color: C.ink55, textTransform: "uppercase" }}>{t("kicker")}</span>
                </div>
                <div className="flex items-center gap-3">
                    <span className="inline-flex items-center overflow-hidden rounded-[3px]" style={{ border: `1px solid ${C.hair}` }}>
                        <button type="button" onClick={() => setLang("en")} aria-pressed={!isAr} className="vp-press" style={{ fontFamily: MONO, fontSize: 10, padding: "3px 8px", background: !isAr ? C.ink : "transparent", color: !isAr ? C.panel : C.ink40, cursor: "pointer" }}>EN</button>
                        <button type="button" onClick={() => setLang("ar")} aria-pressed={isAr} className="vp-press" style={{ fontFamily: MONO, fontSize: 10, padding: "3px 8px", background: isAr ? C.ink : "transparent", color: isAr ? C.panel : C.ink40, cursor: "pointer" }}>عر</button>
                    </span>
                    <Link href="/" className="vp-underlink" style={{ fontFamily: MONO, fontSize: 11, color: C.ink70 }}>{t("back")} {isAr ? "←" : "→"}</Link>
                </div>
            </div>
        </header>
    );
}

function Hero({ t, isAr }: { t: (k: string) => string; isAr: boolean }) {
    return (
        <section className="mx-auto max-w-6xl px-5 pb-20 pt-16 sm:px-8 sm:pt-24">
            <p className="mb-10 flex items-center gap-2.5">
                <span className="vp-pulse h-2 w-2 flex-shrink-0 rounded-full" style={{ background: C.red }} aria-hidden />
                <span style={{ fontFamily: MONO, fontSize: 11, letterSpacing: isAr ? 0 : "0.2em", color: C.ink70, textTransform: "uppercase" }}>{t("kicker")}</span>
            </p>
            <h1 className="max-w-4xl text-[2.7rem] font-normal leading-[1.02] tracking-[-0.02em] sm:text-[4.4rem] sm:leading-[0.98]" style={{ fontFamily: SERIF, color: C.ink }}>
                {t("titleA")}{" "}
                <span className="relative inline-block font-medium italic">
                    {t("titleB")}
                    <svg className="vp-hero-underline absolute left-0 w-full" viewBox="0 0 300 8" preserveAspectRatio="none" aria-hidden>
                        <path d="M2 6 C 60 3, 120 5, 180 4 S 260 3, 298 5" fill="none" stroke={C.red} strokeWidth={4} strokeLinecap="round" pathLength={100} />
                    </svg>
                </span>
            </h1>
            <p className="mt-8 max-w-xl text-[1.05rem] leading-relaxed" style={{ color: C.ink70 }}>{t("lede")}</p>
        </section>
    );
}

/* Act II — the auto-playing vocabulary film. */
function Vocabulary({ t, isAr, reduced }: { t: (k: string) => string; isAr: boolean; reduced: boolean }) {
    const [active, setActive] = useState(0);
    useEffect(() => {
        if (reduced) return;
        const id = setInterval(() => setActive((a) => (a + 1) % STATE_IDS.length), 2400);
        return () => clearInterval(id);
    }, [reduced]);
    return (
        <section className="mx-auto max-w-6xl px-5 py-20 sm:px-8" style={{ borderTop: `1px solid ${C.hair}` }}>
            <div className="grid gap-6 lg:grid-cols-[auto_1fr] lg:gap-16">
                <span style={{ fontFamily: MONO, fontSize: 11, color: C.ink55 }}>{t("vocabKicker")}</span>
                <div>
                    <h2 className="max-w-3xl text-[2.2rem] font-normal leading-[1.03] sm:text-[3.2rem]" style={{ fontFamily: SERIF, color: C.ink }}>{t("vocabTitle")}</h2>
                    <p className="mt-4 max-w-xl leading-relaxed" style={{ color: C.ink70 }}>{t("vocabLede")}</p>
                </div>
            </div>
            <div className="mt-14 grid grid-cols-2 gap-px sm:grid-cols-5" style={{ background: C.hair, border: `1px solid ${C.hair}` }} role="list">
                {STATE_IDS.map((id, i) => {
                    const on = reduced || active === i;
                    return (
                        <button
                            key={id}
                            type="button"
                            role="listitem"
                            onClick={() => setActive(i)}
                            className={`vp-cell vp-press ${on ? "vp-cell-on" : ""}`}
                            style={{ background: on ? C.panel : C.bg }}
                            aria-current={active === i}
                        >
                            <span className="mx-auto block h-16 w-16" style={{ color: C.ink }}>
                                <StateMark id={id} active={on} />
                            </span>
                            <span className="mt-3 block" style={{ fontFamily: SERIF, fontSize: 17, color: C.ink }}>{STATE_COPY[id][isAr ? "ar" : "en"]}</span>
                            <span className="mt-1 block text-[11px] leading-snug" style={{ color: C.ink55 }}>{STATE_COPY[id][isAr ? "arSub" : "enSub"]}</span>
                        </button>
                    );
                })}
            </div>
        </section>
    );
}

/* Act III — the interactive command-room simulation. */
type SimPhase = "idle" | "running" | "replying" | "evidence" | "await-seal" | "sealed";

function CommandSim({ t, isAr, reduced }: { t: (k: string) => string; isAr: boolean; reduced: boolean }) {
    const [phase, setPhase] = useState<SimPhase>("idle");
    const [prompt, setPrompt] = useState("");
    const [spineStep, setSpineStep] = useState(-1);
    const [typed, setTyped] = useState("");
    const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

    const clearTimers = () => {
        timers.current.forEach(clearTimeout);
        timers.current = [];
    };
    useEffect(() => clearTimers, []);

    const reply = t("reply1");

    const start = (chip: string) => {
        clearTimers();
        setPrompt(chip);
        setTyped("");
        setSpineStep(-1);
        setPhase("running");
        const speed = reduced ? 0.12 : 1;
        let at = 300 * speed;
        SIM_SEQUENCE.forEach((s, i) => {
            timers.current.push(setTimeout(() => setSpineStep(i), at));
            at += s.ms * speed;
        });
        timers.current.push(setTimeout(() => setPhase("replying"), at));
    };

    /* typewriter */
    useEffect(() => {
        if (phase !== "replying") return;
        if (reduced) {
            setTyped(reply);
            const id = setTimeout(() => setPhase("evidence"), 250);
            timers.current.push(id);
            return;
        }
        let i = 0;
        const id = setInterval(() => {
            i += 2;
            setTyped(reply.slice(0, i));
            if (i >= reply.length) {
                clearInterval(id);
                timers.current.push(setTimeout(() => setPhase("evidence"), 450));
            }
        }, 18);
        return () => clearInterval(id);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [phase, reply, reduced]);

    useEffect(() => {
        if (phase !== "evidence") return;
        const id = setTimeout(() => setPhase("await-seal"), reduced ? 200 : 1900);
        timers.current.push(id);
        return () => clearTimeout(id);
    }, [phase, reduced]);

    const reset = () => {
        clearTimers();
        setPhase("idle");
        setPrompt("");
        setTyped("");
        setSpineStep(-1);
    };

    const spineActiveId: StateId | null =
        phase === "running" && spineStep >= 0 ? SIM_SEQUENCE[spineStep].id
            : phase === "await-seal" ? "approval"
                : phase === "sealed" ? "completion"
                    : null;

    return (
        <section className="mx-auto max-w-6xl px-5 py-20 sm:px-8" style={{ borderTop: `1px solid ${C.hair}` }}>
            <div className="grid gap-6 lg:grid-cols-[auto_1fr] lg:gap-16">
                <span style={{ fontFamily: MONO, fontSize: 11, color: C.ink55 }}>{t("simKicker")}</span>
                <div>
                    <h2 className="max-w-3xl text-[2.2rem] font-normal leading-[1.03] sm:text-[3.2rem]" style={{ fontFamily: SERIF, color: C.ink }}>{t("simTitle")}</h2>
                    <p className="mt-4 max-w-xl leading-relaxed" style={{ color: C.ink70 }}>{t("simLede")}</p>
                </div>
            </div>

            <div className="mt-12 grid gap-8 lg:grid-cols-[220px_minmax(0,1fr)]">
                {/* The spine — Rico's visible nervous system */}
                <aside className="hidden lg:block" aria-hidden>
                    <ol className="relative flex flex-col gap-0" style={{ borderInlineStart: `1px solid ${C.hair}` }}>
                        {SIM_SEQUENCE.map((s, i) => {
                            const on = phase === "running" && spineStep === i;
                            const done = (phase !== "idle" && phase !== "running") || (phase === "running" && spineStep > i);
                            return (
                                <li key={`${s.id}-${i}`} className="relative flex items-center gap-3 py-2.5 ps-5">
                                    <span
                                        className={`absolute start-0 top-1/2 h-px w-3 -translate-y-1/2 transition-all duration-300 ${on ? "opacity-100" : done ? "opacity-60" : "opacity-20"}`}
                                        style={{ background: on ? C.red : C.ink }}
                                    />
                                    <span className={`h-7 w-7 transition-opacity duration-300 ${on ? "opacity-100" : done ? "opacity-55" : "opacity-25"}`} style={{ color: on ? C.red : C.ink }}>
                                        <StateMark id={s.id} active={on} />
                                    </span>
                                    <span style={{ fontFamily: MONO, fontSize: 10.5, letterSpacing: isAr ? 0 : "0.14em", textTransform: "uppercase", color: on ? C.red : done ? C.ink70 : C.ink40 }}>
                                        {STATE_COPY[s.id][isAr ? "ar" : "en"]}
                                    </span>
                                </li>
                            );
                        })}
                        <li className="relative flex items-center gap-3 py-2.5 ps-5">
                            <span className={`h-7 w-7 ${spineActiveId === "approval" || phase === "sealed" ? "opacity-100" : "opacity-25"}`} style={{ color: C.red }}>
                                <StateMark id={phase === "sealed" ? "completion" : "approval"} active={spineActiveId === "approval" || phase === "sealed"} />
                            </span>
                            <span style={{ fontFamily: MONO, fontSize: 10.5, letterSpacing: isAr ? 0 : "0.14em", textTransform: "uppercase", color: phase === "sealed" ? C.ink : spineActiveId === "approval" ? C.red : C.ink40 }}>
                                {STATE_COPY[phase === "sealed" ? "completion" : "approval"][isAr ? "ar" : "en"]}
                            </span>
                        </li>
                    </ol>
                </aside>

                {/* The ledger */}
                <div className="min-h-[480px] rounded-[4px] p-6 sm:p-8" style={{ background: C.panel, border: `1px solid ${C.hair}` }}>
                    {phase === "idle" ? (
                        <div className="flex flex-col gap-3">
                            <span style={{ fontFamily: MONO, fontSize: 11, letterSpacing: isAr ? 0 : "0.16em", color: C.ink55, textTransform: "uppercase" }}>{t("simTitle")}</span>
                            {[t("chip1"), t("chip2"), t("chip3")].map((chip) => (
                                <button key={chip} type="button" onClick={() => start(chip)} className="vp-chip vp-press text-start" style={{ fontFamily: SERIF, fontSize: 19, color: C.ink }}>
                                    {chip}
                                    <span className="vp-chip-arrow" aria-hidden>{isAr ? "←" : "→"}</span>
                                </button>
                            ))}
                        </div>
                    ) : (
                        <div className="flex flex-col gap-7">
                            {/* user turn, understanding underline draws beneath */}
                            <div>
                                <span className="block" style={{ fontFamily: MONO, fontSize: 10.5, color: C.ink40, textTransform: "uppercase", letterSpacing: isAr ? 0 : "0.14em" }}>{t("you")}</span>
                                <p className="relative mt-1.5 inline-block text-[1.3rem] leading-snug" style={{ fontFamily: SERIF, color: C.ink }}>
                                    {prompt}
                                    <svg className="vp-under-live absolute inline-start-0 start-0 w-full" style={{ bottom: -5, height: 5 }} viewBox="0 0 300 6" preserveAspectRatio="none" aria-hidden>
                                        <path d="M2 4 C 70 2, 150 5, 298 3" fill="none" stroke={C.red} strokeWidth={3} strokeLinecap="round" pathLength={100} />
                                    </svg>
                                </p>
                            </div>

                            {/* live status line while the spine runs */}
                            {phase === "running" && spineStep >= 0 && (
                                <p key={spineStep} className="vp-stage-in flex items-center gap-3" role="status">
                                    <span className="h-6 w-6" style={{ color: C.red }}><StateMark id={SIM_SEQUENCE[spineStep].id} active /></span>
                                    <span className="italic" style={{ fontFamily: SERIF, fontSize: 16.5, color: C.ink70 }}>
                                        {STATE_COPY[SIM_SEQUENCE[spineStep].id][isAr ? "arSub" : "enSub"]}…
                                    </span>
                                </p>
                            )}

                            {/* Rico's reply */}
                            {(phase === "replying" || phase === "evidence" || phase === "await-seal" || phase === "sealed") && (
                                <div className="relative ps-3">
                                    <span aria-hidden className="absolute inset-y-1 start-0 w-px" style={{ background: `linear-gradient(${C.ink}55, transparent)` }} />
                                    <span style={{ fontFamily: MONO, fontSize: 10.5, color: C.red, textTransform: "uppercase", letterSpacing: isAr ? 0 : "0.14em" }}>{t("rico")}</span>
                                    <p className="mt-1 max-w-[64ch] text-[1.05rem] leading-[1.75]" style={{ fontFamily: SERIF, color: C.ink }}>
                                        {typed}
                                        {phase === "replying" && <span className="vp-caret ms-0.5 inline-block h-[1em] w-[0.5ch] translate-y-[0.14em]" style={{ background: C.ink }} aria-hidden />}
                                    </p>
                                </div>
                            )}

                            {/* evidence card assembles */}
                            {(phase === "evidence" || phase === "await-seal" || phase === "sealed") && (
                                <div className="vp-card max-w-lg rounded-[3px] p-5 sm:p-6" style={{ background: C.bg, border: `1px solid ${C.hair}` }}>
                                    <div className="vp-ev vp-ev-a flex items-start justify-between gap-4">
                                        <div>
                                            <span style={{ fontFamily: MONO, fontSize: 10.5, color: C.ink55 }}>{t("evCompany")}</span>
                                            <h3 className="mt-1 text-[1.5rem] leading-tight" style={{ fontFamily: SERIF, color: C.ink }}>{t("evTitle")}</h3>
                                            <p className="mt-1" style={{ fontFamily: MONO, fontSize: 12, color: C.ink70 }}>{t("evSalary")}</p>
                                        </div>
                                        <span className="vp-ev vp-ev-b inline-flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full text-lg" style={{ border: `1.5px solid ${C.red}`, fontFamily: SERIF, color: C.red }}>91</span>
                                    </div>
                                    <div className="my-4 h-px" style={{ background: C.hair }} />
                                    <span className="vp-ev vp-ev-c block" style={{ fontFamily: MONO, fontSize: 10.5, color: C.ink55, textTransform: "uppercase", letterSpacing: isAr ? 0 : "0.14em" }}>{t("evWhy")}</span>
                                    <ol className="mt-3 flex flex-col gap-2.5">
                                        {[t("evR1"), t("evR2"), t("evR3")].map((r, i) => (
                                            <li key={i} className={`vp-ev vp-ev-r${i} grid grid-cols-[auto_1fr] gap-3`}>
                                                <span style={{ fontFamily: MONO, fontSize: 11, color: C.red }}>{`0${i + 1}`}</span>
                                                <span className="text-[0.93rem] leading-snug" style={{ color: C.ink }}>{r}</span>
                                            </li>
                                        ))}
                                    </ol>
                                    <div className="vp-ev vp-ev-w mt-4 rounded-[3px] p-3.5" style={{ background: C.inset }}>
                                        <span style={{ fontFamily: MONO, fontSize: 10.5, color: C.red, textTransform: "uppercase", letterSpacing: isAr ? 0 : "0.14em" }}>{t("evWorth")}</span>
                                        <p className="mt-1 text-[0.93rem]" style={{ color: C.ink70 }}>{t("evConcern")}</p>
                                    </div>
                                </div>
                            )}

                            {/* the seal */}
                            {phase === "await-seal" && <SealButton t={t} onSealed={() => setPhase("sealed")} reduced={reduced} />}
                            {phase === "sealed" && (
                                <div className="vp-stage-in flex flex-col gap-4">
                                    <p className="flex items-center gap-2.5">
                                        <span className="vp-sealed-stamp inline-flex items-center rounded-[3px] px-2.5 py-1" style={{ border: `1.5px solid ${C.red}`, color: C.red, fontFamily: MONO, fontSize: 10.5, letterSpacing: isAr ? 0 : "0.16em", textTransform: "uppercase" }}>{t("sealed")}</span>
                                    </p>
                                    <p className="italic" style={{ fontFamily: SERIF, fontSize: 16.5, color: C.ink70 }}>{t("filedLine")}</p>
                                    <button type="button" onClick={reset} className="vp-underlink self-start" style={{ fontFamily: MONO, fontSize: 11.5, color: C.ink70 }}>
                                        {t("newHunt")} {isAr ? "←" : "→"}
                                    </button>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </section>
    );
}

/* Hold-to-approve: slow on purpose while pressing (deliberate), instant to
   cancel. Works with pointer and keyboard (hold Space/Enter). */
function SealButton({ t, onSealed, reduced }: { t: (k: string) => string; onSealed: () => void; reduced: boolean }) {
    const [holding, setHolding] = useState(false);
    const doneRef = useRef(false);
    const HOLD_MS = reduced ? 150 : 900;

    useEffect(() => {
        if (!holding) return;
        const id = setTimeout(() => {
            doneRef.current = true;
            onSealed();
        }, HOLD_MS);
        return () => clearTimeout(id);
    }, [holding, HOLD_MS, onSealed]);

    const down = () => setHolding(true);
    const up = () => {
        if (!doneRef.current) setHolding(false);
    };

    return (
        <button
            type="button"
            className="vp-seal-btn vp-press inline-flex items-center gap-3 self-start rounded-full px-6 py-3"
            style={{ background: C.ink, color: C.panel, fontFamily: MONO, fontSize: 12.5, letterSpacing: "0.06em" }}
            onPointerDown={down}
            onPointerUp={up}
            onPointerLeave={up}
            onKeyDown={(e) => { if ((e.key === " " || e.key === "Enter") && !e.repeat) down(); }}
            onKeyUp={(e) => { if (e.key === " " || e.key === "Enter") up(); }}
            aria-label={t("holdToSeal")}
        >
            <span className="relative inline-flex h-6 w-6 items-center justify-center" aria-hidden>
                <svg viewBox="0 0 24 24" className="absolute inset-0">
                    <circle cx="12" cy="12" r="10" fill="none" stroke={`${C.panel}44`} strokeWidth="2" />
                    <circle
                        cx="12" cy="12" r="10" fill="none" stroke={C.red} strokeWidth="2.4" strokeLinecap="round"
                        pathLength={100} strokeDasharray={100}
                        style={{
                            strokeDashoffset: holding ? 0 : 100,
                            transition: holding ? `stroke-dashoffset ${HOLD_MS}ms linear` : "stroke-dashoffset 150ms cubic-bezier(0.23,1,0.32,1)",
                            transform: "rotate(-90deg)", transformOrigin: "center",
                        }}
                    />
                </svg>
                <span className="h-2 w-2 rounded-full" style={{ background: C.red }} />
            </span>
            {t("holdToSeal")}
        </button>
    );
}

function Closing({ t, reduced }: { t: (k: string) => string; reduced: boolean }) {
    return (
        <footer style={{ background: C.footer, color: C.footerInk }}>
            <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8">
                <span className="uppercase" style={{ fontFamily: MONO, fontSize: 11, letterSpacing: "0.2em", color: C.footerInk60 }}>{t("closingKicker")}</span>
                <h2 className="mt-5 max-w-2xl text-[2rem] font-normal leading-[1.05] sm:text-[2.6rem]" style={{ fontFamily: SERIF }}>{t("closingTitle")}</h2>
                <p className="mt-5 max-w-xl leading-relaxed" style={{ color: C.footerInk60 }}>{t("closingBody")}</p>
                {reduced && <p className="mt-6" style={{ fontFamily: MONO, fontSize: 11, color: C.footerInk60 }}>{t("reduced")}</p>}
            </div>
        </footer>
    );
}

/* ------------------------------------------------------------------ */
/*  Scoped CSS — the motion engine                                     */
/* ------------------------------------------------------------------ */

const VP_CSS = `
.vp-root .vp-press { transition: transform 140ms cubic-bezier(0.23,1,0.32,1); }
.vp-root .vp-press:active { transform: scale(0.97); }
.vp-root .vp-underlink { border-bottom: 1px solid ${C.hair}; transition: color .2s ease, border-color .2s ease; }
.vp-root .vp-underlink:hover { color: ${C.red}; border-color: ${C.red}; }

.vp-root .vp-pulse { animation: vpPulse 2.4s cubic-bezier(0.4,0,0.6,1) infinite; }
@keyframes vpPulse { 0%,100% { opacity:1 } 50% { opacity:.35 } }

.vp-root .vp-hero-underline { bottom: 0.05em; height: 0.16em; }
.vp-root .vp-hero-underline path,
.vp-root .vp-under-live path { stroke-dasharray: 100; stroke-dashoffset: 100; animation: vpDraw 1.1s cubic-bezier(0.16,1,0.3,1) .2s forwards; }
.vp-root[dir="rtl"] .vp-hero-underline { bottom: -0.14em; }

/* mark engine: any .vp-anim inside an active mark plays its story */
.vp-mark .vp-anim { animation-play-state: paused; }
.vp-mark-on .vp-anim { animation-play-state: running; }

.vp-mark .vp-draw { stroke-dasharray: 100; stroke-dashoffset: 100; animation: vpDraw 1s cubic-bezier(0.23,1,0.32,1) forwards; }
.vp-mark .vp-rise { transform: translateY(6px); opacity: 0; animation: vpRise .6s cubic-bezier(0.23,1,0.32,1) forwards; }
.vp-mark .vp-fill-1 { stroke-dasharray: 100; stroke-dashoffset: 100; animation: vpDraw .5s ease-out .35s forwards; }
.vp-mark .vp-fill-2 { stroke-dasharray: 100; stroke-dashoffset: 100; animation: vpDraw .5s ease-out .55s forwards; }
.vp-mark .vp-fill-3 { stroke-dasharray: 100; stroke-dashoffset: 100; animation: vpDraw .5s ease-out .75s forwards; }
.vp-mark .vp-sweep { transform-origin: 32px 32px; animation: vpSweep 1.6s linear infinite; }
.vp-mark .vp-line-0 { stroke-dasharray: 100; stroke-dashoffset: 100; animation: vpDraw .4s ease-out .1s forwards; }
.vp-mark .vp-line-1 { stroke-dasharray: 100; stroke-dashoffset: 100; animation: vpDraw .4s ease-out .35s forwards; }
.vp-mark .vp-line-2 { stroke-dasharray: 100; stroke-dashoffset: 100; animation: vpDraw .4s ease-out .6s forwards; }
.vp-mark .vp-line-3 { stroke-dasharray: 100; stroke-dashoffset: 100; animation: vpDraw .4s ease-out .85s forwards; }
.vp-mark .vp-line-4 { stroke-dasharray: 100; stroke-dashoffset: 100; animation: vpDraw .4s ease-out 1.1s forwards; }
.vp-mark .vp-stamp { transform-origin: center; transform-box: fill-box; opacity: 0; animation: vpStamp .5s cubic-bezier(0.34,1.2,0.64,1) .3s forwards; }
.vp-mark .vp-ev-0 { opacity: 0; animation: vpFadeUp .45s cubic-bezier(0.23,1,0.32,1) .1s forwards; }
.vp-mark .vp-ev-1 { opacity: 0; animation: vpFadeUp .45s cubic-bezier(0.23,1,0.32,1) .45s forwards; }
.vp-mark .vp-ev-2 { opacity: 0; animation: vpFadeUp .45s cubic-bezier(0.23,1,0.32,1) .8s forwards; }
.vp-mark .vp-waver { animation: vpWaver 1.4s ease-in-out infinite; }
.vp-mark .vp-qmark { opacity: 0; animation: vpFadeUp .5s ease-out .4s forwards; }
.vp-mark .vp-seal { transform-origin: center; transform-box: fill-box; animation: vpSealBreathe 1.8s ease-in-out infinite; }

@keyframes vpDraw { to { stroke-dashoffset: 0 } }
@keyframes vpRise { to { transform: translateY(0); opacity: 1 } }
@keyframes vpSweep { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }
@keyframes vpStamp { 0% { opacity: 0; transform: scale(1.5) rotate(-6deg) } 60% { opacity: 1; transform: scale(0.96) rotate(1deg) } 100% { opacity: 1; transform: scale(1) rotate(0) } }
@keyframes vpFadeUp { from { opacity: 0; transform: translateY(5px) } to { opacity: 1; transform: translateY(0) } }
@keyframes vpWaver { 0%,100% { transform: translateY(0) } 50% { transform: translateY(2.5px) } }
@keyframes vpSealBreathe { 0%,100% { transform: scale(1) } 50% { transform: scale(1.12) } }

.vp-root .vp-cell { padding: 22px 14px 20px; text-align: center; cursor: pointer; transition: background-color .3s ease; }
.vp-root .vp-cell:focus-visible { outline: 2px solid ${C.red}; outline-offset: -2px; }

.vp-root .vp-chip { position: relative; padding: 14px 18px; border: 1px solid ${C.hair}; border-radius: 3px; background: ${C.bg}; cursor: pointer; transition: border-color .2s ease, transform 140ms cubic-bezier(0.23,1,0.32,1); }
.vp-root .vp-chip:hover { border-color: ${C.red}; }
.vp-root .vp-chip .vp-chip-arrow { position: absolute; inset-inline-end: 16px; top: 50%; transform: translateY(-50%); color: ${C.red}; opacity: 0; transition: opacity .2s ease, transform .2s ease; }
.vp-root .vp-chip:hover .vp-chip-arrow { opacity: 1; }

.vp-root .vp-stage-in { animation: vpStageIn .3s cubic-bezier(0.23,1,0.32,1) both; }
@keyframes vpStageIn { from { opacity: 0; filter: blur(3px); transform: translateY(3px) } to { opacity: 1; filter: blur(0); transform: translateY(0) } }

.vp-root .vp-caret { animation: vpCaret 1s step-end infinite; }
@keyframes vpCaret { 0%,45% { opacity: 1 } 50%,100% { opacity: 0 } }

.vp-root .vp-card { animation: vpStageIn .4s cubic-bezier(0.23,1,0.32,1) both; }
.vp-root .vp-ev { opacity: 0; animation: vpFadeUp .5s cubic-bezier(0.23,1,0.32,1) forwards; }
.vp-root .vp-ev-a { animation-delay: .1s } .vp-root .vp-ev-b { animation-delay: .5s }
.vp-root .vp-ev-c { animation-delay: .7s }
.vp-root .vp-ev-r0 { animation-delay: .9s } .vp-root .vp-ev-r1 { animation-delay: 1.15s } .vp-root .vp-ev-r2 { animation-delay: 1.4s }
.vp-root .vp-ev-w { animation-delay: 1.65s }

.vp-root .vp-sealed-stamp { animation: vpStamp .5s cubic-bezier(0.34,1.2,0.64,1) both; }

/* Arabic guards: no letterspacing on connected script, no fake italics */
.vp-root[dir="rtl"], .vp-root[dir="rtl"] * { letter-spacing: 0 !important; }
.vp-root[dir="rtl"] .italic, .vp-root[dir="rtl"] .vp-root .italic { font-style: normal; }

.vp-root a:focus-visible, .vp-root button:focus-visible { outline: 2px solid ${C.red}; outline-offset: 3px; border-radius: 2px; }

@media (prefers-reduced-motion: reduce) {
  .vp-root .vp-pulse, .vp-root .vp-caret, .vp-root .vp-sweep, .vp-root .vp-waver, .vp-root .vp-seal { animation: none !important; }
  .vp-root .vp-hero-underline path, .vp-root .vp-under-live path,
  .vp-mark .vp-anim, .vp-root .vp-stage-in, .vp-root .vp-card, .vp-root .vp-ev, .vp-root .vp-sealed-stamp {
    animation: none !important; opacity: 1 !important; stroke-dashoffset: 0 !important; transform: none !important; filter: none !important;
  }
}
`;
